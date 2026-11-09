"""Tenant-authorized consent, VIN reference and original-byte registration.

Metadata is committed to the existing RLS-protected append-only event journal.
Original media is written to the administrator-provisioned POSIX byte store;
no raw VIN is persisted, and consent withdrawal blocks subsequent evidence use.
"""
from __future__ import annotations

import base64
import binascii
from datetime import datetime, timezone
import hashlib
import hmac
import json
import re
from uuid import UUID

from app.artifact_storage import ArtifactKey, OriginalByteStore
from app.evidence_manifest import CANONICAL_SLOTS
from app.vin_guard import validate_vin
from database.capture_sessions import (
    CaptureAuthorizationError,
    CaptureSessionConflict,
    CaptureSessionStore,
)

MAX_EVIDENCE_BYTES = 25 * 1024 * 1024
DISCLOSURE_VERSION = "disclosure-v1"
_CANONICAL_SLOTS = frozenset(CANONICAL_SLOTS)


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
        conn.execute("SELECT faos.lock_session_for_completion(%s::uuid,%s::text)", (actor.tenant_id, session_id))
        rows = conn.execute(
            "SELECT sequence,kind,actor,payload_json,event_id FROM faos.events "
            "WHERE tenant_id=%s AND session_id=%s ORDER BY sequence",
            (actor.tenant_id, session_id),
        ).fetchall()
        if not rows or len(rows) > 1000 or any(row[0] != i + 1 for i, row in enumerate(rows)):
            raise CaptureSessionConflict("UNSUPPORTED_CAPTURE_HISTORY")
        try:
            return session, [(r[1], r[2], json.loads(r[3]), r[4]) for r in rows]
        except (ValueError, TypeError):
            raise CaptureSessionConflict("INVALID_CAPTURE_HISTORY") from None

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
        return (actor, latest) if latest["accepted"] is True else None

    def record_consent(self, authorization, session_id, *, request_id, accepted, scope):
        session_id = self._session_id(session_id)
        request_id = self._request_id(request_id)
        if type(accepted) is not bool or scope != "capture_review":
            raise ValueError("INVALID_CONSENT")
        with self.sessions._authorized(authorization) as (conn, actor):
            if actor.actor_role != "owner":
                raise CaptureAuthorizationError("OWNER_IDENTITY_REQUIRED")
            _session, history = self._history(conn, actor, session_id, creator_required=False)
            previous = self._consent_state(history)
            event_id = "consent:" + request_id
            payload = {
                "accepted": accepted,
                "owner_actor_id": actor.actor_id,
                "disclosure_version": DISCLOSURE_VERSION,
                "scope": scope,
                "request_id": request_id,
            }
            for kind, _event_actor, old, old_id in history:
                if old_id == event_id:
                    if kind == "CONSENT_RECORDED" and old == payload:
                        return {"session_id": session_id, "accepted": accepted, "replayed": True}
                    raise CaptureSessionConflict("IDEMPOTENCY_CONFLICT")
            consent_events = [(who, data) for kind, who, data, _ in history if kind == "CONSENT_RECORDED"]
            if accepted:
                if consent_events:
                    raise CaptureSessionConflict("CONSENT_ALREADY_RECORDED")
            else:
                if consent_events and (previous is None or previous[0] != actor.actor_id):
                    raise CaptureAuthorizationError("CONSENT_OWNER_REQUIRED")
            self._append(conn, actor, session_id, history, event_id=event_id,
                         kind="CONSENT_RECORDED", reason="owner consent state recorded", payload=payload)
        return {"session_id": session_id, "accepted": accepted, "replayed": False}

    def record_vehicle(self, authorization, session_id, *, request_id, vin):
        session_id = self._session_id(session_id)
        request_id = self._request_id(request_id)
        if not isinstance(vin, str) or not vin.isascii():
            raise ValueError("INVALID_VIN")
        validity = validate_vin(vin)
        if not validity.ok or validity.normalization_changed or validity.vin != vin:
            raise ValueError("VIN_VALIDATION_FAILED")
        vin_digest = hmac.new(self._vin_pepper, vin.upper().encode("ascii"), hashlib.sha256).hexdigest()
        payload = {"request_id": request_id, "vin_hmac_sha256": vin_digest, "disclosure_version": DISCLOSURE_VERSION}
        event_id = "vehicle:" + request_id
        with self.sessions._authorized(authorization) as (conn, actor):
            if actor.actor_role not in ("operator", "supervisor"):
                raise CaptureAuthorizationError("OPERATOR_IDENTITY_REQUIRED")
            _session, history = self._history(conn, actor, session_id, creator_required=True)
            if self._consent_state(history) is None:
                raise CaptureSessionConflict("ACTIVE_OWNER_CONSENT_REQUIRED")
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
        if slot not in _CANONICAL_SLOTS:
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
        payload = {"request_id": request_id, "artifact_id": artifact_id, "slot": slot,
                   "sha256": sha256_hex, "byte_length": len(raw)}
        with self.sessions._authorized(authorization) as (conn, actor):
            if actor.actor_role not in ("operator", "supervisor"):
                raise CaptureAuthorizationError("OPERATOR_IDENTITY_REQUIRED")
            _session, history = self._history(conn, actor, session_id, creator_required=True)
            if self._consent_state(history) is None:
                raise CaptureSessionConflict("ACTIVE_OWNER_CONSENT_REQUIRED")
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
