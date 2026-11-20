"""Real authenticated HTTP/database persistence coverage for capture safety controls."""
import base64
import hashlib
import os
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from test_capture_sessions_integration import CaptureSessionIntegration


class CapturePauseExceptionHttpIntegration(unittest.TestCase):
    def setUp(self):
        self.db = CaptureSessionIntegration()
        self.db.setUp()
        self.addCleanup(self.db.doCleanups)

    def test_pause_resume_and_exception_resolution_persist_through_http_and_postgres(self):
        from fastapi.testclient import TestClient
        from app.capture_api import CaptureRuntime, create_capture_app
        from app.identity import CredentialResolver
        from app.main import Settings
        from database.capture_sessions import CaptureSessionStore
        from database.claim_cases import ClaimCaseStore

        resolver = CredentialResolver(self.db.credentials)
        store = CaptureSessionStore(resolver, self.db.dsns)
        claim_cases = ClaimCaseStore(store)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "original-evidence"
            root.mkdir(mode=0o700)
            with patch.dict(os.environ, {
                "C2C_ARTIFACT_STORAGE_ROOT": str(root),
                "C2C_VIN_HMAC_PEPPER": "P" * 43,
            }):
                runtime = CaptureRuntime(resolver, store, Settings(), claim_cases)
                with TestClient(create_capture_app(runtime, enable_evidence=True)) as client:
                    operator = {"Authorization": self.db.auth()}
                    owner = {"Authorization": self.db.owner_auth()}
                    claim_id = str(uuid.uuid4())
                    created = client.post("/v1/claim-cases", headers=operator,
                        json={"claim_id": claim_id, "request_id": str(uuid.uuid4())})
                    self.assertEqual(created.status_code, 201, created.text)
                    session_id = created.json()["capture_session_id"]

                    consent = client.post(f"/v1/capture-sessions/{session_id}/consent", headers=owner,
                        json={"request_id": str(uuid.uuid4()), "accepted": True, "scope": "capture_review"})
                    self.assertEqual(consent.status_code, 200, consent.text)
                    vehicle = client.post(f"/v1/capture-sessions/{session_id}/vehicle-reference", headers=operator,
                        json={"request_id": str(uuid.uuid4()), "vin": "1HGCM82633A004352"})
                    self.assertEqual(vehicle.status_code, 200, vehicle.text)

                    pause_id = str(uuid.uuid4())
                    pause_body = {"request_id": pause_id, "reason": "synthetic safety stop"}
                    paused = client.post(f"/v1/capture-sessions/{session_id}/pause", headers=operator, json=pause_body)
                    self.assertEqual(paused.status_code, 200, paused.text)
                    self.assertTrue(paused.json()["paused"])
                    pause_retry = client.post(f"/v1/capture-sessions/{session_id}/pause", headers=operator, json=pause_body)
                    self.assertEqual(pause_retry.status_code, 200, pause_retry.text)
                    self.assertTrue(pause_retry.json()["replayed"])

                    readiness = client.get(f"/v1/capture-sessions/{session_id}/evidence-readiness", headers=operator)
                    self.assertEqual(readiness.status_code, 200, readiness.text)
                    self.assertTrue(readiness.json()["capture_paused"])
                    raw = b"synthetic-pause-blocked-original"
                    artifact_id = str(uuid.uuid4())
                    blocked = client.post(f"/v1/capture-sessions/{session_id}/artifacts", headers=operator,
                        json={"request_id": str(uuid.uuid4()), "artifact_id": artifact_id,
                              "slot": "00_front_exterior", "payload_base64": base64.b64encode(raw).decode(),
                              "sha256": hashlib.sha256(raw).hexdigest()})
                    self.assertEqual(blocked.status_code, 409, blocked.text)
                    self.assertEqual(blocked.json()["detail"], "CAPTURE_SESSION_CONFLICT", "HTTP intentionally sanitizes internal capture conflict details")

                    resumed = client.post(f"/v1/capture-sessions/{session_id}/resume", headers=operator,
                        json={"request_id": str(uuid.uuid4()), "reason": "synthetic safety stop cleared"})
                    self.assertEqual(resumed.status_code, 200, resumed.text)
                    self.assertFalse(resumed.json()["paused"])
                    readiness = client.get(f"/v1/capture-sessions/{session_id}/evidence-readiness", headers=operator)
                    self.assertFalse(readiness.json()["capture_paused"])
                    uploaded = client.post(f"/v1/capture-sessions/{session_id}/artifacts", headers=operator,
                        json={"request_id": str(uuid.uuid4()), "artifact_id": artifact_id,
                              "slot": "00_front_exterior", "payload_base64": base64.b64encode(raw).decode(),
                              "sha256": hashlib.sha256(raw).hexdigest()})
                    self.assertEqual(uploaded.status_code, 200, uploaded.text)
                    self.assertEqual(uploaded.json()["artifact_id"], artifact_id)

                    opened = client.post(f"/v1/capture-sessions/{session_id}/exceptions", headers=operator,
                        json={"request_id": str(uuid.uuid4()), "slot": "01_front_right_exterior",
                              "reason_code": "WEATHER_HAZARD", "explanation": "synthetic weather condition"})
                    self.assertEqual(opened.status_code, 200, opened.text)
                    readiness = client.get(f"/v1/capture-sessions/{session_id}/evidence-readiness", headers=operator)
                    self.assertEqual([item["slot"] for item in readiness.json()["active_capture_exceptions"]],
                                     ["01_front_right_exterior"])
                    retry_without_artifact = client.post(f"/v1/capture-sessions/{session_id}/exceptions/resolve", headers=operator,
                        json={"request_id": str(uuid.uuid4()), "slot": "01_front_right_exterior",
                              "resolution_code": "CAPTURED_AFTER_RETRY", "explanation": "synthetic retry without artifact"})
                    self.assertEqual(retry_without_artifact.status_code, 409, retry_without_artifact.text)

                    resolved = client.post(f"/v1/capture-sessions/{session_id}/exceptions/resolve", headers=operator,
                        json={"request_id": str(uuid.uuid4()), "slot": "01_front_right_exterior",
                              "resolution_code": "NO_LONGER_APPLICABLE", "explanation": "synthetic exception resolved"})
                    self.assertEqual(resolved.status_code, 200, resolved.text)
                    readiness = client.get(f"/v1/capture-sessions/{session_id}/evidence-readiness", headers=operator)
                    self.assertEqual(readiness.json()["active_capture_exceptions"], [])

                    events = self.db.f.seed.execute(
                        "SELECT kind,event_id,payload_json FROM faos.events WHERE tenant_id=%s AND session_id=%s ORDER BY sequence",
                        (self.db.f.tenants[0], session_id)).fetchall()
                    kinds = [row[0] for row in events]
                    self.assertEqual(kinds.count("CAPTURE_SESSION_PAUSED"), 1, kinds)
                    self.assertEqual(kinds.count("CAPTURE_SESSION_RESUMED"), 1, kinds)
                    self.assertEqual(kinds.count("CAPTURE_EXCEPTION_RECORDED"), 1, kinds)
                    self.assertEqual(kinds.count("CAPTURE_EXCEPTION_RESOLVED"), 1, kinds)
                    self.assertEqual(kinds.count("ARTIFACT_REGISTERED"), 1, kinds)
                    original_path = root / self.db.f.tenants[0] / session_id / (artifact_id + ".original")
                    self.assertTrue(original_path.exists(), "accepted original bytes persist in the evidence root")
                    self.assertTrue(any('"reason":"synthetic safety stop"' in row[2] for row in events))
                    self.assertTrue(any('"reason_code":"WEATHER_HAZARD"' in row[2] for row in events))


if __name__ == "__main__":
    unittest.main()
