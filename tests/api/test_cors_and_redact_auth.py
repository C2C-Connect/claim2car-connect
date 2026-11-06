"""Regression: CORS allowlist + authenticated compute routes."""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.app.security import parse_cors_origins, require_service_token
from backend.app.api import dispatch
from config import forensic_constants as C


class CorsOriginParsingTests(unittest.TestCase):
    def test_wildcard_stripped_when_credentials_enabled(self):
        origins = parse_cors_origins("*,https://app.example.com", allow_credentials=True)
        self.assertNotIn("*", origins)
        self.assertIn("https://app.example.com", origins)

    def test_default_localhost_when_empty(self):
        origins = parse_cors_origins("", allow_credentials=True)
        self.assertTrue(any("localhost" in o for o in origins))


class ServiceTokenTests(unittest.TestCase):
    def test_missing_config_fails_closed(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(HTTPException) as caught:
                require_service_token(authorization=None)
            self.assertEqual(caught.exception.status_code, 503)

    def test_valid_token_accepted(self):
        with patch.dict(os.environ, {"C2C_SERVICE_TOKEN": "test-token-xyz"}, clear=False):
            got = require_service_token(authorization="Bearer test-token-xyz")
            self.assertEqual(got, "test-token-xyz")


class ComputeRouteAuthTests(unittest.TestCase):
    def test_physics_rejects_unauthenticated(self):
        from backend.app.main import app

        with patch.dict(os.environ, {"C2C_SERVICE_TOKEN": "pilot-secret"}, clear=False):
            client = TestClient(app)
            r = client.post(
                "/api/v1/analysis/physics",
                json={
                    "mass_kg": 1500,
                    "velocity_kph": 40,
                    "zones": [{"zone": "front", "depth_cm": 10}],
                },
            )
            self.assertEqual(r.status_code, 401)

    def test_physics_accepts_bearer(self):
        from backend.app.main import app

        with patch.dict(os.environ, {"C2C_SERVICE_TOKEN": "pilot-secret"}, clear=False):
            client = TestClient(app)
            r = client.post(
                "/api/v1/analysis/physics",
                headers={"Authorization": "Bearer pilot-secret"},
                json={
                    "mass_kg": 1500,
                    "velocity_kph": 36,
                    "zones": [{"zone": "front", "depth_cm": 15, "area_cm2": 4000}],
                },
            )
            self.assertEqual(r.status_code, 200)
            body = r.json()
            self.assertIn("e_k_kj", body)
            self.assertIn("p_tl_physics", body)
            self.assertEqual(body["formula_version"], C.VERSION)

    def test_redact_rejects_unauthenticated(self):
        from backend.app.main import app

        with patch.dict(os.environ, {"C2C_SERVICE_TOKEN": "pilot-secret"}, clear=False):
            client = TestClient(app)
            r = client.post(
                "/api/v1/dispatch/redact",
                json={"role": "owner", "payload": {"vin": "1HGCM82633A004352"}},
            )
            self.assertEqual(r.status_code, 401)

    def test_constants_require_auth(self):
        from backend.app.main import app

        with patch.dict(os.environ, {"C2C_SERVICE_TOKEN": "pilot-secret"}, clear=False):
            client = TestClient(app)
            bare = client.get("/api/v1/config/constants")
            self.assertEqual(bare.status_code, 401)
            ok = client.get(
                "/api/v1/config/constants",
                headers={"Authorization": "Bearer pilot-secret"},
            )
            self.assertEqual(ok.status_code, 200)
            self.assertEqual(ok.json()["OPERATOR_PAYOUT_USD"], 110.0)

    def test_health_stays_public(self):
        from backend.app.main import app

        client = TestClient(app)
        self.assertEqual(client.get("/health/live").status_code, 200)
        self.assertEqual(client.get("/api/v1/analysis/health").status_code, 200)

    def test_dispatch_health_advertises_redact_auth(self):
        result = dispatch.dispatch_health()
        self.assertEqual(result["redact_auth"], "bearer_required")


class DarciConstantsPresentTests(unittest.TestCase):
    def test_required_physics_constants_exist(self):
        for name in (
            "SIGMA_YIELD_MPA",
            "KE_FACTOR_DIVISOR_KJ",
            "KE_FACTOR_CAP",
            "P_BRITTLE_BETA",
            "P_BRITTLE_CAP",
            "A_ZONE_M2",
            "SEVERE_EK_KJ",
            "LOW_IMPACT_RY",
            "ENTROPY_AI_OVERRIDE_BITS",
            "DEFAULT_TAX_RATE",
        ):
            self.assertTrue(hasattr(C, name), f"missing {name}")

    def test_no_owner_payout(self):
        self.assertEqual(C.OPERATOR_PAYOUT_USD, 110.0)
        self.assertFalse(hasattr(C, "OWNER_PAYOUT_USD"))


if __name__ == "__main__":
    unittest.main()
