"""Transactional foundation migrator; full authority plan is the default.

Not production-certified. Provisioning and recovery rehearsal remain prerequisites.
SQL must not contain transaction control or modify the migration ledger/lock.
Nonempty schemas without a ledger cannot be adopted by this runner.
"""
import argparse
import os
from pathlib import Path
import psycopg
from database.migration_plan import discover, discover_authority, pending

LOCK_KEY = 734190281632
LEDGER_DDL = """
CREATE TABLE IF NOT EXISTS public.faos_migration_history (
    ordinal bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name text NOT NULL UNIQUE,
    sha256 text NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    applied_at timestamptz NOT NULL DEFAULT clock_timestamp()
)
"""

def apply(conn, candidate):
    if not conn.autocommit or conn.info.transaction_status != psycopg.pq.TransactionStatus.IDLE:
        raise ValueError('IDLE_AUTOCOMMIT_CONNECTION_REQUIRED')
    with conn.transaction():
        conn.execute('SELECT pg_advisory_xact_lock(%s)', (LOCK_KEY,))
        ledger = conn.execute("SELECT to_regclass('public.faos_migration_history')").fetchone()[0]
        schema = conn.execute("SELECT to_regnamespace('faos')").fetchone()[0]
        if ledger is None and schema is not None:
            raise ValueError('UNTRACKED_EXISTING_SCHEMA')
        conn.execute(LEDGER_DDL)
        conn.execute('REVOKE ALL ON public.faos_migration_history FROM PUBLIC')
        history = conn.execute('SELECT name,sha256 FROM public.faos_migration_history ORDER BY ordinal').fetchall()
        plan = pending(candidate, history)
        for migration in plan:
            conn.execute(migration.sql)
            conn.execute('INSERT INTO public.faos_migration_history(name,sha256) VALUES (%s,%s)',
                         (migration.name, migration.sha256))
    return tuple(item.name for item in plan)

def run_migrations(legacy_baseline=False):
    root = Path(__file__).resolve().parents[1]
    if legacy_baseline:
        if os.environ.get('FAOS_LEGACY_BASELINE_ALLOWED') != '1':
            raise ValueError('EXPLICIT_LEGACY_TEST_BASELINE_REQUIRED')
        candidate = discover(root/'migrations')
    else:
        candidate = discover_authority(root)
    url = os.environ['MIGRATION_DATABASE_URL']
    with psycopg.connect(url, autocommit=True, connect_timeout=5) as conn:
        return apply(conn, candidate)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--legacy-baseline',action='store_true',help='Disposable pre-cutover comparison tests only; requires FAOS_LEGACY_BASELINE_ALLOWED=1')
    args = parser.parse_args()
    for name in run_migrations(legacy_baseline=args.legacy_baseline):
        print('Applied migration: ' + name)
