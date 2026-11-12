"""Database-event contract tests for consent and HMAC vehicle references."""
from contextlib import contextmanager
from dataclasses import dataclass
import base64
import hashlib
from pathlib import Path
import json
import tempfile
import unittest
from uuid import UUID

from app.artifact_storage import OriginalByteStore
from app.evidence_manifest import LEGACY_CANONICAL_SLOTS as CANONICAL_SLOTS
from app.capture_protocols import DEFAULT_CAPTURE_PROTOCOL, LEGACY_CAPTURE_PROTOCOL, resolve_capture_protocol
from database.capture_evidence import CaptureEvidenceService
from database.capture_sessions import (
    CaptureAuthorizationError, CaptureSession, CaptureSessionConflict, CaptureSessionStore,
)


@dataclass(frozen=True)
class Actor:
    actor_id: str
    tenant_id: UUID
    actor_role: str


class Result:
    def __init__(self, one=None, many=None):
        self.one, self.many = one, many
    def fetchone(self): return self.one
    def fetchall(self): return self.many


class FakeConnection:
    def __init__(self, protocol_version=LEGACY_CAPTURE_PROTOCOL):
        payload = {"synthetic": True} if protocol_version == LEGACY_CAPTURE_PROTOCOL else {
            "capture_protocol_version": protocol_version, "synthetic": True,
        }
        self.rows = [(1, "SESSION_CREATED", "operator-1", json.dumps(payload), "capture-created")]
        self.appended = []
        self.owner_bindings = {}

    def execute(self, sql, args=()):
        if "faos.bind_claim_case_owner" in sql:
            _tenant, session, owner = args
            current = self.owner_bindings.get(session)
            if current is None:
                self.owner_bindings[session] = owner
                return Result(one=("BOUND",))
            return Result(one=("BOUND" if current == owner else "CONFLICT",))
        if "SELECT s.session_id FROM faos.sessions" in sql:
            return Result(many=[(str(UUID(int=2)),)])
        if "SELECT sequence,kind,actor,payload_json,event_id" in sql:
            return Result(many=list(self.rows))
        if "faos.append_event" in sql:
            tenant, session, event_id, sequence, kind, actor, when, reason, payload, version = args
            self.rows.append((sequence, kind, actor, payload, event_id))
            self.appended.append((kind, actor, json.loads(payload)))
            return Result(one=("ACCEPTED",))
        return Result(one=(None,))


class FakeSessions(CaptureSessionStore):
    def __init__(self, creator, protocol_version=LEGACY_CAPTURE_PROTOCOL):
        self.protocol_version = protocol_version
        self.conn = FakeConnection(protocol_version)
        self.creator = creator
        self.actors = {}
        self.scope = 'controlled-test'
        self.claim_id = None

    @contextmanager
    def _authorized(self, authorization):
        yield self.conn, self.actors[authorization]

    def _read(self, conn, actor, session_id, created=False):
        return CaptureSession(session_id, str(actor.tenant_id), self.creator,
                              "2026-11-08T00:00:00+00:00", created, self.scope,
                              self.claim_id, self.conn.owner_bindings.get(session_id), self.protocol_version)


class RecordingByteStore(OriginalByteStore):
    def __init__(self, root):
        super().__init__(root)
        self.originals = {}

    def put(self, key, data, *, expected_sha256):
        self.asserted = hashlib.sha256(data).hexdigest() == expected_sha256
        old = self.originals.setdefault(key, data)
        if old != data:
            raise ValueError("ARTIFACT_ALREADY_EXISTS_WITH_DIFFERENT_BYTES")
        return type("Receipt", (), {"created": old == data})()

    def get(self, key, *, expected_sha256):
        data = self.originals[key]
        if hashlib.sha256(data).hexdigest() != expected_sha256:
            raise ValueError("ARTIFACT_HASH_MISMATCH")
        return data

    def delete(self, key):
        return self.originals.pop(key, None) is not None


