"""Registry-backed decisions in PostgreSQL; no durable completion transition."""
from dataclasses import asdict, replace
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
import uuid
import psycopg
from database.journal import append
from database.eligibility import check_registered_completion

class RegisteredCompletionTests(unittest.TestCase):
    def setUp(self):
        import test_manifest_roots as fixtures
        self.fixture = fixtures.ManifestRootTests()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.setUp()

    def check(self, data=None, tenant=None):
        f = self.fixture
        return check_registered_completion(f.conn, tenant or f.tenant, f.session, f.data if data is None else data)

    def test_eligible_history_without_registered_root_blocks(self):
        with self.assertRaisesRegex(ValueError, '^MANIFEST_ROOT_NOT_REGISTERED$'):
            self.check()
        self.assertIsNone(self.fixture.conn.execute('SELECT faos.tenant_id()').fetchone()[0])

    def test_registered_root_allows_current_eligible_snapshot(self):
        f = self.fixture
        self.assertEqual(f.register(), 'REGISTERED')
        decision = self.check()
        self.assertEqual((decision.status, decision.reasons, decision.event_count), ('ELIGIBLE', (), len(f.events)))
        self.assertIsNone(f.conn.execute('SELECT faos.tenant_id()').fetchone()[0])

    def test_tampered_bytes_block_despite_registered_root(self):
        self.assertEqual(self.fixture.register(), 'REGISTERED')
        with self.assertRaisesRegex(ValueError, 'INTEGRITY_NOT_VERIFIED'):
            self.check(dict(self.fixture.data, front=b'tampered'))

    def test_registered_root_does_not_override_revoked_consent(self):
        f = self.fixture
        self.assertEqual(f.register(), 'REGISTERED')
        revoked = replace(f.events[1], event_id='revoke-consent', sequence=len(f.events)+1,
                          payload_json='{"disclosure_version":"synthetic-v1","evidence_scope":false}')
        self.assertEqual(append(f.conn, f.tenant, revoked), 'ACCEPTED')
        with self.assertRaisesRegex(ValueError, 'REQUIRED_CONSENT_MISSING'):
            self.check()

    def test_new_seal_requires_its_own_registration(self):
        f = self.fixture
        self.assertEqual(f.register(), 'REGISTERED')
        newer = replace(f.events[-1], event_id='new-seal', sequence=len(f.events)+1)
        self.assertEqual(append(f.conn, f.tenant, newer), 'ACCEPTED')
        with self.assertRaisesRegex(ValueError, '^MANIFEST_ROOT_NOT_REGISTERED$'):
            self.check()
        self.assertEqual(f.register((f.tenant, f.session, newer.event_id, f.digest, f.version)), 'REGISTERED')
        self.assertEqual(self.check().status, 'ELIGIBLE')

    def test_other_tenant_cannot_evaluate_registered_session(self):
        self.assertEqual(self.fixture.register(), 'REGISTERED')
        with self.assertRaises(psycopg.errors.RaiseException) as caught:
            self.check(tenant=str(uuid.uuid4()))
        self.assertEqual(caught.exception.sqlstate, 'P0001')
        self.assertEqual(caught.exception.diag.message_primary, 'SESSION_NOT_FOUND')
        self.assertEqual(self.check().status, 'ELIGIBLE')

    def test_fresh_process_loads_root_without_caller_digest(self):
        f = self.fixture
        self.assertEqual(f.register(), 'REGISTERED')
        child = """import json, os, sys
from dataclasses import asdict
import psycopg
from database.eligibility import check_registered_completion
value = json.load(sys.stdin)
data = {key: bytes.fromhex(raw) for key, raw in value['bytes_hex'].items()}
with psycopg.connect(os.environ['RECOVERY_DATABASE_URL'], autocommit=True) as conn:
    result = check_registered_completion(conn, value['tenant'], value['session'], data)
print(json.dumps(asdict(result), sort_keys=True))
"""
        env = os.environ.copy()
        env['RECOVERY_DATABASE_URL'] = os.getenv('APP_DATABASE_URL', 'postgresql://faos_app:synthetic-app-only@127.0.0.1:55432/claim2car_test')
        payload = {'tenant': f.tenant, 'session': f.session, 'bytes_hex': {key: raw.hex() for key, raw in f.data.items()}}
        result = subprocess.run([sys.executable, '-c', child], input=json.dumps(payload), cwd=Path(__file__).resolve().parents[2],
                                env=env, text=True, capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), json.loads(json.dumps(asdict(self.check()))))

if __name__ == '__main__':
    unittest.main()
