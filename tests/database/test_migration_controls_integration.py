"""Real PostgreSQL tests in a unique disposable database per method.
Requires the synthetic CI bootstrap roles and a database-creating admin.
Does not connect to production; defaults match the ephemeral compose stack.
"""
from dataclasses import replace
import hashlib
import os
import unittest
import uuid
import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo
from database.migrate import apply, LOCK_KEY
from database.migration_plan import Migration

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
