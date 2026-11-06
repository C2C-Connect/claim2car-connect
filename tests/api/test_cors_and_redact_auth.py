"""Regression: CORS allowlist + authenticated dispatch/redact."""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.app.security import parse_cors_origins, require_service_token
from backend.app.api import dispatch


class CorsOriginParsingTests(unittest.TestCase):
    def test_wildcard_stripped_when_credentials_enabled(self):
        origins = parse_cors_origins("*,https://app.example.com", allow_credentials=True)
        self.assertNotIn("*", origins)
        self.assertIn("https://app.example.com", origins)

    def test_default_localhost_when_empty(self):
        origins = parse_cors_origins("", allow_credentials=True)
        self.assertTrue(any("localhost" in o for o in origins))

    def test_explicit_list_preserved(self):
        origins = parse_cors_origins(
            "https://a.example.com, https://b.example.com",
            allow_credentials=True,
        )
        self.assertEqual(
            origins,
            ["https://a.example.com", "https://b.example.com"],
        )


class ServiceTokenTests(unittest.TestCase):
    def test_missing_config_fails_closed(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(HTTPException) as caught:
                require_service_token(authorization=None)
            self.assertEqual(caught.exception.status_code, 503)
            self.assertEqual(caught.exception.detail["code"], "auth_not_configured")

    def test_missing_header_unauthorized(self):
        with patch.dict(os.environ, {"C2C_SERVICE_TOKEN": "test-token-xyz"}, clear=False):
            with self.assertRaises(HTTPException) as caught:
                require_service_token(authorization=None)
            self.assertEqual(caught.exception.status_code, 401)
            self.assertEqual(caught.exception.detail["code"], "missing_bearer_token")

    def test_invalid_token_rejected(self):
        with patch.dict(os.environ, {"C2C_SERVICE_TOKEN": "test-token-xyz"}, clear=False):
            with self.assertRaises(HTTPException) as caught:
                require_service_token(authorization="Bearer wrong")
            self.assertEqual(caught.exception.status_code, 401)
            self.assertEqual(caught.exception.detail["code"], "invalid_bearer_token")

    def test_valid_token_accepted(self):
        with patch.dict(os.environ, {"C2C_SERVICE_TOKEN": "test-token-xyz"}, clear=False):
            got = require_service_token(authorization="Bearer test-token-xyz")
            self.assertEqual(got, "test-token-xyz")


class DispatchRedactAuthTests(unittest.TestCase):
    def test_redact_rejects_unauthenticated_http(self):
        from backend.app.main import app

        with patch.dict(os.environ, {"C2C_SERVICE_TOKEN": "pilot-secret"}, clear=False):
            # Re-import not required; dependency reads env at call time
            client = TestClient(app)
            r = client.post(
                "/api/v1/dispatch/redact",
                json={"role": "owner", "payload": {"vin": "1HGCM82633A004352", "session_id": "s1"}},
            )
            self.assertEqual(r.status_code, 401)
            self.assertEqual(r.json()["detail"]["code"], "missing_bearer_token")

    def test_redact_accepts_valid_bearer(self):
        from backend.app.main import app

        with patch.dict(os.environ, {"C2C_SERVICE_TOKEN": "pilot-secret"}, clear=False):
            client = TestClient(app)
            r = client.post(
                "/api/v1/dispatch/redact",
                headers={"Authorization": "Bearer pilot-secret"},
                json={
                    "role": "owner",
                    "payload": {
                        "vin": "1HGCM82633A004352",
                        "session_id": "s1",
                        "final_tier": "total_loss",
                    },
                },
            )
            self.assertEqual(r.status_code, 200)
            body = r.json()
            self.assertTrue(body.get("redacted"))
            self.assertEqual(body.get("role"), "owner")
            self.assertNotIn("vin", body)

    def test_health_advertises_redact_auth(self):
        result = dispatch.dispatch_health()
        self.assertEqual(result["redact_auth"], "bearer_required")


if __name__ == "__main__":
    unittest.main()
