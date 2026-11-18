"""Provider-neutral integrated staging smoke checks, with no real network calls."""
import json
import unittest
from unittest.mock import patch

from scripts import integrated_staging_smoke as smoke


SHA = "1" * 40
ORIGIN = "https://staging.example.invalid"


class IntegratedStagingSmokeTests(unittest.TestCase):
    def setUp(self):
        self.calls = []

    def response(self, base, path):
        self.assertEqual(base, ORIGIN)
        self.calls.append(path)
        if path == "/health/ready":
            return 200, json.dumps({"status": "ready"}).encode()
        if path == "/health/live":
            return 200, b'{"status":"alive"}'
        if path == "/health/build":
            return 200, json.dumps({"revision": SHA, "runtime_mode": "integrated"}).encode()
        if path == "/":
            return 200, b"operator shell"
        if path in ("/api/v1/capture-sessions", "/api/v1/review-queue",
                    "/internal/v1/analysis/health"):
            return 401, b'{"detail":"unauthorized"}'
        if path == "/api/v1/analysis/physics":
            return 404, b'{"detail":"not found"}'
        return 500, b"unexpected path"

    def verify(self, **kwargs):
        with patch.object(smoke, "request", side_effect=self.response):
            with patch.object(smoke.time, "sleep") as sleep:
                result = smoke.verify(ORIGIN, SHA, **kwargs)
        sleep.assert_not_called()
        return result

    def test_integrated_revision_and_boundaries_pass(self):
        result = self.verify()
        self.assertEqual(result, {
            "result": "passed", "revision": SHA, "runtime_mode": "integrated",
        })
        self.assertEqual(self.calls, [
            "/health/ready", "/health/live", "/health/build", "/",
            "/api/v1/capture-sessions", "/api/v1/review-queue",
            "/internal/v1/analysis/health", "/api/v1/analysis/physics",
        ])

    def test_http_origin_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "INVALID_INTEGRATED_STAGING_TARGET"):
            smoke.verify("http://staging.example.invalid", SHA)

    def test_wrong_revision_is_rejected(self):
        def wrong_build(base, path):
            result = self.response(base, path)
            if path == "/health/build":
                return 200, json.dumps({"revision": "2" * 40, "runtime_mode": "integrated"}).encode()
            return result
        with patch.object(smoke, "request", side_effect=wrong_build):
            with self.assertRaisesRegex(RuntimeError, "DEPLOYED_REVISION_OR_RUNTIME_MODE_MISMATCH"):
                smoke.verify(ORIGIN, SHA)

    def test_wrong_runtime_mode_is_rejected(self):
        def wrong_mode(base, path):
            result = self.response(base, path)
            if path == "/health/build":
                return 200, json.dumps({"revision": SHA, "runtime_mode": "restricted"}).encode()
            return result
        with patch.object(smoke, "request", side_effect=wrong_mode):
            with self.assertRaisesRegex(RuntimeError, "DEPLOYED_REVISION_OR_RUNTIME_MODE_MISMATCH"):
                smoke.verify(ORIGIN, SHA)

    def test_public_physics_route_is_rejected(self):
        def exposed(base, path):
            result = self.response(base, path)
            return (200, b"unexpected") if path == "/api/v1/analysis/physics" else result
        with patch.object(smoke, "request", side_effect=exposed):
            with self.assertRaisesRegex(RuntimeError, "PUBLIC_ANALYSIS_ROUTE_EXPOSED"):
                smoke.verify(ORIGIN, SHA)

    def test_missing_authentication_boundary_is_rejected(self):
        def exposed(base, path):
            result = self.response(base, path)
            return (200, b"unexpected") if path == "/api/v1/capture-sessions" else result
        with patch.object(smoke, "request", side_effect=exposed):
            with self.assertRaisesRegex(RuntimeError, "CAPTURE_API_AUTH_BOUNDARY_FAILED"):
                smoke.verify(ORIGIN, SHA)

    def test_readiness_must_be_explicit(self):
        def warming(base, path):
            if path == "/health/ready":
                return 200, b'{"status":"warming"}'
            return self.response(base, path)
        with patch.object(smoke, "request", side_effect=warming):
            with patch.object(smoke.time, "sleep"):
                with self.assertRaisesRegex(RuntimeError, "INTEGRATED_STAGING_NOT_READY"):
                    smoke.verify(ORIGIN, SHA, attempts=2, interval_seconds=0)

    def test_invalid_retry_policy_is_rejected(self):
        for attempts, interval in ((0, 1), (1, -1)):
            with self.subTest(attempts=attempts, interval=interval):
                with self.assertRaisesRegex(RuntimeError, "INVALID_RETRY_POLICY"):
                    smoke.verify(ORIGIN, SHA, attempts=attempts, interval_seconds=interval)


if __name__ == "__main__":
    unittest.main()
