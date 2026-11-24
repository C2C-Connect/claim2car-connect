"""Full synthetic evidence evaluation while holding the database session lock."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import os
import unittest
import uuid
import psycopg
from database.journal import append, tenant_transaction
from database.readback import locked_journal
from app.synthetic_evidence import check_completion
from tenant_login import TenantLogin

class LockedEvaluationTests(unittest.TestCase):
    def setUp(self):
        import test_completion_coverage as fixtures
        self.events, self.data, self.digest = fixtures.CompletionCoverage().fixture()
        self.session = self.events[0].session_id
        self.tenant, self.other = str(uuid.uuid4()), str(uuid.uuid4())
        self.login = TenantLogin(self.tenant, organization_name='synthetic locked evaluation')
        self.other_login = TenantLogin(self.other, organization_name='synthetic other tenant')
        self.addCleanup(self.login.close)
        self.addCleanup(self.other_login.close)
        self.url = self.login.url
        self.conn = self.login.connect(autocommit=True)
        self.other_conn = self.other_login.connect(autocommit=True)
        self.addCleanup(self.conn.close)
        self.addCleanup(self.other_conn.close)
        with tenant_transaction(self.conn, self.tenant):
            self.conn.execute('INSERT INTO faos.sessions(tenant_id,session_id) VALUES (%s,%s)', (self.tenant, self.session))
        for event in self.events:
            self.assertEqual(append(self.conn, self.tenant, event), 'ACCEPTED')
        self.revocation = replace(self.events[1], event_id='revoke-consent', sequence=len(self.events)+1,
                                  payload_json='{"disclosure_version":"synthetic-v1","evidence_scope":false}')

    def blocked_revocation(self):
        with psycopg.connect(self.url, autocommit=True, connect_timeout=5) as conn:
            conn.execute("SET lock_timeout='200ms'")
            conn.execute("SET statement_timeout='3s'")
            try:
                append(conn, self.tenant, self.revocation)
            except psycopg.errors.LockNotAvailable as error:
                return error.sqlstate
            raise AssertionError('REVOCATION_WAS_NOT_SERIALIZED')

    def append_revocation_after_release(self):
        with psycopg.connect(self.url, autocommit=True, connect_timeout=5) as conn:
            conn.execute("SET lock_timeout='1s'")
            conn.execute("SET statement_timeout='3s'")
            self.assertEqual(append(conn, self.tenant, self.revocation), 'ACCEPTED')

    def test_full_evaluation_serializes_consent_change(self):
        with locked_journal(self.conn, self.tenant, self.session) as journal:
            self.assertEqual(journal.events, self.events)
            self.assertEqual(check_completion(self.session, journal.events, self.data, self.digest).status, 'ELIGIBLE')
            with ThreadPoolExecutor(max_workers=1) as pool:
                self.assertEqual(pool.submit(self.blocked_revocation).result(timeout=10), '55P03')
        self.assertIsNone(self.conn.execute('SELECT faos.tenant_id()').fetchone()[0])
        self.append_revocation_after_release()
        with self.assertRaisesRegex(ValueError, 'REQUIRED_CONSENT_MISSING'):
            with locked_journal(self.conn, self.tenant, self.session) as journal:
                check_completion(self.session, journal.events, self.data, self.digest)
        self.assertIsNone(self.conn.execute('SELECT faos.tenant_id()').fetchone()[0])

    def test_caller_exception_releases_lock_and_context(self):
        with self.assertRaisesRegex(RuntimeError, '^synthetic evaluation failure$'):
            with locked_journal(self.conn, self.tenant, self.session) as journal:
                self.assertEqual(journal.events, self.events)
                raise RuntimeError('synthetic evaluation failure')
        self.assertIsNone(self.conn.execute('SELECT faos.tenant_id()').fetchone()[0])
        self.append_revocation_after_release()

    def test_other_tenant_cannot_enter_locked_read(self):
        with self.assertRaises(psycopg.errors.RaiseException) as caught:
            with locked_journal(self.other_conn, self.other, self.session):
                self.fail('other tenant entered locked read')
        self.assertEqual(caught.exception.sqlstate, 'P0001')
        self.assertEqual(caught.exception.diag.message_primary, 'SESSION_NOT_FOUND')
        self.assertIsNone(self.conn.execute('SELECT faos.tenant_id()').fetchone()[0])
        with locked_journal(self.conn, self.tenant, self.session) as journal:
            self.assertEqual(journal.events, self.events)

if __name__ == '__main__':
    unittest.main()
