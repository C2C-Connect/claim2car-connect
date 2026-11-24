"""Authenticated HTTP-to-PostgreSQL-to-original-bytes acceptance journey.

Uses synthetic records and the disposable PostgreSQL authority fixture. This
proves the integrated capture API boundary, not real-device or production
hosting acceptance.
"""
import base64
import hashlib
import json
import os
import tempfile
import time
import unittest
import uuid
from io import BytesIO
from pathlib import Path

from PIL import Image
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
            from app.capture_protocols import DEFAULT_CAPTURE_PROTOCOL
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
                    collision_id = str(uuid.uuid4())
                    collision_created = client.post(
                        "/v1/collisions",
                        headers={"Authorization": self.db.auth()},
                        json={"collision_id": collision_id, "request_id": str(uuid.uuid4())},
                    )
                    self.assertEqual(collision_created.status_code, 201, collision_created.text)

                    claim_id = str(uuid.uuid4())
                    created = client.post(
                        "/v1/claim-cases",
                        headers={"Authorization": self.db.auth()},
                        json={"claim_id": claim_id, "request_id": str(uuid.uuid4())},
                    )
                    self.assertEqual(created.status_code, 201, created.text)
                    session_id = created.json()["capture_session_id"]
                    linked = client.post(
                        f"/v1/collisions/{collision_id}/claims",
                        headers={"Authorization": self.db.auth()},
                        json={"claim_id": claim_id, "request_id": str(uuid.uuid4())},
                    )
                    self.assertEqual(linked.status_code, 201, linked.text)
                    collision_view = client.get(
                        f"/v1/collisions/{collision_id}",
                        headers={"Authorization": self.db.auth()},
                    )
                    self.assertEqual(collision_view.status_code, 200, collision_view.text)
                    self.assertEqual(collision_view.json()["claims"][0]["capture_session_id"], session_id)
                    self.assertEqual(collision_view.json()["claims"][0]["claim_id"], claim_id)

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

                    vehicle_id = str(uuid.uuid4())
                    collision_vehicle = client.post(
                        f"/v1/collisions/{collision_id}/vehicles",
                        headers=operator_headers,
                        json={
                            "claim_id": claim_id,
                            "vehicle_id": vehicle_id,
                            "request_id": str(uuid.uuid4()),
                            "relationship": "INVOLVED",
                        },
                    )
                    self.assertEqual(collision_vehicle.status_code, 201, collision_vehicle.text)
                    self.assertEqual(collision_vehicle.json()["vehicle_id"], vehicle_id)
                    self.assertEqual(collision_vehicle.json()["vin_source"], "CONSENTED_CAPTURE_SESSION")
                    self.assertEqual(collision_vehicle.json()["source_consent_status"], "ACTIVE")
                    self.assertNotIn("vin_hmac_sha256", collision_vehicle.json())

                    from app.vehicle_intelligence.vpic import VpicClient
                    provider_row = {
                        "VIN": "1HGCM82633A004352", "ErrorCode": "0", "SuggestedVIN": "",
                        "Make": "HONDA", "Model": "Accord", "ModelYear": "2003",
                        "Trim": "EX", "BodyClass": "Sedan", "VehicleType": "PASSENGER CAR",
                        "CurbWeightLB": "", "GVWR": "CLASS 1",
                    }
                    provider_calls = []
                    fake_decoder = VpicClient(fetcher=lambda *args: (
                        provider_calls.append(args) or (
                            200, "application/json",
                            json.dumps({"Count": 1, "Results": [provider_row]}).encode(),
                        )
                    ))
                    with patch("app.capture_api._vpic_client", fake_decoder):
                        blocked_decode = client.post(
                            f"/v1/capture-sessions/{session_id}/vehicle-profile",
                            headers=operator_headers,
                            json={"request_id": str(uuid.uuid4()), "vin": "1HGCM82633A004352"},
                        )
                    self.assertEqual(blocked_decode.status_code, 403, blocked_decode.text)
                    self.assertEqual(provider_calls, [])
                    disclosure = client.get(
                        "/v1/vehicle-decode-disclosure",
                        headers=owner_headers,
                    )
                    self.assertEqual(disclosure.status_code, 200, disclosure.text)
                    self.assertEqual(disclosure.json()["disclosure_version"], "vehicle-decode-disclosure-v1")
                    self.assertTrue(any("NHTSA vPIC" in item for item in disclosure.json()["sections"]))
                    stale_disclosure = client.post(
                        f"/v1/capture-sessions/{session_id}/vehicle-decode-consent",
                        headers=owner_headers,
                        json={
                            "request_id": str(uuid.uuid4()),
                            "accepted": True,
                            "scope": "nhtsa_vpic_decode",
                            "disclosure_version": "vehicle-decode-disclosure-old",
                        },
                    )
                    self.assertEqual(stale_disclosure.status_code, 422, stale_disclosure.text)

                    decode_consent = client.post(
                        f"/v1/capture-sessions/{session_id}/vehicle-decode-consent",
                        headers=owner_headers,
                        json={
                            "request_id": str(uuid.uuid4()),
                            "accepted": True,
                            "scope": "nhtsa_vpic_decode",
                            "disclosure_version": "vehicle-decode-disclosure-v1",
                        },
                    )
                    self.assertEqual(decode_consent.status_code, 200, decode_consent.text)
                    profile_request_id = str(uuid.uuid4())
                    with patch("app.capture_api._vpic_client", fake_decoder):
                        decoded = client.post(
                            f"/v1/capture-sessions/{session_id}/vehicle-profile",
                            headers=operator_headers,
                            json={"request_id": profile_request_id, "vin": "1HGCM82633A004352"},
                        )
                        decoded_retry = client.post(
                            f"/v1/capture-sessions/{session_id}/vehicle-profile",
                            headers=operator_headers,
                            json={"request_id": profile_request_id, "vin": "1HGCM82633A004352"},
                        )
                    self.assertEqual(decoded.status_code, 200, decoded.text)
                    self.assertEqual(decoded_retry.status_code, 200, decoded_retry.text)
                    self.assertTrue(decoded_retry.json()["replayed"])
                    self.assertEqual(decoded.json()["status"], "DECODED")
                    self.assertEqual(decoded.json()["provider"], "NHTSA_VPIC")
                    self.assertEqual(decoded.json()["attributes"]["make"]["value"], "HONDA")
                    self.assertEqual(decoded.json()["attributes"]["model_year"]["value"], 2003)
                    self.assertEqual(decoded.json()["physics_input_eligibility"], "NOT_ESTABLISHED")
                    self.assertNotIn("vin", decoded.json())
                    self.assertNotIn("vin_hmac_sha256", decoded.json())
                    self.assertEqual(len(provider_calls), 1)
                    persisted_profile = self.db.f.seed.execute(
                        "SELECT provider,decode_status,response_sha256,attributes_json::text "
                        "FROM faos.vehicle_decode_snapshots WHERE tenant_id=%s AND source_session_id=%s",
                        (self.db.f.tenants[0], session_id),
                    ).fetchone()
                    self.assertEqual(persisted_profile[0:2], ("NHTSA_VPIC", "DECODED"))
                    self.assertEqual(len(persisted_profile[2]), 64)
                    self.assertNotIn("1HGCM82633A004352", persisted_profile[3])
                    self.assertNotIn("rawResult", persisted_profile[3])

                    collision_view_with_vehicle = client.get(
                        f"/v1/collisions/{collision_id}",
                        headers=operator_headers,
                    )
                    self.assertEqual(collision_view_with_vehicle.status_code, 200, collision_view_with_vehicle.text)
                    self.assertEqual(collision_view_with_vehicle.json()["vehicles"][0]["vehicle_id"], vehicle_id)
                    self.assertEqual(collision_view_with_vehicle.json()["vehicles"][0]["source_consent_status"], "ACTIVE")

                    originals = {}
                    for slot in CANONICAL_SLOTS:
                        if slot == CANONICAL_SLOTS[0]:
                            image_buffer = BytesIO()
                            Image.new("RGB", (320, 240), "silver").save(image_buffer, format="JPEG")
                            raw = image_buffer.getvalue()
                        else:
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
                    seal_request_id = str(uuid.uuid4())
                    sealed = client.post(
                        f"/v1/capture-sessions/{session_id}/seal",
                        headers=operator_headers,
                        json={"request_id": seal_request_id},
                    )
                    self.assertEqual(sealed.status_code, 200, sealed.text)
                    self.assertTrue(sealed.json()["root_registered"])
                    manifest_digest = sealed.json()["manifest_digest"]
                    seal_retry = client.post(
                        f"/v1/capture-sessions/{session_id}/seal",
                        headers=operator_headers,
                        json={"request_id": seal_request_id},
                    )
                    self.assertEqual(seal_retry.status_code, 200, seal_retry.text)
                    self.assertTrue(seal_retry.json()["root_registered"])
                    self.assertTrue(seal_retry.json()["replayed"])
                    self.assertEqual(seal_retry.json()["manifest_digest"], manifest_digest)
                    root = self.db.f.seed.execute(
                        "SELECT manifest_digest,shot_list_version,seal_sequence,seal_chain_hash,"
                        "context_binding_hash,binding_version FROM faos.manifest_roots "
                        "WHERE tenant_id=%s AND session_id=%s",
                        (self.db.f.tenants[0], session_id),
                    ).fetchone()
                    self.assertIsNotNone(root, "CAPTURE_SEAL_DID_NOT_REGISTER_MANIFEST_ROOT")
                    self.assertEqual(root[0], manifest_digest)
                    self.assertEqual(root[1], DEFAULT_CAPTURE_PROTOCOL)
                    self.assertGreater(root[2], 0)
                    self.assertRegex(root[3], r"^[0-9a-f]{64}$")
                    self.assertRegex(root[4], r"^[0-9a-f]{64}$")
                    self.assertEqual(root[5], "manifest-context-v1")
                    seal_id = self.db.f.seed.execute(
                        "SELECT seal_event_id FROM faos.manifest_roots "
                        "WHERE tenant_id=%s AND session_id=%s",
                        (self.db.f.tenants[0], session_id),
                    ).fetchone()[0]
                    self.assertTrue(self.db.f.seed.execute(
                        "SELECT faos.verify_manifest_root_binding(%s::uuid,%s::text,%s::text)",
                        (self.db.f.tenants[0], session_id, seal_id),
                    ).fetchone()[0])

                    cross_tenant = client.get(
                        f"/v1/review-sessions/{session_id}",
                        headers={"Authorization": f"Bearer {cross_tenant_reviewer_token}"},
                    )
                    self.assertEqual(cross_tenant.status_code, 404)
                    reviewed = client.post(
                        f"/v1/capture-sessions/{session_id}/review",
                        headers={"Authorization": self.db.reviewer_auth()},
                        json={
                            "request_id": str(uuid.uuid4()),
                            "disposition": "NOTE_ONLY",
                            "reason": "Synthetic report-generation test; no real claim decision.",
                        },
                    )
                    self.assertEqual(reviewed.status_code, 200, reviewed.text)

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
                    self.assertEqual(details.json()["review"]["actor_id"], "claim-reviewer-0")
                    first_artifact_id, first_bytes = next(iter(originals.items()))
                    report_request_id = str(uuid.uuid4())
                    report_request = {
                        "request_id": report_request_id,
                        "vehicle_description": "2003 Honda Accord (synthetic integration fixture)",
                        "findings": [{
                            "finding_id": "D-HTTP-001",
                            "component": "Front bumper",
                            "vehicle_location": "Front center",
                            "damage_type": "surface deformation candidate",
                            "observation": "Synthetic fixture region for report rendering.",
                            "evidence_artifact_id": first_artifact_id,
                            "bbox_normalized": [0.2, 0.2, 0.7, 0.7],
                            "status": "CONFIRMED_BY_REVIEWER",
                            "limitations": "Synthetic image; no real damage conclusion.",
                        }],
                        "estimate_lines": [{
                            "line_id": "L-HTTP-001",
                            "category": "BODY_LABOR",
                            "description": "Synthetic body labor line",
                            "quantity": "1.5",
                            "unit": "hours",
                            "unit_price_cents": 8000,
                            "source_name": "Synthetic shop rate matrix",
                            "source_reference": "TEST-RATE-001",
                            "effective_date": "2026-11-24",
                            "related_finding_id": "D-HTTP-001",
                        }],
                        "camera_angles": {
                            first_artifact_id: {"yaw_degrees": 25, "pitch_degrees": -2, "roll_degrees": 0},
                        },
                    }
                    report = restarted.post(
                        f"/v1/review-sessions/{session_id}/damage-assessment-report",
                        headers={"Authorization": self.db.reviewer_auth()},
                        json=report_request,
                    )
                    self.assertEqual(report.status_code, 200, report.text)
                    self.assertTrue(report.content.startswith(b"%PDF-"))
                    self.assertEqual(report.headers["content-type"], "application/pdf")
                    report_artifact_id = report.headers["x-report-artifact-id"]
                    report_sha = report.headers["x-report-sha256"]
                    report_path = storage_root / self.db.f.tenants[0] / session_id / (report_artifact_id + ".original")
                    report_json_artifact_id = report.headers["x-report-json-artifact-id"]
                    report_json_sha = report.headers["x-report-json-sha256"]
                    report_json_path = storage_root / self.db.f.tenants[0] / session_id / (report_json_artifact_id + ".original")
                    self.assertTrue(report_path.exists(), "DAMAGE_REPORT_BYTES_NOT_PERSISTED")
                    self.assertTrue(report_json_path.exists(), "DAMAGE_REPORT_JSON_BYTES_NOT_PERSISTED")
                    self.assertNotIn(first_bytes, report.content, "REPORT_EMBEDDED_ORIGINAL_BYTES_INSTEAD_OF_REFERENCING_IMMUTABLE_KEY")
                    self.assertNotIn(first_bytes, report.content, "REPORT_EMBEDDED_ORIGINAL_BYTES_INSTEAD_OF_REFERENCING_IMMUTABLE_KEY")
                    self.assertEqual(hashlib.sha256(report.content).hexdigest(), report_sha)
                    report_retry = restarted.post(
                        f"/v1/review-sessions/{session_id}/damage-assessment-report",
                        headers={"Authorization": self.db.reviewer_auth()},
                        json=report_request,
                    )
                    self.assertEqual(report_retry.status_code, 200, report_retry.text)
                    self.assertEqual(report_retry.content, report.content)
                    self.assertEqual(report_retry.headers["x-report-json-artifact-id"], report_json_artifact_id)
                    self.assertEqual(report_retry.headers["x-report-json-sha256"], report_json_sha)
                    self.assertEqual(report_retry.headers["x-report-json-artifact-id"], report_json_artifact_id)
                    self.assertEqual(report_retry.headers["x-report-json-sha256"], report_json_sha)
                    altered_request = {**report_request, "vehicle_description": "Altered vehicle"}
                    altered_retry = restarted.post(
                        f"/v1/review-sessions/{session_id}/damage-assessment-report",
                        headers={"Authorization": self.db.reviewer_auth()},
                        json=altered_request,
                    )
                    self.assertEqual(altered_retry.status_code, 409)
                    report_download = restarted.get(
                        f"/v1/review-sessions/{session_id}/damage-assessment-reports/{report_artifact_id}",
                        headers={"Authorization": self.db.reviewer_auth()},
                    )
                    self.assertEqual(report_download.status_code, 200, report_download.text)
                    self.assertEqual(report_download.content, report.content)
                    report_json_download = restarted.get(
                        f"/v1/review-sessions/{session_id}/damage-assessment-reports/{report_artifact_id}/json",
                        headers={"Authorization": self.db.reviewer_auth()},
                    )
                    self.assertEqual(report_json_download.status_code, 200, report_json_download.text)
                    self.assertEqual(hashlib.sha256(report_json_download.content).hexdigest(), report_json_sha)
                    carrier_payload = report_json_download.json()
                    self.assertEqual(carrier_payload["capture_protocol_version"], DEFAULT_CAPTURE_PROTOCOL)
                    self.assertIn("A bounding box is a suspect-region identifier only", carrier_payload["disclosures"][0])
                    carrier_finding = carrier_payload["findings"][0]
                    self.assertEqual(carrier_finding["slot_id"], CANONICAL_SLOTS[0])
                    self.assertEqual(carrier_finding["bbox_normalized"], {
                        "x_min": 0.2, "y_min": 0.2, "x_max": 0.7, "y_max": 0.7,
                    })
                    self.assertEqual(carrier_finding["reviewer_attribution"]["actor_id"], "claim-reviewer-0")
                    self.assertEqual(carrier_finding["source_image"]["artifact_id"], first_artifact_id)
                    self.assertEqual(
                        carrier_finding["source_image"]["storage_key"],
                        f"{self.db.f.tenants[0]}/{session_id}/{first_artifact_id}.original",
                    )
                    self.assertEqual(carrier_finding["camera_angle"]["yaw_degrees"], 25)
                    self.assertEqual(report_json_download.headers["x-report-json-artifact-id"], report_json_artifact_id)
                    report_event = self.db.f.seed.execute(
                        "SELECT payload_json FROM faos.events WHERE tenant_id=%s AND session_id=%s "
                        "AND kind='DAMAGE_ASSESSMENT_REPORT_GENERATED' AND payload_json::jsonb->>'request_id'=%s",
                        (self.db.f.tenants[0], session_id, report_artifact_id),
                    ).fetchall()
                    self.assertEqual(len(report_event), 1, "DAMAGE_REPORT_REGISTRY_EVENT_NOT_UNIQUE")
                    report_event_payload = json.loads(report_event[0][0])
                    self.assertEqual(report_event_payload["report_json_artifact_id"], report_json_artifact_id)
                    self.assertEqual(report_event_payload["report_json_sha256"], report_json_sha)

                    fresh_store = CaptureSessionStore(resolver, self.db.dsns)
                    fresh_runtime = CaptureRuntime(resolver, fresh_store, Settings(), ClaimCaseStore(fresh_store))
                    with TestClient(create_capture_app(fresh_runtime, enable_evidence=True)) as fresh:
                        fresh_pdf = fresh.get(
                            f"/v1/review-sessions/{session_id}/damage-assessment-reports/{report_artifact_id}",
                            headers={"Authorization": self.db.reviewer_auth()},
                        )
                        fresh_json = fresh.get(
                            f"/v1/review-sessions/{session_id}/damage-assessment-reports/{report_artifact_id}/json",
                            headers={"Authorization": self.db.reviewer_auth()},
                        )
                        self.assertEqual(fresh_pdf.status_code, 200, fresh_pdf.text)
                        self.assertEqual(fresh_pdf.content, report.content)
                        self.assertEqual(fresh_json.status_code, 200, fresh_json.text)
                        self.assertEqual(fresh_json.content, report_json_download.content)

                    collision_evidence = restarted.get(
                        f"/v1/review-collisions/{collision_id}",
                        headers={"Authorization": self.db.reviewer_auth()},
                    )
                    self.assertEqual(collision_evidence.status_code, 200, collision_evidence.text)
                    self.assertEqual(len(collision_evidence.json()["claims"]), 1)
                    self.assertEqual(collision_evidence.json()["claims"][0]["claim_id"], claim_id)
                    self.assertEqual(collision_evidence.json()["claims"][0]["capture_session_id"], session_id)
                    self.assertEqual(collision_evidence.json()["claims"][0]["evidence_status"], "READY")
                    self.assertEqual(
                        collision_evidence.json()["claims"][0]["evidence"]["manifest_digest"],
                        manifest_digest,
                    )
                    collision_view_after_restart = restarted.get(
                        f"/v1/collisions/{collision_id}",
                        headers={"Authorization": self.db.auth()},
                    )
                    self.assertEqual(collision_view_after_restart.status_code, 200, collision_view_after_restart.text)
                    self.assertEqual(collision_view_after_restart.json()["vehicles"][0]["vehicle_id"], vehicle_id)
                    self.assertEqual(collision_view_after_restart.json()["vehicles"][0]["source_consent_status"], "ACTIVE")
                    self.assertEqual(collision_view_after_restart.json()["vehicles"][0]["vehicle_profile_status"], "DECODED")
                    self.assertEqual(
                        collision_view_after_restart.json()["vehicles"][0]["vehicle_profile"]["make"]["value"],
                        "HONDA",
                    )

                    decode_withdrawn = restarted.post(
                        f"/v1/capture-sessions/{session_id}/vehicle-decode-consent",
                        headers={"Authorization": self.db.owner_auth()},
                        json={
                            "request_id": str(uuid.uuid4()),
                            "accepted": False,
                            "scope": "nhtsa_vpic_decode",
                            "disclosure_version": "vehicle-decode-disclosure-v1",
                        },
                    )
                    self.assertEqual(decode_withdrawn.status_code, 200, decode_withdrawn.text)
                    profile_after_decode_withdrawal = restarted.get(
                        f"/v1/collisions/{collision_id}",
                        headers={"Authorization": self.db.auth()},
                    )
                    self.assertEqual(profile_after_decode_withdrawal.status_code, 200)
                    self.assertEqual(profile_after_decode_withdrawal.json()["vehicles"][0]["vehicle_profile_status"], "REVOKED")
                    self.assertIsNone(profile_after_decode_withdrawal.json()["vehicles"][0]["vehicle_profile"])

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
                    self.assertFalse(report_path.exists(), "CONSENT_WITHDRAWAL_DID_NOT_DELETE_REPORT_BYTES")
                    self.assertFalse(report_json_path.exists(), "CONSENT_WITHDRAWAL_DID_NOT_DELETE_REPORT_JSON_BYTES")
                    report_after_withdrawal = restarted.get(
                        f"/v1/review-sessions/{session_id}/damage-assessment-reports/{report_artifact_id}",
                        headers={"Authorization": self.db.reviewer_auth()},
                    )
                    self.assertEqual(report_after_withdrawal.status_code, 409)
                    vehicle_after_withdrawal = restarted.get(
                        f"/v1/collisions/{collision_id}",
                        headers={"Authorization": self.db.auth()},
                    )
                    self.assertEqual(vehicle_after_withdrawal.status_code, 200, vehicle_after_withdrawal.text)
                    self.assertEqual(vehicle_after_withdrawal.json()["vehicles"][0]["source_consent_status"], "REVOKED")
                    self.assertEqual(vehicle_after_withdrawal.json()["vehicles"][0]["vin_source"], "UNVERIFIED")
                    self.assertEqual(vehicle_after_withdrawal.json()["vehicles"][0]["vin_validation_status"], "UNVERIFIED")
                    relink_after_withdrawal = restarted.post(
                        f"/v1/collisions/{collision_id}/vehicles",
                        headers={"Authorization": self.db.auth()},
                        json={
                            "claim_id": claim_id,
                            "vehicle_id": str(uuid.uuid4()),
                            "request_id": str(uuid.uuid4()),
                            "relationship": "INVOLVED",
                        },
                    )
                    self.assertEqual(relink_after_withdrawal.status_code, 403, relink_after_withdrawal.text)
                    after_withdrawal = restarted.get(
                        f"/v1/review-sessions/{session_id}",
                        headers={"Authorization": self.db.reviewer_auth()},
                    )
                    self.assertEqual(after_withdrawal.status_code, 409)
                    self.assertEqual(after_withdrawal.json(), {"detail": "CAPTURE_SESSION_CONFLICT"})


if __name__ == "__main__":
    unittest.main()
