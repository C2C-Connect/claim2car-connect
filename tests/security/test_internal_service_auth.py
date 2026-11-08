"""Fail-closed authentication tests for the internal analysis service."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.app.main import app


TOKEN = "T" * 43


def _routes():
    return {
        (route.path, method): route
        for route in app.routes
        if isinstance(route, APIRoute)
        for method in (route.methods or set())
    }


def test_internal_business_routes_require_service_dependency():
    routes = _routes()
    protected = {
        ("/api/v1/analysis/physics", "POST"),
        ("/api/v1/analysis/run", "POST"),
        ("/api/v1/triage/adjudicate", "POST"),
        ("/api/v1/dispatch/redact", "POST"),
    }
    for key in protected:
        assert key in routes
        assert routes[key].dependant.dependencies, f"{key} missing service authorization"


def test_internal_routes_fail_closed_when_secret_is_not_configured():
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("C2C_INTERNAL_SERVICE_TOKEN", None)
        response = TestClient(app).post(
            "/api/v1/analysis/physics",
            json={"mass_kg": 1500, "velocity_kph": 30, "zones": []},
        )
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "INTERNAL_SERVICE_AUTH_NOT_CONFIGURED"


def test_internal_routes_reject_missing_and_invalid_bearer_tokens():
    with patch.dict(os.environ, {"C2C_INTERNAL_SERVICE_TOKEN": TOKEN}):
        client = TestClient(app)
        missing = client.post("/api/v1/analysis/physics", json={"mass_kg": 1500, "velocity_kph": 30})
        invalid = client.post(
            "/api/v1/analysis/physics",
            headers={"Authorization": "Bearer " + "X" * 43},
            json={"mass_kg": 1500, "velocity_kph": 30},
        )
    assert missing.status_code == 401
    assert invalid.status_code == 401



def test_internal_route_rejects_non_ascii_authorization_header_safely():
    from backend.app.security import require_internal_service

    with patch.dict(os.environ, {"C2C_INTERNAL_SERVICE_TOKEN": TOKEN}):
        with pytest.raises(HTTPException) as exc:
            require_internal_service("Bearer " + "é" * 43)
    assert exc.value.status_code == 401
    assert exc.value.detail == {"code": "UNAUTHORIZED"}


def test_internal_route_accepts_configured_service_token():
    with patch.dict(os.environ, {"C2C_INTERNAL_SERVICE_TOKEN": TOKEN}):
        response = TestClient(app).post(
            "/api/v1/analysis/physics",
            headers={"Authorization": f"Bearer {TOKEN}"},
            json={"mass_kg": 1500, "velocity_kph": 30, "zones": []},
        )
    assert response.status_code == 200
    assert "e_k_j" in response.json()


def test_public_health_and_verification_remain_explicitly_public():
    routes = _routes()
    assert routes[("/api/v1/analysis/health", "GET")].dependant.dependencies == []
    assert routes[("/api/v1/triage/health", "GET")].dependant.dependencies == []
    assert routes[("/api/v1/verify/", "POST")].dependant.dependencies == []
    assert routes[("/api/v1/verify/{session_id}", "GET")].dependant.dependencies == []


def test_dispatch_build_remains_hard_disabled_without_authorization():
    response = TestClient(app).post("/api/v1/dispatch/build", json={"adjudication": {}})
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "dispatch_build_disabled"
