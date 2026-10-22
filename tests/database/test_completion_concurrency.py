"""Two-connection receipt/revocation races; not exhaustive concurrency proof."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import os
from threading import Barrier
import unittest
import uuid
import psycopg
from database.completion import record_registered_completion
from database.eligibility import check_registered_completion
from database.journal import append
from database.readback import load_journal

class CompletionConcurrencyTests(unittest.TestCase):
    def setUp(self):
        import test_atomic_completion as fixtures
        self.base = fixtures.AtomicCompletionTests()
        self.addCleanup(self.base.doCleanups)
        self.base.setUp()
        self.f = self.base.f
        self.storage = self.base.storage

    def race(self, first, second):
        barrier = Barrier(2, timeout=10)
        def worker(role, action):
            url = self.f.admin_url if role == 'faos_writer' else os.getenv('APP_DATABASE_URL', 'postgresql://faos_app:synthetic-app-only@127.0.0.1:55432/claim2car_test')
            with psycopg.connect(url, autocommit=True, connect_timeout=5) as conn:
                if role == 'faos_writer':
                    conn.execute('SET ROLE faos_writer')
                self.assertEqual(conn.execute('SELECT current_user').fetchone()[0], role)
                conn.execute("SET default_transaction_isolation='read committed'")
                conn.execute("SET lock_timeout='5s'")
                conn.execute("SET statement_timeout='8s'")
                barrier.wait()
                return action(conn)
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(worker, role, action) for role, action in (first, second)]
            return [future.result(timeout=20) for future in futures]

    def complete(self, conn, request):
        f = self.f
        return record_registered_completion(conn, f.tenant, f.session, request, f.data)

    def test_identical_concurrent_request_creates_one_receipt(self):
        request = self.storage.request
        action = lambda conn: self.complete(conn, request)
        results = self.race(('faos_writer', action), ('faos_writer', action))
        self.assertCountEqual([result.receipt_status for result in results], ['RECORDED', 'DUPLICATE'])
        for result in results:
            self.assertEqual((result.request_id, result.seal_event_id, result.event_sequence, result.decision.status),
                             (request, self.f.seal, len(self.f.events), 'ELIGIBLE'))
        self.assertEqual(self.storage.receipts(), [(request, self.f.seal, len(self.f.events), 'faos_writer')])

    def test_distinct_concurrent_requests_record_distinct_receipts(self):
        first, second = self.storage.request, str(uuid.uuid4())
        results = self.race(('faos_writer', lambda conn: self.complete(conn, first)),
                            ('faos_writer', lambda conn: self.complete(conn, second)))
        self.assertEqual([result.receipt_status for result in results], ['RECORDED', 'RECORDED'])
        self.assertCountEqual(self.storage.receipts(), [(request, self.f.seal, len(self.f.events), 'faos_writer') for request in (first, second)])

    def test_concurrent_revocation_has_only_serialized_outcomes(self):
        f = self.f
        revocation = replace(f.events[1], event_id='race-revocation', sequence=len(f.events)+1,
                             payload_json='{"disclosure_version":"synthetic-v1","evidence_scope":false}')
        def complete(conn):
            try:
                return ('RECORDED', self.complete(conn, self.storage.request))
            except ValueError as error:
                return ('BLOCKED', str(error))
        completed, appended = self.race(('faos_writer', complete),
                                        ('faos_app', lambda conn: append(conn, f.tenant, revocation)))
        self.assertEqual(appended, 'ACCEPTED')
        self.assertEqual(load_journal(f.conn, f.tenant, f.session).events, f.events + (revocation,))
        if completed[0] == 'RECORDED':
            result = completed[1]
            self.assertEqual((result.receipt_status, result.event_sequence, result.decision.status),
                             ('RECORDED', len(f.events), 'ELIGIBLE'))
            self.assertEqual(self.storage.receipts(), [(self.storage.request, f.seal, len(f.events), 'faos_writer')])
        else:
            self.assertEqual(completed[0], 'BLOCKED')
            self.assertIn('REQUIRED_CONSENT_MISSING', completed[1])
            self.assertEqual(self.storage.receipts(), [])
        with self.assertRaisesRegex(ValueError, 'REQUIRED_CONSENT_MISSING'):
            check_registered_completion(f.conn, f.tenant, f.session, f.data)

if __name__ == '__main__':
    unittest.main()
