"""Explicit authority migration track for controlled synthetic acceptance.

After cutover use this entry point, not the legacy seven-migration runner.
The same ledger, exact-byte checks and transaction lock protect both tracks.
"""
import os
from pathlib import Path
import psycopg
from database.migrate import apply
from database.migration_plan import discover


def migration_plan(root=None):
    root = Path(root) if root is not None else Path(__file__).resolve().parents[1]
    plan = tuple(sorted(discover(root/'migrations') + discover(root/'authority_migrations'),key=lambda item:item.name))
    versions = [item.name.split('_',1)[0] for item in plan]
    if len(versions) != len(set(versions)):
        raise ValueError('DUPLICATE_MIGRATION_VERSION')
    return plan


def run_migrations():
    plan = migration_plan()
    with psycopg.connect(os.environ['MIGRATION_DATABASE_URL'],autocommit=True,connect_timeout=5) as conn:
        return apply(conn,plan)

if __name__ == '__main__':
    for name in run_migrations():
        print('Applied authority-track migration: '+name)
