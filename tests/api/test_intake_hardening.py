"""Mocked ASGI regressions; no database or device acceptance claim."""
from dataclasses import dataclass
from datetime import datetime, timezone
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from uuid import UUID
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.intake_api import create_intake_app

@dataclass
class RichDraft:
    session_id: UUID
    timestamp: datetime

class IntakeHardeningTests(unittest.TestCase):
    def setUp(self):
        self.resolver = Mock()
        self.store = Mock()
        runtime = SimpleNamespace(resolver=self.resolver, store=Mock())
        factory = patch('app.intake_api.create_capture_app', side_effect=lambda runtime: FastAPI())
        store = patch('app.intake_api.IntakeDraftStore', return_value=self.store)
        factory.start(); self.addCleanup(factory.stop)
        store.start(); self.addCleanup(store.stop)
        self.client = TestClient(create_intake_app(runtime))
        self.addCleanup(self.client.close)
        self.path = '/v1/capture-sessions/' + str(UUID(int=2)) + '/draft'
        self.headers = {'Authorization': 'Bearer synthetic-test'}

    def test_missing_header_rejected_without_resolver_or_store(self):
        response = self.client.get(self.path)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.headers['www-authenticate'], 'Bearer')
        self.resolver.resolve.assert_not_called()
        self.store.get.assert_not_called()

    def test_uuid_and_datetime_encode(self):
        self.store.get.return_value = RichDraft(UUID(int=2), datetime(2026, 1, 1, tzinfo=timezone.utc))
        response = self.client.get(self.path, headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['session_id'], str(UUID(int=2)))
        self.assertEqual(response.json()['timestamp'], '2026-01-01T00:00:00+00:00')

    def test_non_dataclass_result_returns_safe_500(self):
        self.store.get.return_value = object()
        response = self.client.get(self.path, headers=self.headers)
        self.assertEqual((response.status_code, response.json()), (500, {'detail': 'INTAKE_OPERATION_FAILED'}))
        self.assertEqual(response.headers['cache-control'], 'no-store')

    def test_encoding_value_error_is_not_misclassified_as_client_error(self):
        self.store.get.return_value = RichDraft(UUID(int=2), datetime(2026, 1, 1, tzinfo=timezone.utc))
        with patch('app.intake_api.jsonable_encoder', side_effect=ValueError('private-internal-detail')):
            response = self.client.get(self.path, headers=self.headers)
        self.assertEqual(response.status_code, 500)
        self.assertNotIn('private-internal-detail', response.text)

if __name__ == '__main__':
    unittest.main()
