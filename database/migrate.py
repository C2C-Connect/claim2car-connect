import os, psycopg
from pathlib import Path
def run_migrations():
    conn_str = os.getenv('MIGRATION_DATABASE_URL', 'postgresql://faos_migrator:synthetic-migrator-only@127.0.0.1:55432/claim2car_test')
    with psycopg.connect(conn_str, autocommit=True) as conn:
        migrations_dir = Path('migrations')
        for path in sorted(migrations_dir.glob('*.sql')):
            print(f"Executing migration: {path.name}")
            conn.execute(path.read_text())
if __name__ == '__main__':
    run_migrations()
