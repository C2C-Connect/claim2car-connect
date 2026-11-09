"""HTTP unit tests for the provider-neutral restricted staging surface."""
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import restricted_staging
from backend.app.api import dispatch


REVISION = "1" * 40


class RestrictedStagingTests(unittest.TestCase):
    def client(self):
        with patch.object(restricted_staging, "read_build_revision", return_value=REVISION):
            return TestClient(restricted_staging.create_staging_app())

    def test_readiness_is_scoped_not_business_acceptance(self):
        with self.client() as client:
            for path, status in (("/health/live", "alive"), ("/health/ready", "ready")):
                response = client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.headers["cache-control"], "no-store")
                body = response.json()
                self.assertEqual(body["status"], status)
                self.assertEqual(body["revision"], REVISION)
                self.assertEqual(body["scope"], restricted_staging.SCOPE)
                for key in (
                    "business_ready", "database_integrated", "capture_enabled",
                    "analysis_enabled", "dispatch_build_enabled", "payments_enabled",
                ):
                    self.assertIs(body[key], False)

    def test_business_and_documentation_routes_are_not_mounted(self):
        with self.client() as client:
            for method, path in (
                ("GET", "/docs"), ("GET", "/redoc"), ("GET", "/openapi.json"),
                ("POST", "/api/v1/analysis/run"), ("POST", "/api/v1/triage/adjudicate"),
                ("POST", "/api/v1/dispatch/redact"), ("POST", "/api/v1/verify/"),
                ("GET", "/api/v1/verify/synthetic"),
                ("POST", "/v1/capture-sessions"),
            ):
                with self.subTest(method=method, path=path):
                    self.assertEqual(client.request(method, path).status_code, 404)

    def test_dispatch_cannot_build_or_mutate_ledger_even_for_malformed_body(self):
        with self.client() as client, patch.object(dispatch, "build_dispatch") as builder:
            with patch.object(dispatch.LEDGER, "append") as append:
                for payload in (
                    b"",
                    b"not-json",
                    b'{"adjudication":{"execution_mode":"model","provenance_verified":true}}',
                ):
                    response = client.post(
                        "/api/v1/dispatch/build",
                        content=payload,
                        headers={"Content-Type": "application/json"},
                    )
                    self.assertEqual(response.status_code, 503)
                    self.assertEqual(response.json()["detail"]["code"], "dispatch_build_disabled")
                    self.assertEqual(response.headers["cache-control"], "no-store")
                builder.assert_not_called()
                append.assert_not_called()

    def test_dispatch_health_is_disabled(self):
        with self.client() as client:
            body = client.get("/api/v1/dispatch/health").json()
        self.assertEqual(body["status"], "disabled")
        self.assertIs(body["build_enabled"], False)
        self.assertIs(body["redact_enabled"], False)
        self.assertIs(body["verify_enabled"], False)
        self.assertEqual(body["scope"], restricted_staging.SCOPE)

    def test_build_revision_must_be_a_full_commit(self):
        for value in ("UNSTAMPED", "", "main", "a" * 39, "a" * 41, "../../secret"):
            with self.subTest(value=value):
                with patch("pathlib.Path.read_text", return_value=value):
                    with self.assertRaisesRegex(RuntimeError, "BUILD_REVISION_INVALID"):
                        restricted_staging.create_staging_app()
        with patch("pathlib.Path.read_text", return_value=REVISION + "\n"):
            self.assertEqual(restricted_staging.read_build_revision(), REVISION)

    def test_missing_build_revision_fails_startup(self):
        with patch("pathlib.Path.read_text", side_effect=OSError):
            with self.assertRaisesRegex(RuntimeError, "BUILD_REVISION_UNAVAILABLE"):
                restricted_staging.create_staging_app()

    def test_port_defaults_and_override(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(restricted_staging.listen_port(), 8000)
        with patch.dict(os.environ, {"PORT": "18765"}):
            self.assertEqual(restricted_staging.listen_port(), 18765)

    def test_invalid_ports_fail_closed(self):
        for value in ("", "abc", "0", "-1", "65536"):
            with self.subTest(value=value), patch.dict(os.environ, {"PORT": value}):
                with self.assertRaisesRegex(RuntimeError, "PORT_INVALID"):
                    restricted_staging.listen_port()

    def test_ci_workflow_verifies_without_deploying_to_a_provider(self):
        root = Path(__file__).resolve().parents[2]
        workflow = (root / ".github" / "workflows" / "restricted-container-verification.yml").read_text(encoding="utf-8")
        self.assertIn("docker build --file Dockerfile.restricted-staging", workflow)
        self.assertIn("python scripts/container_smoke.py", workflow)
        self.assertIn("contents: read", workflow)
        self.assertNotIn("railway", workflow.lower())
        self.assertNotIn("docker push", workflow.lower())
        self.assertNotIn("RAILWAY_", workflow)

    def test_container_build_configuration_is_provider_neutral(self):
        root = Path(__file__).resolve().parents[2]
        dockerfile = (root / "Dockerfile.restricted-staging").read_text(encoding="utf-8")
        self.assertIn("USER 10001:10001", dockerfile)
        self.assertIn("app.restricted_staging", dockerfile)


if __name__ == "__main__":
    unittest.main()
