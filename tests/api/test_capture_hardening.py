"""Regression tests: mocked store I/O, not PostgreSQL or pilot acceptance."""
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
from uuid import UUID

from fastapi.testclient import TestClient
from app.capture_api import CaptureRuntime, _target, create_capture_app, load_runtime
from app.main import Settings

@dataclass
class EncodableSession:
    session_id: UUID
    created_at: datetime
    created: bool = False

class CaptureHardeningTests(unittest.TestCase):
    def client(self):
        self.resolver = Mock()
        self.store = Mock()
        runtime = CaptureRuntime(self.resolver, self.store, Settings())
        return TestClient(create_capture_app(runtime))

    def test_single_explicit_target_remains_supported(self):
        self.assertEqual(_target('host=localhost port=5432 dbname=test user=operator'), ('localhost', '', '5432', 'test'))

    def test_target_rejects_all_multitarget_fields(self):
        for field in ('host', 'hostaddr', 'port'):
            values = {'host': 'localhost', 'port': '5432', 'dbname': 'test', 'user': 'operator', 'hostaddr': '127.0.0.1'}
            values[field] = {'host': 'one,two', 'hostaddr': '127.0.0.1,127.0.0.2', 'port': '5432,5433'}[field]
            with self.subTest(field=field), self.assertRaises(ValueError):
                _target(' '.join(key + '=' + value for key, value in values.items()))

    def test_invalid_target_types_and_syntax_are_normalized(self):
        for value in (None, 12, '', ' ', 'not a connection string'):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, '^INVALID_DATABASE_URL$'):
                _target(value)

    def test_nonstandard_json_constants_are_rejected(self):
        for constant in ('NaN', 'Infinity', '-Infinity'):
            with self.subTest(constant=constant), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'config.json'
                path.write_text('{"health_database_url":' + constant + ',"dsn_by_role":{},"credentials":[]}', encoding='utf-8')
                with self.assertRaisesRegex(ValueError, '^INVALID_CAPTURE_RUNTIME_CONFIGURATION$'):
                    load_runtime(path)

    def test_validation_response_does_not_echo_private_input(self):
        secret = 'synthetic-private-do-not-echo'
        with self.client() as client:
            response = client.post('/v1/capture-sessions', json={'session_id': secret}, headers={'Authorization': 'Bearer test'})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json(), {'detail': 'INVALID_CAPTURE_REQUEST'})
        self.assertNotIn(secret, response.text)
        self.assertEqual(response.headers['cache-control'], 'no-store')
        self.store.create.assert_not_called()

    def test_uuid_and_datetime_are_encoded(self):
        with self.client() as client:
            self.store.get.return_value = EncodableSession(UUID(int=2), datetime(2026, 1, 1, tzinfo=timezone.utc))
            response = client.get('/v1/capture-sessions/' + str(UUID(int=2)), headers={'Authorization': 'Bearer test'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['session_id'], str(UUID(int=2)))
        self.assertEqual(response.json()['created_at'], '2026-01-01T00:00:00+00:00')

    def test_serialization_failure_is_controlled(self):
        with self.client() as client:
            self.store.get.return_value = object()
            response = client.get('/v1/capture-sessions/' + str(UUID(int=2)), headers={'Authorization': 'Bearer test'})
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json(), {'detail': 'CAPTURE_OPERATION_FAILED'})
        self.assertEqual(response.headers['cache-control'], 'no-store')

    def test_missing_header_is_rejected_even_with_permissive_resolver(self):
        with self.client() as client:
            response = client.get('/v1/capture-sessions/' + str(UUID(int=2)))
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.headers['www-authenticate'], 'Bearer')
        self.resolver.resolve.assert_not_called()
        self.store.get.assert_not_called()

if __name__ == '__main__':
    unittest.main()
