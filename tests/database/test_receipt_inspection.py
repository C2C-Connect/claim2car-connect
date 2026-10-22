"""Historical/current snapshot distinction with real PostgreSQL receipt readback."""
from dataclasses import asdict, replace
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
import uuid
import psycopg
from database.eligibility import check_registered_completion
from database.journal import append
from database.receipts import inspect_completion_receipt

class ReceiptInspectionTests(unittest.TestCase):
    def setUp(self):
        import test_atomic_completion as fixtures
        self.base = fixtures.AtomicCompletionTests()
        self.addCleanup(self.base.doCleanups)
        self.base.setUp()
        self.f = self.base.f
        self.request = self.base.storage.request
        self.assertEqual(self.base.record().receipt_status, 'RECORDED')

    def inspect(self, tenant=None, request=None):
        f = self.f
        return inspect_completion_receipt(f.conn, tenant or f.tenant, f.session, request or self.request)

    def test_metadata_matches_committed_snapshot(self):
        f = self.f
        result = self.inspect()
        self.assertEqual((result.tenant_id,result.session_id,result.request_id,result.seal_event_id),
                         (f.tenant,f.session,self.request,f.seal))
        self.assertEqual((result.event_sequence,result.manifest_digest,result.shot_list_version),
                         (len(f.events),f.digest,f.version))
        self.assertEqual(result.authority_role, 'faos_writer')
        self.assertTrue(result.authority_session)
        self.assertIsNotNone(result.recorded_at.utcoffset())
        self.assertTrue(result.snapshot_matches_current_history)
        self.assertEqual(result.current_event_sequence, len(f.events))
        self.assertIsNone(f.conn.execute('SELECT faos.tenant_id()').fetchone()[0])

    def test_revocation_marks_history_mismatch_not_current_completion(self):
        self.base.revoke()
        result = self.inspect()
        self.assertFalse(result.snapshot_matches_current_history)
        self.assertEqual((result.event_sequence,result.current_event_sequence), (len(self.f.events),len(self.f.events)+1))
        with self.assertRaisesRegex(ValueError, 'REQUIRED_CONSENT_MISSING'):
            check_registered_completion(self.f.conn, self.f.tenant, self.f.session, self.f.data)

    def test_new_note_changes_snapshot_without_implying_ineligibility(self):
        f = self.f
        note = replace(f.events[-1],event_id='inspection-note',sequence=len(f.events)+1,kind='REVIEW_RECORDED',
                       payload_json='{"artifact_ids":["front"],"disposition":"NOTE_ONLY","schema_version":"0.1"}')
        self.assertEqual(append(f.conn, f.tenant, note), 'ACCEPTED')
        self.assertFalse(self.inspect().snapshot_matches_current_history)
        self.assertEqual(check_registered_completion(f.conn, f.tenant, f.session, f.data).status, 'ELIGIBLE')

    def test_unknown_request_rejected(self):
        with self.assertRaisesRegex(ValueError, '^RECEIPT_NOT_FOUND_OR_NOT_VISIBLE$'):
            self.inspect(request=str(uuid.uuid4()))

    def test_other_tenant_cannot_inspect_receipt(self):
        with self.assertRaises(psycopg.errors.RaiseException) as caught:
            self.inspect(tenant=str(uuid.uuid4()))
        self.assertEqual(caught.exception.sqlstate, 'P0001')
        self.assertEqual(caught.exception.diag.message_primary, 'SESSION_NOT_FOUND')
        self.assertEqual(self.inspect().request_id, self.request)

    def test_fresh_process_reads_same_metadata(self):
        child = """import json, os, sys
from dataclasses import asdict
import psycopg
from database.receipts import inspect_completion_receipt
value = json.load(sys.stdin)
with psycopg.connect(os.environ['RECOVERY_DATABASE_URL'], autocommit=True) as conn:
    result = inspect_completion_receipt(conn,value['tenant'],value['session'],value['request'])
print(json.dumps(asdict(result),default=str,sort_keys=True))
"""
        env = os.environ.copy()
        env['RECOVERY_DATABASE_URL'] = os.getenv('APP_DATABASE_URL', 'postgresql://faos_app:synthetic-app-only@127.0.0.1:55432/claim2car_test')
        payload = {'tenant':self.f.tenant,'session':self.f.session,'request':self.request}
        result = subprocess.run([sys.executable,'-c',child],input=json.dumps(payload),cwd=Path(__file__).resolve().parents[2],
                                env=env,text=True,capture_output=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout),json.loads(json.dumps(asdict(self.inspect()),default=str)))

if __name__ == '__main__':
    unittest.main()
