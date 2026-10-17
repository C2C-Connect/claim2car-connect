import os
import unittest
import uuid

import psycopg


class TenantContextRegression(unittest.TestCase):
    def setUp(self):
        self.conn = psycopg.connect(os.getenv(
            'APP_DATABASE_URL',
            'postgresql://faos_app:synthetic-app-only@127.0.0.1:55432/claim2car_test',
        ))
        self.addCleanup(self.conn.close)

    def context(self):
        return self.conn.execute('SELECT faos.tenant_id()').fetchone()[0]

    def set_context(self, tenant):
        self.conn.execute(
            "SELECT set_config('faos.tenant_id', %s, true)", (str(tenant),)
        )

    def test_context_clears_after_commit_on_same_connection(self):
        tenant = uuid.uuid4()
        self.assertIsNone(self.context())
        self.set_context(tenant)
        self.assertEqual(self.context(), tenant)
        self.conn.commit()
        self.assertIsNone(self.context())

    def test_context_clears_after_rollback_on_same_connection(self):
        tenant = uuid.uuid4()
        self.assertIsNone(self.context())
        self.set_context(tenant)
        self.assertEqual(self.context(), tenant)
        self.conn.rollback()
        self.assertIsNone(self.context())

    def test_empty_context_returns_null(self):
        self.conn.execute(
            "SELECT set_config('faos.tenant_id', '', true)"
        )
        self.assertIsNone(self.context())

    def test_malformed_context_rejected_as_invalid_uuid(self):
        self.conn.execute(
            "SELECT set_config('faos.tenant_id', 'not-a-uuid', true)"
        )
        with self.assertRaises(psycopg.errors.InvalidTextRepresentation) as caught:
            self.context()
        self.assertEqual(caught.exception.sqlstate, '22P02')
        self.conn.rollback()

    def assert_append_denied(self, tenant):
        with self.assertRaises(psycopg.errors.RaiseException) as caught:
            self.conn.execute(
                'SELECT faos.append_event(%s::uuid, %s::text, %s::text, '
                '%s::bigint, %s::text, %s::text, %s::text, %s::text, '
                '%s::text, %s::text)',
                (str(tenant), 'context-regression-session',
                 'context-regression-event', 1, 'SESSION_CREATED',
                 'synthetic-test', '2026-01-01T00:00:00Z',
                 'context regression', '{}', '0.1'),
            )
        self.assertEqual(caught.exception.sqlstate, 'P0001')
        self.assertEqual(
            caught.exception.diag.message_primary, 'TENANT_CONTEXT_MISMATCH'
        )
        self.conn.rollback()

    def test_append_rejects_mismatched_context_with_exact_error(self):
        self.set_context(uuid.uuid4())
        self.assert_append_denied(uuid.uuid4())

    def test_append_rejects_missing_context_with_exact_error(self):
        self.assertIsNone(self.context())
        self.assert_append_denied(uuid.uuid4())


if __name__ == '__main__':
    unittest.main()
