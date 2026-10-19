"""Mocked connection tests; not PostgreSQL evidence."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch
import psycopg
import database.migrate as migrate
from database.migration_plan import Migration

class MigrationPreflightTests(unittest.TestCase):
    def connection(self, history=(), ledger='faos_migration_history', schema=None):
        conn=MagicMock()
        conn.autocommit=True
        conn.info.transaction_status=psycopg.pq.TransactionStatus.IDLE
        def execute(sql, params=None):
            cursor=MagicMock()
            if 'to_regclass' in sql: cursor.fetchone.return_value=(ledger,)
            elif 'to_regnamespace' in sql: cursor.fetchone.return_value=(schema,)
            elif 'ORDER BY ordinal' in sql: cursor.fetchall.return_value=list(history)
            return cursor
        conn.execute.side_effect=execute
        return conn
    def candidate(self):
        return (Migration('0001_first.sql','a'*64,'SELECT 1;'),)
    def test_initial_execution(self):
        conn=self.connection(ledger=None)
        self.assertEqual(migrate.apply(conn,self.candidate()), ('0001_first.sql',))
        conn.execute.assert_any_call('SELECT 1;')
        sqls=[c.args[0] for c in conn.execute.call_args_list]
        self.assertIn('pg_advisory_xact_lock',sqls[0])
        conn.transaction.return_value.__exit__.assert_called_once_with(None,None,None)
    def test_noop(self):
        conn=self.connection([('0001_first.sql','a'*64)])
        self.assertEqual(migrate.apply(conn,self.candidate()), ())
        self.assertNotIn('SELECT 1;', [c.args[0] for c in conn.execute.call_args_list])
    def test_history_conflict(self):
        conn=self.connection([('0001_first.sql','b'*64)])
        with self.assertRaisesRegex(ValueError,'APPLIED_MIGRATION_CHANGED'):
            migrate.apply(conn,self.candidate())
        self.assertNotIn('SELECT 1;', [c.args[0] for c in conn.execute.call_args_list])
    def test_untracked_schema(self):
        conn=self.connection(ledger=None,schema='faos')
        with self.assertRaisesRegex(ValueError,'UNTRACKED_EXISTING_SCHEMA'):
            migrate.apply(conn,self.candidate())
    def test_bad_connections(self):
        for auto,status in [(False,psycopg.pq.TransactionStatus.IDLE),(True,psycopg.pq.TransactionStatus.INTRANS)]:
            conn=self.connection(); conn.autocommit=auto; conn.info.transaction_status=status
            with self.assertRaisesRegex(ValueError,'IDLE_AUTOCOMMIT_CONNECTION_REQUIRED'):
                migrate.apply(conn,self.candidate())
            conn.execute.assert_not_called()
    def test_filesystem_preflight_before_connect(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(migrate,'__file__',str(Path(tmp)/'database/migrate.py')), patch.object(migrate.psycopg,'connect') as connect:
                with self.assertRaisesRegex(ValueError,'MIGRATIONS_NOT_FOUND'):
                    migrate.run_migrations()
                connect.assert_not_called()
