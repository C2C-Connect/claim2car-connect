from dataclasses import FrozenInstanceError, replace
import unittest
from app.domain_events import DomainEvent, EventJournal


class EventContractRegression(unittest.TestCase):
    def setUp(self):
        self.event = DomainEvent(
            'synthetic-session', 'event-1', 1, 'SESSION_CREATED',
            'synthetic-test', '2026-01-01T00:00:00Z',
            'contract regression', '{}',
        )

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
            ({'occurred_at': '2026-01-01 00:00:00Z'}, 'INVALID_TIMESTAMP'),
            ({'occurred_at': '2026-01-01T00:00:00.1234567Z'}, 'INVALID_TIMESTAMP'),
            ({'occurred_at': '2026-02-30T00:00:00Z'}, 'INVALID_TIMESTAMP'),
            ({'payload_json': '{'}, 'INVALID_PAYLOAD'),
            ({'payload_json': None}, 'INVALID_PAYLOAD'),
            ({'payload_json': '{"a": 1}'}, 'NONCANONICAL_PAYLOAD'),
            ({'payload_json': '[]'}, 'NONCANONICAL_PAYLOAD'),
            ({'payload_json': '{"a":NaN}'}, 'INVALID_PAYLOAD'),
            ({'payload_json': '{"value":1e0}'}, 'NONCANONICAL_PAYLOAD'),
        ]
        for changes, error in cases:
            with self.subTest(changes=changes):
                with self.assertRaisesRegex(ValueError, '^' + error + '$'):
                    replace(self.event, **changes).validate()

    def test_canonical_unicode_and_decimal_payload_uses_utf8_fixed_notation(self):
        event = replace(self.event, payload_json='{"label":"é","metric":0.00001}')
        self.assertIs(event.validate(), event)

    def test_event_is_frozen_and_payload_read_is_independent(self):
        with self.assertRaises(FrozenInstanceError):
            self.event.reason = 'changed'
        payload = self.event.payload
        payload['injected'] = True
        self.assertEqual(self.event.payload, {})


class DurableTimestampRegression(unittest.TestCase):
    """Database RFC3339 boundary; all probes use synthetic fixture rows."""
    def setUp(self):
        import test_journal_integration as fixtures
        self.fixture = fixtures.TestJournalIntegration()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.setUp()
        self.conn = self.fixture.conn
        present = self.conn.execute("SELECT 1 FROM pg_constraint WHERE conname='event_timestamp_rfc3339' AND conrelid='faos.events'::regclass").fetchone()
        if present is None:
            self.skipTest('RFC3339 SQL contract requires authority migration 0017; covered by migration-control integration')

    def append_at(self, timestamp):
        f = self.fixture
        return self.conn.execute(
            'SELECT faos.append_event(%s::uuid,%s::text,%s::text,%s::bigint,%s::text,%s::text,%s::text,%s::text,%s::text,%s::text)',
            (f.tenant,f.session,'timestamp-event',2,'SESSION_CREATED','synthetic-test',timestamp,'timestamp SQL regression','{}','0.1'),
        ).fetchone()[0]

    def test_non_rfc3339_timestamps_rejected_without_history_mutation(self):
        import psycopg
        before = self.fixture.history()
        for timestamp in (
            'not-a-timestamp',
            '2026-02-30T00:00:00Z',
            '2026-01-01T00:00:00',
            '2026-01-01 00:00:00Z',
            '2026-01-01T00:00:00.1234567Z',
        ):
            with self.subTest(timestamp=timestamp):
                with self.assertRaises(psycopg.errors.CheckViolation):
                    with self.conn.transaction():
                        self.append_at(timestamp)
                self.assertEqual(self.fixture.history(),before)
        self.assertEqual(self.append_at('2026-01-01T00:00:00Z'),'ACCEPTED')
        self.assertEqual(self.append_at('2026-01-01T00:00:00Z'),'DUPLICATE')
        self.assertEqual(len(self.fixture.history()),len(before)+1)

    def test_offset_timestamp_round_trips_exact_text(self):
        timestamp = '2026-01-01T00:00:00+05:30'
        self.assertEqual(self.append_at(timestamp),'ACCEPTED')
        self.assertEqual(self.fixture.history()[-1][4],timestamp)


