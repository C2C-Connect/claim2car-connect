import os
from pathlib import Path

import psycopg


def run_migrations():
    migrations_dir = Path(__file__).resolve().parents[1] / 'migrations'
    paths = sorted(migrations_dir.glob('*.sql'))
    if not paths:
        raise ValueError('MIGRATIONS_NOT_FOUND')
    plan = []
    for path in paths:
        sql = path.read_text(encoding='utf-8')
        if not sql.strip():
            raise ValueError('EMPTY_MIGRATION:' + path.name)
        plan.append((path.name, sql))
    conn_str = os.getenv('MIGRATION_DATABASE_URL', 'postgresql://faos_migrator:synthetic-migrator-only@127.0.0.1:55432/claim2car_test')
    with psycopg.connect(conn_str, autocommit=True) as conn:
        for name, sql in plan:
            print(f"Executing migration: {name}")
            conn.execute(sql)


if __name__ == '__main__':
    run_migrations()
