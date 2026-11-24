"""The adjudication API must not trust client-asserted integrity or valuation inputs."""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api.triage import router, triage_health
from backend.app.security import require_internal_service


def test_health_marks_adjudication_disabled_until_server_verification():
    health = triage_health()
    assert health["status"] == "disabled"
    assert health["adjudication_enabled"] is False
    assert health["reason"] == "SERVER_VERIFIED_EVIDENCE_REQUIRED"


def test_client_asserted_integrity_inputs_cannot_reach_adjudication():
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[require_internal_service] = lambda: None
    client = TestClient(app)
    response = client.post(
        "/api/v1/triage/adjudicate",
        json={
            "session_id": "forged-session",
            "master_hash_valid": True,
            "hash_tamper_suspected": False,
            "chain_coverage": 1.0,
            "chain_uniqueness": 1.0,
            "meta_completeness": 1.0,
            "gps_accuracy_m": 0.1,
            "internal_acv_a": 25000,
            "internal_acv_b": 25000,
            "internal_acv_c": 25000,
        },
    )
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "SERVER_VERIFIED_EVIDENCE_REQUIRED"
    assert response.headers["cache-control"] == "no-store"