class DirectSqlCanonicalParityRegression(unittest.TestCase):
    """Direct SQL must reject payloads Python cannot replay; no history mutation."""
    def setUp(self):
        import test_journal_integration as fixtures
        self.fixture = fixtures.TestJournalIntegration()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.setUp()
        self.conn = self.fixture.conn
        self.before = self.fixture.history()
        present = self.conn.execute("SELECT 1 FROM pg_constraint WHERE conname='event_payload_python_canonical' AND conrelid='faos.events'::regclass").fetchone()
        if present is None:
            self.skipTest('canonical SQL contract requires authority migration 0017; covered by migration-control integration')

    def append_direct(self, event_id, payload):
        f = self.fixture
        return self.conn.execute(
            'SELECT faos.append_event(%s::uuid,%s::text,%s::text,%s::bigint,'
            '%s::text,%s::text,%s::text,%s::text,%s::text,%s::text)',
            (f.tenant, f.session, event_id, 2, 'SESSION_CREATED',
             'synthetic-direct-sql-probe', '2026-01-01T00:00:00Z',
             'canonical parity probe', payload, '0.1'),
        ).fetchone()[0]

    def assert_payload_rejected_without_mutation(self, event_id, payload):
        import psycopg
        with self.assertRaises(psycopg.errors.CheckViolation):
            with self.conn.transaction():
                self.append_direct(event_id, payload)
        self.assertEqual(self.fixture.history(), self.before)

    def test_direct_sql_rejects_noncanonical_key_order(self):
        self.assert_payload_rejected_without_mutation('unordered-keys', '{"z":1,"a":2}')

    def test_direct_sql_rejects_noncanonical_numeric_exponent(self):
        self.assert_payload_rejected_without_mutation('numeric-exponent', '{"value":1e0}')

    def test_direct_sql_accepts_canonical_decimal_values_and_python_reads_them(self):
        from app.domain_events import DomainEvent
        f = self.fixture
        payload = '{"large":100000000000000000000,"small":0.00001,"value":1.25}'
        self.assertEqual(self.append_direct('canonical-decimals', payload), 'ACCEPTED')
        row = self.conn.execute(
            'SELECT session_id,event_id,sequence,kind,actor,occurred_at,reason,payload_json,schema_version '
            'FROM faos.events WHERE tenant_id=%s AND session_id=%s AND event_id=%s',
            (f.tenant, f.session, 'canonical-decimals'),
        ).fetchone()
        event = DomainEvent(*row).validate()
        self.assertEqual(event.payload['value'], 1.25)
        self.assertEqual(len(self.fixture.history()), len(self.before) + 1)

    def test_direct_sql_rejects_whitespace_outside_json_strings(self):
        self.assert_payload_rejected_without_mutation('spaced-json', '{ "a":1}')

    def test_direct_sql_accepts_utf8_canonical_payload_and_python_reads_it(self):
        from app.domain_events import DomainEvent
        f = self.fixture
        payload = '{"label":"é"}'
        self.assertEqual(self.append_direct('canonical-utf8', payload), 'ACCEPTED')
        row = self.conn.execute(
            'SELECT session_id,event_id,sequence,kind,actor,occurred_at,reason,payload_json,schema_version '
            'FROM faos.events WHERE tenant_id=%s AND session_id=%s AND event_id=%s',
            (f.tenant, f.session, 'canonical-utf8'),
        ).fetchone()
        self.assertEqual(DomainEvent(*row).validate().payload, {'label': 'é'})
        self.assertEqual(len(self.fixture.history()), len(self.before) + 1)

    def test_sql_and_python_share_the_complete_event_kind_allowlist(self):
        from app.domain_events import KINDS
        for index, kind in enumerate(sorted(KINDS), start=2):
            event_id = 'kind-' + str(index)
            result = self.conn.execute(
                'SELECT faos.append_event(%s::uuid,%s::text,%s::text,%s::bigint,%s::text,%s::text,%s::text,%s::text,%s::text,%s::text)',
                (self.fixture.tenant, self.fixture.session, event_id, index, kind,
                 'synthetic-kind-probe', '2026-01-01T00:00:00Z',
                 'event kind parity', '{}', '0.1'),
            ).fetchone()[0]
            self.assertEqual(result, 'ACCEPTED')
        rows = self.conn.execute(
            'SELECT kind FROM faos.events WHERE tenant_id=%s AND session_id=%s ORDER BY sequence',
            (self.fixture.tenant, self.fixture.session),
        ).fetchall()
        self.assertEqual({row[0] for row in rows[1:]}, set(KINDS))


if __name__ == '__main__':
    unittest.main()
