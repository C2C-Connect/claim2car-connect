"""Integrated-runtime composition and route-boundary acceptance tests.

These tests exercise the actual FastAPI application factory with a private,
synthetic service configuration. They do not require PostgreSQL because every
database-backed request is stopped at the authentication boundary.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
from unittest.mock import patch

import pytest
from uuid import UUID

from fastapi.testclient import TestClient

from app.main import create_app


SERVICE_TOKEN = "I" * 43
OPERATOR_TOKEN = "O" * 43
SESSION_ID = str(UUID(int=2))


def _runtime_environment(directory: str) -> dict[str, str]:
    root = Path(directory)
    config_path = root / "private-runtime.json"
    database_url = (
        "postgresql://faos_app:synthetic-app-only@127.0.0.1:55432/"
        "claim2car_test"
    )
    role_url = (
        "postgresql://tenant_login_operator:synthetic-operator-only@"
        "127.0.0.1:55432/claim2car_test"
    )
    config = {
        "health_database_url": database_url,
        "dsn_by_role": {"tenant_login_operator": role_url},
        "credentials": [
            {
                "actor_id": "operator-1",
                "tenant_id": str(UUID(int=1)),
                "database_role": "tenant_login_operator",
                "token_sha256": hashlib.sha256(
                    OPERATOR_TOKEN.encode("ascii")
                ).hexdigest(),
                "expires_at": int(time.time()) + 3600,
                "enabled": True,
                "actor_role": "operator",
            }
        ],
    }
    config_path.write_text(json.dumps(config), encoding="utf-8")
    storage_root = root / "original-evidence"
    storage_root.mkdir(mode=0o700)
    return {
        "C2C_CAPTURE_CONFIG_FILE": str(config_path),
        "C2C_ARTIFACT_STORAGE_ROOT": str(storage_root),
        "C2C_VIN_HMAC_PEPPER": "P" * 43,
        "C2C_INTERNAL_SERVICE_TOKEN": SERVICE_TOKEN,
    }


def test_integrated_runtime_mounts_capture_and_internal_analysis_only():
    with tempfile.TemporaryDirectory() as directory:
        environment = _runtime_environment(directory)
        with patch.dict(os.environ, environment, clear=False):
            app = create_app(runtime_mode="integrated")
            with TestClient(app) as client:
                assert client.get("/health/live").status_code == 200

                # Capture and reviewer APIs are mounted under /api and retain
                # their end-user credential boundary.
                capture = client.get(f"/api/v1/capture-sessions/{SESSION_ID}")
                assert capture.status_code == 401
                review_queue = client.get("/api/v1/review-queue")
                assert review_queue.status_code == 401

                # Analytical APIs are not exposed on their legacy public path.
                assert client.post(
                    "/api/v1/analysis/physics",
                    json={"mass_kg": 1500, "velocity_kph": 30, "zones": []},
                ).status_code == 404

                # The internal route is mounted, but fails closed without the
                # service credential and executes with the configured token.
                payload = {
                    "mass_kg": 1500,
                    "velocity_kph": 30,
                    "zones": [],
                }
                denied = client.post(
                    "/internal/v1/analysis/physics", json=payload
                )
                assert denied.status_code == 401
                allowed = client.post(
                    "/internal/v1/analysis/physics",
                    headers={"Authorization": f"Bearer {SERVICE_TOKEN}"},
                    json=payload,
                )
                assert allowed.status_code == 200
                assert "e_k_j" in allowed.json()


def test_integrated_runtime_refuses_missing_internal_service_secret():
    with tempfile.TemporaryDirectory() as directory:
        environment = _runtime_environment(directory)
        environment.pop("C2C_INTERNAL_SERVICE_TOKEN")
        with patch.dict(os.environ, environment, clear=False):
            with pytest.raises(
                ValueError, match="^INTERNAL_SERVICE_AUTH_CONFIGURATION_REQUIRED$"
            ):
                create_app(runtime_mode="integrated")


def test_integrated_dispatch_remains_disabled_after_service_authentication():
    with tempfile.TemporaryDirectory() as directory:
        environment = _runtime_environment(directory)
        with patch.dict(os.environ, environment, clear=False):
            app = create_app(runtime_mode="integrated")
            with TestClient(app) as client:
                path = "/internal/v1/dispatch/build"
                denied = client.post(path, json={"adjudication": {}})
                assert denied.status_code == 401

                disabled = client.post(
                    path,
                    headers={"Authorization": f"Bearer {SERVICE_TOKEN}"},
                    json={"adjudication": {}},
                )
                assert disabled.status_code == 503
                assert disabled.json()["detail"]["code"] == "dispatch_build_disabled"
