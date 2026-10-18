import os
import unittest
import uuid

import psycopg


class TestAccessHardening(unittest.TestCase):
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
        self.tenant = str(uuid.uuid4())
        self.session = 'access-' + uuid.uuid4().hex
        self.conn.execute("SELECT set_config('faos.tenant_id', %s, true)", (self.tenant,))
        self.conn.execute(
            'INSERT INTO faos.organizations(tenant_id, name) VALUES (%s, %s)',
            (self.tenant, 'synthetic access fixture'),
        )
        self.conn.execute(
            'INSERT INTO faos.sessions(tenant_id, session_id) VALUES (%s, %s)',
            (self.tenant, self.session),
        )
        self.assertEqual(self.append_event('event-1', 1), 'ACCEPTED')

    def append_event(self, event_id, sequence):
        return self.conn.execute(
            'SELECT faos.append_event(%s::uuid, %s::text, %s::text, '
            '%s::bigint, %s::text, %s::text, %s::text, %s::text, '
            '%s::text, %s::text)',
            (self.tenant, self.session, event_id, sequence, 'SESSION_CREATED',
             'synthetic-test', '2026-01-01T00:00:00Z',
             'access hardening', '{}', '0.1'),
        ).fetchone()[0]

    def history(self):
        return self.conn.execute(
            'SELECT event_id, sequence, kind, actor, occurred_at, reason, '
            'payload_json, schema_version FROM faos.events '
            'WHERE tenant_id = %s AND session_id = %s ORDER BY sequence',
            (self.tenant, self.session),
        ).fetchall()

    def assert_direct_write_denied(self, sql, params):
        before = self.history()
        self.assertEqual(len(before), 1)
        with self.assertRaises(psycopg.errors.InsufficientPrivilege) as caught:
            with self.conn.transaction():
                self.conn.execute(sql, params)
        self.assertEqual(caught.exception.sqlstate, '42501')
        self.assertEqual(self.history(), before)
        self.assertEqual(self.append_event('event-2', 2), 'ACCEPTED')
        after = self.history()
        self.assertEqual(len(after), 2)
        self.assertEqual(after[0], before[0])
        self.assertEqual(after[1][0:2], ('event-2', 2))

    def test_direct_event_insert_denied(self):
        self.assert_direct_write_denied(
            'INSERT INTO faos.events '
            '(tenant_id, session_id, event_id, sequence, kind, actor, '
            'occurred_at, reason, payload_json, schema_version) '
            'SELECT tenant_id, session_id, %s, 2, kind, actor, occurred_at, '
            'reason, payload_json, schema_version FROM faos.events '
            'WHERE tenant_id = %s AND session_id = %s AND event_id = %s',
            ('direct-event', self.tenant, self.session, 'event-1'),
        )

    def test_direct_event_update_denied(self):
        self.assert_direct_write_denied(
            'UPDATE faos.events SET reason = %s '
            'WHERE tenant_id = %s AND session_id = %s AND event_id = %s',
            ('unauthorized change', self.tenant, self.session, 'event-1'),
        )

    def test_direct_event_delete_denied(self):
        self.assert_direct_write_denied(
            'DELETE FROM faos.events '
            'WHERE tenant_id = %s AND session_id = %s AND event_id = %s',
            (self.tenant, self.session, 'event-1'),
        )


if __name__ == '__main__':
    unittest.main()