class CaptureEvidenceServiceTests(unittest.TestCase):
    def setUp(self):
        self.session_id = str(UUID(int=2))
        self.tenant = UUID(int=1)
        self.operator = Actor("operator-1", self.tenant, "operator")
        self.owner = Actor("owner-1", self.tenant, "owner")
        self.reviewer = Actor("reviewer-1", self.tenant, "reviewer")
        self.sessions = FakeSessions(self.operator.actor_id)
        self.sessions.actors = {
            "operator-token": self.operator, "owner-token": self.owner,
            "reviewer-token": self.reviewer,
        }
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        # This suite does not write the byte store; POSIX byte publication has
        # dedicated Linux integration coverage in the repository.
        self.byte_store = RecordingByteStore(Path(temp.name).resolve())
        self.service = CaptureEvidenceService(self.sessions, self.byte_store, "p" * 43)

    def test_owner_consent_and_keyed_vin_reference_never_store_raw_vin(self):
        self.service.record_consent(
            "owner-token", self.session_id, request_id=UUID(int=3),
            accepted=True, scope="capture_review",
        )
        vin = "1HGCM82633A004352"
        result = self.service.record_vehicle(
            "operator-token", self.session_id, request_id=UUID(int=4), vin=vin,
        )
        self.assertEqual(len(result["vin_hmac_sha256"]), 64)
        self.assertNotIn(vin, json.dumps(self.sessions.conn.appended))
        self.assertEqual([event[0] for event in self.sessions.conn.appended],
                         ["CONSENT_RECORDED", "VEHICLE_RECORDED"])

    def test_persistent_claim_consent_binds_one_owner_identity(self):
        self.sessions.scope = "persistent-claim-case"
        self.sessions.claim_id = str(UUID(int=77))
        self.sessions.actors["other-owner-token"] = Actor("owner-2", self.tenant, "owner")
        self.service.record_consent(
            "owner-token", self.session_id, request_id=UUID(int=78),
            accepted=True, scope="capture_review",
        )
        self.assertEqual(self.sessions.conn.owner_bindings[self.session_id], "owner-1")
        with self.assertRaisesRegex(CaptureAuthorizationError, "CLAIM_CASE_OWNER_BINDING_DENIED"):
            self.service.record_consent(
                "other-owner-token", self.session_id, request_id=UUID(int=79),
                accepted=True, scope="capture_review",
            )
        self.assertEqual(len([event for event in self.sessions.conn.appended if event[0] == "CONSENT_RECORDED"]), 1)

    def test_declined_or_withdrawn_consent_blocks_vehicle_recording(self):
        self.service.record_consent(
            "owner-token", self.session_id, request_id=UUID(int=5),
            accepted=False, scope="capture_review",
        )
        with self.assertRaisesRegex(CaptureSessionConflict, "ACTIVE_OWNER_CONSENT_REQUIRED"):
            self.service.record_vehicle(
                "operator-token", self.session_id, request_id=UUID(int=6), vin="1HGCM82633A004352",
            )

    def test_evidence_readiness_tracks_active_consent_and_vehicle_reference(self):
        initial = self.service.evidence_readiness("operator-token", self.session_id)
        self.assertFalse(initial["consent_active"])
        self.assertFalse(initial["vehicle_reference_present"])
        self.assertFalse(initial["capture_allowed"])

        self.service.record_consent(
            "owner-token", self.session_id, request_id=UUID(int=80),
            accepted=True, scope="capture_review",
        )
        consented = self.service.evidence_readiness("operator-token", self.session_id)
        self.assertTrue(consented["consent_active"])
        self.assertFalse(consented["vehicle_reference_present"])
        self.assertFalse(consented["capture_allowed"])

        self.service.record_vehicle(
            "operator-token", self.session_id, request_id=UUID(int=81), vin="1HGCM82633A004352",
        )
        ready = self.service.evidence_readiness("operator-token", self.session_id)
        self.assertTrue(ready["capture_allowed"])

        self.service.record_consent(
            "owner-token", self.session_id, request_id=UUID(int=82),
            accepted=False, scope="capture_review",
        )
        withdrawn = self.service.evidence_readiness("operator-token", self.session_id)
        self.assertFalse(withdrawn["consent_active"])
        self.assertFalse(withdrawn["capture_allowed"])

    def test_evidence_readiness_requires_creator_operator_or_supervisor(self):
        self.sessions.actors["other-operator-token"] = Actor("operator-2", self.tenant, "operator")
        with self.assertRaisesRegex(CaptureAuthorizationError, "CAPTURE_AUTHORITY_DENIED"):
            self.service.evidence_readiness("other-operator-token", self.session_id)
        with self.assertRaisesRegex(CaptureAuthorizationError, "OPERATOR_IDENTITY_REQUIRED"):
            self.service.evidence_readiness("reviewer-token", self.session_id)

    def test_only_owner_role_can_record_consent_and_only_operator_can_record_vehicle(self):
        with self.assertRaisesRegex(CaptureAuthorizationError, "OWNER_IDENTITY_REQUIRED"):
            self.service.record_consent(
                "operator-token", self.session_id, request_id=UUID(int=7),
                accepted=True, scope="capture_review",
            )
        self.service.record_consent(
            "owner-token", self.session_id, request_id=UUID(int=8),
            accepted=True, scope="capture_review",
        )
        with self.assertRaisesRegex(CaptureAuthorizationError, "OPERATOR_IDENTITY_REQUIRED"):
            self.service.record_vehicle(
                "owner-token", self.session_id, request_id=UUID(int=9), vin="1HGCM82633A004352",
            )

    def test_original_bytes_are_registered_only_under_active_consent(self):
        self.service.record_consent(
            "owner-token", self.session_id, request_id=UUID(int=10),
            accepted=True, scope="capture_review",
        )
        original = b"synthetic-original-image-bytes"
        digest = hashlib.sha256(original).hexdigest()
        encoded = base64.b64encode(original).decode("ascii")
        with self.assertRaisesRegex(CaptureSessionConflict, "VEHICLE_REFERENCE_REQUIRED"):
            self.service.register_artifact(
                "operator-token", self.session_id, request_id=UUID(int=11),
                artifact_id=UUID(int=12), slot="front", payload_base64=encoded, sha256_hex=digest,
            )
        self.service.record_vehicle(
            "operator-token", self.session_id, request_id=UUID(int=16), vin="1HGCM82633A004352",
        )
        result = self.service.register_artifact(
            "operator-token", self.session_id, request_id=UUID(int=11),
            artifact_id=UUID(int=12), slot="front", payload_base64=encoded, sha256_hex=digest,
        )
        key = next(iter(self.byte_store.originals))
        self.assertEqual(self.byte_store.originals[key], original)
        self.assertTrue(self.byte_store.asserted)
        self.assertEqual(result["sha256"], digest)
        self.assertNotIn(encoded, json.dumps(self.sessions.conn.appended))

        self.service.record_consent(
            "owner-token", self.session_id, request_id=UUID(int=13),
            accepted=False, scope="capture_review",
        )
        self.assertEqual(len(self.byte_store.originals), 0)
        with self.assertRaisesRegex(CaptureSessionConflict, "ACTIVE_OWNER_CONSENT_REQUIRED"):
            self.service.register_artifact(
                "operator-token", self.session_id, request_id=UUID(int=14),
                artifact_id=UUID(int=15), slot="front_left", payload_base64=encoded,
                sha256_hex=digest,
            )
        self.assertEqual(len(self.byte_store.originals), 0)

    def test_quality_is_advisory_then_integrity_seal_and_human_review(self):
        self.service.record_consent(
            "owner-token", self.session_id, request_id=UUID(int=30),
            accepted=True, scope="capture_review",
        )
        self.service.record_vehicle(
            "operator-token", self.session_id, request_id=UUID(int=31), vin="1HGCM82633A004352",
        )
        for index, slot in enumerate(CANONICAL_SLOTS, start=1):
            original = ("synthetic-image:" + slot).encode("ascii")
            self.service.register_artifact(
                "operator-token", self.session_id,
                request_id=UUID(int=100 + index), artifact_id=UUID(int=200 + index),
                slot=slot, payload_base64=base64.b64encode(original).decode("ascii"),
                sha256_hex=hashlib.sha256(original).hexdigest(),
            )
        quality = {slot: slot != "front" for slot in CANONICAL_SLOTS}
        self.assertTrue(self.service.record_quality(
            "operator-token", self.session_id, request_id=UUID(int=32), results=quality,
        )["advisory_only"])
        sealed = self.service.seal_capture(
            "operator-token", self.session_id, request_id=UUID(int=33),
        )
        self.assertEqual(len(sealed["manifest_digest"]), 64)
        queue = self.service.list_review_queue("reviewer-token")
        self.assertEqual(queue[0]["session_id"], self.session_id)
        self.assertEqual(len(queue[0]["artifacts"]), len(CANONICAL_SLOTS))
        details = self.service.get_review_details("reviewer-token", self.session_id)
        self.assertEqual(details["session_id"], self.session_id)
        self.assertEqual(details["manifest_digest"], sealed["manifest_digest"])
        self.assertEqual(len(details["artifacts"]), len(CANONICAL_SLOTS))
        self.assertEqual(
            {item["slot"] for item in details["artifacts"]}, set(CANONICAL_SLOTS)
        )
        self.assertNotIn("1HGCM82633A004352", json.dumps(details))

        first_slot = CANONICAL_SLOTS[0]
        first_artifact = UUID(int=201)
        self.assertEqual(queue[0]["artifacts"][0]["artifact_id"], str(first_artifact))
        self.assertEqual(queue[0]["artifacts"][0]["slot"], first_slot)
        self.assertEqual(queue[0]["artifacts"][0]["byte_length"], len(("synthetic-image:" + first_slot).encode("ascii")))
        expected_bytes = ("synthetic-image:" + first_slot).encode("ascii")
        self.assertEqual(
            self.service.retrieve_for_review("reviewer-token", self.session_id, first_artifact),
            expected_bytes,
        )
        with self.assertRaisesRegex(CaptureAuthorizationError, "REVIEWER_IDENTITY_REQUIRED"):
            self.service.retrieve_for_review("operator-token", self.session_id, first_artifact)
        review = self.service.record_review(
            "reviewer-token", self.session_id, request_id=UUID(int=34),
            disposition="HUMAN_QC_REQUIRED", reason="Reviewer requests shop confirmation.",
        )
        self.assertEqual(review["manifest_digest"], sealed["manifest_digest"])
        self.assertEqual(self.sessions.conn.appended[-1][1], "reviewer-1")


    def test_16_v1_persistent_evidence_lifecycle_uses_exact_session_slots(self):
        sessions = FakeSessions(self.operator.actor_id, DEFAULT_CAPTURE_PROTOCOL)
        sessions.actors = self.sessions.actors
        service = CaptureEvidenceService(sessions, self.byte_store, "p" * 43)
        readiness = service.evidence_readiness("operator-token", self.session_id)
        self.assertEqual(readiness["capture_protocol_version"], DEFAULT_CAPTURE_PROTOCOL)
        self.assertEqual(readiness["capture_protocol_status"], "implemented")
        self.assertFalse(readiness["capture_allowed"])
        service.record_consent("owner-token", self.session_id, request_id=UUID(int=430),
                               accepted=True, scope="capture_review")
        service.record_vehicle("operator-token", self.session_id, request_id=UUID(int=431),
                               vin="1HGCM82633A004352")
        slots = resolve_capture_protocol(DEFAULT_CAPTURE_PROTOCOL).slots
        for index, slot in enumerate(slots, start=1):
            original = ("synthetic-16-v1:" + slot).encode("ascii")
            service.register_artifact(
                "operator-token", self.session_id, request_id=UUID(int=500 + index),
                artifact_id=UUID(int=600 + index), slot=slot,
                payload_base64=base64.b64encode(original).decode("ascii"),
                sha256_hex=hashlib.sha256(original).hexdigest(),
            )
        self.assertTrue(service.record_quality(
            "operator-token", self.session_id, request_id=UUID(int=432),
            results={slot: True for slot in slots},
        )["advisory_only"])
        sealed = service.seal_capture("operator-token", self.session_id, request_id=UUID(int=433))
        self.assertEqual(sealed["shot_list_version"], DEFAULT_CAPTURE_PROTOCOL)
        self.assertEqual(len(sealed["artifact_ids"]), 16)
        queue = service.list_review_queue("reviewer-token")
        self.assertEqual(queue[0]["shot_list_version"], DEFAULT_CAPTURE_PROTOCOL)
        self.assertEqual(len(queue[0]["artifacts"]), 16)
        details = service.get_review_details("reviewer-token", self.session_id)
        self.assertEqual(details["shot_list_version"], DEFAULT_CAPTURE_PROTOCOL)
        self.assertEqual(len(details["artifacts"]), 16)
        self.assertEqual({item["slot"] for item in details["artifacts"]}, set(slots))

if __name__ == "__main__":
    unittest.main()
