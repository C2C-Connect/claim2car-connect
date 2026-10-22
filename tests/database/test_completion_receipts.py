"""Privileged receipt-storage tests, not evidence-policy or lifecycle completion tests."""
from dataclasses import replace
import os
import unittest
import uuid
import psycopg
from database.journal import append, tenant_transaction

RECORD = 'SELECT faos.record_completion_receipt(%s::uuid,%s::text,%s::uuid,%s::text,%s::bigint)'

class CompletionReceiptTests(unittest.TestCase):
    def setUp(self):
        import test_manifest_roots as fixtures
        self.fixture = fixtures.ManifestRootTests()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.setUp()
        self.assertEqual(self.fixture.register(), 'REGISTERED')
        self.request = str(uuid.uuid4())

    def values(self):
        f = self.fixture
        return (f.tenant, f.session, self.request, f.seal, len(f.events))

    def record(self, values=None, context=True):
        f = self.fixture
        with psycopg.connect(f.admin_url, autocommit=True) as conn:
            with conn.transaction():
                conn.execute('SET LOCAL ROLE faos_writer')
                self.assertEqual(conn.execute('SELECT current_user').fetchone()[0], 'faos_writer')
                if context:
                    conn.execute("SELECT set_config('faos.tenant_id',%s,true)", (f.tenant,))
                return conn.execute(RECORD, values or self.values()).fetchone()[0]

    def receipts(self, tenant=None):
        f = self.fixture
        with tenant_transaction(f.conn, tenant or f.tenant):
            return f.conn.execute('SELECT request_id::text,seal_event_id,event_sequence,authority_role::text FROM faos.completion_receipts ORDER BY request_id').fetchall()

    def assert_rejected(self, values, message, context=True):
        with self.assertRaises(psycopg.errors.RaiseException) as caught:
            self.record(values, context=context)
        self.assertEqual(caught.exception.sqlstate, 'P0001')
        self.assertEqual(caught.exception.diag.message_primary, message)

    def test_privileged_record_and_same_snapshot_retry(self):
        f = self.fixture
        self.assertEqual(self.record(), 'RECORDED')
        self.assertEqual(self.record(), 'DUPLICATE')
        self.assertEqual(self.receipts(), [(self.request, f.seal, len(f.events), 'faos_writer')])

    def test_application_cannot_record_or_insert(self):
        f = self.fixture
        insert = 'INSERT INTO faos.completion_receipts(tenant_id,session_id,request_id,seal_event_id,event_sequence) VALUES (%s,%s,%s,%s,%s)'
        for statement in (RECORD, insert):
            with self.subTest(statement=statement):
                with self.assertRaises(psycopg.errors.InsufficientPrivilege) as caught:
                    with tenant_transaction(f.conn, f.tenant):
                        f.conn.execute(statement, self.values())
                self.assertEqual(caught.exception.sqlstate, '42501')
        self.assertEqual(self.receipts(), [])

    def test_application_cannot_update_delete_or_truncate_recorded_receipt(self):
        f = self.fixture
        self.assertEqual(self.record(), 'RECORDED')
        expected = [(self.request, f.seal, len(f.events), 'faos_writer')]
        keys = (f.tenant, f.session, self.request)
        statements = (
            ('UPDATE faos.completion_receipts SET seal_event_id=seal_event_id WHERE tenant_id=%s AND session_id=%s AND request_id=%s', keys),
            ('DELETE FROM faos.completion_receipts WHERE tenant_id=%s AND session_id=%s AND request_id=%s', keys),
            ('TRUNCATE faos.completion_receipts', ()),
        )
        for statement, values in statements:
            with self.subTest(statement=statement):
                with self.assertRaises(psycopg.errors.InsufficientPrivilege) as caught:
                    with tenant_transaction(f.conn, f.tenant):
                        f.conn.execute(statement, values)
                        raise AssertionError('UNEXPECTED_RECEIPT_MUTATION_ALLOWED')
                self.assertEqual(caught.exception.sqlstate, '42501')
                self.assertEqual(self.receipts(), expected)

    def test_wrong_sequence_rejected_without_receipt(self):
        values = self.values()
        self.assert_rejected(values[:-1] + (values[-1]+1,), 'COMPLETION_SEQUENCE_CHANGED')
        self.assertEqual(self.receipts(), [])

    def test_stale_seal_rejected_without_receipt(self):
        f = self.fixture
        newer = replace(f.events[-1], event_id='new-seal', sequence=len(f.events)+1)
        self.assertEqual(append(f.conn, f.tenant, newer), 'ACCEPTED')
        self.assert_rejected((f.tenant, f.session, self.request, f.seal, newer.sequence), 'SEAL_SNAPSHOT_CHANGED')
        self.assertEqual(self.receipts(), [])

    def test_request_cannot_be_reused_for_different_snapshot(self):
        f = self.fixture
        self.assertEqual(self.record(), 'RECORDED')
        note = replace(f.events[-1], event_id='review-note', sequence=len(f.events)+1, kind='REVIEW_RECORDED',
                       payload_json='{"artifact_ids":["front"],"disposition":"NOTE_ONLY","schema_version":"0.1"}')
        self.assertEqual(append(f.conn, f.tenant, note), 'ACCEPTED')
        self.assert_rejected((f.tenant, f.session, self.request, f.seal, note.sequence), 'RECEIPT_CONFLICT')
        self.assertEqual(self.receipts(), [(self.request, f.seal, len(f.events), 'faos_writer')])

    def test_other_tenant_cannot_read_receipt(self):
        self.assertEqual(self.record(), 'RECORDED')
        self.assertEqual(self.receipts(str(uuid.uuid4())), [])
        self.assertEqual(len(self.receipts()), 1)

    def test_missing_context_rejected(self):
        self.assert_rejected(self.values(), 'TENANT_CONTEXT_MISMATCH', context=False)
        self.assertEqual(self.receipts(), [])

if __name__ == '__main__':
    unittest.main()
