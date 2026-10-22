"""Evaluated historical receipts; no terminal lifecycle or production authority claim."""
from contextlib import contextmanager
from dataclasses import replace
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch
import psycopg
from database.completion import record_registered_completion
from database.eligibility import check_registered_completion
from database.journal import append

class AtomicCompletionTests(unittest.TestCase):
    def setUp(self):
        import test_completion_receipts as fixtures
        self.storage = fixtures.CompletionReceiptTests()
        self.addCleanup(self.storage.doCleanups)
        self.storage.setUp()
        self.f = self.storage.fixture

    @contextmanager
    def writer(self):
        with psycopg.connect(self.f.admin_url, autocommit=True) as conn:
            conn.execute('SET ROLE faos_writer')
            self.assertEqual(conn.execute('SELECT current_user').fetchone()[0], 'faos_writer')
            yield conn

    def record(self, data=None):
        f = self.f
        with self.writer() as conn:
            return record_registered_completion(conn, f.tenant, f.session, self.storage.request, f.data if data is None else data)

    def revoke(self):
        f = self.f
        event = replace(f.events[1], event_id='revoke-consent', sequence=len(f.events)+1,
                        payload_json='{"disclosure_version":"synthetic-v1","evidence_scope":false}')
        self.assertEqual(append(f.conn, f.tenant, event), 'ACCEPTED')

    def test_valid_evaluation_records_and_retries_once(self):
        f = self.f
        first, retry = self.record(), self.record()
        self.assertEqual((first.receipt_status, retry.receipt_status), ('RECORDED', 'DUPLICATE'))
        self.assertEqual(first.decision.status, 'ELIGIBLE')
        self.assertEqual((first.seal_event_id, first.event_sequence), (f.seal, len(f.events)))
        self.assertEqual(self.storage.receipts(), [(self.storage.request, f.seal, len(f.events), 'faos_writer')])

    def test_tampering_cannot_write_receipt(self):
        with self.assertRaisesRegex(ValueError, 'INTEGRITY_NOT_VERIFIED'):
            self.record(dict(self.f.data, front=b'tampered'))
        self.assertEqual(self.storage.receipts(), [])

    def test_revoked_consent_cannot_write_receipt(self):
        self.revoke()
        with self.assertRaisesRegex(ValueError, 'REQUIRED_CONSENT_MISSING'):
            self.record()
        self.assertEqual(self.storage.receipts(), [])

    def test_unregistered_new_seal_cannot_write_receipt(self):
        f = self.f
        event = replace(f.events[-1], event_id='new-seal', sequence=len(f.events)+1)
        self.assertEqual(append(f.conn, f.tenant, event), 'ACCEPTED')
        with self.assertRaisesRegex(ValueError, '^MANIFEST_ROOT_NOT_REGISTERED$'):
            self.record()
        self.assertEqual(self.storage.receipts(), [])

    def test_application_role_cannot_use_writer_adapter(self):
        f = self.f
        with self.assertRaisesRegex(ValueError, '^TRUSTED_WRITER_ROLE_REQUIRED$'):
            record_registered_completion(f.conn, f.tenant, f.session, self.storage.request, f.data)
        self.assertEqual(self.storage.receipts(), [])

    def test_failure_after_insert_rolls_back_receipt(self):
        with patch('database.completion.CompletionResult', side_effect=RuntimeError('synthetic post-insert failure')):
            with self.assertRaisesRegex(RuntimeError, '^synthetic post-insert failure$'):
                self.record()
        self.assertEqual(self.storage.receipts(), [])
        self.assertEqual(self.record().receipt_status, 'RECORDED')

    def test_historical_receipt_does_not_override_later_revocation(self):
        self.assertEqual(self.record().receipt_status, 'RECORDED')
        before = self.storage.receipts()
        self.revoke()
        with self.assertRaisesRegex(ValueError, 'REQUIRED_CONSENT_MISSING'):
            self.record()
        with self.assertRaisesRegex(ValueError, 'REQUIRED_CONSENT_MISSING'):
            check_registered_completion(self.f.conn, self.f.tenant, self.f.session, self.f.data)
        self.assertEqual(self.storage.receipts(), before)

    def test_committed_receipt_readable_in_fresh_process(self):
        self.assertEqual(self.record().receipt_status, 'RECORDED')
        child = """import json, os, sys
import psycopg
from database.journal import tenant_transaction
value = json.load(sys.stdin)
with psycopg.connect(os.environ['RECOVERY_DATABASE_URL'], autocommit=True) as conn:
    with tenant_transaction(conn, value['tenant']):
        rows = conn.execute('SELECT request_id::text,seal_event_id,event_sequence,authority_role::text FROM faos.completion_receipts WHERE tenant_id=%s AND session_id=%s ORDER BY request_id', (value['tenant'], value['session'])).fetchall()
print(json.dumps(rows))
"""
        env = os.environ.copy()
        env['RECOVERY_DATABASE_URL'] = os.getenv('APP_DATABASE_URL', 'postgresql://faos_app:synthetic-app-only@127.0.0.1:55432/claim2car_test')
        result = subprocess.run([sys.executable, '-c', child], input=json.dumps({'tenant':self.f.tenant,'session':self.f.session}),
                                cwd=Path(__file__).resolve().parents[2], env=env, text=True, capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), json.loads(json.dumps(self.storage.receipts())))

if __name__ == '__main__':
    unittest.main()
