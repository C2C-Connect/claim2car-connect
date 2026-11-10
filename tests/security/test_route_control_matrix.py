"""
Route-to-control matrix verification (Slice 3, plan v1.3 workstream D).

The matrix in docs/security/route-control-matrix.md is enforced here as code:
- The M1 public surface exposes ONLY health routes (no business API).
- Every authenticated M1 business route carries the Bearer authorize dependency.
- The M5 analysis app is a separate internal surface; dispatch/build stays
  disabled regardless of client-supplied provenance.
- CORS on the analysis app cannot be wildcard-with-credentials.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from fastapi.routing import APIRoute

from app.capture_api import create_capture_app
from app.identity import ActorBinding, Credential, CredentialResolver
from app.main import Settings, create_app
from app.intake_api import create_intake_app


def route_table(app):
    return {
        (route.path, tuple(sorted(route.methods)))
        for route in app.routes
        if isinstance(route, APIRoute)
    }


class M1PublicSurfaceTests(unittest.TestCase):
    def test_foundation_app_exposes_only_health_routes(self):
        table = route_table(create_app(Settings()))
        self.assertEqual(
            table,
            {("/health/live", ("GET",)), ("/health/ready", ("GET",))},
            "The M1 public surface must expose only health routes — no business API.",
        )

    def test_business_routes_exist_only_on_authenticated_apps(self):
        table = route_table(create_app(Settings()))
        for path, _ in table:
            self.assertNotIn("capture-sessions", path)
            self.assertNotIn("draft", path)


class M1AuthenticatedRouteTests(unittest.TestCase):
    """Every business route must carry the server-side Bearer authorize dependency."""

    def _authorize_dependencies(self, app):
        required = []
        for route in app.routes:
            if isinstance(route, APIRoute) and "capture-sessions" in route.path:
                assert route.dependant.dependencies, f"{route.path} has no authorize dependency"
                required.append((route.path, tuple(sorted(route.methods))))
        return required

    def test_capture_routes_all_require_bearer(self):
        app = create_capture_app(self._runtime())
        secured = self._authorize_dependencies(app)
        self.assertEqual(
            set(secured),
            {
                ("/v1/capture-sessions", ("GET",)),
                ("/v1/capture-sessions", ("POST",)),
                ("/v1/capture-sessions/{session_id}", ("GET",)),
            },
        )

    def test_intake_routes_all_require_bearer(self):
        app = create_intake_app(self._runtime())
        secured = self._authorize_dependencies(app)
        # intake app wraps the capture app; both surfaces must be secured
        self.assertEqual(
            set(secured),
            {
                ("/v1/capture-sessions", ("GET",)),
                ("/v1/capture-sessions", ("POST",)),
                ("/v1/capture-sessions/{session_id}", ("GET",)),
                ("/v1/capture-sessions/{session_id}/draft", ("GET",)),
                ("/v1/capture-sessions/{session_id}/draft", ("PUT",)),
            },
        )

    def _runtime(self):
        import hashlib
        import time
        import uuid

        binding = ActorBinding("matrix-actor", uuid.UUID(int=1), "tenant_login_matrix")
        credential = Credential(
            hashlib.sha256(b"m" * 43).hexdigest(), binding, int(time.time()) + 3600
        )
        from unittest.mock import Mock

        from database.capture_sessions import CaptureSessionStore

        return type(
            "R",
            (),
            {
                "resolver": CredentialResolver([credential]),
                "store": Mock(spec=CaptureSessionStore),
                "health_settings": Settings(),
            },
        )()


class AnalysisSurfaceIsolationTests(unittest.TestCase):
    def test_integrated_runtime_rehomes_analysis_behind_internal_auth(self):
        import os
        from unittest.mock import patch
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        token = "t" * 43
        intake = FastAPI()
        intake.state.health_settings = Settings("integrated-health-dsn")
        intake.get("/v1/capture-sessions")(
            lambda: {"scope": "tenant-authenticated-intake"}
        )
        with patch("app.intake_api.create_intake_app", return_value=intake), patch.dict(
            os.environ, {"C2C_INTERNAL_SERVICE_TOKEN": token}
        ):
            integrated = create_app(Settings(), runtime_mode="integrated")
            table = route_table(integrated)
            self.assertIn(("/internal/v1/analysis/health", ("GET",)), table)
            self.assertIn(("/internal/v1/triage/health", ("GET",)), table)
            self.assertIn(("/internal/v1/dispatch/health", ("GET",)), table)
            self.assertNotIn(("/api/v1/analysis/health", ("GET",)), table)

            with patch("app.main.probe_database", return_value=True) as probe:
                with TestClient(integrated) as client:
                    missing = client.get("/internal/v1/analysis/health")
                    accepted = client.get(
                        "/internal/v1/analysis/health",
                        headers={"Authorization": f"Bearer {token}"},
                    )
                    intake_route = client.get("/api/v1/capture-sessions")
                    readiness = client.get("/health/ready")
                probe.assert_called_once_with("integrated-health-dsn")
            self.assertEqual(missing.status_code, 401)
            self.assertEqual(accepted.status_code, 200)
            self.assertEqual(
                intake_route.json(), {"scope": "tenant-authenticated-intake"}
            )
            self.assertEqual(readiness.json()["status"], "ready")

    def test_runtime_mode_rejects_unknown_values(self):
        with self.assertRaisesRegex(ValueError, "INVALID_C2C_RUNTIME_MODE"):
            create_app(Settings(), runtime_mode="anything_else")

    def test_analysis_app_is_separate_from_m1_surface(self):
        from backend.app.main import app as analysis_app

        m1 = route_table(create_app(Settings()))
        analysis = route_table(analysis_app)
        overlap = {p for p, _ in m1} & {p for p, _ in analysis}
        # health routes may overlap by design; business routes must not
        business_overlap = {p for p in overlap if "capture" in p or "triage" in p or "dispatch" in p}
        self.assertEqual(business_overlap, set())

    def test_dispatch_build_stays_disabled(self):
        from fastapi.testclient import TestClient

        from backend.app.main import app as analysis_app

        with TestClient(analysis_app) as client:
            response = client.post(
                "/api/v1/dispatch/build",
                json={"adjudication": {}, "vin": "123", "photo_hashes": []},
            )
            self.assertEqual(response.status_code, 503)
            self.assertEqual(response.json()["detail"]["code"], "dispatch_build_disabled")
            health = client.get("/api/v1/dispatch/health")
            self.assertFalse(health.json().get("build_enabled", True))

    def test_analysis_cors_is_not_wildcard_with_credentials(self):
        from backend.app.main import ALLOWED_ORIGINS

        self.assertNotIn(
            "*",
            ALLOWED_ORIGINS,
            "Wildcard CORS with credentials is forbidden; use an explicit allowlist.",
        )


if __name__ == "__main__":
    unittest.main()
