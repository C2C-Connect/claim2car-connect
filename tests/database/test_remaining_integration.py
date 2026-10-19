"""Session/event SELECT isolation; not complete tenant-security acceptance."""
import os
import unittest
import uuid

import psycopg


class TestRemainingIntegration(unittest.TestCase):
    def setUp(self):
        self.conn = psycopg.connect(os.getenv(
            'APP_DATABASE_URL',
            'postgresql://faos_app:synthetic-app-only@127.0.0.1:55432/claim2car_test',
        ))
        self.addCleanup(self.conn.close)
        self.addCleanup(self.conn.rollback)
        role = self.conn.execute(
            'SELECT current_user, rolsuper, rolbypassrls FROM pg_roles '
            'WHERE rolname = current_user'
        ).fetchone()
        self.assertEqual(role, ('faos_app', False, False))
        self.tenants = (str(uuid.uuid4()), str(uuid.uuid4()))
        self.session = 'isolation-' + uuid.uuid4().hex
        for tenant in self.tenants:
            self.set_context(tenant)
            self.conn.execute(
                'INSERT INTO faos.organizations(tenant_id, name) VALUES (%s, %s)',
                (tenant, 'synthetic isolation fixture'),
            )
            self.conn.execute(
                'INSERT INTO faos.sessions(tenant_id, session_id) VALUES (%s, %s)',
                (tenant, self.session),
            )
            outcome = self.conn.execute(
                'SELECT faos.append_event(%s::uuid, %s::text, %s::text, '
                '%s::bigint, %s::text, %s::text, %s::text, %s::text, '
                '%s::text, %s::text)',
                (tenant, self.session, 'event-1', 1, 'SESSION_CREATED',
                 'synthetic-test', '2026-01-01T00:00:00Z',
                 'tenant isolation', '{}', '0.1'),
            ).fetchone()[0]
            self.assertEqual(outcome, 'ACCEPTED')

    def set_context(self, tenant):
        self.conn.execute(
            "SELECT set_config('faos.tenant_id', %s, true)", (tenant,)
        )

    def sessions(self):
        return self.conn.execute(
            'SELECT tenant_id::text, session_id FROM faos.sessions '
            'WHERE session_id = %s', (self.session,)
        ).fetchall()

    def events(self):
        return self.conn.execute(
            'SELECT tenant_id::text, session_id, event_id, sequence '
            'FROM faos.events WHERE session_id = %s', (self.session,)
        ).fetchall()

    def assert_own_rows_only(self, tenant):
        self.assertEqual(self.sessions(), [(tenant, self.session)])
        self.assertEqual(self.events(), [(tenant, self.session, 'event-1', 1)])

    def test_switching_context_limits_reads_without_tenant_predicates(self):
        for tenant in (self.tenants[0], self.tenants[1], self.tenants[0]):
            with self.subTest(tenant=tenant):
                self.set_context(tenant)
                self.assert_own_rows_only(tenant)

    def test_cleared_context_exposes_neither_tenants_rows(self):
        for tenant in self.tenants:
            with self.subTest(tenant=tenant):
                self.set_context(tenant)
                self.assert_own_rows_only(tenant)
                self.set_context('')
                self.assertIsNone(
                    self.conn.execute('SELECT faos.tenant_id()').fetchone()[0]
                )
                self.assertEqual(self.sessions(), [])
                self.assertEqual(self.events(), [])
                self.set_context(tenant)
                self.assert_own_rows_only(tenant)

    def seed_users(self):
        user = str(uuid.uuid4())
        for tenant in self.tenants:
            self.set_context(tenant)
            self.conn.execute('INSERT INTO faos.users(tenant_id,user_id,external_subject) VALUES (%s,%s,%s)',
                              (tenant, user, 'synthetic-' + tenant))
        return user

    def test_cross_tenant_user_insert_denied(self):
        own, other = self.tenants
        user = str(uuid.uuid4())
        self.set_context(own)
        with self.assertRaises(psycopg.errors.InsufficientPrivilege) as caught:
            with self.conn.transaction():
                self.conn.execute('INSERT INTO faos.users(tenant_id,user_id,external_subject) VALUES (%s,%s,%s)',
                                  (other, user, 'attempt-' + user))
        self.assertEqual(caught.exception.sqlstate, '42501')
        self.set_context(other)
        self.assertEqual(self.conn.execute('SELECT count(*) FROM faos.users WHERE user_id=%s', (user,)).fetchone()[0], 0)
        self.set_context(own)
        result = self.conn.execute('INSERT INTO faos.users(tenant_id,user_id,external_subject) VALUES (%s,%s,%s)',
                                   (own, user, 'own-' + user))
        self.assertEqual(result.rowcount, 1)

    def test_cross_tenant_user_update_affects_no_rows(self):
        user = self.seed_users()
        own, other = self.tenants
        self.set_context(own)
        denied = self.conn.execute('UPDATE faos.users SET external_subject=%s WHERE tenant_id=%s AND user_id=%s',
                                   ('tampered', other, user))
        self.assertEqual(denied.rowcount, 0)
        allowed = self.conn.execute('UPDATE faos.users SET external_subject=%s WHERE tenant_id=%s AND user_id=%s',
                                    ('own-updated', own, user))
        self.assertEqual(allowed.rowcount, 1)
        self.assertEqual(self.conn.execute('SELECT external_subject FROM faos.users WHERE user_id=%s', (user,)).fetchall(), [('own-updated',)])
        self.set_context(other)
        self.assertEqual(self.conn.execute('SELECT external_subject FROM faos.users WHERE user_id=%s', (user,)).fetchall(), [('synthetic-' + other,)])

    def test_cross_tenant_user_delete_affects_no_rows(self):
        user = self.seed_users()
        own, other = self.tenants
        self.set_context(own)
        denied = self.conn.execute('DELETE FROM faos.users WHERE tenant_id=%s AND user_id=%s', (other, user))
        self.assertEqual(denied.rowcount, 0)
        allowed = self.conn.execute('DELETE FROM faos.users WHERE tenant_id=%s AND user_id=%s', (own, user))
        self.assertEqual(allowed.rowcount, 1)
        self.assertEqual(self.conn.execute('SELECT count(*) FROM faos.users WHERE user_id=%s', (user,)).fetchone()[0], 0)
        self.set_context(other)
        self.assertEqual(self.conn.execute('SELECT external_subject FROM faos.users WHERE user_id=%s', (user,)).fetchall(), [('synthetic-' + other,)])

    def test_missing_context_user_insert_denied(self):
        own = self.tenants[0]
        user = str(uuid.uuid4())
        self.set_context('')
        with self.assertRaises(psycopg.errors.InsufficientPrivilege) as caught:
            with self.conn.transaction():
                self.conn.execute('INSERT INTO faos.users(tenant_id,user_id,external_subject) VALUES (%s,%s,%s)',
                                  (own, user, 'missing-context-' + user))
        self.assertEqual(caught.exception.sqlstate, '42501')
        self.set_context(own)
        self.assertEqual(self.conn.execute('SELECT count(*) FROM faos.users WHERE user_id=%s', (user,)).fetchone()[0], 0)


if __name__ == '__main__':
    unittest.main()
