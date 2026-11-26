"""Tenant-authorized consent, VIN reference and original-byte registration.

Metadata is committed to the existing RLS-protected append-only event journal.
Original media is written to the administrator-provisioned POSIX byte store;
no raw VIN is persisted, and consent withdrawal deletes registered originals.
"""
from __future__ import annotations

import base64
import binascii
from datetime import datetime, timezone
import hashlib
import hmac
import json
import re
from uuid import UUID, uuid5

import psycopg

from app.artifact_storage import (
    ArtifactIntegrityError, ArtifactKey, ArtifactNotFound, OriginalByteStore,
)
from app.evidence_manifest import ManifestEntry, build_manifest
from app.capture_protocols import DEFAULT_CAPTURE_PROTOCOL, require_implemented_protocol
from app.vin_guard import validate_vin
from database.readback import locked_verified_journal_in_transaction
from database.capture_sessions import (
    CaptureAuthorizationError,
    CaptureSessionConflict,
    CaptureSessionStore,
)

MAX_EVIDENCE_BYTES = 25 * 1024 * 1024


class _EvidenceArtifactIntegrityFailure(Exception):
    def __init__(self, artifact_id, slot, expected_sha256, failure_code):
        self.artifact_id = artifact_id
        self.slot = slot
        self.expected_sha256 = expected_sha256
        self.failure_code = failure_code
        super().__init__(failure_code)

DISCLOSURE_VERSION = "disclosure-v1"
VEHICLE_DECODE_DISCLOSURE_VERSION = "vehicle-decode-disclosure-v1"


