"""Real PostgreSQL migration controls in unique disposable databases."""
from dataclasses import replace
import hashlib
import os
from pathlib import Path
import unittest
from unittest.mock import patch
import uuid
import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo
from database.migrate import apply, LOCK_KEY, run_migrations
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
        self.assertEqual(plan[-1].name,'0017_event_contract_parity.sql')
        with patch.dict(os.environ,{'MIGRATION_DATABASE_URL':self.url}):
            self.assertEqual(run_migrations(),tuple(item.name for item in plan))
            before = self.history()
            self.assertEqual(run_migrations(),())
        self.assertEqual(self.history(),[(item.name,item.sha256) for item in plan])
        self.assertEqual(self.history(),before)
        self.assertIsNotNone(self.conn.execute("SELECT to_regclass('faos.tenant_login_bindings')").fetchone()[0])

    def test_default_entry_point_upgrades_legacy_seven_migration_schema(self):
        legacy = discover(Path(__file__).resolve().parents[2]/'migrations')
        self.assertEqual(len(legacy),7)
        apply(self.conn,legacy)
        self.assertIsNone(self.conn.execute("SELECT to_regclass('faos.tenant_login_bindings')").fetchone()[0])
        with patch.dict(os.environ,{'MIGRATION_DATABASE_URL':self.url}):
            self.assertEqual(run_migrations(),('0008_tenant_login_authority.sql','0009_integer_financial_ledger.sql','0010_claim_case_registry.sql','0011_claim_case_idempotency_conflicts.sql','0012_claim_case_retry_without_update_lock.sql','0013_claim_case_capture_session.sql','0014_claim_case_incident_intake.sql','0015_incident_event_kinds.sql','0016_claim_case_incident_read_boundary.sql','0017_event_contract_parity.sql'))
            self.assertEqual(run_migrations(),())
        self.assertEqual(self.history(),[(item.name,item.sha256) for item in self.authority_plan()])

    def test_full_migration_enforces_python_sql_event_contract_parity(self):
        from app.domain_events import DomainEvent, KINDS
        plan = self.authority_plan()
        apply(self.conn, plan)
        app_url = make_conninfo(
            os.getenv('APP_DATABASE_URL', 'postgresql://faos_app:synthetic-app-only@127.0.0.1:55432/claim2car_test'),
            dbname=self.db,
        )
        with psycopg.connect(app_url, autocommit=True) as app:
            tenant = str(uuid.uuid4())
            session = 'event-contract-' + uuid.uuid4().hex
            def append(event_id, sequence, kind, timestamp, payload):
                return app.execute(
                    'SELECT faos.append_event(%s::uuid,%s::text,%s::text,%s::bigint,'
                    '%s::text,%s::text,%s::text,%s::text,%s::text,%s::text)',
                    (tenant, session, event_id, sequence, kind, 'synthetic-contract-test',
                     timestamp, 'event contract integration', payload, '0.1'),
                ).fetchone()[0]

            with app.transaction():
                app.execute("SELECT set_config('faos.tenant_id',%s,true)", (tenant,))
                app.execute(
                    'INSERT INTO faos.organizations(tenant_id,name) VALUES (%s,%s)',
                    (tenant, 'synthetic event contract fixture'),
                )
                app.execute(
                    'INSERT INTO faos.sessions(tenant_id,session_id) VALUES (%s,%s)',
                    (tenant, session),
                )
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
                with self.subTest(event_id=event_id):
                    with app.transaction():
                        app.execute("SELECT set_config('faos.tenant_id',%s,true)", (tenant,))
                        with self.assertRaises(psycopg.errors.CheckViolation):
                            with app.transaction():
                                append(event_id, 2, 'SESSION_CREATED', timestamp, payload)
                        count = app.execute(
                            'SELECT count(*) FROM faos.events WHERE tenant_id=%s AND session_id=%s',
                            (tenant, session),
                        ).fetchone()[0]
                        self.assertEqual(count, 1)

            valid_payload = '{"large":100000000000000000000,"label":"é","small":0.00001,"value":1.25}'
            with app.transaction():
                app.execute("SELECT set_config('faos.tenant_id',%s,true)", (tenant,))
                self.assertEqual(append(
                    'event-2', 2, 'QUALITY_RECORDED', '2026-01-01T00:00:00+05:30', valid_payload
                ), 'ACCEPTED')
                row = app.execute(
                    'SELECT session_id,event_id,sequence,kind,actor,occurred_at,reason,payload_json,schema_version '
                    'FROM faos.events WHERE tenant_id=%s AND session_id=%s AND event_id=%s',
                    (tenant, session, 'event-2'),
                ).fetchone()
                self.assertEqual(DomainEvent(*row).validate().payload['value'], 1.25)

            sequence = 3
            with app.transaction():
                app.execute("SELECT set_config('faos.tenant_id',%s,true)", (tenant,))
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

    def test_applied_authority_migration_checksum_change_is_rejected(self):
        plan = self.authority_plan()
        apply(self.conn,plan)
        before = self.history()
        changed = plan[:-1]+(replace(plan[-1],sha256='0'*64),)
        with self.assertRaisesRegex(ValueError,'APPLIED_MIGRATION_CHANGED:0017_event_contract_parity'):
            apply(self.conn,changed)
        self.assertEqual(self.history(),before)
