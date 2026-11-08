from dataclasses import FrozenInstanceError, replace
import unittest
from app.domain_events import DomainEvent, EventJournal

class EventContractRegression(unittest.TestCase):
    def setUp(self):
        self.event = DomainEvent('synthetic-session', 'event-1', 1, 'SESSION_CREATED', 'synthetic-test', '2026-01-01T00:00:00Z', 'contract regression', '{}')

    def test_valid_history_reconstructs_independent_journal(self):
        second = replace(self.event, event_id='event-2', sequence=2, kind='CONSENT_RECORDED')
        source = [self.event, second]
        journal = EventJournal.replay(self.event.session_id, source)
        source.clear()
        self.assertEqual(journal.events, (self.event, second))
        self.assertIsNot(journal, EventJournal.replay(self.event.session_id, journal.events))

    def test_identical_retry_is_not_appended_twice(self):
        journal = EventJournal(self.event.session_id)
        self.assertEqual(journal.append(self.event), 'ACCEPTED')
        self.assertEqual(journal.append(self.event), 'DUPLICATE')
        self.assertEqual(journal.events, (self.event,))

    def test_conflicting_retry_rejected_without_mutation(self):
        journal = EventJournal.replay(self.event.session_id, [self.event])
        with self.assertRaisesRegex(ValueError, '^CONFLICTING_EVENT_DUPLICATE$'):
            journal.append(replace(self.event, reason='conflict'))
        self.assertEqual(journal.events, (self.event,))

    def test_duplicate_history_rejected(self):
        with self.assertRaisesRegex(ValueError, '^DUPLICATE_IN_HISTORY$'):
            EventJournal.replay(self.event.session_id, [self.event, self.event])

    def test_cross_session_history_rejected(self):
        with self.assertRaisesRegex(ValueError, '^CROSS_SESSION_REFERENCE$'):
            EventJournal.replay('another-session', [self.event])

    def test_gap_rejected_without_mutation(self):
        journal = EventJournal(self.event.session_id)
        with self.assertRaisesRegex(ValueError, '^SEQUENCE_CONFLICT$'):
            journal.append(replace(self.event, sequence=2))
        self.assertEqual(journal.events, ())

    def test_invalid_contract_fields(self):
        cases = [
            ({'schema_version': 'unsupported'}, 'UNSUPPORTED_SCHEMA'),
            ({'actor': ' '}, 'MISSING_CONTEXT'),
            ({'sequence': True}, 'INVALID_SEQUENCE'),
            ({'sequence': 0}, 'INVALID_SEQUENCE'),
            ({'kind': 'UNKNOWN'}, 'INVALID_EVENT_KIND'),
            ({'occurred_at': None}, 'INVALID_TIMESTAMP'),
            ({'occurred_at': 123}, 'INVALID_TIMESTAMP'),
            ({'occurred_at': ''}, 'INVALID_TIMESTAMP'),
            ({'occurred_at': 'not-a-timestamp'}, 'INVALID_TIMESTAMP'),
            ({'occurred_at': '2026-01-01T00:00:00'}, 'INVALID_TIMESTAMP'),
            ({'payload_json': '{'}, 'INVALID_PAYLOAD'),
            ({'payload_json': None}, 'INVALID_PAYLOAD'),
            ({'payload_json': '{"a": 1}'}, 'NONCANONICAL_PAYLOAD'),
            ({'payload_json': '[]'}, 'NONCANONICAL_PAYLOAD'),
            ({'payload_json': '{"a":NaN}'}, 'INVALID_PAYLOAD'),
        ]
        for changes, error in cases:
            with self.subTest(changes=changes):
                with self.assertRaisesRegex(ValueError, '^' + error + '$'):
                    replace(self.event, **changes).validate()

    def test_event_is_frozen_and_payload_read_is_independent(self):
        with self.assertRaises(FrozenInstanceError):
            self.event.reason = 'changed'
        payload = self.event.payload
        payload['injected'] = True
        self.assertEqual(self.event.payload, {})