class CaptureEvidenceService:
    def __init__(self, sessions: CaptureSessionStore, byte_store: OriginalByteStore, vin_pepper: str):
        if not isinstance(sessions, CaptureSessionStore) or not isinstance(byte_store, OriginalByteStore):
            raise ValueError("INVALID_EVIDENCE_CONFIGURATION")
        if not isinstance(vin_pepper, str) or not vin_pepper.isascii() or len(vin_pepper) < 32:
            raise ValueError("VIN_HMAC_PEPPER_CONFIGURATION_REQUIRED")
        self.sessions = sessions
        self.byte_store = byte_store
        self._vin_pepper = vin_pepper.encode("ascii")

    @staticmethod
    def _session_id(value):
        try:
            return str(UUID(str(value)))
        except (TypeError, ValueError, AttributeError):
            raise ValueError("INVALID_CAPTURE_SESSION_ID") from None

    @staticmethod
    def _request_id(value):
        try:
            return str(UUID(str(value)))
        except (TypeError, ValueError, AttributeError):
            raise ValueError("INVALID_REQUEST_ID") from None

    def _history(self, conn, actor, session_id, *, creator_required):
        session = self.sessions._read(conn, actor, session_id)
        if creator_required and session.created_by != actor.actor_id:
            raise CaptureAuthorizationError("CAPTURE_AUTHORITY_DENIED")
        try:
            journal = locked_verified_journal_in_transaction(conn, actor.tenant_id, session_id)
        except ValueError as error:
            raise CaptureSessionConflict("CAPTURE_HISTORY_CHAIN_INVALID") from error
        events = journal.events
        if not events or len(events) > 1000:
            raise CaptureSessionConflict("UNSUPPORTED_CAPTURE_HISTORY")
        try:
            history = [(event.kind, event.actor, json.loads(event.payload_json), event.event_id)
                       for event in events]
        except (ValueError, TypeError):
            raise CaptureSessionConflict("INVALID_CAPTURE_HISTORY") from None
        return session, history

    @staticmethod
    def _append(conn, actor, session_id, history, *, event_id, kind, reason, payload):
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
        result = conn.execute(
            "SELECT faos.append_event(%s::uuid,%s::text,%s::text,%s::bigint,%s::text,%s::text,%s::text,%s::text,%s::text,%s::text)",
            (actor.tenant_id, session_id, event_id, len(history) + 1, kind, actor.actor_id,
             datetime.now(timezone.utc).isoformat(), reason, canonical, "0.1"),
        ).fetchone()[0]
        if result != "ACCEPTED":
            raise CaptureSessionConflict("CAPTURE_EVENT_NOT_ACCEPTED")

    @staticmethod
    def _consent_state(history):
        consents = [(actor, payload) for kind, actor, payload, _ in history if kind == "CONSENT_RECORDED"]
        if not consents:
            return None
        actor, latest = consents[-1]
        if type(latest) is not dict or set(latest) != {
            "accepted", "owner_actor_id", "disclosure_version", "scope", "request_id"
        } or type(latest.get("accepted")) is not bool or latest.get("owner_actor_id") != actor:
            raise CaptureSessionConflict("UNSUPPORTED_CONSENT_HISTORY")
        if latest["disclosure_version"] != DISCLOSURE_VERSION or latest["scope"] != "capture_review":
            raise CaptureSessionConflict("UNSUPPORTED_CONSENT_HISTORY")
        return (actor, latest) if latest["accepted"] is True else None

    @staticmethod
    def _has_valid_vehicle_reference(history, consent):
        if consent is None:
            return False
        consent_id = "consent:" + consent[1]["request_id"]
        consent_index = next((i for i, item in enumerate(history) if item[3] == consent_id), -1)
        for index, (kind, _actor, payload, _event_id) in enumerate(history):
            if index <= consent_index or kind != "VEHICLE_RECORDED":
                continue
            if (type(payload) is dict
                    and set(payload) == {"request_id", "vin_hmac_sha256", "disclosure_version", "recorded_by_role"}
                    and payload["disclosure_version"] == DISCLOSURE_VERSION
                    and payload["recorded_by_role"] in ("operator", "supervisor")
                    and isinstance(payload["vin_hmac_sha256"], str)
                    and re.fullmatch(r"[0-9a-f]{64}", payload["vin_hmac_sha256"])):
                return True
        return False

    @staticmethod
    def _last_capture_event(history):
        sidecar = {
            "VEHICLE_DECODE_CONSENT_RECORDED", "VEHICLE_PROFILE_DECODED",
            "ARTIFACT_INTEGRITY_FAILURE_RECORDED",
        }
        return next((item for item in reversed(history) if item[0] not in sidecar), None)

    @staticmethod
    def _vehicle_decode_consent_state(history, capture_consent):
        if capture_consent is None:
            return None
        events = [(actor, payload) for kind, actor, payload, _ in history
                  if kind == "VEHICLE_DECODE_CONSENT_RECORDED"]
        if not events:
            return None
        actor, latest = events[-1]
        required = {"accepted", "owner_actor_id", "disclosure_version", "scope", "request_id"}
        if (type(latest) is not dict or set(latest) != required
                or type(latest.get("accepted")) is not bool
                or latest.get("owner_actor_id") != actor
                or actor != capture_consent[0]
                or latest.get("disclosure_version") != VEHICLE_DECODE_DISCLOSURE_VERSION
                or latest.get("scope") != "nhtsa_vpic_decode"):
            raise CaptureSessionConflict("UNSUPPORTED_VEHICLE_DECODE_CONSENT_HISTORY")
        return (actor, latest) if latest["accepted"] is True else None

    def evidence_readiness(self, authorization, session_id):
        """Return the server-authoritative consent/VIN gate before local evidence is queued."""
        session_id = self._session_id(session_id)
        with self.sessions._authorized(authorization) as (conn, actor):
            if actor.actor_role not in ("operator", "supervisor"):
                raise CaptureAuthorizationError("OPERATOR_IDENTITY_REQUIRED")
            _session, history = self._history(conn, actor, session_id, creator_required=True)
            consent = self._consent_state(history)
            vehicle_present = self._has_valid_vehicle_reference(history, consent)
            protocol = require_implemented_protocol(_session.capture_protocol_version)
            paused = self._capture_paused(history)
            exceptions = list(self._active_capture_exceptions(history).values())
            slots = tuple(protocol.slots)
            latest_artifacts = {}
            quality_results = {}
            quality_recorded = False
            sealed = False
            review_recorded = False
            for kind, _event_actor, payload, _event_id in history:
                if kind == "ARTIFACT_REGISTERED":
                    required = {"request_id", "artifact_id", "slot", "sha256", "byte_length", "recorded_by_role"}
                    if type(payload) is not dict or set(payload) != required:
                        raise CaptureSessionConflict("UNSUPPORTED_ARTIFACT_HISTORY")
                    if (payload.get("slot") not in slots or not isinstance(payload.get("artifact_id"), str)
                            or not isinstance(payload.get("sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", payload["sha256"])
                            or type(payload.get("byte_length")) is not int or payload["byte_length"] <= 0):
                        raise CaptureSessionConflict("UNSUPPORTED_ARTIFACT_HISTORY")
                    latest_artifacts[payload["slot"]] = {
                        "artifact_id": payload["artifact_id"], "slot": payload["slot"],
                        "sha256": payload["sha256"], "byte_length": payload["byte_length"],
                    }
                elif kind == "QUALITY_RECORDED":
                    if (type(payload) is not dict or set(payload) != {"request_id", "results", "advisory_only"}
                            or payload.get("advisory_only") is not True or type(payload.get("results")) is not dict
                            or set(payload["results"]) != set(slots)
                            or any(type(value) is not bool for value in payload["results"].values())):
                        raise CaptureSessionConflict("UNSUPPORTED_QUALITY_HISTORY")
                    quality_recorded = True
                    quality_results = payload["results"]
                elif kind == "MANIFEST_SEALED":
                    sealed = True
                elif kind == "REVIEW_RECORDED":
                    review_recorded = True
            return {
                "session_id": session_id,
                "capture_protocol_version": _session.capture_protocol_version,
                "capture_protocol_status": "implemented",
                "consent_active": consent is not None,
                "vehicle_reference_present": vehicle_present,
                "capture_allowed": consent is not None and vehicle_present and not paused,
                "capture_paused": paused,
                "active_capture_exceptions": exceptions,
                "registered_artifacts": [latest_artifacts[slot] for slot in slots if slot in latest_artifacts],
                "quality_recorded": quality_recorded,
                "quality_results": quality_results,
                "sealed": sealed,
                "review_recorded": review_recorded,
            }


    @staticmethod
    def _capture_paused(history):
        paused = False
        for kind, _actor, payload, _event_id in history:
            if kind not in ("CAPTURE_SESSION_PAUSED", "CAPTURE_SESSION_RESUMED"):
                continue
            if type(payload) is not dict or set(payload) != {"request_id", "reason"}:
                raise CaptureSessionConflict("UNSUPPORTED_CAPTURE_PAUSE_HISTORY")
            try:
                UUID(payload["request_id"])
            except (ValueError, TypeError, AttributeError):
                raise CaptureSessionConflict("UNSUPPORTED_CAPTURE_PAUSE_HISTORY") from None
            if not isinstance(payload["reason"], str) or not payload["reason"].strip() or len(payload["reason"]) > 500:
                raise CaptureSessionConflict("UNSUPPORTED_CAPTURE_PAUSE_HISTORY")
            if kind == "CAPTURE_SESSION_PAUSED":
                if paused:
                    raise CaptureSessionConflict("INVALID_CAPTURE_PAUSE_HISTORY")
                paused = True
            else:
                if not paused:
                    raise CaptureSessionConflict("INVALID_CAPTURE_PAUSE_HISTORY")
                paused = False
        return paused

    @staticmethod
    def _active_capture_exceptions(history):
        active = {}
        reason_codes = {"UNSAFE_TO_APPROACH", "ACCESS_RESTRICTED", "VEHICLE_IN_MOTION",
                        "WEATHER_HAZARD", "OWNER_DECLINED", "EQUIPMENT_FAILURE", "OTHER"}
        resolution_codes = {"CAPTURED_AFTER_RETRY", "NO_LONGER_APPLICABLE", "SUPERVISOR_REVIEWED"}
        for kind, actor, payload, event_id in history:
            if kind == "CAPTURE_EXCEPTION_RECORDED":
                required = {"request_id", "slot", "reason_code", "explanation"}
                if type(payload) is not dict or set(payload) != required:
                    raise CaptureSessionConflict("UNSUPPORTED_CAPTURE_EXCEPTION_HISTORY")
                try:
                    UUID(payload["request_id"])
                except (ValueError, TypeError, AttributeError):
                    raise CaptureSessionConflict("UNSUPPORTED_CAPTURE_EXCEPTION_HISTORY") from None
                if (not isinstance(payload["slot"], str) or not payload["slot"]
                        or payload["reason_code"] not in reason_codes
                        or not isinstance(payload["explanation"], str)
                        or not payload["explanation"].strip() or len(payload["explanation"]) > 500):
                    raise CaptureSessionConflict("UNSUPPORTED_CAPTURE_EXCEPTION_HISTORY")
                if payload["slot"] in active:
                    raise CaptureSessionConflict("INVALID_CAPTURE_EXCEPTION_HISTORY")
                active[payload["slot"]] = {"slot": payload["slot"], "reason_code": payload["reason_code"],
                    "explanation": payload["explanation"], "recorded_by": actor, "event_id": event_id}
            elif kind == "CAPTURE_EXCEPTION_RESOLVED":
                required = {"request_id", "slot", "exception_event_id", "resolution_code", "explanation"}
                if type(payload) is not dict or set(payload) != required:
                    raise CaptureSessionConflict("UNSUPPORTED_CAPTURE_EXCEPTION_HISTORY")
                try:
                    UUID(payload["request_id"])
                except (ValueError, TypeError, AttributeError):
                    raise CaptureSessionConflict("UNSUPPORTED_CAPTURE_EXCEPTION_HISTORY") from None
                if (not isinstance(payload["slot"], str) or not payload["slot"]
                        or payload["resolution_code"] not in resolution_codes
                        or not isinstance(payload["exception_event_id"], str)
                        or not isinstance(payload["explanation"], str)
                        or not payload["explanation"].strip() or len(payload["explanation"]) > 500):
                    raise CaptureSessionConflict("UNSUPPORTED_CAPTURE_EXCEPTION_HISTORY")
                current = active.get(payload["slot"])
                if current is None or current["event_id"] != payload["exception_event_id"]:
                    raise CaptureSessionConflict("INVALID_CAPTURE_EXCEPTION_HISTORY")
                del active[payload["slot"]]
        return active

    def record_capture_exception(self, authorization, session_id, *, request_id, slot, reason_code, explanation):
        session_id = self._session_id(session_id)
        request_id = self._request_id(request_id)
        allowed = {"UNSAFE_TO_APPROACH", "ACCESS_RESTRICTED", "VEHICLE_IN_MOTION",
                   "WEATHER_HAZARD", "OWNER_DECLINED", "EQUIPMENT_FAILURE", "OTHER"}
        if not isinstance(reason_code, str) or reason_code not in allowed or not isinstance(explanation, str) or not explanation.strip() or len(explanation) > 500:
            raise ValueError("INVALID_CAPTURE_EXCEPTION")
        event_id = "capture-exception:" + request_id
        with self.sessions._authorized(authorization) as (conn, actor):
            if actor.actor_role not in ("operator", "supervisor"):
                raise CaptureAuthorizationError("OPERATOR_IDENTITY_REQUIRED")
            session, history = self._history(conn, actor, session_id, creator_required=True)
            slots = frozenset(require_implemented_protocol(session.capture_protocol_version).slots)
            if not isinstance(slot, str) or slot not in slots:
                raise ValueError("INVALID_CAPTURE_SLOT")
            payload = {"request_id": request_id, "slot": slot, "reason_code": reason_code,
                       "explanation": explanation.strip()}
            for kind, _who, old, old_id in history:
                if old_id == event_id:
                    if kind == "CAPTURE_EXCEPTION_RECORDED" and old == payload:
                        return {"session_id": session_id, **payload, "replayed": True}
                    raise CaptureSessionConflict("IDEMPOTENCY_CONFLICT")
            if self._capture_paused(history):
                raise CaptureSessionConflict("CAPTURE_SESSION_PAUSED")
            if any(kind in ("QUALITY_RECORDED", "MANIFEST_SEALED", "REVIEW_RECORDED") for kind, *_ in history):
                raise CaptureSessionConflict("CAPTURE_SET_ALREADY_QUALITY_CHECKED")
            consent = self._consent_state(history)
            if consent is None:
                raise CaptureSessionConflict("ACTIVE_OWNER_CONSENT_REQUIRED")
            if not self._has_valid_vehicle_reference(history, consent):
                raise CaptureSessionConflict("VEHICLE_REFERENCE_REQUIRED")
            artifacts = {item[2].get("slot") for item in history if item[0] == "ARTIFACT_REGISTERED" and type(item[2]) is dict}
            if slot in artifacts:
                raise CaptureSessionConflict("CAPTURE_SLOT_ALREADY_REGISTERED")
            if slot in self._active_capture_exceptions(history):
                raise CaptureSessionConflict("CAPTURE_EXCEPTION_ALREADY_OPEN")
            self._append(conn, actor, session_id, history, event_id=event_id,
                         kind="CAPTURE_EXCEPTION_RECORDED", reason="capture exception recorded", payload=payload)
        return {"session_id": session_id, **payload, "replayed": False}

    def resolve_capture_exception(self, authorization, session_id, *, request_id, slot, resolution_code, explanation):
        session_id = self._session_id(session_id)
        request_id = self._request_id(request_id)
        if resolution_code not in {"CAPTURED_AFTER_RETRY", "NO_LONGER_APPLICABLE", "SUPERVISOR_REVIEWED"}:
            raise ValueError("INVALID_CAPTURE_EXCEPTION_RESOLUTION")
        if not isinstance(explanation, str) or not explanation.strip() or len(explanation) > 500:
            raise ValueError("INVALID_CAPTURE_EXCEPTION_RESOLUTION")
        event_id = "capture-exception-resolved:" + request_id
        payload = None
        with self.sessions._authorized(authorization) as (conn, actor):
            if actor.actor_role not in ("operator", "supervisor"):
                raise CaptureAuthorizationError("OPERATOR_IDENTITY_REQUIRED")
            _session, history = self._history(conn, actor, session_id, creator_required=True)
            for kind, _who, old, old_id in history:
                if old_id == event_id:
                    if kind == "CAPTURE_EXCEPTION_RESOLVED" and type(old) is dict:
                        return {"session_id": session_id, **old, "replayed": True}
                    raise CaptureSessionConflict("IDEMPOTENCY_CONFLICT")
            if self._capture_paused(history):
                raise CaptureSessionConflict("CAPTURE_SESSION_PAUSED")
            if any(kind in ("QUALITY_RECORDED", "MANIFEST_SEALED", "REVIEW_RECORDED") for kind, *_ in history):
                raise CaptureSessionConflict("CAPTURE_SET_ALREADY_QUALITY_CHECKED")
            if resolution_code == "SUPERVISOR_REVIEWED" and actor.actor_role != "supervisor":
                raise CaptureAuthorizationError("SUPERVISOR_IDENTITY_REQUIRED")
            current = self._active_capture_exceptions(history).get(slot)
            if current is None:
                raise CaptureSessionConflict("ACTIVE_CAPTURE_EXCEPTION_REQUIRED")
            artifacts = {item[2].get("slot") for item in history if item[0] == "ARTIFACT_REGISTERED" and type(item[2]) is dict}
            if resolution_code == "CAPTURED_AFTER_RETRY" and slot not in artifacts:
                raise CaptureSessionConflict("CAPTURE_ARTIFACT_REQUIRED_TO_RESOLVE_EXCEPTION")
            payload = {"request_id": request_id, "slot": slot, "exception_event_id": current["event_id"],
                       "resolution_code": resolution_code, "explanation": explanation.strip()}
            self._append(conn, actor, session_id, history, event_id=event_id,
                         kind="CAPTURE_EXCEPTION_RESOLVED", reason="capture exception resolution recorded", payload=payload)
        return {"session_id": session_id, **payload, "replayed": False}

    def pause_capture_session(self, authorization, session_id, *, request_id, reason):
        return self._set_capture_pause(authorization, session_id, request_id=request_id, reason=reason, pause=True)

    def resume_capture_session(self, authorization, session_id, *, request_id, reason):
        return self._set_capture_pause(authorization, session_id, request_id=request_id, reason=reason, pause=False)

    def _set_capture_pause(self, authorization, session_id, *, request_id, reason, pause):
        session_id = self._session_id(session_id)
        request_id = self._request_id(request_id)
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 500:
            raise ValueError("INVALID_CAPTURE_PAUSE_REASON")
        kind = "CAPTURE_SESSION_PAUSED" if pause else "CAPTURE_SESSION_RESUMED"
        prefix = "capture-pause:" if pause else "capture-resume:"
        event_id = prefix + request_id
        payload = {"request_id": request_id, "reason": reason.strip()}
        with self.sessions._authorized(authorization) as (conn, actor):
            if actor.actor_role not in ("operator", "supervisor"):
                raise CaptureAuthorizationError("OPERATOR_IDENTITY_REQUIRED")
            _session, history = self._history(conn, actor, session_id, creator_required=True)
            for old_kind, _who, old, old_id in history:
                if old_id == event_id:
                    if old_kind == kind and old == payload:
                        return {"session_id": session_id, "paused": pause, "replayed": True}
                    raise CaptureSessionConflict("IDEMPOTENCY_CONFLICT")
            paused = self._capture_paused(history)
            if paused == pause:
                raise CaptureSessionConflict("CAPTURE_SESSION_ALREADY_PAUSED" if pause else "CAPTURE_SESSION_NOT_PAUSED")
            if any(old_kind in ("QUALITY_RECORDED", "MANIFEST_SEALED", "REVIEW_RECORDED") for old_kind, *_ in history):
                raise CaptureSessionConflict("CAPTURE_SET_ALREADY_QUALITY_CHECKED")
            self._append(conn, actor, session_id, history, event_id=event_id,
                         kind=kind, reason="capture session " + ("paused" if pause else "resumed"), payload=payload)
        return {"session_id": session_id, "paused": pause, "replayed": False}

    def record_consent(self, authorization, session_id, *, request_id, accepted, scope):
        session_id = self._session_id(session_id)
        request_id = self._request_id(request_id)
        if type(accepted) is not bool or scope != "capture_review":
            raise ValueError("INVALID_CONSENT")
        with self.sessions._authorized(authorization) as (conn, actor):
            if actor.actor_role != "owner":
                raise CaptureAuthorizationError("OWNER_IDENTITY_REQUIRED")
            _session, history = self._history(conn, actor, session_id, creator_required=False)
            if _session.scope == "persistent-claim-case":
                binding = conn.execute(
                    "SELECT faos.bind_claim_case_owner(%s::uuid,%s::text,%s::text)",
                    (actor.tenant_id, session_id, actor.actor_id),
                ).fetchone()[0]
                if binding != "BOUND":
                    raise CaptureAuthorizationError("CLAIM_CASE_OWNER_BINDING_DENIED")
            previous = self._consent_state(history)
            event_id = "consent:" + request_id
            payload = {
                "accepted": accepted,
                "owner_actor_id": actor.actor_id,
                "disclosure_version": DISCLOSURE_VERSION,
                "scope": scope,
                "request_id": request_id,
            }
            replayed = False
            for kind, _event_actor, old, old_id in history:
                if old_id == event_id:
                    if kind == "CONSENT_RECORDED" and old == payload:
                        replayed = True
                        break
                    raise CaptureSessionConflict("IDEMPOTENCY_CONFLICT")
            if not replayed:
                consent_events = [(who, data) for kind, who, data, _ in history if kind == "CONSENT_RECORDED"]
                if accepted:
                    if consent_events:
                        raise CaptureSessionConflict("CONSENT_ALREADY_RECORDED")
                    if any(kind in ("VEHICLE_RECORDED", "ARTIFACT_REGISTERED", "QUALITY_RECORDED", "MANIFEST_SEALED", "REVIEW_RECORDED") for kind, *_ in history):
                        raise CaptureSessionConflict("CONSENT_ORDER_VIOLATION")
                elif consent_events and (previous is None or previous[0] != actor.actor_id):
                    raise CaptureAuthorizationError("CONSENT_OWNER_REQUIRED")
                self._append(conn, actor, session_id, history, event_id=event_id,
                             kind="CONSENT_RECORDED", reason="owner consent state recorded", payload=payload)
                history.append(("CONSENT_RECORDED", actor.actor_id, payload, event_id))
            if not accepted:
                artifacts = [data["artifact_id"] for kind, _who, data, _ in history
                    if kind == "ARTIFACT_REGISTERED" and type(data) is dict
                    and isinstance(data.get("artifact_id"), str)]
                deletion_tenant = actor.tenant_id
                if _session.scope == "persistent-claim-case" and _session.claim_id:
                    conn.execute(
                        "SELECT faos.revoke_collision_vehicle_source(%s::uuid,%s::text,%s::text)",
                        (actor.tenant_id, session_id, actor.actor_id),
                    )
                    conn.execute(
                        "SELECT faos.withdraw_claim_case_incident(%s::uuid,%s::uuid,%s::text)",
                        (actor.tenant_id, _session.claim_id, actor.actor_id),
                    )
                    conn.execute(
                        "SELECT faos.revoke_vehicle_decode_profiles(%s::uuid,%s::text,%s::text)",
                        (actor.tenant_id, session_id, actor.actor_id),
                    )
            else:
                artifacts = []
                deletion_tenant = actor.tenant_id
        deleted = sum(bool(self.byte_store.delete(
            ArtifactKey(deletion_tenant, UUID(session_id), UUID(artifact_id)))) for artifact_id in artifacts)
        return {"session_id": session_id, "accepted": accepted, "replayed": replayed,
                "deleted_original_artifacts": deleted}

    def record_vehicle_decode_consent(self, authorization, session_id, *, request_id, accepted, scope, disclosure_version):
        session_id = self._session_id(session_id)
        request_id = self._request_id(request_id)
        if (type(accepted) is not bool or scope != "nhtsa_vpic_decode"
                or disclosure_version != VEHICLE_DECODE_DISCLOSURE_VERSION):
            raise ValueError("INVALID_VEHICLE_DECODE_CONSENT")
        with self.sessions._authorized(authorization) as (conn, actor):
            if actor.actor_role != "owner":
                raise CaptureAuthorizationError("OWNER_IDENTITY_REQUIRED")
            _session, history = self._history(conn, actor, session_id, creator_required=False)
            capture_consent = self._consent_state(history)
            if capture_consent is None or capture_consent[0] != actor.actor_id:
                raise CaptureAuthorizationError("ACTIVE_CAPTURE_OWNER_CONSENT_REQUIRED")
            event_id = "vehicle-decode-consent:" + request_id
            payload = {
                "accepted": accepted,
                "owner_actor_id": actor.actor_id,
                "disclosure_version": VEHICLE_DECODE_DISCLOSURE_VERSION,
                "scope": scope,
                "request_id": request_id,
            }
            replayed = False
            for kind, _event_actor, old, old_id in history:
                if old_id == event_id:
                    if kind == "VEHICLE_DECODE_CONSENT_RECORDED" and old == payload:
                        replayed = True
                        break
                    raise CaptureSessionConflict("IDEMPOTENCY_CONFLICT")
            if not replayed:
                self._append(
                    conn, actor, session_id, history, event_id=event_id,
                    kind="VEHICLE_DECODE_CONSENT_RECORDED",
                    reason="owner vehicle-decoding consent state recorded",
                    payload=payload,
                )
            if not accepted:
                conn.execute(
                    "SELECT faos.revoke_vehicle_decode_profiles(%s::uuid,%s::text,%s::text)",
                    (actor.tenant_id, session_id, actor.actor_id),
                )
        return {
            "session_id": session_id, "accepted": accepted,
            "scope": scope, "disclosure_version": VEHICLE_DECODE_DISCLOSURE_VERSION,
            "replayed": replayed,
        }

    def decode_vehicle_profile(self, authorization, session_id, *, request_id, vin, decoder):
        """Decode only after separate owner opt-in; persist normalized provider data only.

        The keyed VIN digest is checked both before and after the network call.
        Consent is re-read under the session lock before persistence so a
        concurrent withdrawal cannot commit a newly returned profile.
        """
        from app.vehicle_intelligence.vpic import VpicDecodeError

        session_id = self._session_id(session_id)
        request_id = self._request_id(request_id)
        if not isinstance(vin, str) or not vin.isascii():
            raise ValueError("INVALID_VIN")
        validity = validate_vin(vin)
        if not validity.ok or validity.normalization_changed or validity.vin != vin:
            raise ValueError("VIN_VALIDATION_FAILED")
        vin_digest = hmac.new(self._vin_pepper, vin.upper().encode("ascii"), hashlib.sha256).hexdigest()

        def authorized_source(conn, actor, history):
            capture_consent = self._consent_state(history)
            decode_consent = self._vehicle_decode_consent_state(history, capture_consent)
            if capture_consent is None or decode_consent is None:
                raise CaptureAuthorizationError("ACTIVE_VEHICLE_DECODE_CONSENT_REQUIRED")
            row = conn.execute(
                "SELECT vehicle_id FROM faos.vehicle_identity_sources "
                "WHERE tenant_id=%s AND source_session_id=%s "
                "AND owner_actor_id=%s AND vin_hmac_sha256=%s AND source_status='ACTIVE'",
                (actor.tenant_id, session_id, capture_consent[0], vin_digest),
            ).fetchone()
            if row is None:
                raise CaptureSessionConflict("ACTIVE_CONSENTED_VEHICLE_IDENTITY_REQUIRED")
            return str(row[0])

        with self.sessions._authorized(authorization) as (conn, actor):
            if actor.actor_role not in ("operator", "supervisor"):
                raise CaptureAuthorizationError("OPERATOR_IDENTITY_REQUIRED")
            _session, history = self._history(conn, actor, session_id, creator_required=True)
            vehicle_id = authorized_source(conn, actor, history)
            prior = conn.execute(
                "SELECT vehicle_id,source_session_id,decode_status,provider,provider_api,requested_at,"
                "response_sha256,decode_error_code,attributes_json FROM faos.vehicle_decode_snapshots "
                "WHERE tenant_id=%s AND request_id=%s",
                (actor.tenant_id, request_id),
            ).fetchone()
            if prior is not None:
                if str(prior[0]) != vehicle_id or prior[1] != session_id:
                    raise CaptureSessionConflict("IDEMPOTENCY_CONFLICT")
                return {
                    "session_id": session_id, "vehicle_id": vehicle_id,
                    "status": prior[2], "provider": prior[3], "provider_api": prior[4],
                    "requested_at": prior[5].isoformat(), "response_sha256": prior[6],
                    "decode_error_code": prior[7], "attributes": prior[8] or {},
                    "replayed": True, "physics_input_eligibility": "NOT_ESTABLISHED",
                }

        try:
            profile = decoder.decode(vin)
            profile_data = profile.to_dict()
        except VpicDecodeError as error:
            profile_data = {
                "status": "ERROR", "provider": "NHTSA_VPIC",
                "provider_api": "DecodeVinValuesExtended",
                "requested_at": datetime.now(timezone.utc).isoformat(),
                "response_sha256": None, "decode_error_code": error.code,
                "attributes": {},
                "physics_input_eligibility": "NOT_ESTABLISHED",
            }

        with self.sessions._authorized(authorization) as (conn, actor):
            if actor.actor_role not in ("operator", "supervisor"):
                raise CaptureAuthorizationError("OPERATOR_IDENTITY_REQUIRED")
            _session, history = self._history(conn, actor, session_id, creator_required=True)
            current_vehicle_id = authorized_source(conn, actor, history)
            if current_vehicle_id != vehicle_id:
                raise CaptureSessionConflict("VEHICLE_IDENTITY_CHANGED_DURING_DECODE")
            prior = conn.execute(
                "SELECT vehicle_id,source_session_id,decode_status,provider,provider_api,requested_at,"
                "response_sha256,decode_error_code,attributes_json FROM faos.vehicle_decode_snapshots "
                "WHERE tenant_id=%s AND request_id=%s",
                (actor.tenant_id, request_id),
            ).fetchone()
            if prior is not None:
                if str(prior[0]) != vehicle_id or prior[1] != session_id:
                    raise CaptureSessionConflict("IDEMPOTENCY_CONFLICT")
                return {
                    "session_id": session_id, "vehicle_id": vehicle_id,
                    "status": prior[2], "provider": prior[3], "provider_api": prior[4],
                    "requested_at": prior[5].isoformat(), "response_sha256": prior[6],
                    "decode_error_code": prior[7], "attributes": prior[8] or {},
                    "replayed": True, "physics_input_eligibility": "NOT_ESTABLISHED",
                }
            requested_at = profile_data["requested_at"]
            attributes = profile_data.get("attributes") or {}
            attributes_json = json.dumps(attributes, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            event_id = "vehicle-profile:" + request_id
            event_payload = {
                "request_id": request_id, "vehicle_id": vehicle_id,
                "provider": profile_data["provider"], "provider_api": profile_data["provider_api"],
                "decode_status": profile_data["status"],
                "response_sha256": profile_data.get("response_sha256"),
                "decode_error_code": profile_data.get("decode_error_code"),
                "disclosure_version": VEHICLE_DECODE_DISCLOSURE_VERSION,
            }
            outcome = conn.execute(
                "SELECT faos.record_vehicle_decode_snapshot("
                "%s::uuid,%s::uuid,%s::text,%s::uuid,%s::text,%s::text,%s::timestamptz,"
                "%s::text,%s::text,%s::text,%s::jsonb,%s::text,%s::text)",
                (
                    actor.tenant_id, vehicle_id, session_id, request_id,
                    profile_data["provider"], profile_data["provider_api"], requested_at,
                    profile_data.get("response_sha256"), profile_data["status"],
                    profile_data.get("decode_error_code"), attributes_json, actor.actor_id,
                    vin_digest,
                ),
            ).fetchone()[0]
            if outcome != "ACCEPTED":
                raise CaptureSessionConflict("VEHICLE_PROFILE_SNAPSHOT_NOT_ACCEPTED")
            self._append(
                conn, actor, session_id, history, event_id=event_id,
                kind="VEHICLE_PROFILE_DECODED",
                reason="consented NHTSA vPIC vehicle profile result recorded",
                payload=event_payload,
            )
        return {
            "session_id": session_id, "vehicle_id": vehicle_id,
            **profile_data, "replayed": False,
        }

    def record_vehicle(self, authorization, session_id, *, request_id, vin):
        session_id = self._session_id(session_id)
        request_id = self._request_id(request_id)
        if not isinstance(vin, str) or not vin.isascii():
            raise ValueError("INVALID_VIN")
        validity = validate_vin(vin)
        if not validity.ok or validity.normalization_changed or validity.vin != vin:
            raise ValueError("VIN_VALIDATION_FAILED")
        vin_digest = hmac.new(self._vin_pepper, vin.upper().encode("ascii"), hashlib.sha256).hexdigest()
        event_id = "vehicle:" + request_id
        with self.sessions._authorized(authorization) as (conn, actor):
            if actor.actor_role not in ("operator", "supervisor"):
                raise CaptureAuthorizationError("OPERATOR_IDENTITY_REQUIRED")
            _session, history = self._history(conn, actor, session_id, creator_required=True)
            if self._consent_state(history) is None:
                raise CaptureSessionConflict("ACTIVE_OWNER_CONSENT_REQUIRED")
            payload = {"request_id": request_id, "vin_hmac_sha256": vin_digest,
                       "disclosure_version": DISCLOSURE_VERSION, "recorded_by_role": actor.actor_role}
            if any(kind == "ARTIFACT_REGISTERED" for kind, *_ in history):
                raise CaptureSessionConflict("VEHICLE_ORDER_VIOLATION")
            for kind, _event_actor, old, old_id in history:
                if old_id == event_id:
                    if kind == "VEHICLE_RECORDED" and old == payload:
                        return {"session_id": session_id, "vin_hmac_sha256": vin_digest, "replayed": True}
                    raise CaptureSessionConflict("IDEMPOTENCY_CONFLICT")
            if any(kind == "VEHICLE_RECORDED" for kind, *_ in history):
                raise CaptureSessionConflict("VEHICLE_REFERENCE_ALREADY_RECORDED")
            self._append(conn, actor, session_id, history, event_id=event_id,
                         kind="VEHICLE_RECORDED", reason="keyed vehicle reference recorded", payload=payload)
        return {"session_id": session_id, "vin_hmac_sha256": vin_digest, "replayed": False}

    def register_artifact(self, authorization, session_id, *, request_id, artifact_id, slot,
                          payload_base64, sha256_hex):
        session_id = self._session_id(session_id)
        request_id = self._request_id(request_id)
        artifact_id = self._request_id(artifact_id)
        if not isinstance(slot, str) or not slot:
            raise ValueError("INVALID_CAPTURE_SLOT")
        if not isinstance(sha256_hex, str) or re.fullmatch("[0-9a-f]{64}", sha256_hex) is None:
            raise ValueError("INVALID_SHA256")
        if not isinstance(payload_base64, str) or len(payload_base64) > ((MAX_EVIDENCE_BYTES + 2) // 3) * 4:
            raise ValueError("ARTIFACT_TOO_LARGE")
        try:
            raw = base64.b64decode(payload_base64, validate=True)
        except (ValueError, binascii.Error):
            raise ValueError("INVALID_ARTIFACT_ENCODING") from None
        if not raw or len(raw) > MAX_EVIDENCE_BYTES:
            raise ValueError("INVALID_ARTIFACT_SIZE")
        if hashlib.sha256(raw).hexdigest() != sha256_hex:
            raise ValueError("ARTIFACT_HASH_MISMATCH")
        event_id = "artifact:" + request_id
        with self.sessions._authorized(authorization) as (conn, actor):
            if actor.actor_role not in ("operator", "supervisor"):
                raise CaptureAuthorizationError("OPERATOR_IDENTITY_REQUIRED")
            _session, history = self._history(conn, actor, session_id, creator_required=True)
            slots = frozenset(require_implemented_protocol(_session.capture_protocol_version).slots)
            if slot not in slots:
                raise ValueError("INVALID_CAPTURE_SLOT")
            if self._capture_paused(history):
                raise CaptureSessionConflict("CAPTURE_SESSION_PAUSED")
            consent = self._consent_state(history)
            if consent is None:
                raise CaptureSessionConflict("ACTIVE_OWNER_CONSENT_REQUIRED")
            if not self._has_valid_vehicle_reference(history, consent):
                raise CaptureSessionConflict("VEHICLE_REFERENCE_REQUIRED")
            if any(kind in ("QUALITY_RECORDED", "MANIFEST_SEALED", "REVIEW_RECORDED")
                   for kind, *_ in history):
                raise CaptureSessionConflict("CAPTURE_SET_ALREADY_QUALITY_CHECKED")
            payload = {"request_id": request_id, "artifact_id": artifact_id, "slot": slot,
                       "sha256": sha256_hex, "byte_length": len(raw), "recorded_by_role": actor.actor_role}
            for kind, _event_actor, old, old_id in history:
                if old_id == event_id:
                    if kind == "ARTIFACT_REGISTERED" and old == payload:
                        self.byte_store.put(ArtifactKey(actor.tenant_id, UUID(session_id), UUID(artifact_id)),
                                            raw, expected_sha256=sha256_hex)
                        return {**payload, "replayed": True}
                    raise CaptureSessionConflict("IDEMPOTENCY_CONFLICT")
            if any(kind == "ARTIFACT_REGISTERED" and type(old) is dict
                   and old.get("artifact_id") == artifact_id for kind, _, old, _ in history):
                raise CaptureSessionConflict("ARTIFACT_ID_ALREADY_REGISTERED")
            key = ArtifactKey(actor.tenant_id, UUID(session_id), UUID(artifact_id))
            self.byte_store.put(key, raw, expected_sha256=sha256_hex)
            self._append(conn, actor, session_id, history, event_id=event_id,
                         kind="ARTIFACT_REGISTERED", reason="original evidence bytes registered", payload=payload)
        return {**payload, "replayed": False}

    @staticmethod
    def _artifact_set(history, protocol_version=DEFAULT_CAPTURE_PROTOCOL):
        slots = frozenset(require_implemented_protocol(protocol_version).slots)
        latest = {}
        for kind, actor, payload, _event_id in history:
            if kind != "ARTIFACT_REGISTERED":
                continue
            if (type(payload) is not dict
                    or set(payload) != {"request_id", "artifact_id", "slot", "sha256", "byte_length", "recorded_by_role"}
                    or not isinstance(payload["slot"], str) or payload["slot"] not in slots
                    or not isinstance(payload["sha256"], str) or re.fullmatch(r"[0-9a-f]{64}", payload["sha256"]) is None
                    or type(payload["byte_length"]) is not int or payload["byte_length"] <= 0
                    or payload["recorded_by_role"] not in ("operator", "supervisor")):
                raise CaptureSessionConflict("UNSUPPORTED_ARTIFACT_HISTORY")
            try:
                UUID(payload["artifact_id"])
                UUID(payload["request_id"])
            except (ValueError, TypeError, AttributeError):
                raise CaptureSessionConflict("UNSUPPORTED_ARTIFACT_HISTORY") from None
            latest[payload["slot"]] = (actor, payload)
        if set(latest) != slots:
            raise CaptureSessionConflict("CAPTURE_SET_INCOMPLETE")
        return latest

    def _verified_manifest(self, actor, session_id, history, protocol_version=DEFAULT_CAPTURE_PROTOCOL):
        latest = self._artifact_set(history, protocol_version)
        manifest = build_manifest(
            session_id,
            tuple(ManifestEntry(data["artifact_id"], slot, data["sha256"])
                  for slot, (_actor, data) in latest.items()),
            protocol_version=protocol_version,
        )
        for entry in manifest.entries:
            record = latest[entry.slot][1]
            try:
                original = self.byte_store.get(
                    ArtifactKey(actor.tenant_id, UUID(session_id), UUID(entry.artifact_id)),
                    expected_sha256=entry.sha256_hex,
                )
            except ArtifactIntegrityError as error:
                raise _EvidenceArtifactIntegrityFailure(
                    entry.artifact_id, entry.slot, entry.sha256_hex, "ARTIFACT_HASH_MISMATCH"
                ) from error
            except ArtifactNotFound as error:
                raise _EvidenceArtifactIntegrityFailure(
                    entry.artifact_id, entry.slot, entry.sha256_hex, "ARTIFACT_MISSING"
                ) from error
            if len(original) != record["byte_length"]:
                raise CaptureSessionConflict("EVIDENCE_BYTE_LENGTH_MISMATCH")
        return manifest

    def record_quality(self, authorization, session_id, *, request_id, results):
        session_id = self._session_id(session_id)
        request_id = self._request_id(request_id)
        if type(results) is not dict or any(type(value) is not bool for value in results.values()):
            raise ValueError("INVALID_ADVISORY_QUALITY_RESULTS")
        event_id = "quality:" + request_id
        with self.sessions._authorized(authorization) as (conn, actor):
            if actor.actor_role not in ("operator", "supervisor"):
                raise CaptureAuthorizationError("OPERATOR_IDENTITY_REQUIRED")
            _session, history = self._history(conn, actor, session_id, creator_required=True)
            slots = frozenset(require_implemented_protocol(_session.capture_protocol_version).slots)
            if set(results) != slots:
                raise ValueError("INVALID_ADVISORY_QUALITY_RESULTS")
            if self._capture_paused(history):
                raise CaptureSessionConflict("CAPTURE_SESSION_PAUSED")
            if self._active_capture_exceptions(history):
                raise CaptureSessionConflict("UNRESOLVED_CAPTURE_EXCEPTIONS")
            consent = self._consent_state(history)
            if consent is None:
                raise CaptureSessionConflict("ACTIVE_OWNER_CONSENT_REQUIRED")
            if not self._has_valid_vehicle_reference(history, consent):
                raise CaptureSessionConflict("VEHICLE_REFERENCE_REQUIRED")
            for kind, _who, old, old_id in history:
                if old_id == event_id:
                    if kind == "QUALITY_RECORDED" and old == {
                        "request_id": request_id, "results": results, "advisory_only": True,
                    }:
                        return {"session_id": session_id, "advisory_only": True, "replayed": True}
                    raise CaptureSessionConflict("IDEMPOTENCY_CONFLICT")
            if any(kind in ("QUALITY_RECORDED", "MANIFEST_SEALED", "REVIEW_RECORDED")
                   for kind, *_ in history):
                raise CaptureSessionConflict("QUALITY_ALREADY_RECORDED")
            self._verified_manifest(actor, session_id, history, _session.capture_protocol_version)
            payload = {"request_id": request_id, "results": results, "advisory_only": True}
            self._append(conn, actor, session_id, history, event_id=event_id,
                         kind="QUALITY_RECORDED", reason="advisory image quality recorded", payload=payload)
        return {"session_id": session_id, "advisory_only": True, "replayed": False}

    @staticmethod
    def _register_manifest_root(conn, actor, session_id, seal_event_id, request_id, payload, *, seal_actor=None):
        try:
            status = conn.execute(
                "SELECT faos.register_manifest_root_from_capture("
                "%s::uuid,%s::text,%s::text,%s::text,%s::text,%s::text,%s::uuid)",
                (actor.tenant_id, session_id, seal_event_id, payload["manifest_digest"],
                 payload["shot_list_version"], seal_actor or actor.actor_id, request_id),
            ).fetchone()[0]
        except psycopg.errors.RaiseException as error:
            code = error.diag.message_primary or "MANIFEST_ROOT_REGISTRATION_FAILED"
            if code in {
                "TENANT_CONTEXT_MISMATCH", "SESSION_NOT_FOUND",
                "ROOT_PROTOCOL_SESSION_MISMATCH", "SEAL_EVENT_NOT_FOUND",
                "CAPTURE_SEAL_ACTOR_OR_KIND_MISMATCH", "ROOT_SEAL_MISMATCH",
                "QUALITY_REVIEW_REQUIRED_BEFORE_SEAL", "UNSUPPORTED_CAPTURE_PROTOCOL",
                "SEALED_ARTIFACT_SET_MISMATCH", "SEAL_NOT_CURRENT_EVENT",
                "MANIFEST_BINDING_CHAIN_INVALID", "MANIFEST_BINDING_SEAL_PREFIX_INVALID",
                "MANIFEST_BINDING_CHAIN_TAIL_INVALID", "ROOT_CONFLICT",
            }:
                raise CaptureSessionConflict(code) from None
            raise
        if status not in ("REGISTERED", "DUPLICATE"):
            raise CaptureSessionConflict("MANIFEST_ROOT_REGISTRATION_FAILED")
        verified = conn.execute(
            "SELECT faos.verify_manifest_root_binding(%s::uuid,%s::text,%s::text)",
            (actor.tenant_id, session_id, seal_event_id),
        ).fetchone()[0]
        if verified is not True:
            raise CaptureSessionConflict("MANIFEST_ROOT_BINDING_INVALID")
        return status

    def seal_capture(self, authorization, session_id, *, request_id):
        session_id = self._session_id(session_id)
        request_id = self._request_id(request_id)
        event_id = "seal:" + request_id
        with self.sessions._authorized(authorization) as (conn, actor):
            if actor.actor_role not in ("operator", "supervisor"):
                raise CaptureAuthorizationError("OPERATOR_IDENTITY_REQUIRED")
            _session, history = self._history(conn, actor, session_id, creator_required=True)
            if self._capture_paused(history):
                raise CaptureSessionConflict("CAPTURE_SESSION_PAUSED")
            if self._active_capture_exceptions(history):
                raise CaptureSessionConflict("UNRESOLVED_CAPTURE_EXCEPTIONS")
            if self._consent_state(history) is None:
                raise CaptureSessionConflict("ACTIVE_OWNER_CONSENT_REQUIRED")
            for kind, seal_actor, old, old_id in history:
                if old_id == event_id:
                    if kind == "MANIFEST_SEALED" and type(old) is dict:
                        self._register_manifest_root(conn, actor, session_id, event_id, request_id, old, seal_actor=seal_actor)
                        return {"session_id": session_id, **old, "root_registered": True, "replayed": True}
                    raise CaptureSessionConflict("IDEMPOTENCY_CONFLICT")
            last_capture_event = self._last_capture_event(history)
            if last_capture_event is None or last_capture_event[0] != "QUALITY_RECORDED":
                raise CaptureSessionConflict("QUALITY_REVIEW_REQUIRED_BEFORE_SEAL")
            manifest = self._verified_manifest(actor, session_id, history, _session.capture_protocol_version)
            payload = {
                "schema_version": "0.1",
                "request_id": request_id,
                "manifest_digest": manifest.digest(),
                "shot_list_version": manifest.shot_list_version,
                "artifact_ids": [entry.artifact_id for entry in manifest.entries],
            }
            self._append(conn, actor, session_id, history, event_id=event_id,
                         kind="MANIFEST_SEALED", reason="verified original-byte manifest sealed", payload=payload)
            self._register_manifest_root(conn, actor, session_id, event_id, request_id, payload)
        return {"session_id": session_id, **payload, "root_registered": True, "replayed": False}

    def record_review(self, authorization, session_id, *, request_id, disposition, reason):
        session_id = self._session_id(session_id)
        request_id = self._request_id(request_id)
        if disposition not in ("NOTE_ONLY", "HUMAN_QC_REQUIRED"):
            raise ValueError("INVALID_REVIEW_DISPOSITION")
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 1000:
            raise ValueError("INVALID_REVIEW_REASON")
        event_id = "review:" + request_id
        with self.sessions._authorized(authorization) as (conn, actor):
            if actor.actor_role not in ("reviewer", "supervisor"):
                raise CaptureAuthorizationError("REVIEWER_IDENTITY_REQUIRED")
            session, history = self._history(conn, actor, session_id, creator_required=False)
            if actor.actor_id == session.created_by:
                raise CaptureAuthorizationError("INDEPENDENT_REVIEWER_REQUIRED")
            consent = self._consent_state(history)
            if consent is None:
                raise CaptureSessionConflict("ACTIVE_OWNER_CONSENT_REQUIRED")
            prior_seal = next((item for item in reversed(history) if item[0] == "MANIFEST_SEALED"), None)
            if prior_seal is None or type(prior_seal[2]) is not dict:
                raise CaptureSessionConflict("SEALED_SESSION_REQUIRED_FOR_REVIEW")
            self._register_manifest_root(
                conn, actor, session_id, prior_seal[3],
                prior_seal[2]["request_id"], prior_seal[2], seal_actor=prior_seal[1],
            )
            for kind, _who, old, old_id in history:
                if old_id == event_id:
                    if kind == "REVIEW_RECORDED" and type(old) is dict and old.get("disposition") == disposition and old.get("reason") == reason:
                        return {"session_id": session_id, **old, "replayed": True}
                    raise CaptureSessionConflict("IDEMPOTENCY_CONFLICT")
            last_capture_event = self._last_capture_event(history)
            if last_capture_event is None or last_capture_event[0] != "MANIFEST_SEALED":
                raise CaptureSessionConflict("SEALED_SESSION_REQUIRED_FOR_REVIEW")
            manifest = self._verified_manifest(actor, session_id, history, session.capture_protocol_version)
            seal = last_capture_event[2]
            if seal.get("manifest_digest") != manifest.digest():
                raise CaptureSessionConflict("SEALED_MANIFEST_MISMATCH")
            self._register_manifest_root(
                conn, actor, session_id, last_capture_event[3],
                seal["request_id"], seal, seal_actor=last_capture_event[1],
            )
            payload = {
                "request_id": request_id,
                "manifest_digest": manifest.digest(),
                "disposition": disposition,
                "reason": reason.strip(),
                "artifact_ids": [entry.artifact_id for entry in manifest.entries],
            }
            self._append(conn, actor, session_id, history, event_id=event_id,
                         kind="REVIEW_RECORDED", reason="independent human review recorded", payload=payload)
        return {"session_id": session_id, **payload, "replayed": False}

    def list_review_queue(self, authorization, *, limit=100):
        if type(limit) is not int or not 1 <= limit <= 200:
            raise ValueError("INVALID_REVIEW_QUEUE_LIMIT")
        queued = []
        with self.sessions._authorized(authorization) as (conn, actor):
            if actor.actor_role not in ("reviewer", "supervisor"):
                raise CaptureAuthorizationError("REVIEWER_IDENTITY_REQUIRED")
            rows = conn.execute(
                "SELECT s.session_id FROM faos.sessions s "
                "JOIN LATERAL (SELECT kind,occurred_at FROM faos.events e "
                "WHERE e.tenant_id=s.tenant_id AND e.session_id=s.session_id "
                "AND e.kind NOT IN ('VEHICLE_DECODE_CONSENT_RECORDED','VEHICLE_PROFILE_DECODED') "
                "ORDER BY sequence DESC LIMIT 1) last_event ON last_event.kind='MANIFEST_SEALED' "
                "WHERE s.tenant_id=%s ORDER BY last_event.occurred_at,s.session_id LIMIT %s",
                (actor.tenant_id, limit),
            ).fetchall()
            for (session_id,) in rows:
                session_id = self._session_id(session_id)
                _session, history = self._history(conn, actor, session_id, creator_required=False)
                last_capture_event = self._last_capture_event(history)
                if last_capture_event is None or last_capture_event[0] != "MANIFEST_SEALED" or self._consent_state(history) is None:
                    continue
                seal_payload = last_capture_event[2]
                if (type(seal_payload) is not dict
                        or set(seal_payload) != {"schema_version", "request_id", "manifest_digest", "shot_list_version", "artifact_ids"}
                        or not isinstance(seal_payload.get("manifest_digest"), str)):
                    raise CaptureSessionConflict("UNSUPPORTED_SEAL_HISTORY")
                # Verify the sealed originals before exposing reviewer-safe metadata.
                manifest = self._verified_manifest(actor, session_id, history, _session.capture_protocol_version)
                self._register_manifest_root(
                    conn, actor, session_id, last_capture_event[3],
                    seal_payload["request_id"], seal_payload, seal_actor=last_capture_event[1],
                )
                expected_artifact_ids = [entry.artifact_id for entry in manifest.entries]
                if (
                    manifest.digest() != seal_payload["manifest_digest"]
                    or seal_payload["shot_list_version"] != manifest.shot_list_version
                    or seal_payload["artifact_ids"] != expected_artifact_ids
                ):
                    raise CaptureSessionConflict("SEALED_MANIFEST_MISMATCH")
                latest = self._artifact_set(history, _session.capture_protocol_version)
                queued.append({
                    "session_id": session_id,
                    "manifest_digest": seal_payload["manifest_digest"],
                    "shot_list_version": seal_payload["shot_list_version"],
                    "artifact_count": len(seal_payload["artifact_ids"]),
                    "artifacts": [
                        {
                            "artifact_id": entry.artifact_id,
                            "slot": entry.slot,
                            "sha256": entry.sha256_hex,
                            "byte_length": latest[entry.slot][1]["byte_length"],
                        }
                        for entry in manifest.entries
                    ],
                    "reviewer_must_decide": True,
                })
                if len(queued) == limit:
                    break
        return queued

    def _record_integrity_failure(self, authorization, session_id, failure):
        """Commit an idempotent journal audit event after a failed original-byte read."""
        with self.sessions._authorized(authorization) as (conn, actor):
            if actor.actor_role not in ("reviewer", "supervisor"):
                raise CaptureAuthorizationError("REVIEWER_IDENTITY_REQUIRED")
            _session, history = self._history(conn, actor, session_id, creator_required=False)
            idempotency_key = (
                "artifact-integrity-failure:" + failure.artifact_id + ":" + failure.expected_sha256[:16]
            )
            event_id = str(uuid5(
                UUID(failure.artifact_id),
                "integrity-failure:" + failure.failure_code + ":" + failure.expected_sha256,
            ))
            payload = {
                "idempotency_key": idempotency_key,
                "artifact_id": failure.artifact_id,
                "slot": failure.slot,
                "expected_sha256": failure.expected_sha256,
                "failure_code": failure.failure_code,
            }
            existing = next((item for item in history if item[3] == event_id), None)
            if existing is not None:
                if existing[0] != "ARTIFACT_INTEGRITY_FAILURE_RECORDED" or existing[2] != payload:
                    raise CaptureSessionConflict("INTEGRITY_AUDIT_IDEMPOTENCY_CONFLICT")
                return
            self._append(
                conn, actor, session_id, history, event_id=event_id,
                kind="ARTIFACT_INTEGRITY_FAILURE_RECORDED",
                reason="server detected original evidence integrity failure: " + failure.failure_code,
                payload=payload,
            )

    def get_review_details(self, authorization, session_id):
        """Return a verified sealed manifest to an independent reviewer."""
        session_id = self._session_id(session_id)
        try:
            with self.sessions._authorized(authorization) as (conn, actor):
                if actor.actor_role not in ("reviewer", "supervisor"):
                    raise CaptureAuthorizationError("REVIEWER_IDENTITY_REQUIRED")
                session, history = self._history(conn, actor, session_id, creator_required=False)
                if actor.actor_id == session.created_by:
                    raise CaptureAuthorizationError("INDEPENDENT_REVIEWER_REQUIRED")
                if self._consent_state(history) is None:
                    raise CaptureSessionConflict("ACTIVE_OWNER_CONSENT_REQUIRED")
                last_capture_event = self._last_capture_event(history)
                if last_capture_event is None or last_capture_event[0] != "MANIFEST_SEALED":
                    raise CaptureSessionConflict("SEALED_SESSION_REQUIRED_FOR_REVIEW")
                manifest = self._verified_manifest(actor, session_id, history, session.capture_protocol_version)
                self._register_manifest_root(
                    conn, actor, session_id, last_capture_event[3],
                    last_capture_event[2]["request_id"], last_capture_event[2],
                    seal_actor=last_capture_event[1],
                )
                latest = self._artifact_set(history, session.capture_protocol_version)
                return {
                    "session_id": session_id,
                    "manifest_digest": manifest.digest(),
                    "shot_list_version": manifest.shot_list_version,
                    "consent_recorded": True,
                    "artifacts": [
                        {
                            "artifact_id": entry.artifact_id,
                            "slot": entry.slot,
                            "sha256": entry.sha256_hex,
                            "byte_length": latest[entry.slot][1]["byte_length"],
                        }
                        for entry in manifest.entries
                    ],
                }
        except _EvidenceArtifactIntegrityFailure as failure:
            # Commit the audit in a fresh transaction after the failed read rolls back.
            self._record_integrity_failure(authorization, session_id, failure)
            raise CaptureSessionConflict("EVIDENCE_ARTIFACT_INTEGRITY_FAILURE") from None

    def retrieve_for_review(self, authorization, session_id, artifact_id):
        session_id = self._session_id(session_id)
        artifact_id = self._request_id(artifact_id)
        try:
            with self.sessions._authorized(authorization) as (conn, actor):
                if actor.actor_role not in ("reviewer", "supervisor"):
                    raise CaptureAuthorizationError("REVIEWER_IDENTITY_REQUIRED")
                _session, history = self._history(conn, actor, session_id, creator_required=False)
                if actor.actor_id == _session.created_by:
                    raise CaptureAuthorizationError("INDEPENDENT_REVIEWER_REQUIRED")
                if self._consent_state(history) is None:
                    raise CaptureSessionConflict("ACTIVE_OWNER_CONSENT_REQUIRED")
                last_capture_event = self._last_capture_event(history)
                if last_capture_event is None or last_capture_event[0] != "MANIFEST_SEALED":
                    raise CaptureSessionConflict("SEALED_SESSION_REQUIRED_FOR_REVIEW")
                manifest = self._verified_manifest(actor, session_id, history, _session.capture_protocol_version)
                self._register_manifest_root(
                    conn, actor, session_id, last_capture_event[3],
                    last_capture_event[2]["request_id"], last_capture_event[2],
                    seal_actor=last_capture_event[1],
                )
                entry = next((item for item in manifest.entries if item.artifact_id == artifact_id), None)
                if entry is None:
                    raise CaptureSessionConflict("ARTIFACT_NOT_IN_SEALED_MANIFEST")
                return self.byte_store.get(
                    ArtifactKey(actor.tenant_id, UUID(session_id), UUID(artifact_id)),
                    expected_sha256=entry.sha256_hex,
                )
        except _EvidenceArtifactIntegrityFailure as failure:
            self._record_integrity_failure(authorization, session_id, failure)
            raise CaptureSessionConflict("EVIDENCE_ARTIFACT_INTEGRITY_FAILURE") from None
