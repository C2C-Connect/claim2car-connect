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
from uuid import UUID

from app.artifact_storage import ArtifactKey, OriginalByteStore
from app.evidence_manifest import CANONICAL_SLOTS, ManifestEntry, build_manifest
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
                        "SELECT faos.withdraw_claim_case_incident(%s::uuid,%s::uuid,%s::text)",
                        (actor.tenant_id, _session.claim_id, actor.actor_id),
                    )
            else:
                artifacts = []
                deletion_tenant = actor.tenant_id
        deleted = sum(bool(self.byte_store.delete(
            ArtifactKey(deletion_tenant, UUID(session_id), UUID(artifact_id)))) for artifact_id in artifacts)
        return {"session_id": session_id, "accepted": accepted, "replayed": replayed,
                "deleted_original_artifacts": deleted}

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
        if not isinstance(slot, str) or slot not in _CANONICAL_SLOTS:
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
    def _artifact_set(history):
        latest = {}
        for kind, actor, payload, _event_id in history:
            if kind != "ARTIFACT_REGISTERED":
                continue
            if (type(payload) is not dict
                    or set(payload) != {"request_id", "artifact_id", "slot", "sha256", "byte_length", "recorded_by_role"}
                    or not isinstance(payload["slot"], str) or payload["slot"] not in _CANONICAL_SLOTS
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
        if set(latest) != _CANONICAL_SLOTS:
            raise CaptureSessionConflict("CAPTURE_SET_INCOMPLETE")
        return latest

    def _verified_manifest(self, actor, session_id, history):
        latest = self._artifact_set(history)
        manifest = build_manifest(
            session_id,
            tuple(ManifestEntry(data["artifact_id"], slot, data["sha256"])
                  for slot, (_actor, data) in latest.items()),
        )
        for entry in manifest.entries:
            record = latest[entry.slot][1]
            original = self.byte_store.get(
                ArtifactKey(actor.tenant_id, UUID(session_id), UUID(entry.artifact_id)),
                expected_sha256=entry.sha256_hex,
            )
            if len(original) != record["byte_length"]:
                raise CaptureSessionConflict("EVIDENCE_BYTE_LENGTH_MISMATCH")
        return manifest

    def record_quality(self, authorization, session_id, *, request_id, results):
        session_id = self._session_id(session_id)
        request_id = self._request_id(request_id)
        if (type(results) is not dict or set(results) != _CANONICAL_SLOTS
                or any(type(value) is not bool for value in results.values())):
            raise ValueError("INVALID_ADVISORY_QUALITY_RESULTS")
        event_id = "quality:" + request_id
        with self.sessions._authorized(authorization) as (conn, actor):
            if actor.actor_role not in ("operator", "supervisor"):
                raise CaptureAuthorizationError("OPERATOR_IDENTITY_REQUIRED")
            _session, history = self._history(conn, actor, session_id, creator_required=True)
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
            self._verified_manifest(actor, session_id, history)
            payload = {"request_id": request_id, "results": results, "advisory_only": True}
            self._append(conn, actor, session_id, history, event_id=event_id,
                         kind="QUALITY_RECORDED", reason="advisory image quality recorded", payload=payload)
        return {"session_id": session_id, "advisory_only": True, "replayed": False}

    def seal_capture(self, authorization, session_id, *, request_id):
        session_id = self._session_id(session_id)
        request_id = self._request_id(request_id)
        event_id = "seal:" + request_id
        with self.sessions._authorized(authorization) as (conn, actor):
            if actor.actor_role not in ("operator", "supervisor"):
                raise CaptureAuthorizationError("OPERATOR_IDENTITY_REQUIRED")
            _session, history = self._history(conn, actor, session_id, creator_required=True)
            if self._consent_state(history) is None:
                raise CaptureSessionConflict("ACTIVE_OWNER_CONSENT_REQUIRED")
            for kind, _who, old, old_id in history:
                if old_id == event_id:
                    if kind == "MANIFEST_SEALED" and type(old) is dict:
                        return {"session_id": session_id, **old, "replayed": True}
                    raise CaptureSessionConflict("IDEMPOTENCY_CONFLICT")
            if not history or history[-1][0] != "QUALITY_RECORDED":
                raise CaptureSessionConflict("QUALITY_REVIEW_REQUIRED_BEFORE_SEAL")
            manifest = self._verified_manifest(actor, session_id, history)
            payload = {
                "schema_version": "0.1",
                "request_id": request_id,
                "manifest_digest": manifest.digest(),
                "shot_list_version": manifest.shot_list_version,
                "artifact_ids": [entry.artifact_id for entry in manifest.entries],
            }
            self._append(conn, actor, session_id, history, event_id=event_id,
                         kind="MANIFEST_SEALED", reason="verified original-byte manifest sealed", payload=payload)
        return {"session_id": session_id, **payload, "replayed": False}

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
            for kind, _who, old, old_id in history:
                if old_id == event_id:
                    if kind == "REVIEW_RECORDED" and type(old) is dict and old.get("disposition") == disposition and old.get("reason") == reason:
                        return {"session_id": session_id, **old, "replayed": True}
                    raise CaptureSessionConflict("IDEMPOTENCY_CONFLICT")
            if not history or history[-1][0] != "MANIFEST_SEALED":
                raise CaptureSessionConflict("SEALED_SESSION_REQUIRED_FOR_REVIEW")
            manifest = self._verified_manifest(actor, session_id, history)
            seal = history[-1][2]
            if seal.get("manifest_digest") != manifest.digest():
                raise CaptureSessionConflict("SEALED_MANIFEST_MISMATCH")
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
                "ORDER BY sequence DESC LIMIT 1) last_event ON last_event.kind='MANIFEST_SEALED' "
                "WHERE s.tenant_id=%s ORDER BY last_event.occurred_at,s.session_id LIMIT %s",
                (actor.tenant_id, limit),
            ).fetchall()
            for (session_id,) in rows:
                session_id = self._session_id(session_id)
                _session, history = self._history(conn, actor, session_id, creator_required=False)
                if not history or history[-1][0] != "MANIFEST_SEALED" or self._consent_state(history) is None:
                    continue
                seal_payload = history[-1][2]
                if (type(seal_payload) is not dict
                        or set(seal_payload) != {"schema_version", "request_id", "manifest_digest", "shot_list_version", "artifact_ids"}
                        or not isinstance(seal_payload.get("manifest_digest"), str)):
                    raise CaptureSessionConflict("UNSUPPORTED_SEAL_HISTORY")
                queued.append({
                    "session_id": session_id,
                    "manifest_digest": seal_payload["manifest_digest"],
                    "shot_list_version": seal_payload["shot_list_version"],
                    "artifact_count": len(seal_payload["artifact_ids"]),
                    "reviewer_must_decide": True,
                })
                if len(queued) == limit:
                    break
        return queued

    def get_review_details(self, authorization, session_id):
        """Return a verified sealed manifest to an independent reviewer."""
        session_id = self._session_id(session_id)
        with self.sessions._authorized(authorization) as (conn, actor):
            if actor.actor_role not in ("reviewer", "supervisor"):
                raise CaptureAuthorizationError("REVIEWER_IDENTITY_REQUIRED")
            session, history = self._history(conn, actor, session_id, creator_required=False)
            if actor.actor_id == session.created_by:
                raise CaptureAuthorizationError("INDEPENDENT_REVIEWER_REQUIRED")
            if self._consent_state(history) is None:
                raise CaptureSessionConflict("ACTIVE_OWNER_CONSENT_REQUIRED")
            if not history or history[-1][0] != "MANIFEST_SEALED":
                raise CaptureSessionConflict("SEALED_SESSION_REQUIRED_FOR_REVIEW")
            manifest = self._verified_manifest(actor, session_id, history)
            latest = self._artifact_set(history)
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

    def retrieve_for_review(self, authorization, session_id, artifact_id):
        session_id = self._session_id(session_id)
        artifact_id = self._request_id(artifact_id)
        with self.sessions._authorized(authorization) as (conn, actor):
            if actor.actor_role not in ("reviewer", "supervisor"):
                raise CaptureAuthorizationError("REVIEWER_IDENTITY_REQUIRED")
            _session, history = self._history(conn, actor, session_id, creator_required=False)
            if actor.actor_id == _session.created_by:
                raise CaptureAuthorizationError("INDEPENDENT_REVIEWER_REQUIRED")
            if self._consent_state(history) is None:
                raise CaptureSessionConflict("ACTIVE_OWNER_CONSENT_REQUIRED")
            if not history or history[-1][0] != "MANIFEST_SEALED":
                raise CaptureSessionConflict("SEALED_SESSION_REQUIRED_FOR_REVIEW")
            manifest = self._verified_manifest(actor, session_id, history)
            entry = next((item for item in manifest.entries if item.artifact_id == artifact_id), None)
            if entry is None:
                raise CaptureSessionConflict("ARTIFACT_NOT_IN_SEALED_MANIFEST")
            return self.byte_store.get(
                ArtifactKey(actor.tenant_id, UUID(session_id), UUID(artifact_id)),
                expected_sha256=entry.sha256_hex,
            )
