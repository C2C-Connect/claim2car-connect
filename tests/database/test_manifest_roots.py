"""Protected synthetic registry tests; fixture endorsement is not real-world authenticity."""
import os
import unittest
from dataclasses import replace
import uuid
import psycopg
from database.journal import append, tenant_transaction
from database.manifest_binding import manifest_context_binding_hash, verify_registered_manifest_binding

REGISTER = 'SELECT faos.register_manifest_root(%s::uuid,%s::text,%s::text,%s::text,%s::text)'

class ManifestRootTests(unittest.TestCase):
    def setUp(self):
        import test_completion_coverage as fixtures
        self.events, self.data, self.digest = fixtures.CompletionCoverage().fixture()
        self.tenant = str(uuid.uuid4())
        self.session = self.events[0].session_id
        self.seal = self.events[-1].event_id
        self.version = 'claims2car-12-v1'
        self.values = (self.tenant, self.session, self.seal, self.digest, self.version)
        self.admin_url = os.getenv('MIGRATION_TEST_ADMIN_URL', 'postgresql://postgres:synthetic-container-only@127.0.0.1:55432/claim2car_test')
        self.conn = psycopg.connect(os.getenv('APP_DATABASE_URL', 'postgresql://faos_app:synthetic-app-only@127.0.0.1:55432/claim2car_test'), autocommit=True)
        self.addCleanup(self.conn.close)
        self.assertEqual(self.conn.execute('SELECT current_user,rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user').fetchone(), ('faos_app', False, False))
        with tenant_transaction(self.conn, self.tenant):
            self.conn.execute('INSERT INTO faos.organizations(tenant_id,name) VALUES (%s,%s)', (self.tenant, 'synthetic root fixture'))
            has_protocol_column = self.conn.execute("SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='faos' AND table_name='sessions' AND column_name='capture_protocol_version')").fetchone()[0]
            if has_protocol_column:
                self.conn.execute('INSERT INTO faos.sessions(tenant_id,session_id,capture_protocol_version) VALUES (%s,%s,%s)', (self.tenant, self.session, self.version))
            else:
                self.conn.execute('INSERT INTO faos.sessions(tenant_id,session_id) VALUES (%s,%s)', (self.tenant, self.session))
        for event in self.events:
            self.assertEqual(append(self.conn, self.tenant, event), 'ACCEPTED')

    def register(self, values=None, context=True):
        with psycopg.connect(self.admin_url, autocommit=True) as conn:
            with conn.transaction():
                conn.execute('SET LOCAL ROLE faos_fixture')
                self.assertEqual(conn.execute('SELECT current_user').fetchone()[0], 'faos_fixture')
                if context:
                    conn.execute("SELECT set_config('faos.tenant_id',%s,true)", (self.tenant,))
                return conn.execute(REGISTER, values or self.values).fetchone()[0]

    def roots(self, tenant):
        with tenant_transaction(self.conn, tenant):
            return self.conn.execute('SELECT seal_event_id,manifest_digest,shot_list_version FROM faos.manifest_roots ORDER BY seal_event_id').fetchall()

    def test_fixture_registration_and_exact_retry(self):
        self.assertEqual(self.register(), 'REGISTERED')
        self.assertEqual(self.register(), 'DUPLICATE')
        self.assertEqual(self.roots(self.tenant), [(self.seal, self.digest, self.version)])

    def test_registered_root_contains_and_verifies_seal_chain_binding(self):
        self.assertEqual(self.register(), 'REGISTERED')
        with tenant_transaction(self.conn, self.tenant):
            row = self.conn.execute(
                'SELECT seal_sequence,seal_chain_hash,context_binding_hash,binding_version,'
                'faos.verify_manifest_root_binding(tenant_id,session_id,seal_event_id) '
                'FROM faos.manifest_roots WHERE tenant_id=%s AND session_id=%s AND seal_event_id=%s',
                (self.tenant, self.session, self.seal),
            ).fetchone()
            sql_hash = self.conn.execute(
                'SELECT faos.manifest_context_binding_hash(%s::uuid,%s::text,%s::text,%s::bigint,%s::text)',
                (self.tenant, self.session, self.version, row[0], row[1]),
            ).fetchone()[0]
            python_verified = verify_registered_manifest_binding(self.conn, self.tenant, self.session, self.seal)
        self.assertEqual(row[0], len(self.events))
        self.assertEqual(len(row[1]), 64)
        self.assertTrue(all(ch in '0123456789abcdef' for ch in row[1]))
        self.assertEqual(len(row[2]), 64)
        self.assertTrue(all(ch in '0123456789abcdef' for ch in row[2]))
        self.assertEqual(row[3], 'manifest-context-v1')
        self.assertTrue(row[4])
        self.assertEqual(row[2], sql_hash)
        self.assertEqual(row[2], manifest_context_binding_hash(self.tenant, self.session, self.version, row[0], row[1]))
        self.assertTrue(python_verified['valid'])
        self.assertTrue(python_verified['python_sql_agreement'])

    def test_privileged_context_binding_tamper_fails_verification(self):
        self.assertEqual(self.register(), 'REGISTERED')
        with psycopg.connect(self.admin_url, autocommit=True) as admin:
            admin.execute(
                "UPDATE faos.manifest_roots SET context_binding_hash=%s WHERE tenant_id=%s AND session_id=%s AND seal_event_id=%s",
                ('0' * 64, self.tenant, self.session, self.seal),
            )
        with tenant_transaction(self.conn, self.tenant):
            verified = self.conn.execute(
                'SELECT faos.verify_manifest_root_binding(%s::uuid,%s::text,%s::text)',
                (self.tenant, self.session, self.seal),
            ).fetchone()[0]
            with self.assertRaisesRegex(ValueError, '^MANIFEST_ROOT_CONTEXT_HASH_MISMATCH$'):
                verify_registered_manifest_binding(self.conn, self.tenant, self.session, self.seal)
        self.assertFalse(verified)

    def test_registered_binding_rejects_tampered_chain_tail(self):
        post_seal = replace(
            self.events[-1],
            event_id='post-seal-event',
            sequence=len(self.events) + 1,
            kind='REVIEW_RECORDED',
            payload_json='{"artifact_ids":[],"disposition":"NOTE_ONLY","schema_version":"0.1"}',
        )
        self.assertEqual(append(self.conn, self.tenant, post_seal), 'ACCEPTED')
        self.assertEqual(self.register(), 'REGISTERED')
        with psycopg.connect(self.admin_url, autocommit=True) as admin:
            admin.execute('ALTER TABLE faos.events DISABLE TRIGGER faos_event_chain_guard_mutation')
            try:
                admin.execute(
                    "UPDATE faos.events SET payload_json=%s WHERE tenant_id=%s AND session_id=%s AND event_id=%s",
                    ('{"artifact_ids":[],"disposition":"HUMAN_QC_REQUIRED","schema_version":"0.1"}',
                     self.tenant, self.session, post_seal.event_id),
                )
            finally:
                admin.execute('ALTER TABLE faos.events ENABLE TRIGGER faos_event_chain_guard_mutation')
        with tenant_transaction(self.conn, self.tenant):
            verified = self.conn.execute(
                'SELECT faos.verify_manifest_root_binding(%s::uuid,%s::text,%s::text)',
                (self.tenant, self.session, self.seal),
            ).fetchone()[0]
            with self.assertRaisesRegex(ValueError, '^MANIFEST_ROOT_EVENT_CHAIN_INVALID
        attempts = [
            (REGISTER, self.values),
            ('INSERT INTO faos.manifest_roots(tenant_id,session_id,seal_event_id,manifest_digest,shot_list_version) VALUES (%s,%s,%s,%s,%s)', self.values),
        ]
        for statement, values in attempts:
            with self.subTest(statement=statement):
                with self.assertRaises(psycopg.errors.InsufficientPrivilege) as caught:
                    with tenant_transaction(self.conn, self.tenant):
                        self.conn.execute(statement, values)
                self.assertEqual(caught.exception.sqlstate, '42501')
        self.assertEqual(self.roots(self.tenant), [])

    def test_application_cannot_update_delete_or_truncate_registered_root(self):
        self.assertEqual(self.register(), 'REGISTERED')
        expected = [(self.seal, self.digest, self.version)]
        keys = (self.tenant, self.session, self.seal)
        statements = (
            ('UPDATE faos.manifest_roots SET manifest_digest=manifest_digest WHERE tenant_id=%s AND session_id=%s AND seal_event_id=%s', keys),
            ('DELETE FROM faos.manifest_roots WHERE tenant_id=%s AND session_id=%s AND seal_event_id=%s', keys),
            ('TRUNCATE faos.manifest_roots', ()),
        )
        for statement, values in statements:
            with self.subTest(statement=statement):
                with self.assertRaises(psycopg.errors.InsufficientPrivilege) as caught:
                    with tenant_transaction(self.conn, self.tenant):
                        self.conn.execute(statement, values)
                        raise AssertionError('UNEXPECTED_ROOT_MUTATION_ALLOWED')
                self.assertEqual(caught.exception.sqlstate, '42501')
                self.assertEqual(self.roots(self.tenant), expected)

    def assert_registration_rejected(self, values, message, context=True):
        with self.assertRaises(psycopg.errors.RaiseException) as caught:
            self.register(values, context=context)
        self.assertEqual(caught.exception.sqlstate, 'P0001')
        self.assertEqual(caught.exception.diag.message_primary, message)
        self.assertEqual(self.roots(self.tenant), [])

    def test_digest_must_match_persisted_seal(self):
        self.assert_registration_rejected((self.tenant, self.session, self.seal, '0' * 64, self.version), 'ROOT_SEAL_MISMATCH')

    def test_nonseal_event_rejected(self):
        self.assert_registration_rejected((self.tenant, self.session, self.events[0].event_id, self.digest, self.version), 'INVALID_SEAL_EVENT')

    def test_other_tenant_cannot_read_registered_root(self):
        self.assertEqual(self.register(), 'REGISTERED')
        self.assertEqual(self.roots(str(uuid.uuid4())), [])
        self.assertEqual(self.roots(self.tenant), [(self.seal, self.digest, self.version)])

    def test_missing_context_cannot_register(self):
        self.assert_registration_rejected(self.values, 'TENANT_CONTEXT_MISMATCH', context=False)


if __name__ == '__main__':
    unittest.main()
):
                verify_registered_manifest_binding(self.conn, self.tenant, self.session, self.seal)
        self.assertFalse(verified)

    def test_application_cannot_register_or_insert_root(self):
        attempts = [
            (REGISTER, self.values),
            ('INSERT INTO faos.manifest_roots(tenant_id,session_id,seal_event_id,manifest_digest,shot_list_version) VALUES (%s,%s,%s,%s,%s)', self.values),
        ]
        for statement, values in attempts:
            with self.subTest(statement=statement):
                with self.assertRaises(psycopg.errors.InsufficientPrivilege) as caught:
                    with tenant_transaction(self.conn, self.tenant):
                        self.conn.execute(statement, values)
                self.assertEqual(caught.exception.sqlstate, '42501')
        self.assertEqual(self.roots(self.tenant), [])

    def test_application_cannot_update_delete_or_truncate_registered_root(self):
        self.assertEqual(self.register(), 'REGISTERED')
        expected = [(self.seal, self.digest, self.version)]
        keys = (self.tenant, self.session, self.seal)
        statements = (
            ('UPDATE faos.manifest_roots SET manifest_digest=manifest_digest WHERE tenant_id=%s AND session_id=%s AND seal_event_id=%s', keys),
            ('DELETE FROM faos.manifest_roots WHERE tenant_id=%s AND session_id=%s AND seal_event_id=%s', keys),
            ('TRUNCATE faos.manifest_roots', ()),
        )
        for statement, values in statements:
            with self.subTest(statement=statement):
                with self.assertRaises(psycopg.errors.InsufficientPrivilege) as caught:
                    with tenant_transaction(self.conn, self.tenant):
                        self.conn.execute(statement, values)
                        raise AssertionError('UNEXPECTED_ROOT_MUTATION_ALLOWED')
                self.assertEqual(caught.exception.sqlstate, '42501')
                self.assertEqual(self.roots(self.tenant), expected)

    def assert_registration_rejected(self, values, message, context=True):
        with self.assertRaises(psycopg.errors.RaiseException) as caught:
            self.register(values, context=context)
        self.assertEqual(caught.exception.sqlstate, 'P0001')
        self.assertEqual(caught.exception.diag.message_primary, message)
        self.assertEqual(self.roots(self.tenant), [])

    def test_digest_must_match_persisted_seal(self):
        self.assert_registration_rejected((self.tenant, self.session, self.seal, '0' * 64, self.version), 'ROOT_SEAL_MISMATCH')

    def test_nonseal_event_rejected(self):
        self.assert_registration_rejected((self.tenant, self.session, self.events[0].event_id, self.digest, self.version), 'INVALID_SEAL_EVENT')

    def test_other_tenant_cannot_read_registered_root(self):
        self.assertEqual(self.register(), 'REGISTERED')
        self.assertEqual(self.roots(str(uuid.uuid4())), [])
        self.assertEqual(self.roots(self.tenant), [(self.seal, self.digest, self.version)])

    def test_missing_context_cannot_register(self):
        self.assert_registration_rejected(self.values, 'TENANT_CONTEXT_MISMATCH', context=False)


if __name__ == '__main__':
    unittest.main()
