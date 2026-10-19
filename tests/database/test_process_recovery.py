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


class PersistedEvidenceRecovery(unittest.TestCase):
    """Synthetic persisted-history integration, not durable completion or crash recovery."""
    def setUp(self):
        from hashlib import sha256
        from app.evidence_manifest import load_shot_contract
        from app.synthetic_evidence import manifest_for, reconstruct
        self.url = os.getenv('APP_DATABASE_URL', 'postgresql://faos_app:synthetic-app-only@127.0.0.1:55432/claim2car_test')
        self.tenant = str(uuid.uuid4())
        self.session = 'evidence-recovery-' + uuid.uuid4().hex
        self.events = []
        self.data = {}
        self.add_event('SESSION_CREATED', {'synthetic': True})
        self.add_event('CONSENT_RECORDED', {'disclosure_version': 'synthetic-v1', 'evidence_scope': True})
        self.add_event('VEHICLE_RECORDED', {'status': 'AVAILABLE', 'reference': 'synthetic-vehicle', 'unavailable_reason': None})
        version, slots = load_shot_contract()
        for slot in slots:
            data = ('SYNTHETIC-NOT-A-PHOTO-' + slot).encode()
            self.data[slot] = data
            self.add_event('ARTIFACT_REGISTERED', {'artifact_id': slot, 'slot': slot, 'bytes_hex': data.hex(), 'sha256_hex': sha256(data).hexdigest()})
            self.add_event('QUALITY_RECORDED', {'artifact_id': slot, 'passed': True, 'method': 'synthetic-fixture'})
        self.digest = manifest_for(reconstruct(self.session, self.events)).digest()
        self.add_event('MANIFEST_SEALED', {'schema_version': '0.1', 'shot_list_version': version, 'manifest_digest': self.digest})
        with psycopg.connect(self.url, autocommit=True) as conn:
            role = conn.execute('SELECT current_user,rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user').fetchone()
            self.assertEqual(role, ('faos_app', False, False))
            with tenant_transaction(conn, self.tenant):
                conn.execute('INSERT INTO faos.organizations(tenant_id,name) VALUES (%s,%s)', (self.tenant, 'synthetic evidence recovery'))
                conn.execute('INSERT INTO faos.sessions(tenant_id,session_id) VALUES (%s,%s)', (self.tenant, self.session))
            for event in self.events:
                self.assertEqual(append(conn, self.tenant, event), 'ACCEPTED')

    def add_event(self, kind, payload):
        n = len(self.events) + 1
        self.events.append(DomainEvent(self.session, str(n), n, kind, 'synthetic-test', '2026-10-19T00:00:00Z',
                                       'persisted evidence test', json.dumps(payload, sort_keys=True, separators=(',', ':'))))
        return self.events[-1]

    def test_full_evidence_reconstructs_in_fresh_process(self):
        from app.synthetic_evidence import reconstruct, check_completion
        child = """import json, os, sys
from dataclasses import asdict
import psycopg
from database.readback import load_journal
from app.synthetic_evidence import reconstruct, check_completion
value = json.load(sys.stdin)
with psycopg.connect(os.environ['RECOVERY_DATABASE_URL'], autocommit=True) as conn:
    history = load_journal(conn, value['tenant'], value['session']).events
data = {key: bytes.fromhex(raw) for key, raw in value['bytes_hex'].items()}
state = reconstruct(value['session'], history)
decision = check_completion(value['session'], history, data, value['trusted_digest'])
print(json.dumps({'state': asdict(state), 'decision': asdict(decision)}, sort_keys=True))
"""
        env = os.environ.copy()
        env['RECOVERY_DATABASE_URL'] = self.url
        payload = {'tenant': self.tenant, 'session': self.session, 'bytes_hex': {key: raw.hex() for key, raw in self.data.items()}, 'trusted_digest': self.digest}
        result = subprocess.run([sys.executable, '-c', child], input=json.dumps(payload), cwd=Path(__file__).resolve().parents[2], env=env, text=True, capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        expected = {'state': asdict(reconstruct(self.session, self.events)),
                    'decision': asdict(check_completion(self.session, self.events, self.data, self.digest))}
        self.assertEqual(json.loads(result.stdout), json.loads(json.dumps(expected)))

    def test_persisted_consent_revocation_blocks_completion(self):
        from app.synthetic_evidence import check_completion
        event = self.add_event('CONSENT_RECORDED', {'disclosure_version': 'synthetic-v1', 'evidence_scope': False})
        with psycopg.connect(self.url, autocommit=True) as conn:
            self.assertEqual(append(conn, self.tenant, event), 'ACCEPTED')
            history = load_journal(conn, self.tenant, self.session).events
        self.assertEqual(history, tuple(self.events))
        with self.assertRaisesRegex(ValueError, 'REQUIRED_CONSENT_MISSING'):
            check_completion(self.session, history, self.data, self.digest)

    def test_other_tenant_cannot_load_evidence(self):
        with psycopg.connect(self.url, autocommit=True) as conn:
            with self.assertRaisesRegex(ValueError, '^SESSION_NOT_FOUND_OR_NOT_VISIBLE$'):
                load_journal(conn, str(uuid.uuid4()), self.session)
            self.assertEqual(load_journal(conn, self.tenant, self.session).events, tuple(self.events))

    def test_tampered_bytes_block_persisted_history(self):
        from app.synthetic_evidence import check_completion
        with psycopg.connect(self.url, autocommit=True) as conn:
            history = load_journal(conn, self.tenant, self.session).events
        with self.assertRaisesRegex(ValueError, 'INTEGRITY_NOT_VERIFIED'):
            check_completion(self.session, history, dict(self.data, front=b'tampered'), self.digest)

    def test_wrong_root_blocks_persisted_history(self):
        from app.synthetic_evidence import check_completion
        with psycopg.connect(self.url, autocommit=True) as conn:
            history = load_journal(conn, self.tenant, self.session).events
        with self.assertRaisesRegex(ValueError, 'INTEGRITY_NOT_VERIFIED'):
            check_completion(self.session, history, self.data, '0' * 64)

    def test_full_history_retry_is_idempotent(self):
        with psycopg.connect(self.url, autocommit=True) as conn:
            for event in self.events:
                self.assertEqual(append(conn, self.tenant, event), 'DUPLICATE')
            self.assertEqual(load_journal(conn, self.tenant, self.session).events, tuple(self.events))


if __name__ == '__main__':
    unittest.main()
