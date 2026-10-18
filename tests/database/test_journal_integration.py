import os
import unittest
import uuid

import psycopg


class TestJournalIntegration(unittest.TestCase):
    def setUp(self):
        self.conn = psycopg.connect(os.getenv(
            'APP_DATABASE_URL',
            'postgresql://faos_app:synthetic-app-only@127.0.0.1:55432/claim2car_test',
        ))
        self.addCleanup(self.conn.close)
        self.addCleanup(self.conn.rollback)
        self.tenant = str(uuid.uuid4())
        self.session = 'journal-' + uuid.uuid4().hex
        self.conn.execute("SELECT set_config('faos.tenant_id', %s, true)", (self.tenant,))
        self.conn.execute(
            'INSERT INTO faos.organizations(tenant_id, name) VALUES (%s, %s)',
            (self.tenant, 'synthetic journal integration'),
        )
        self.conn.execute(
            'INSERT INTO faos.sessions(tenant_id, session_id) VALUES (%s, %s)',
            (self.tenant, self.session),
        )
        self.assertEqual(self.append_event('event-1', 1), 'ACCEPTED')

    def append_event(self, event_id, sequence, payload='{}'):
        return self.conn.execute(
            'SELECT faos.append_event(%s::uuid, %s::text, %s::text, '
            '%s::bigint, %s::text, %s::text, %s::text, %s::text, '
            '%s::text, %s::text)',
            (self.tenant, self.session, event_id, sequence, 'SESSION_CREATED',
             'synthetic-test', '2026-01-01T00:00:00Z',
             'journal integration', payload, '0.1'),
        ).fetchone()[0]

    def history(self):
        return self.conn.execute(
            'SELECT event_id, sequence, kind, actor, occurred_at, reason, '
            'payload_json, schema_version FROM faos.events '
            'WHERE tenant_id = %s AND session_id = %s ORDER BY sequence',
            (self.tenant, self.session),
        ).fetchall()

    def assert_rejected(self, event_id, sequence, message, payload='{}'):
        with self.assertRaises(psycopg.errors.RaiseException) as caught:
            with self.conn.transaction():
                self.append_event(event_id, sequence, payload)
        self.assertEqual(caught.exception.sqlstate, 'P0001')
        self.assertEqual(caught.exception.diag.message_primary, message)

    def test_duplicate_is_idempotent_and_conflicting_duplicate_preserves_history(self):
        before = self.history()
        self.assertEqual(len(before), 1)
        self.assertEqual(before[0][0:2], ('event-1', 1))
        self.assertEqual(self.append_event('event-1', 1), 'DUPLICATE')
        self.assertEqual(self.history(), before)
        self.assert_rejected(
            'event-1', 1, 'CONFLICTING_EVENT_DUPLICATE', '{"changed":true}'
        )
        self.assertEqual(self.history(), before)

    def test_sequence_conflicts_preserve_history_and_allow_next_valid_append(self):
        before = self.history()
        self.assertEqual(len(before), 1)
        self.assert_rejected('event-2', 1, 'SEQUENCE_CONFLICT')
        self.assertEqual(self.history(), before)
        self.assert_rejected('event-2', 3, 'SEQUENCE_CONFLICT')
        self.assertEqual(self.history(), before)
        self.assertEqual(self.append_event('event-2', 2), 'ACCEPTED')
        after = self.history()
        self.assertEqual(len(after), 2)
        self.assertEqual(after[0], before[0])
        self.assertEqual(after[1][0:2], ('event-2', 2))


if __name__ == '__main__':
    unittest.main()
