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
                # The integrated runtime serves the real operator/reviewer shell.
                shell = client.get("/")
                assert shell.status_code == 200
                assert "Claim2Car Connect" in shell.text

                # Verify the document actually bootstraps the connected
                # operator/reviewer workbench, rather than merely returning
                # an unrelated HTML page while another frontend's assets
                # happen to be mounted at the root.
                assert '<link rel="stylesheet" href="/assets/app.css">' in shell.text
                assert '<script type="module" src="/assets/app.js"></script>' in shell.text
                assert "/app.mjs" not in shell.text
                assert "/styles.css" not in shell.text

                workbench_script = client.get("/assets/app.js")
                assert workbench_script.status_code == 200
                assert "createClaimCase" in workbench_script.text
                assert "/api/v1/claim-cases" in workbench_script.text
                assert "/api/v1/capture-protocols" in workbench_script.text
                assert "capture_protocol_version" in workbench_script.text
                assert 'id="capture-protocol-version"' in shell.text
                assert "/api/v1/review-queue" in workbench_script.text
                assert "createOfflineEvidenceQueue" in workbench_script.text

                # Every fixed DOM lookup made by the shipped workbench must
                # resolve against the actual root document. This catches
                # partially wired shells before a browser user encounters
                # null-element failures during connection or capture.
                import re

                script_ids = set(re.findall(r'\$\("([^"]+)"\)', workbench_script.text))
                document_ids = set(re.findall(r'\bid="([^"]+)"', shell.text))
                assert script_ids <= document_ids, (
                    "Workbench references missing from root HTML: "
                    + ", ".join(sorted(script_ids - document_ids))
                )

                assert client.get("/assets/app.css").status_code == 200
                assert client.get("/assets/offline_evidence_queue.mjs").status_code == 200
                # The newer controlled-test interface is deliberately
                # isolated under /prototype. It must not shadow the persistent
                # claim-case workbench at the product root.
                prototype = client.get("/prototype/")
                assert prototype.status_code == 200
                assert '<link rel="stylesheet" href="/prototype/styles.css">' in prototype.text
                assert '<script type="module" src="/prototype/app.mjs"></script>' in prototype.text
                assert client.get("/prototype/app.mjs").status_code == 200
                assert client.get("/prototype/styles.css").status_code == 200
                assert client.get("/app.mjs").status_code == 404
                assert client.get("/styles.css").status_code == 404
                assert client.get("/src/modules/capture/vin.mjs").status_code == 200

                # Capture and reviewer APIs are mounted under /api and retain
                # their end-user credential boundary.
                capture = client.get(f"/api/v1/capture-sessions/{SESSION_ID}")
                assert capture.status_code == 401
                review_queue = client.get("/api/v1/review-queue")
                assert review_queue.status_code == 401
                review_details = client.get(f"/api/v1/review-sessions/{SESSION_ID}")
                assert review_details.status_code == 401

                # The protocol registry is authenticated and distinguishes
                # the approved 16-v1 default from the executable 12-v1
                # alternative without inventing the pending 16 slots.
                registry_denied = client.get("/api/v1/capture-protocols")
                assert registry_denied.status_code == 401
                registry = client.get(
                    "/api/v1/capture-protocols",
                    headers={"Authorization": f"Bearer {OPERATOR_TOKEN}"},
                )
                assert registry.status_code == 200
                assert registry.json()["default_protocol_version"] == "claims2car-16-v1"
                by_version = {item["version"]: item for item in registry.json()["protocols"]}
                assert by_version["claims2car-16-v1"]["status"] == "definition_pending"
                assert by_version["claims2car-16-v1"]["required_slots"] == []
                assert by_version["claims2car-16-v1"]["capture_enabled"] is False
                assert by_version["claims2car-12-v1"]["status"] == "implemented"
                assert len(by_version["claims2car-12-v1"]["required_slots"]) == 12
                ui_slots_match = re.search(r"const SLOTS = \[(.*?)\];", workbench_script.text, re.S)
                assert ui_slots_match is not None
                ui_slots = re.findall(r'\["([^"]+)"', ui_slots_match.group(1))
                assert ui_slots == by_version["claims2car-12-v1"]["required_slots"]
                # Identity discovery is authenticated and returns only the
                # server-resolved actor/tenant/role, never client assertions.
                identity_denied = client.get("/api/v1/identity")
                assert identity_denied.status_code == 401
                identity = client.get(
                    "/api/v1/identity",
                    headers={"Authorization": f"Bearer {OPERATOR_TOKEN}"},
                )
                assert identity.status_code == 200
                assert identity.json() == {
                    "actor_id": "operator-1",
                    "tenant_id": str(UUID(int=1)),
                    "actor_role": "operator",
                }

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
            os.environ.pop("C2C_INTERNAL_SERVICE_TOKEN", None)
            try:
                create_app(runtime_mode="integrated")
            except ValueError as error:
                assert str(error) == "INTERNAL_SERVICE_AUTH_CONFIGURATION_REQUIRED"
            else:
                raise AssertionError("INTEGRATED_RUNTIME_STARTED_WITHOUT_SERVICE_SECRET")


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
