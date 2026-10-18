"""Mocked adapter boundary tests; not PostgreSQL integration evidence."""
from dataclasses import replace
import unittest
from unittest.mock import Mock
import uuid

from psycopg.pq import TransactionStatus

from app.domain_events import DomainEvent
from database.journal import append


class TestAdapterValidation(unittest.TestCase):
    def setUp(self):
        self.tenant = str(uuid.uuid4())
        self.event = DomainEvent(
            'adapter-session', 'event-1', 1, 'SESSION_CREATED',
            'synthetic-test', '2026-01-01T00:00:00Z',
            'adapter boundary test', '{}',
        )

    def connection(self):
        conn = Mock()
        conn.autocommit = True
        conn.info.transaction_status = TransactionStatus.IDLE
        conn.execute.side_effect = AssertionError('UNEXPECTED_SQL')
        conn.transaction.side_effect = AssertionError('UNEXPECTED_TRANSACTION')
        return conn

    def assert_no_database_calls(self, conn):
        conn.execute.assert_not_called()
        conn.transaction.assert_not_called()

    def test_non_events_rejected_before_database_calls(self):
        for value in (None, {}, object()):
            with self.subTest(value_type=type(value).__name__):
                conn = self.connection()
                with self.assertRaisesRegex(ValueError, '^INVALID_EVENT$'):
                    append(conn, self.tenant, value)
                self.assert_no_database_calls(conn)

    def test_invalid_event_fields_rejected_before_database_calls(self):
        cases = [
            ({'schema_version': 'unsupported'}, 'UNSUPPORTED_SCHEMA'),
            ({'actor': ' '}, 'MISSING_CONTEXT'),
            ({'sequence': True}, 'INVALID_SEQUENCE'),
            ({'sequence': 0}, 'INVALID_SEQUENCE'),
            ({'kind': 'UNKNOWN'}, 'INVALID_EVENT_KIND'),
            ({'occurred_at': 'not-a-timestamp'}, 'INVALID_TIMESTAMP'),
            ({'payload_json': '{'}, 'INVALID_PAYLOAD'),
            ({'payload_json': '{"a": 1}'}, 'NONCANONICAL_PAYLOAD'),
        ]
        for changes, error in cases:
            with self.subTest(changes=changes):
                conn = self.connection()
                with self.assertRaisesRegex(ValueError, '^' + error + '$'):
                    append(conn, self.tenant, replace(self.event, **changes))
                self.assert_no_database_calls(conn)

    def test_malformed_tenant_rejected_before_database_calls(self):
        conn = self.connection()
        with self.assertRaises(ValueError):
            append(conn, 'not-a-uuid', self.event)
        self.assert_no_database_calls(conn)

    def test_unsuitable_connections_rejected_before_database_calls(self):
        cases = [
            (False, TransactionStatus.IDLE),
            (True, TransactionStatus.ACTIVE),
            (True, TransactionStatus.INTRANS),
            (True, TransactionStatus.INERROR),
            (True, TransactionStatus.UNKNOWN),
        ]
        for autocommit, status in cases:
            with self.subTest(autocommit=autocommit, status=status):
                conn = self.connection()
                conn.autocommit = autocommit
                conn.info.transaction_status = status
                with self.assertRaisesRegex(
                    ValueError, '^IDLE_AUTOCOMMIT_CONNECTION_REQUIRED$'
                ):
                    append(conn, self.tenant, self.event)
                self.assert_no_database_calls(conn)


if __name__ == '__main__':
    unittest.main()
