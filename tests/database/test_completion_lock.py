"""Transaction-lock tests with distinct tenant-bound identities."""
from concurrent.futures import ThreadPoolExecutor
import unittest
import uuid
import psycopg
from app.domain_events import DomainEvent
from database.journal import append, tenant_transaction
from database.readback import load_journal
from tenant_login import TenantLogin


class CompletionLockTests(unittest.TestCase):
    def setUp(self):
        self.tenant, self.other = str(uuid.uuid4()), str(uuid.uuid4())
        self.login = TenantLogin(self.tenant, organization_name='synthetic completion lock')
        self.other_login = TenantLogin(self.other, organization_name='synthetic other tenant')
        self.addCleanup(self.login.close)
        self.addCleanup(self.other_login.close)
        self.conn = self.login.connect(autocommit=True)
        self.other_conn = self.other_login.connect(autocommit=True)
        self.addCleanup(self.conn.close)
        self.addCleanup(self.other_conn.close)
        self.session = 'completion-lock-' + uuid.uuid4().hex
        self.event = DomainEvent(self.session, 'event-1', 1, 'SESSION_CREATED', 'synthetic-test',
                                 '2026-10-19T00:00:00Z', 'completion lock fixture', '{"synthetic":true}')
        with tenant_transaction(self.conn, self.tenant):
            self.conn.execute('INSERT INTO faos.sessions(tenant_id,session_id) VALUES (%s,%s)', (self.tenant, self.session))

    def lock(self, conn, tenant, session):
        return conn.execute('SELECT faos.lock_session_for_completion(%s::uuid,%s::text)', (tenant, session))

    def blocked_writer(self):
        with psycopg.connect(self.login.url, autocommit=True, connect_timeout=5) as conn:
            conn.execute("SET lock_timeout='200ms'")
            conn.execute("SET statement_timeout='3s'")
            try:
                append(conn, self.tenant, self.event)
            except psycopg.errors.LockNotAvailable as error:
                return error.sqlstate
            raise AssertionError('WRITER_DID_NOT_BLOCK_ON_HELD_SESSION_LOCK')

    def assert_writer_blocked(self):
        with ThreadPoolExecutor(max_workers=1) as pool:
            self.assertEqual(pool.submit(self.blocked_writer).result(timeout=10), '55P03')

    def assert_append_after_release(self):
        self.assertEqual(append(self.conn, self.tenant, self.event), 'ACCEPTED')
        self.assertEqual(load_journal(self.conn, self.tenant, self.session).events, (self.event,))

    def test_lock_serializes_append_until_commit(self):
        with tenant_transaction(self.conn, self.tenant):
            self.lock(self.conn, self.tenant, self.session)
            self.assert_writer_blocked()
        self.assert_append_after_release()

    def test_lock_released_after_rollback(self):
        with self.assertRaisesRegex(RuntimeError, '^synthetic rollback$'):
            with tenant_transaction(self.conn, self.tenant):
                self.lock(self.conn, self.tenant, self.session)
                self.assert_writer_blocked()
                raise RuntimeError('synthetic rollback')
        self.assert_append_after_release()

    def assert_rejection(self, conn, context, parameter, session, message):
        with self.assertRaises(psycopg.errors.RaiseException) as caught:
            with tenant_transaction(conn, context):
                self.lock(conn, parameter, session)
        self.assertEqual(caught.exception.sqlstate, 'P0001')
        self.assertEqual(caught.exception.diag.message_primary, message)

    def test_mismatched_tenant_rejected(self):
        self.assert_rejection(self.conn, self.tenant, self.other, self.session, 'TENANT_CONTEXT_MISMATCH')

    def test_other_tenant_session_not_visible(self):
        self.assert_rejection(self.other_conn, self.other, self.other, self.session, 'SESSION_NOT_FOUND')

    def test_missing_session_rejected(self):
        self.assert_rejection(self.conn, self.tenant, self.tenant, self.session + '-missing', 'SESSION_NOT_FOUND')

    def test_missing_context_rejected(self):
        with self.assertRaises(psycopg.errors.RaiseException) as caught:
            with self.conn.transaction():
                self.lock(self.conn, self.tenant, self.session)
        self.assertEqual(caught.exception.sqlstate, 'P0001')
        self.assertEqual(caught.exception.diag.message_primary, 'TENANT_CONTEXT_MISMATCH')


if __name__ == '__main__':
    unittest.main()
