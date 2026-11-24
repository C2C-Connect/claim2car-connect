"""PostgreSQL migration controls with session-bound tenant context and 16-v1 root binding."""
from dataclasses import replace
import hashlib
import os
import subprocess
import sys
from pathlib import Path
import unittest
from unittest.mock import patch
import uuid
import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo
from database.migrate import apply, LOCK_KEY, run_migrations
from database.journal import tenant_transaction
from database.manifest_binding import verify_registered_manifest_binding
from database.migration_plan import Migration, discover, discover_authority

class MigrationControlsIntegration(unittest.TestCase):
    def setUp(self):
        admin_url=os.getenv('MIGRATION_TEST_ADMIN_URL', 'postgresql://postgres:synthetic-container-only@127.0.0.1:55432/claim2car_test')
        migrator_url=os.getenv('MIGRATION_DATABASE_URL', 'postgresql://faos_migrator:synthetic-migrator-only@127.0.0.1:55432/claim2car_test')
        self.admin=psycopg.connect(admin_url,autocommit=True)
        self.addCleanup(self.admin.close)
        self.db='migration_control_'+uuid.uuid4().hex
        self.admin.execute(sql.SQL('CREATE DATABASE {} OWNER faos_migrator TEMPLATE template0').format(sql.Identifier(self.db)))
        self.addCleanup(self.drop_database)
        self.url=make_conninfo(migrator_url,dbname=self.db)
        self.conn=psycopg.connect(self.url,autocommit=True)
        self.addCleanup(self.conn.close)
        self.admin_db=psycopg.connect(make_conninfo(admin_url,dbname=self.db),autocommit=True)
        self.addCleanup(self.admin_db.close)
        self.first=self.migration('0001_first.sql','CREATE SCHEMA faos; CREATE TABLE faos.probe(value integer); INSERT INTO faos.probe VALUES (1);')
    def drop_database(self):
        self.admin.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(self.db)))
    def migration(self,name,text):
        return Migration(name,hashlib.sha256(text.encode('utf-8')).hexdigest(),text)
    def history(self):
        return self.conn.execute('SELECT name,sha256 FROM public.faos_migration_history ORDER BY ordinal').fetchall()
    def test_first_application(self):
        self.assertEqual(apply(self.conn,(self.first,)),(self.first.name,))
        self.assertEqual(self.history(),[(self.first.name,self.first.sha256)])
        self.assertEqual(self.conn.execute('SELECT value FROM faos.probe').fetchall(),[(1,)])
    def test_identical_rerun(self):
        apply(self.conn,(self.first,))
        self.assertEqual(apply(self.conn,(self.first,)),())
        self.assertEqual(self.conn.execute('SELECT count(*) FROM faos.probe').fetchone()[0],1)
    def test_pending_suffix(self):
        apply(self.conn,(self.first,))
        second=self.migration('0002_second.sql','INSERT INTO faos.probe VALUES (2);')
        self.assertEqual(apply(self.conn,(self.first,second)),(second.name,))
        self.assertEqual(len(self.history()),2)
    def test_checksum_change_rejected(self):
        apply(self.conn,(self.first,))
        before=self.history()
        with self.assertRaisesRegex(ValueError,'APPLIED_MIGRATION_CHANGED'):
            apply(self.conn,(replace(self.first,sha256='0'*64),))
        self.assertEqual(self.history(),before)
    def test_failed_batch_rolls_back_ddl_and_ledger(self):
        broken=self.migration('0002_broken.sql','SELECT 1/0;')
        with self.assertRaises(psycopg.errors.DivisionByZero):
            apply(self.conn,(self.first,broken))
        self.assertEqual(self.conn.execute("SELECT to_regnamespace('faos'),to_regclass('public.faos_migration_history')").fetchone(),(None,None))
        self.assertEqual(apply(self.conn,(self.first,)),(self.first.name,))
    def test_lock_contention_and_release(self):
        with psycopg.connect(self.url,autocommit=True) as blocker:
            with blocker.transaction():
                blocker.execute('SELECT pg_advisory_xact_lock(%s)',(LOCK_KEY,))
                self.conn.execute("SET lock_timeout = '200ms'")
                with self.assertRaises(psycopg.errors.LockNotAvailable):
                    apply(self.conn,(self.first,))
                self.assertIsNone(self.conn.execute("SELECT to_regclass('public.faos_migration_history')").fetchone()[0])
            self.conn.execute("SET lock_timeout = '0'")
            self.assertEqual(apply(self.conn,(self.first,)),(self.first.name,))

    def authority_plan(self):
        return discover_authority(Path(__file__).resolve().parents[2])

    def test_default_entry_point_clean_full_initialization_and_rerun(self):
        plan = self.authority_plan()
        self.assertEqual(plan[-1].name,'0030_runtime_manifest_registration.sql')
        with patch.dict(os.environ,{'MIGRATION_DATABASE_URL':self.url}):
            self.assertEqual(run_migrations(),tuple(item.name for item in plan))
            before = self.history()
            self.assertEqual(run_migrations(),())
        self.assertEqual(self.history(),[(item.name,item.sha256) for item in plan])
        self.assertEqual(self.history(),before)
        self.assertIsNotNone(self.conn.execute("SELECT to_regclass('faos.tenant_login_bindings')").fetchone()[0])
        # Exercise M1 root binding consumers against an isolated full authority schema.
        selectors = (
            'test_manifest_roots.ManifestRootTests.test_registered_root_contains_and_verifies_seal_chain_binding',
            'test_manifest_roots.ManifestRootTests.test_privileged_context_binding_tamper_fails_verification',
            'test_manifest_roots.ManifestRootTests.test_registered_binding_rejects_tampered_chain_tail',
            'test_registered_completion.RegisteredCompletionTests.test_registered_root_context_binding_tamper_fails_closed',
            'test_completion_receipts.CompletionReceiptTests.test_receipt_inspection_fails_closed_on_root_binding_tamper',
            'test_completion_receipts.CompletionReceiptTests.test_receipt_write_rejects_root_binding_tamper',
            'test_receipt_inspection.ReceiptInspectionTests.test_metadata_matches_committed_snapshot',
        )
        env = os.environ.copy()
        admin_base = os.getenv('MIGRATION_TEST_ADMIN_URL','postgresql://postgres:synthetic-container-only@127.0.0.1:55432/claim2car_test')
        app_base = os.getenv('APP_DATABASE_URL','postgresql://faos_app:synthetic-app-only@127.0.0.1:55432/claim2car_test')
        env.update({
            'PYTHONPATH': str(Path(__file__).resolve().parents[2]) + os.pathsep + env.get('PYTHONPATH',''),
            'MIGRATION_DATABASE_URL': self.url,
            'MIGRATION_TEST_ADMIN_URL': make_conninfo(admin_base,dbname=self.db),
            'APP_DATABASE_URL': make_conninfo(app_base,dbname=self.db),
            'RECOVERY_DATABASE_URL': make_conninfo(app_base,dbname=self.db),
        })
        result = subprocess.run(
            [sys.executable,'-m','unittest',*selectors],
            cwd=Path(__file__).resolve().parent,env=env,text=True,capture_output=True,timeout=120,
        )
        self.assertEqual(result.returncode,0,result.stdout+'\n'+result.stderr)

    def test_manifest_binding_migration_backfills_existing_root_and_restores_rls(self):
        plan=self.authority_plan()
        apply(self.conn,plan[:-1])
        from test_manifest_roots import ManifestRootTests
        admin_base=os.getenv('MIGRATION_TEST_ADMIN_URL','postgresql://postgres:synthetic-container-only@127.0.0.1:55432/claim2car_test')
        app_base=os.getenv('APP_DATABASE_URL','postgresql://faos_app:synthetic-app-only@127.0.0.1:55432/claim2car_test')
        fixture=ManifestRootTests()
        env={
            'MIGRATION_DATABASE_URL':self.url,
            'MIGRATION_TEST_ADMIN_URL':make_conninfo(admin_base,dbname=self.db),
            'APP_DATABASE_URL':make_conninfo(app_base,dbname=self.db),
            'RECOVERY_DATABASE_URL':make_conninfo(app_base,dbname=self.db),
        }
        with patch.dict(os.environ,env):
            fixture.setUp()
            try:
                self.assertEqual(fixture.register(),'REGISTERED')
                self.assertEqual(run_migrations(),('0030_runtime_manifest_registration.sql',))
                with patch.dict(os.environ,env):
                    with tenant_transaction(fixture.conn,fixture.tenant):
                        privileges=fixture.conn.execute(
                            "SELECT has_schema_privilege('faos_writer','faos','CREATE'),"
                            "has_function_privilege('faos_app',"
                            "'faos.register_manifest_root_from_capture(uuid,text,text,text,text,text,uuid)','EXECUTE'),"
                            "has_function_privilege('faos_app',"
                            "'faos.register_manifest_root(uuid,text,text,text,text)','EXECUTE'),"
                            "(SELECT pg_get_userbyid(proowner) FROM pg_proc "
                            "WHERE oid='faos.register_manifest_root_from_capture(uuid,text,text,text,text,text,uuid)'::regprocedure)"
                        ).fetchone()
                        self.assertEqual(privileges,(False,True,False,'faos_writer'))
                    with tenant_transaction(fixture.conn,fixture.tenant):
                        row=fixture.conn.execute(
                            'SELECT seal_sequence,seal_chain_hash,context_binding_hash,binding_version,'
                            'faos.verify_manifest_root_binding(tenant_id,session_id,seal_event_id) '
                            'FROM faos.manifest_roots WHERE tenant_id=%s AND session_id=%s AND seal_event_id=%s',
                            (fixture.tenant,fixture.session,fixture.seal),
                        ).fetchone()
                        self.assertTrue(row[4])
                        self.assertEqual(row[0],len(fixture.events))
                        seal_hash=fixture.conn.execute('SELECT entry_hash FROM faos.events WHERE tenant_id=%s AND session_id=%s AND event_id=%s',(fixture.tenant,fixture.session,fixture.seal)).fetchone()[0]
                        self.assertEqual(row[1],seal_hash)
                        self.assertEqual(row[3],'manifest-context-v1')
                        self.assertTrue(verify_registered_manifest_binding(
                            fixture.conn,fixture.tenant,fixture.session,fixture.seal)['valid'])
                rls=self.admin_db.execute(
                    "SELECT c.relrowsecurity,c.relforcerowsecurity FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                    "WHERE n.nspname='faos' AND c.relname IN ('events','sessions','manifest_roots') ORDER BY c.relname"
                ).fetchall()
                self.assertEqual(rls,[(True,True),(True,True),(True,True)])
            finally:
                fixture.doCleanups()

    def test_default_entry_point_upgrades_legacy_seven_migration_schema(self):
        legacy = discover(Path(__file__).resolve().parents[2]/'migrations')
        self.assertEqual(len(legacy),7)
        apply(self.conn,legacy)
        self.assertIsNone(self.conn.execute("SELECT to_regclass('faos.tenant_login_bindings')").fetchone()[0])
        with patch.dict(os.environ,{'MIGRATION_DATABASE_URL':self.url}):
            self.assertEqual(run_migrations(),('0008_tenant_login_authority.sql','0009_integer_financial_ledger.sql','0010_claim_case_registry.sql','0011_claim_case_idempotency_conflicts.sql','0012_claim_case_retry_without_update_lock.sql','0013_claim_case_capture_session.sql','0014_claim_case_incident_intake.sql','0015_incident_event_kinds.sql','0016_claim_case_incident_read_boundary.sql','0017_event_contract_parity.sql','0018_capture_protocol_session_binding.sql','0019_manifest_root_protocol_binding.sql','0020_collision_lifecycle_record.sql','0021_collision_claim_link.sql','0022_collision_vehicle_capture_link.sql','0023_consented_vehicle_profile.sql','0024_audited_capture_exceptions_pause_resume.sql','0025_square_sandbox_payment_intents.sql','0026_square_sandbox_webhook_reconciliation.sql','0027_capture_protocol_16_v2.sql','0028_persistent_event_hash_chain.sql','0029_manifest_root_chain_context_binding.sql','0030_runtime_manifest_registration.sql'))
            self.assertEqual(run_migrations(),())
        self.assertEqual(self.history(),[(item.name,item.sha256) for item in self.authority_plan()])

    def test_event_chain_backfill_gap_rolls_back_migration(self):
        plan=self.authority_plan()
        apply(self.conn,plan[:-2])
        tenant=str(uuid.uuid4())
        session='chain-gap-'+uuid.uuid4().hex
        payload='{"synthetic":true}'
        self.admin_db.execute('INSERT INTO faos.organizations(tenant_id,name) VALUES (%s,%s)',(tenant,'synthetic chain-gap fixture'))
        self.admin_db.execute('INSERT INTO faos.sessions(tenant_id,session_id) VALUES (%s,%s)',(tenant,session))
        for sequence,event_id in ((1,'gap-event-1'),(3,'gap-event-3')):
            self.admin_db.execute(
                'INSERT INTO faos.events VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                (tenant,session,event_id,sequence,'SESSION_CREATED','synthetic-test',
                 f'2026-01-01T00:00:0{sequence}Z','sequence-gap fixture',payload,'0.1'),
            )
        before=self.history()
        with self.assertRaises(psycopg.errors.RaiseException) as raised:
            apply(self.conn,plan)
        self.assertTrue(raised.exception.diag.message_primary.startswith('EVENT_CHAIN_BACKFILL_SEQUENCE_GAP'))
        self.assertEqual(self.history(),before,'FAILED_CHAIN_BACKFILL_ADVANCED_MIGRATION_LEDGER')
        self.assertFalse(self.admin_db.execute(
            "SELECT EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema='faos' AND table_name='events' AND column_name='entry_hash')"
        ).fetchone()[0],'FAILED_CHAIN_BACKFILL_LEFT_PARTIAL_DDL')

    def test_event_chain_migration_restores_forced_rls(self):
        plan=self.authority_plan()
        apply(self.conn,plan)
        flags=self.admin_db.execute(
            "SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE oid='faos.events'::regclass"
        ).fetchone()
        self.assertEqual(flags,(True,True))
        self.assertTrue(self.admin_db.execute("SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname='pgcrypto')").fetchone()[0])
        columns=self.admin_db.execute(
            "SELECT column_name,is_nullable FROM information_schema.columns WHERE table_schema='faos' AND table_name='events' AND column_name IN ('previous_hash','entry_hash','hash_version') ORDER BY column_name"
        ).fetchall()
        self.assertEqual(columns,[('entry_hash','NO'),('hash_version','NO'),('previous_hash','NO')])

    def test_capture_protocol_migration_preserves_legacy_and_defaults_new_sessions(self):
        plan = self.authority_plan()
        protocol_index = next(i for i, item in enumerate(plan)
                              if item.name == '0018_capture_protocol_session_binding.sql')
        apply(self.conn, plan[:protocol_index])
        tenant = str(uuid.uuid4())
        legacy_session = 'legacy-' + uuid.uuid4().hex
        new_session = 'new-' + uuid.uuid4().hex
        admin_url = make_conninfo(
            os.getenv('MIGRATION_TEST_ADMIN_URL', 'postgresql://postgres:synthetic-container-only@127.0.0.1:55432/claim2car_test'),
            dbname=self.db,
        )
        with psycopg.connect(admin_url, autocommit=True) as admin:
            admin.execute('INSERT INTO faos.organizations(tenant_id,name) VALUES (%s,%s)',
                          (tenant,'protocol migration fixture'))
            admin.execute('INSERT INTO faos.sessions(tenant_id,session_id) VALUES (%s,%s)',
                          (tenant,legacy_session))
            self.assertEqual(apply(self.conn,plan[:protocol_index + 1]),
                             (plan[protocol_index].name,))
            legacy_version = admin.execute(
                'SELECT capture_protocol_version FROM faos.sessions WHERE tenant_id=%s AND session_id=%s',
                (tenant,legacy_session)).fetchone()[0]
            self.assertEqual(legacy_version,'claims2car-12-v1')
            admin.execute('INSERT INTO faos.sessions(tenant_id,session_id) VALUES (%s,%s)',
                          (tenant,new_session))
            new_version = admin.execute(
                'SELECT capture_protocol_version FROM faos.sessions WHERE tenant_id=%s AND session_id=%s',
                (tenant,new_session)).fetchone()[0]
            self.assertEqual(new_version,'claims2car-16-v1')
            with self.assertRaises(psycopg.errors.RaiseException) as raised:
                admin.execute(
                    "UPDATE faos.sessions SET capture_protocol_version='claims2car-16-v1' WHERE tenant_id=%s AND session_id=%s",
                    (tenant,legacy_session))
            self.assertEqual(raised.exception.diag.message_primary,'CAPTURE_PROTOCOL_VERSION_IMMUTABLE')

    def test_manifest_root_protocol_binding_accepts_16_and_rejects_mismatch(self):
        plan = self.authority_plan()
        apply(self.conn, plan)
        tenant = str(uuid.uuid4())
        session = 'manifest-root-16-' + uuid.uuid4().hex
        seal = 'seal-16-' + uuid.uuid4().hex
        digest = 'a' * 64
        payload = '{"manifest_digest":"' + digest + '","schema_version":"0.1","shot_list_version":"claims2car-16-v1"}'
        self.admin_db.execute(
            'INSERT INTO faos.organizations(tenant_id,name) VALUES (%s,%s)',
            (tenant, 'synthetic manifest root protocol fixture'),
        )
        self.admin_db.execute(
            'INSERT INTO faos.sessions(tenant_id,session_id,capture_protocol_version) VALUES (%s,%s,%s)',
            (tenant, session, 'claims2car-16-v1'),
        )
        self.admin_db.execute(
            'INSERT INTO faos.events(tenant_id,session_id,event_id,sequence,kind,actor,occurred_at,reason,payload_json,schema_version) '
            'VALUES (%s,%s,%s,1,%s,%s,%s,%s,%s,%s)',
            (tenant, session, seal, 'MANIFEST_SEALED', 'synthetic-test',
             '2026-01-01T00:00:00Z', 'synthetic 16-v1 manifest root', payload, '0.1'),
        )
        self.admin_db.execute(
            'INSERT INTO faos.tenant_login_bindings(role_oid,role_name,tenant_id,enabled) '
            'SELECT oid,rolname,%s,true FROM pg_roles WHERE rolname=session_user',
            (tenant,),
        )

        def register(version):
            with self.admin_db.transaction():
                self.admin_db.execute('SET LOCAL ROLE faos_fixture')
                self.admin_db.execute("SELECT set_config('faos.tenant_id',%s,true)", (tenant,))
                context = self.admin_db.execute(
                    "SELECT current_user,current_setting('faos.tenant_id',true),faos.tenant_id()::text"
                ).fetchone()
                self.assertEqual(context, ('faos_fixture', tenant, tenant), 'FIXTURE_TENANT_CONTEXT_NOT_ESTABLISHED')
                return self.admin_db.execute(
                    'SELECT faos.register_manifest_root(%s::uuid,%s::text,%s::text,%s::text,%s::text)',
                    (tenant, session, seal, digest, version),
                ).fetchone()[0]

        self.assertEqual(register('claims2car-16-v1'), 'REGISTERED')
        with self.assertRaisesRegex(psycopg.errors.RaiseException, 'ROOT_PROTOCOL_SESSION_MISMATCH'):
            register('claims2car-12-v1')

        with self.assertRaises(psycopg.errors.RaiseException) as raised:
            with self.admin_db.transaction():
                self.admin_db.execute('SET LOCAL ROLE faos_writer')
                self.admin_db.execute("SELECT set_config('faos.tenant_id',%s,true)", (tenant,))
                context = self.admin_db.execute(
                    "SELECT current_user,current_setting('faos.tenant_id',true),faos.tenant_id()::text"
                ).fetchone()
                self.assertEqual(context, ('faos_writer', tenant, tenant), 'WRITER_TENANT_CONTEXT_NOT_ESTABLISHED')
                self.admin_db.execute(
                    'INSERT INTO faos.manifest_roots(tenant_id,session_id,seal_event_id,manifest_digest,shot_list_version) '
                    'VALUES (%s,%s,%s,%s,%s)',
                    (tenant, session, seal, digest, 'claims2car-12-v1'),
                )
        self.assertEqual(raised.exception.diag.message_primary, 'ROOT_PROTOCOL_SESSION_MISMATCH')
        self.assertEqual(
            self.admin_db.execute(
                'SELECT shot_list_version FROM faos.manifest_roots WHERE tenant_id=%s AND session_id=%s',
                (tenant, session),
            ).fetchall(),
            [('claims2car-16-v1',)],
        )

    def test_full_migration_enforces_python_sql_event_contract_parity(self):
        from app.domain_events import DomainEvent, KINDS
        from database.journal import tenant_transaction
        plan = self.authority_plan()
        apply(self.conn, plan)
        app_url = make_conninfo(
            os.getenv('APP_DATABASE_URL', 'postgresql://faos_app:synthetic-app-only@127.0.0.1:55432/claim2car_test'),
            dbname=self.db,
        )
        admin_url = make_conninfo(
            os.getenv('MIGRATION_TEST_ADMIN_URL', 'postgresql://postgres:synthetic-container-only@127.0.0.1:55432/claim2car_test'),
            dbname=self.db,
        )
        with psycopg.connect(admin_url, autocommit=True) as admin, psycopg.connect(app_url, autocommit=True) as app:
            tenant = str(uuid.uuid4())
            session = 'event-contract-' + uuid.uuid4().hex
            def append(event_id, sequence, kind, timestamp, payload):
                return app.execute(
                    'SELECT faos.append_event(%s::uuid,%s::text,%s::text,%s::bigint,'
                    '%s::text,%s::text,%s::text,%s::text,%s::text,%s::text)',
                    (tenant, session, event_id, sequence, kind, 'synthetic-contract-test',
                     timestamp, 'event contract integration', payload, '0.1'),
                ).fetchone()[0]

            admin.execute(
                'INSERT INTO faos.organizations(tenant_id,name) VALUES (%s,%s)',
                (tenant, 'synthetic event contract fixture'),
            )
            admin.execute(
                'INSERT INTO faos.sessions(tenant_id,session_id) VALUES (%s,%s)',
                (tenant, session),
            )
            admin.execute(
                'INSERT INTO faos.tenant_login_bindings(role_oid,role_name,tenant_id,enabled) '
                'SELECT oid,rolname,%s,true FROM pg_roles WHERE rolname=%s',
                (tenant, 'faos_app'),
            )
            with tenant_transaction(app, tenant):
                self.assertEqual(append(
                    'event-1', 1, 'SESSION_CREATED', '2026-01-01T00:00:00Z', '{}'
                ), 'ACCEPTED')

            invalid_timestamps = (
                '2026-01-01T00:00:00',
                '2026-01-01 00:00:00Z',
                '2026-01-01T00:00:00.1234567Z',
                '2026-02-30T00:00:00Z',
            )
            invalid_payloads = (
                '{ "a":1}',
                '{"z":1,"a":2}',
                '{"value":1e0}',
                '{"label":"\\u00e9"}',
            )
            probes = [
                ('timestamp-' + str(i), '2026-01-01T00:00:00Z', '{}')
                for i in range(len(invalid_timestamps))
            ] + [
                ('payload-' + str(i), '2026-01-01T00:00:00Z', payload)
                for i, payload in enumerate(invalid_payloads)
            ]
            for index, (event_id, _valid_placeholder, payload) in enumerate(probes):
                timestamp = invalid_timestamps[index] if index < len(invalid_timestamps) else '2026-01-01T00:00:00Z'
                expected_constraint = ('event_timestamp_input_valid' if timestamp == '2026-02-30T00:00:00Z'
                                      else 'event_timestamp_rfc3339' if timestamp != '2026-01-01T00:00:00Z'
                                      else 'event_payload_compact' if payload.startswith('{ ')
                                      else 'event_payload_python_canonical')
                with self.subTest(event_id=event_id):
                    with tenant_transaction(app, tenant):
                        with self.assertRaises(psycopg.errors.CheckViolation) as rejected:
                            with app.transaction():
                                append(event_id, 2, 'SESSION_CREATED', timestamp, payload)
                        self.assertEqual(rejected.exception.diag.constraint_name, expected_constraint)
                        count = app.execute(
                            'SELECT count(*) FROM faos.events WHERE tenant_id=%s AND session_id=%s',
                            (tenant, session),
                        ).fetchone()[0]
                        self.assertEqual(count, 1)

            valid_payload = '{"label":"é","large":100000000000000000000,"small":0.00001,"value":1.25}'
            sql_canonical = app.execute(
                'SELECT faos.canonical_event_jsonb(%s::jsonb)', (valid_payload,)
            ).fetchone()[0]
            self.assertEqual(sql_canonical, valid_payload, f'SQL_CANONICAL_PAYLOAD={sql_canonical!r}')
            with tenant_transaction(app, tenant):
                self.assertEqual(append(
                    'event-2', 2, 'QUALITY_RECORDED', '2026-01-01T00:00:00+05:30', valid_payload
                ), 'ACCEPTED')
                row = app.execute(
                    'SELECT session_id,event_id,sequence,kind,actor,occurred_at,reason,payload_json,schema_version '
                    'FROM faos.events WHERE tenant_id=%s AND session_id=%s AND event_id=%s',
                    (tenant, session, 'event-2'),
                ).fetchone()
                self.assertEqual(DomainEvent(*row).validate().payload['value'], 1.25)
                self.assertEqual(row[7], valid_payload, 'PERSISTED_EVENT_PAYLOAD_BYTES_CHANGED')

            sequence = 3
            with tenant_transaction(app, tenant):
                for kind in sorted(KINDS - {'SESSION_CREATED', 'QUALITY_RECORDED'}):
                    self.assertEqual(append(
                        'kind-' + str(sequence), sequence, kind, '2026-01-01T00:00:00Z', '{}'
                    ), 'ACCEPTED')
                    sequence += 1
                kinds = app.execute(
                    'SELECT kind FROM faos.events WHERE tenant_id=%s AND session_id=%s ORDER BY sequence',
                    (tenant, session),
                ).fetchall()
                self.assertEqual({row[0] for row in kinds}, set(KINDS))

    def test_parity_migration_preserves_existing_event_payload_bytes(self):
        plan = self.authority_plan()
        apply(self.conn, plan[:-4])
        tenant = str(uuid.uuid4())
        session = 'preserve-payload-' + uuid.uuid4().hex
        payload = '{"label":"é","metric":0.00001}'
        self.admin_db.execute('INSERT INTO faos.organizations(tenant_id,name) VALUES (%s,%s)',
                          (tenant, 'synthetic history preservation fixture'))
        self.admin_db.execute('INSERT INTO faos.sessions(tenant_id,session_id) VALUES (%s,%s)',
                          (tenant, session))
        self.admin_db.execute(
            'INSERT INTO faos.events VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
            (tenant, session, 'preserved-event', 1, 'SESSION_CREATED',
             'synthetic-test', '2026-01-01T00:00:00Z', 'preserve exact bytes', payload, '0.1'),
        )
        before = self.admin_db.execute(
            'SELECT payload_json,occurred_at FROM faos.events WHERE tenant_id=%s AND session_id=%s',
            (tenant, session),
        ).fetchone()
        apply(self.conn, plan)
        after = self.admin_db.execute(
            'SELECT payload_json,occurred_at FROM faos.events WHERE tenant_id=%s AND session_id=%s',
            (tenant, session),
        ).fetchone()
        self.assertEqual(after, before, 'MIGRATION_REWROTE_HISTORICAL_EVENT_BYTES')
        hashes = self.admin_db.execute(
            'SELECT previous_hash,entry_hash,hash_version FROM faos.events WHERE tenant_id=%s AND session_id=%s',
            (tenant,session),
        ).fetchone()
        genesis = self.admin_db.execute(
            'SELECT faos.event_chain_genesis_hash(%s::uuid,%s)',(tenant,session),
        ).fetchone()[0]
        expected = self.admin_db.execute(
            'SELECT faos.event_chain_entry_hash(%s::uuid,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
            (tenant,session,'preserved-event',1,'SESSION_CREATED','synthetic-test',
             '2026-01-01T00:00:00Z','preserve exact bytes',payload,'0.1',genesis),
        ).fetchone()[0]
        self.assertEqual(hashes,(genesis,expected,'event-hash-v1'),'BACKFILL_HASH_MISMATCH')

    def test_noncanonical_historical_event_blocks_parity_migration_without_rewrite(self):
        plan = self.authority_plan()
        parity_index = next(i for i, item in enumerate(plan)
                            if item.name == '0017_event_contract_parity.sql')
        apply(self.conn, plan[:parity_index])
        tenant = str(uuid.uuid4())
        session = 'reject-history-' + uuid.uuid4().hex
        payload = '{"z":1,"a":2}'
        self.admin_db.execute('INSERT INTO faos.organizations(tenant_id,name) VALUES (%s,%s)',
                          (tenant, 'synthetic invalid history fixture'))
        self.admin_db.execute('INSERT INTO faos.sessions(tenant_id,session_id) VALUES (%s,%s)',
                          (tenant, session))
        self.admin_db.execute(
            'INSERT INTO faos.events VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
            (tenant, session, 'noncanonical-event', 1, 'SESSION_CREATED',
             'synthetic-test', '2026-01-01T00:00:00Z', 'preserve invalid history',
             payload, '0.1'),
        )
        before_history = self.history()
        before_payload = self.admin_db.execute(
            'SELECT payload_json FROM faos.events WHERE tenant_id=%s AND session_id=%s',
            (tenant, session),
        ).fetchone()[0]
        with self.assertRaises(psycopg.errors.CheckViolation):
            apply(self.conn, plan)
        self.assertEqual(self.history(), before_history, 'FAILED_MIGRATION_ADVANCED_LEDGER')
        after_payload = self.admin_db.execute(
            'SELECT payload_json FROM faos.events WHERE tenant_id=%s AND session_id=%s',
            (tenant, session),
        ).fetchone()[0]
        self.assertEqual(after_payload, before_payload, 'FAILED_MIGRATION_REWROTE_HISTORY')

    def test_applied_authority_migration_checksum_change_is_rejected(self):
        plan = self.authority_plan()
        apply(self.conn,plan)
        before = self.history()
        changed = plan[:-1]+(replace(plan[-1],sha256='0'*64),)
        with self.assertRaisesRegex(ValueError,'APPLIED_MIGRATION_CHANGED:0029_manifest_root_chain_context_binding.sql'):
            apply(self.conn,changed)
        self.assertEqual(self.history(),before)
