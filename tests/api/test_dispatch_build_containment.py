"""Direct-handler regression tests; not live HTTP or deployment evidence."""
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from backend.app.api import dispatch


class DispatchBuildContainmentTests(unittest.TestCase):
    def test_build_rejects_missing_synthetic_and_claimed_model_provenance(self):
        cases = [
            {},
            {"execution_mode": "synthetic"},
            {"execution_mode": "model", "provenance_verified": True},
        ]
        for supplied in cases:
            with self.subTest(supplied=supplied):
                body = dispatch.DispatchRequest(
                    adjudication={"session_id": "synthetic-test-session", **supplied}
                )
                with patch.object(dispatch, "build_dispatch") as builder:
                    with patch.object(dispatch.LEDGER, "append") as append:
                        with self.assertRaises(HTTPException) as caught:
                            dispatch.dispatch_build(body)
                        self.assertEqual(caught.exception.status_code, 503)
                        self.assertEqual(
                            caught.exception.detail["code"], "dispatch_build_disabled"
                        )
                        self.assertEqual(
                            caught.exception.headers["Cache-Control"], "no-store"
                        )
                        builder.assert_not_called()
                        append.assert_not_called()

    def test_health_does_not_advertise_build_readiness(self):
        result = dispatch.dispatch_health()
        self.assertEqual(result["status"], "disabled")
        self.assertIs(result["build_enabled"], False)
        self.assertEqual(result["reason"], "trusted_provenance_not_integrated")


if __name__ == "__main__":
    unittest.main()
