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

if __name__ == '__main__':
    unittest.main()