class DurableTimestampRegression(unittest.TestCase):
    """SQL input-validity boundary; not complete timestamp-contract parity."""
    def setUp(self):
        import test_journal_integration as fixtures
        self.fixture = fixtures.TestJournalIntegration()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.setUp()
        self.conn = self.fixture.conn

    def append_at(self, timestamp):
        f = self.fixture
        return self.conn.execute(
            'SELECT faos.append_event(%s::uuid,%s::text,%s::text,%s::bigint,%s::text,%s::text,%s::text,%s::text,%s::text,%s::text)',
            (f.tenant,f.session,'timestamp-event',2,'SESSION_CREATED','synthetic-test',timestamp,'timestamp SQL regression','{}','0.1'),
        ).fetchone()[0]

    def test_malformed_timestamp_rejected_without_history_mutation(self):
        import psycopg
        before = self.fixture.history()
        for timestamp in ('not-a-timestamp','2026-02-30T00:00:00Z',''):
            with self.subTest(timestamp=timestamp):
                with self.assertRaises(psycopg.errors.CheckViolation) as caught:
                    with self.conn.transaction():
                        self.append_at(timestamp)
                        raise AssertionError('INVALID_TIMESTAMP_ACCEPTED')
                self.assertEqual(caught.exception.sqlstate,'23514')
                self.assertEqual(caught.exception.diag.constraint_name,'event_timestamp_input_valid')
                self.assertEqual(self.fixture.history(),before)
        self.assertEqual(self.append_at('2026-01-01T00:00:00Z'),'ACCEPTED')
        self.assertEqual(self.append_at('2026-01-01T00:00:00Z'),'DUPLICATE')
        self.assertEqual(len(self.fixture.history()),len(before)+1)

    def test_offset_timestamp_round_trips_exact_text(self):
        timestamp = '2026-01-01T00:00:00+05:30'
        self.assertEqual(self.append_at(timestamp),'ACCEPTED')
        self.assertEqual(self.fixture.history()[-1][4],timestamp)


if __name__ == '__main__':
    unittest.main()


class DirectSqlCanonicalParityRegression(unittest.TestCase):
    """Expected-failure probes until PostgreSQL enforces the Python event contract.

    These use the restricted faos_app role and the real append function.  The
    expectedFailure markers are intentional: each probe must become a normal
    passing test when the database rejects the noncanonical input.  An
    unexpected success then fails CI and forces removal of the marker.
    """

    def setUp(self):
        import test_journal_integration as fixtures
        self.fixture = fixtures.TestJournalIntegration()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.setUp()
        self.conn = self.fixture.conn
        self.before = self.fixture.history()

    def assert_direct_sql_rejected_without_mutation(self, event_id, timestamp, payload):
        import psycopg
        f = self.fixture
        with self.assertRaises(psycopg.errors.CheckViolation):
            with self.conn.transaction():
                self.conn.execute(
                    'SELECT faos.append_event(%s::uuid,%s::text,%s::text,%s::bigint,'
                    '%s::text,%s::text,%s::text,%s::text,%s::text,%s::text)',
                    (f.tenant, f.session, event_id, 2, 'SESSION_CREATED',
                     'synthetic-direct-sql-probe', timestamp, 'canonical parity probe',
                     payload, '0.1'),
                )
        self.assertEqual(f.history(), self.before)

    @unittest.expectedFailure
    def test_direct_sql_rejects_timezone_naive_timestamp(self):
        self.assert_direct_sql_rejected_without_mutation(
            'naive-timestamp', '2026-01-01T00:00:00', '{}'
        )

    @unittest.expectedFailure
    def test_direct_sql_rejects_noncanonical_key_order(self):
        self.assert_direct_sql_rejected_without_mutation(
            'unordered-keys', '2026-01-01T00:00:00Z', '{"z":1,"a":2}'
        )

    @unittest.expectedFailure
    def test_direct_sql_rejects_noncanonical_unicode_representation(self):
        self.assert_direct_sql_rejected_without_mutation(
            'unicode-literal', '2026-01-01T00:00:00Z', '{"label":"é"}'
        )

    @unittest.expectedFailure
    def test_direct_sql_rejects_noncanonical_numeric_spelling(self):
        self.assert_direct_sql_rejected_without_mutation(
            'numeric-exponent', '2026-01-01T00:00:00Z', '{"value":1e0}'
        )

    def test_direct_sql_valid_event_round_trips_exact_payload_bytes(self):
        f = self.fixture
        payload = '{"a":1,"z":"é"}'
        self.assertEqual(
            f.append_event('canonical-positive-control', 2, payload), 'ACCEPTED'
        )
        row = self.conn.execute(
            'SELECT payload_json FROM faos.events '
            'WHERE tenant_id=%s AND session_id=%s AND event_id=%s',
            (f.tenant, f.session, 'canonical-positive-control'),
        ).fetchone()
        self.assertEqual(row[0], payload)
        from app.domain_events import DomainEvent, EventJournal
        event = DomainEvent(
            f.session, 'canonical-positive-control', 2, 'SESSION_CREATED',
            'synthetic-test', '2026-01-01T00:00:00Z',
            'canonical positive control', payload,
        )
        self.assertEqual(EventJournal.replay(f.session, (self._first_event(), event)).events[-1], event)

    def _first_event(self):
        from app.domain_events import DomainEvent
        f = self.fixture
        return DomainEvent(
            f.session, 'event-1', 1, 'SESSION_CREATED', 'synthetic-test',
            '2026-01-01T00:00:00Z', 'journal integration', '{}',
        )
