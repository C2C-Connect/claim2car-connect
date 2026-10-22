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


class TestConcurrentJournal(unittest.TestCase):
    """Two synchronized connection attempts, not exhaustive concurrency or crash proof."""
    def setUp(self):
        from app.domain_events import DomainEvent
        from database.journal import tenant_transaction
        self.url = os.getenv('APP_DATABASE_URL', 'postgresql://faos_app:synthetic-app-only@127.0.0.1:55432/claim2car_test')
        self.tenant = str(uuid.uuid4())
        self.session = 'concurrent-' + uuid.uuid4().hex
        self.event = DomainEvent(self.session, 'event-1', 1, 'SESSION_CREATED', 'synthetic-test',
                                 '2026-10-19T00:00:00Z', 'concurrent fixture', '{"synthetic":true}')
        with psycopg.connect(self.url, autocommit=True, connect_timeout=5) as conn:
            role = conn.execute('SELECT current_user,rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user').fetchone()
            self.assertEqual(role, ('faos_app', False, False))
            with tenant_transaction(conn, self.tenant):
                conn.execute('INSERT INTO faos.organizations(tenant_id,name) VALUES (%s,%s)', (self.tenant, 'synthetic concurrency fixture'))
                conn.execute('INSERT INTO faos.sessions(tenant_id,session_id) VALUES (%s,%s)', (self.tenant, self.session))

    def race(self, first, second):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from database.journal import append
        barrier = Barrier(2, timeout=10)
        def writer(event):
            with psycopg.connect(self.url, autocommit=True, connect_timeout=5) as conn:
                conn.execute("SET default_transaction_isolation = 'read committed'")
                conn.execute("SET statement_timeout = '8s'")
                conn.execute("SET lock_timeout = '5s'")
                barrier.wait()
                try:
                    return ('OK', append(conn, self.tenant, event), event.reason)
                except psycopg.errors.RaiseException as error:
                    return ('ERROR', error.sqlstate, error.diag.message_primary)
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(writer, event) for event in (first, second)]
            return [future.result(timeout=20) for future in futures]

    def test_identical_concurrent_retry_stores_one_event(self):
        from database.readback import load_journal
        results = self.race(self.event, self.event)
        self.assertCountEqual([r[:2] for r in results], [('OK', 'ACCEPTED'), ('OK', 'DUPLICATE')])
        with psycopg.connect(self.url, autocommit=True, connect_timeout=5) as conn:
            self.assertEqual(load_journal(conn, self.tenant, self.session).events, (self.event,))

    def assert_conflicting_race(self, other, error):
        from dataclasses import replace
        from database.journal import append
        from database.readback import load_journal
        results = self.race(self.event, other)
        self.assertCountEqual([r[:2] for r in results], [('OK', 'ACCEPTED'), ('ERROR', 'P0001')])
        self.assertEqual([r[2] for r in results if r[0] == 'ERROR'], [error])
        with psycopg.connect(self.url, autocommit=True, connect_timeout=5) as conn:
            before = load_journal(conn, self.tenant, self.session).events
            self.assertEqual(len(before), 1)
            self.assertIn(before[0], (self.event, other))
            self.assertEqual([r[2] for r in results if r[0] == 'OK'], [before[0].reason])
            following = replace(self.event, event_id='event-next', sequence=2, kind='CONSENT_RECORDED',
                                payload_json='{"disclosure_version":"synthetic-v1","evidence_scope":true}')
            self.assertEqual(append(conn, self.tenant, following), 'ACCEPTED')
            self.assertEqual(load_journal(conn, self.tenant, self.session).events, before + (following,))

    def test_conflicting_concurrent_retry_rejects_changed_event(self):
        from dataclasses import replace
        self.assert_conflicting_race(replace(self.event, reason='different concurrent content'), 'CONFLICTING_EVENT_DUPLICATE')

    def test_competing_sequence_rejects_one_writer(self):
        from dataclasses import replace
        self.assert_conflicting_race(replace(self.event, event_id='event-competitor', reason='competing writer'), 'SEQUENCE_CONFLICT')


if __name__ == '__main__':
    unittest.main()
