"""Authenticated HTTP-to-PostgreSQL-to-original-bytes acceptance journey.

Uses synthetic records and the disposable PostgreSQL authority fixture. This
proves the integrated capture API boundary, not real-device or production
hosting acceptance.
"""
import base64
import hashlib
import os
import tempfile
import time
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from test_capture_sessions_integration import CaptureSessionIntegration


class CaptureHttpIntegration(unittest.TestCase):
    def setUp(self):
        self.db = CaptureSessionIntegration()
        self.db.setUp()
        self.addCleanup(self.db.doCleanups)

    def test_authenticated_http_capture_survives_runtime_restart_and_fails_closed(self):
        try:
            from fastapi.testclient import TestClient
            from app.capture_api import CaptureRuntime, create_capture_app
            from app.identity import ActorBinding, Credential, CredentialResolver
            from app.main import Settings
            from app.artifact_storage import ArtifactKey
            from database.capture_sessions import CaptureSessionStore
            from database.claim_cases import ClaimCaseStore
            from app.evidence_manifest import CANONICAL_SLOTS
        except ModuleNotFoundError as error:
            self.skipTest(f"HTTP integration dependencies unavailable in this test lane: {error.name}")

        cross_tenant_reviewer_token = "G" * 43
        credentials = [
            *self.db.credentials,
            Credential(
                hashlib.sha256(cross_tenant_reviewer_token.encode()).hexdigest(),
                ActorBinding(
                    "cross-tenant-reviewer",
                    uuid.UUID(self.db.f.tenants[1]),
                    self.db.f.roles[1],
                    "reviewer",
                ),
                int(time.time()) + 3600,
            ),
        ]
        resolver = CredentialResolver(credentials)
        store = CaptureSessionStore(resolver, self.db.dsns)
        claim_cases = ClaimCaseStore(store)

        with tempfile.TemporaryDirectory() as directory:
            storage_root = Path(directory) / "original-evidence"
            storage_root.mkdir(mode=0o700)
            environment = {
                "C2C_ARTIFACT_STORAGE_ROOT": str(storage_root),
                "C2C_VIN_HMAC_PEPPER": "P" * 43,
            }
            runtime = CaptureRuntime(resolver, store, Settings(), claim_cases)
            with patch.dict(os.environ, environment, clear=False):
                with TestClient(create_capture_app(runtime, enable_evidence=True)) as client:
                    claim_id = str(uuid.uuid4())
                    created = client.post(
                        "/v1/claim-cases",
                        headers={"Authorization": self.db.auth()},
                        json={"claim_id": claim_id, "request_id": str(uuid.uuid4())},
                    )
                    self.assertEqual(created.status_code, 201, created.text)
                    session_id = created.json()["capture_session_id"]

                    owner_headers = {"Authorization": self.db.owner_auth()}
                    operator_headers = {"Authorization": self.db.auth()}

                    consent = client.post(
                        f"/v1/capture-sessions/{session_id}/consent",
                        headers=owner_headers,
                        json={"request_id": str(uuid.uuid4()), "accepted": True, "scope": "capture_review"},
                    )
                    self.assertEqual(consent.status_code, 200, consent.text)

                    vehicle = client.post(
                        f"/v1/capture-sessions/{session_id}/vehicle-reference",
                        headers=operator_headers,
                        json={"request_id": str(uuid.uuid4()), "vin": "1HGCM82633A004352"},
                    )
                    self.assertEqual(vehicle.status_code, 200, vehicle.text)

                    originals = {}
                    for slot in CANONICAL_SLOTS:
                        raw = ("synthetic-http-original:" + slot).encode("ascii")
                        artifact_id = str(uuid.uuid4())
                        originals[artifact_id] = raw
                        uploaded = client.post(
                            f"/v1/capture-sessions/{session_id}/artifacts",
                            headers=operator_headers,
                            json={
                                "request_id": str(uuid.uuid4()),
                                "artifact_id": artifact_id,
                                "slot": slot,
                                "payload_base64": base64.b64encode(raw).decode("ascii"),
                                "sha256": hashlib.sha256(raw).hexdigest(),
                            },
                        )
                        self.assertEqual(uploaded.status_code, 200, f"{slot}: {uploaded.text}")

                    quality = client.post(
                        f"/v1/capture-sessions/{session_id}/quality",
                        headers=operator_headers,
                        json={"request_id": str(uuid.uuid4()), "results": {slot: True for slot in CANONICAL_SLOTS}},
                    )
                    self.assertEqual(quality.status_code, 200, quality.text)
                    sealed = client.post(
                        f"/v1/capture-sessions/{session_id}/seal",
                        headers=operator_headers,
                        json={"request_id": str(uuid.uuid4())},
                    )
                    self.assertEqual(sealed.status_code, 200, sealed.text)
                    manifest_digest = sealed.json()["manifest_digest"]

                    cross_tenant = client.get(
                        f"/v1/review-sessions/{session_id}",
                        headers={"Authorization": f"Bearer {cross_tenant_reviewer_token}"},
                    )
                    self.assertEqual(cross_tenant.status_code, 404)

                # Rebuild runtime and database service objects, retaining only
                # PostgreSQL rows and the provisioned evidence directory.
                restarted_store = CaptureSessionStore(resolver, self.db.dsns)
                restarted_runtime = CaptureRuntime(
                    resolver,
                    restarted_store,
                    Settings(),
                    ClaimCaseStore(restarted_store),
                )
                with TestClient(create_capture_app(restarted_runtime, enable_evidence=True)) as restarted:
                    details = restarted.get(
                        f"/v1/review-sessions/{session_id}",
                        headers={"Authorization": self.db.reviewer_auth()},
                    )
                    self.assertEqual(details.status_code, 200, details.text)
                    self.assertEqual(details.json()["manifest_digest"], manifest_digest)
                    self.assertEqual(len(details.json()["artifacts"]), len(CANONICAL_SLOTS))

                    first_artifact_id, first_bytes = next(iter(originals.items()))
                    retrieved = restarted.get(
                        f"/v1/review-sessions/{session_id}/artifacts/{first_artifact_id}",
                        headers={"Authorization": self.db.reviewer_auth()},
                    )
                    self.assertEqual(retrieved.status_code, 200, retrieved.text)
                    self.assertEqual(retrieved.content, first_bytes)

                    # Corrupt one stored original outside the application; the
                    # reviewer API must detect it instead of returning bytes.
                    key = ArtifactKey(
                        uuid.UUID(self.db.f.tenants[0]),
                        uuid.UUID(session_id),
                        uuid.UUID(first_artifact_id),
                    )
                    stored_path = storage_root / str(key.tenant_id) / str(key.session_id) / (str(key.artifact_id) + ".original")
                    stored_path.write_bytes(b"tampered synthetic bytes")
                    tampered = restarted.get(
                        f"/v1/review-sessions/{session_id}",
                        headers={"Authorization": self.db.reviewer_auth()},
                    )
                    self.assertEqual(tampered.status_code, 409)
                    self.assertEqual(tampered.json(), {"detail": "EVIDENCE_ARTIFACT_CONFLICT"})

                    withdrawn = restarted.post(
                        f"/v1/capture-sessions/{session_id}/consent",
                        headers={"Authorization": self.db.owner_auth()},
                        json={"request_id": str(uuid.uuid4()), "accepted": False, "scope": "capture_review"},
                    )
                    self.assertEqual(withdrawn.status_code, 200, withdrawn.text)
                    self.assertFalse(stored_path.exists())
                    after_withdrawal = restarted.get(
                        f"/v1/review-sessions/{session_id}",
                        headers={"Authorization": self.db.reviewer_auth()},
                    )
                    self.assertEqual(after_withdrawal.status_code, 409)
                    self.assertEqual(after_withdrawal.json(), {"detail": "CAPTURE_SESSION_CONFLICT"})


if __name__ == "__main__":
    unittest.main()
