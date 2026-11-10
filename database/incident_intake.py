"""Owner-authorized, consent-gated structured incident intake.

Only coarse incident facts are collected. Street addresses, free-text narratives,
claimant contact details, policy numbers, and financial data are intentionally
outside this v1 contract. The payload lives in a separately deletable table;
the append-only journal stores consent and request references, not the incident details.
"""
from __future__ import annotations
from datetime import datetime, timezone
import json
import re
from uuid import UUID
from database.capture_sessions import CaptureAuthorizationError, CaptureSessionConflict, CaptureSessionStore

DISCLOSURE_VERSION = "incident-intake-v1"
INCIDENT_TYPES = frozenset({"collision", "theft", "weather", "vandalism", "other", "unknown"})

class IncidentIntakeService:
    def __init__(self, sessions: CaptureSessionStore):
        if not isinstance(sessions, CaptureSessionStore):
            raise ValueError("INVALID_INCIDENT_INTAKE_CONFIGURATION")
        self.sessions = sessions

    @staticmethod
    def _uuid(value, code):
        try:
            return str(UUID(str(value)))
        except (ValueError, TypeError, AttributeError):
            raise ValueError(code) from None

    def _history(self, conn, actor, session_id):
        session = self.sessions._read(conn, actor, session_id)
        if session.scope != "persistent-claim-case" or not session.claim_id:
            raise CaptureAuthorizationError("PERSISTENT_CLAIM_CASE_REQUIRED")
        conn.execute("SELECT faos.lock_session_for_completion(%s::uuid,%s::text)", (actor.tenant_id, session_id))
        rows = conn.execute(
            "SELECT sequence,kind,actor,payload_json,event_id FROM faos.events "
            "WHERE tenant_id=%s AND session_id=%s ORDER BY sequence",
            (actor.tenant_id, session_id),
        ).fetchall()
        if not rows or len(rows) > 1000 or any(row[0] != i + 1 for i, row in enumerate(rows)):
            raise CaptureSessionConflict("UNSUPPORTED_CAPTURE_HISTORY")
        try:
            history = [(row[1], row[2], json.loads(row[3]), row[4]) for row in rows]
        except (ValueError, TypeError):
            raise CaptureSessionConflict("INVALID_CAPTURE_HISTORY") from None
        return session, history

    @staticmethod
    def _append(conn, actor, session_id, history, *, event_id, kind, reason, payload):
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
        result = conn.execute(
            "SELECT faos.append_event(%s::uuid,%s::text,%s::text,%s::bigint,%s::text,%s::text,%s::text,%s::text,%s::text,%s::text)",
            (actor.tenant_id, session_id, event_id, len(history) + 1, kind, actor.actor_id,
             datetime.now(timezone.utc).isoformat(), reason, canonical, "0.1"),
        ).fetchone()[0]
        if result != "ACCEPTED":
            raise CaptureSessionConflict("INCIDENT_EVENT_NOT_ACCEPTED")

    @staticmethod
    def _require_owner_and_capture_consent(history, actor):
        if actor.actor_role != "owner":
            raise CaptureAuthorizationError("OWNER_IDENTITY_REQUIRED")
        consents = [item for item in history if item[0] == "CONSENT_RECORDED"]
        if not consents:
            raise CaptureSessionConflict("ACTIVE_CAPTURE_CONSENT_REQUIRED")
        payload = consents[-1][2]
        if (type(payload) is not dict or payload.get("accepted") is not True
                or payload.get("owner_actor_id") != actor.actor_id or consents[-1][1] != actor.actor_id):
            raise CaptureAuthorizationError("ACTIVE_CAPTURE_CONSENT_REQUIRED")

    @staticmethod
    def _bind_owner(conn, actor, session_id):
        result = conn.execute(
            "SELECT faos.bind_claim_case_owner(%s::uuid,%s::text,%s::text)",
            (actor.tenant_id, session_id, actor.actor_id),
        ).fetchone()[0]
        if result != "BOUND":
            raise CaptureAuthorizationError("CLAIM_CASE_OWNER_BINDING_DENIED")

    def record_consent(self, authorization, session_id, *, request_id, accepted):
        session_id = self._uuid(session_id, "INVALID_CAPTURE_SESSION_ID")
        request_id = self._uuid(request_id, "INVALID_REQUEST_ID")
        if type(accepted) is not bool:
            raise ValueError("INVALID_INCIDENT_INTAKE_CONSENT")
        with self.sessions._authorized(authorization) as (conn, actor):
            session, history = self._history(conn, actor, session_id)
            self._require_owner_and_capture_consent(history, actor)
            self._bind_owner(conn, actor, session_id)
            event_id = "incident-consent:" + request_id
            payload = {"accepted": accepted, "owner_actor_id": actor.actor_id,
                       "disclosure_version": DISCLOSURE_VERSION, "scope": "incident_details",
                       "request_id": request_id}
            replayed = False
            for kind, event_actor, old, old_id in history:
                if old_id == event_id:
                    if kind == "INCIDENT_INTAKE_CONSENT_RECORDED" and event_actor == actor.actor_id and old == payload:
                        replayed = True
                        break
                    raise CaptureSessionConflict("IDEMPOTENCY_CONFLICT")
            if not replayed:
                previous = [item for item in history if item[0] == "INCIDENT_INTAKE_CONSENT_RECORDED"]
                if accepted and previous and previous[-1][2].get("accepted") is True:
                    raise CaptureSessionConflict("INCIDENT_INTAKE_CONSENT_ALREADY_ACTIVE")
                self._append(conn, actor, session_id, history, event_id=event_id,
                             kind="INCIDENT_INTAKE_CONSENT_RECORDED",
                             reason="owner incident-intake consent state recorded", payload=payload)
            deleted = False
            if not accepted:
                deleted = conn.execute(
                    "SELECT faos.withdraw_claim_case_incident(%s::uuid,%s::uuid,%s::text)",
                    (actor.tenant_id, session.claim_id, actor.actor_id),
                ).fetchone()[0] == "DELETED"
            return {"session_id": session_id, "accepted": accepted,
                    "disclosure_version": DISCLOSURE_VERSION, "replayed": replayed,
                    "incident_details_deleted": deleted}

    @staticmethod
    def _normalize_details(occurred_at, incident_type, city, region, postal_code):
        if not isinstance(occurred_at, str):
            raise ValueError("INVALID_INCIDENT_OCCURRED_AT")
        try:
            moment = datetime.fromisoformat(occurred_at.replace("Z", "+00:00"))
        except ValueError:
            raise ValueError("INVALID_INCIDENT_OCCURRED_AT") from None
        if moment.tzinfo is None or moment.utcoffset() is None:
            raise ValueError("INCIDENT_TIMEZONE_REQUIRED")
        if incident_type not in INCIDENT_TYPES:
            raise ValueError("INVALID_INCIDENT_TYPE")
        if not isinstance(city, str):
            raise ValueError("INVALID_INCIDENT_CITY")
        city = " ".join(city.split())
        if not 2 <= len(city) <= 80 or not city.isprintable():
            raise ValueError("INVALID_INCIDENT_CITY")
        if not isinstance(region, str) or re.fullmatch(r"[A-Za-z]{2}", region) is None:
            raise ValueError("INVALID_INCIDENT_REGION")
        region = region.upper()
        if not isinstance(postal_code, str) or re.fullmatch(r"[0-9]{5}(?:-[0-9]{4})?", postal_code) is None:
            raise ValueError("INVALID_INCIDENT_POSTAL_CODE")
        return {"incident_occurred_at": moment.astimezone(timezone.utc).isoformat(),
                "incident_type": incident_type, "incident_city": city,
                "incident_region": region, "incident_postal_code": postal_code}

    def record_incident(self, authorization, session_id, *, request_id, occurred_at,
                        incident_type, city, region, postal_code):
        session_id = self._uuid(session_id, "INVALID_CAPTURE_SESSION_ID")
        request_id = self._uuid(request_id, "INVALID_REQUEST_ID")
        details = self._normalize_details(occurred_at, incident_type, city, region, postal_code)
        with self.sessions._authorized(authorization) as (conn, actor):
            session, history = self._history(conn, actor, session_id)
            self._require_owner_and_capture_consent(history, actor)
            self._bind_owner(conn, actor, session_id)
            consents = [item for item in history if item[0] == "INCIDENT_INTAKE_CONSENT_RECORDED"]
            if not consents or cons[-1][2].get("accepted") is not True or cons[-1][1] != actor.actor_id:
                raise CaptureSessionConflict("ACTIVE_INCIDENT_INTAKE_CONSENT_REQUIRED")
            event_id = "incident-recorded:" + request_id
            result = conn.execute(
                "SELECT faos.save_claim_case_incident(%s::uuid,%s::uuid,%s::text,%s::uuid,%s::timestamptz,%s::text,%s::text,%s::text,%s::text)",
                (actor.tenant_id, session.claim_id, actor.actor_id, request_id,
                 details["incident_occurred_at"], details["incident_type"], details["incident_city"],
                 details["incident_region"], details["incident_postal_code"]),
            ).fetchone()[0]
            if result not in ("ACCEPTED", "DUPLICATE"):
                raise CaptureSessionConflict("INCIDENT_INTAKE_CONFLICT")
            stored = conn.execute(
                "SELECT request_id,incident_occurred_at,incident_type,incident_city,incident_region,incident_postal_code "
                "FROM faos.claim_case_incident_intake WHERE tenant_id=%s AND claim_id=%s",
                (actor.tenant_id, session.claim_id),
            ).fetchone()
            if (stored is None or str(stored[0]) != request_id
                    or stored[1].astimezone(timezone.utc).isoformat() != details["incident_occurred_at"]
                    or tuple(stored[2:]) != (details["incident_type"], details["incident_city"],
                                             details["incident_region"], details["incident_postal_code"])):
                raise CaptureSessionConflict("INCIDENT_INTAKE_CONFLICT")
            expected_event = {"request_id": request_id, "disclosure_version": DISCLOSURE_VERSION}
            prior = next((item for item in history if item[3] == event_id), None)
            if prior is not None:
                if prior[0] != "INCIDENT_INTAKE_RECORDED" or prior[1] != actor.actor_id or prior[2] != expected_event:
                    raise CaptureSessionConflict("IDEMPOTENCY_CONFLICT")
                return {"session_id": session_id, **details, "replayed": True}
            self._append(conn, actor, session_id, history, event_id=event_id,
                         kind="INCIDENT_INTAKE_RECORDED", reason="owner submitted structured incident intake",
                         payload=expected_event)
            return {"session_id": session_id, **details, "replayed": result == "DUPLICATE"}
