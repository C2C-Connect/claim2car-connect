"""Deterministic smoke-check retries without network calls or real sleeping."""
from collections import defaultdict, deque
import unittest
from unittest.mock import patch
from urllib.error import URLError

from scripts import container_smoke as smoke


SHA = "1" * 40
OLD_SHA = "2" * 40
ORIGIN = "https://staging.example.invalid"


class Clock:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


class ContainerSmokeTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.faults = defaultdict(deque)
        self.calls = []

    @staticmethod
    def health(path, **overrides):
        body = {
            "status": "ready" if path == "/health/ready" else "alive",
            "revision": SHA, "scope": "synthetic-staging-containment-only",
        }
        for key in (
            "business_ready", "database_integrated", "capture_enabled",
            "analysis_enabled", "dispatch_build_enabled", "payments_enabled",
        ):
            body[key] = False
        return 200, {"Cache-Control": "no-store"}, {**body, **overrides}

    def response(self, base_url, path, payload=None, **kwargs):
        self.assertEqual(base_url, ORIGIN)
        self.calls.append((path, kwargs.get("timeout")))
        if self.faults[path]:
            value = self.faults[path].popleft()
            if isinstance(value, Exception):
                raise value
            return value
        if path in ("/health/live", "/health/ready"):
            return self.health(path)
        if path == "/api/v1/dispatch/health":
            return 200, {}, {
                "status": "disabled", "build_enabled": False,
                "scope": "synthetic-staging-containment-only",
                "redact_enabled": False, "verify_enabled": False,
            }
        if path == "/api/v1/dispatch/build":
            return 503, {"Cache-Control": "no-store"}, {
                "detail": {"code": "dispatch_build_disabled"},
            }
        return 404, {}, {"detail": "Not Found"}

    def verify(self, wait_seconds=10):
        with patch.object(smoke, "request", side_effect=self.response):
            with patch.object(smoke, "time", self.clock):
                return smoke.verify(ORIGIN, SHA, wait_seconds)

    def test_healthy_endpoints_pass_without_sleeping(self):
        self.assertEqual(self.verify()["result"], "passed")
        self.assertEqual(self.clock.sleeps, [])

    def test_ready_503_is_retried_after_live_is_healthy(self):
        self.faults["/health/ready"].append((503, {}, {"detail": "warming"}))
        self.assertEqual(self.verify()["revision"], SHA)
        self.assertEqual(sum(path == "/health/ready" for path, _ in self.calls), 2)
        self.assertEqual(self.clock.sleeps, [2])

    def test_network_and_malformed_response_errors_are_retried(self):
        self.faults["/health/ready"].extend([
            URLError("temporary connection issue"), ValueError("temporary invalid JSON"),
            (200, {}, ["invalid-body"]),
        ])
        self.assertEqual(self.verify()["result"], "passed")
        self.assertEqual(self.clock.sleeps, [2, 2, 2])

    def test_old_revision_on_either_endpoint_is_retried(self):
        for path in ("/health/live", "/health/ready"):
            with self.subTest(path=path):
                self.setUp()
                self.faults[path].append(self.health(path, revision=OLD_SHA))
                self.assertEqual(self.verify()["result"], "passed")
                self.assertEqual(self.clock.sleeps, [2])

    def test_warming_200_status_is_not_mistaken_for_readiness(self):
        self.faults["/health/ready"].append(self.health("/health/ready", status="warming"))
        self.assertEqual(self.verify()["result"], "passed")
        self.assertEqual(self.clock.sleeps, [2])

    def test_both_endpoints_share_one_bounded_deadline(self):
        self.faults["/health/ready"].extend([(503, {}, {})] * 10)
        with self.assertRaisesRegex(RuntimeError, "HEALTH_NOT_READY_BEFORE_DEADLINE"):
            self.verify(wait_seconds=5)
        self.assertEqual(self.clock.now, 5)
        self.assertEqual(self.clock.sleeps, [2, 2, 1])
        self.assertTrue(all(0 < timeout <= 5 for _, timeout in self.calls))
        self.assertTrue(all(path.startswith("/health/") for path, _ in self.calls))

    def test_request_timeout_is_capped_to_remaining_budget(self):
        self.faults["/health/ready"].extend([(503, {}, {})] * 10)
        with self.assertRaisesRegex(RuntimeError, "HEALTH_NOT_READY_BEFORE_DEADLINE"):
            self.verify(wait_seconds=1)
        self.assertTrue(all(timeout == 1 for _, timeout in self.calls))
        self.assertEqual(self.clock.sleeps, [1])

    def test_health_responses_arriving_after_deadline_do_not_pass(self):
        response = self.response

        def late_response(*args, **kwargs):
            result = response(*args, **kwargs)
            if args[1] == "/health/ready":
                self.clock.now += 2
            return result

        with patch.object(smoke, "request", side_effect=late_response):
            with patch.object(smoke, "time", self.clock):
                with self.assertRaisesRegex(RuntimeError, "HEALTH_NOT_READY_BEFORE_DEADLINE"):
                    smoke.verify(ORIGIN, SHA, wait_seconds=1)
        self.assertTrue(all(path.startswith("/health/") for path, _ in self.calls))

    def test_unsafe_capabilities_fail_immediately_without_retry(self):
        for key in (
            "business_ready", "database_integrated", "capture_enabled",
            "analysis_enabled", "dispatch_build_enabled", "payments_enabled",
        ):
            with self.subTest(key=key):
                self.setUp()
                self.faults["/health/ready"].append(self.health("/health/ready", **{key: True}))
                with self.assertRaisesRegex(RuntimeError, "UNEXPECTED_BUSINESS_ENABLEMENT:" + key):
                    self.verify()
                self.assertEqual(self.clock.sleeps, [])

    def test_scope_and_cache_violations_fail_immediately(self):
        for response, error in (
            (self.health("/health/ready", scope="production"), "SCOPE_MISMATCH"),
            ((200, {}, self.health("/health/ready")[2]), "HEALTH_CACHE_POLICY"),
        ):
            with self.subTest(error=error):
                self.setUp()
                self.faults["/health/ready"].append(response)
                with self.assertRaisesRegex(RuntimeError, error):
                    self.verify()
                self.assertEqual(self.clock.sleeps, [])

    def test_dispatch_safety_violation_is_not_retried(self):
        self.faults["/api/v1/dispatch/build"].append((200, {}, {"unexpected": "enabled"}))
        with self.assertRaisesRegex(RuntimeError, "DISPATCH_BUILD_NOT_BLOCKED"):
            self.verify()
        self.assertEqual(self.clock.sleeps, [])
        self.assertEqual(sum(path == "/api/v1/dispatch/build" for path, _ in self.calls), 1)

    def test_nonpositive_wait_fails_before_any_request(self):
        for seconds in (0, -1):
            with self.subTest(seconds=seconds):
                with self.assertRaisesRegex(RuntimeError, "POSITIVE_WAIT_REQUIRED"):
                    self.verify(wait_seconds=seconds)
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()
