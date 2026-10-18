"""Application-process readback test; not a database crash-recovery test."""
from dataclasses import asdict
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
import uuid

import psycopg
from app.domain_events import DomainEvent
from database.journal import append, tenant_transaction
from database.readback import load_journal


class ProcessRecovery(unittest.TestCase):
    def test_committed_history_survives_fresh_reader_process(self):
        url = os.getenv('APP_DATABASE_URL', 'postgresql://faos_app:synthetic-app-only@127.0.0.1:55432/claim2car_test')
        tenant = str(uuid.uuid4())
        other = str(uuid.uuid4())
        session = 'recovery-' + uuid.uuid4().hex
        event = DomainEvent(session, 'event-1', 1, 'SESSION_CREATED', 'synthetic-test', '2026-01-01T00:00:00Z', 'process recovery test', '{}')
        with psycopg.connect(url, autocommit=True) as conn:
            with tenant_transaction(conn, tenant):
                conn.execute('INSERT INTO faos.organizations(tenant_id,name) VALUES (%s,%s)', (tenant, 'synthetic recovery fixture'))
                conn.execute('INSERT INTO faos.sessions(tenant_id,session_id) VALUES (%s,%s)', (tenant, session))
            self.assertEqual(append(conn, tenant, event), 'ACCEPTED')
            self.assertEqual(append(conn, tenant, event), 'DUPLICATE')
        child = '''import json, os
from dataclasses import asdict
import psycopg
from database.readback import load_journal
with psycopg.connect(os.environ['RECOVERY_DATABASE_URL'], autocommit=True) as conn:
    journal = load_journal(conn, os.environ['RECOVERY_TENANT'], os.environ['RECOVERY_SESSION'])
    print(json.dumps([asdict(event) for event in journal.events], sort_keys=True))
'''
        env = os.environ.copy()
        env.update(RECOVERY_DATABASE_URL=url, RECOVERY_TENANT=tenant, RECOVERY_SESSION=session)
        result = subprocess.run([sys.executable, '-c', child], cwd=Path(__file__).resolve().parents[2], env=env, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), [asdict(event)])
        with psycopg.connect(url, autocommit=True) as conn:
            with self.assertRaisesRegex(ValueError, '^SESSION_NOT_FOUND_OR_NOT_VISIBLE$'):
                load_journal(conn, other, session)
            with self.assertRaisesRegex(ValueError, '^SESSION_NOT_FOUND_OR_NOT_VISIBLE$'):
                load_journal(conn, tenant, session + '-missing')
            self.assertEqual(load_journal(conn, tenant, session).events, (event,))


if __name__ == '__main__':
    unittest.main()
