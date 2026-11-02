"""Real PostgreSQL tests; synthetic disposable database only. No HTTP/browser proof."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import threading
import unittest
from unittest.mock import patch
import uuid
from app.identity import ActorBinding,CredentialResolver
from database.capture_sessions import CaptureSessionNotFound,CaptureSessionStore
from database.intake_drafts import DraftAccessDenied,DraftConflict,IntakeDraftStore
from test_capture_sessions_integration import CaptureSessionIntegration

VIN='1HGCM82633A004352'
OTHER='1M8GDM9AXKP042788'

class IntakeDraftIntegration(unittest.TestCase):
    def setUp(self):
        self.base=CaptureSessionIntegration()
        self.addCleanup(self.base.doCleanups)
        self.base.setUp()
        self.base.store.create(self.base.auth(),self.base.key)
        self.store=IntakeDraftStore(self.base.store)
        self.request=str(uuid.uuid4())

    def save(self,**changes):
        args=dict(request_id=self.request,expected_revision=1,vin=VIN)
        args.update(changes)
        return self.store.save(self.base.auth(),self.base.key,**args)

    def count(self):
        return self.base.f.seed.execute('SELECT count(*) FROM faos.events WHERE tenant_id=%s AND session_id=%s',
                                        (self.base.f.tenants[0],self.base.key)).fetchone()[0]

    def test_save_and_fresh_store_readback(self):
        self.assertEqual(self.store.get(self.base.auth(),self.base.key).revision,1)
        self.save()
        reopened=IntakeDraftStore(CaptureSessionStore(CredentialResolver(self.base.credentials),self.base.dsns))
        state=reopened.get(self.base.auth(),self.base.key)
        self.assertEqual((state.revision,state.vin),(2,VIN))
        self.assertEqual(self.count(),2)

    def test_retry_and_old_receipt_do_not_duplicate_events(self):
        self.save()
        self.assertTrue(self.save().replayed)
        self.save(request_id=str(uuid.uuid4()),expected_revision=2,vin=OTHER)
        retry=self.save()
        self.assertEqual((retry.revision,retry.vin,retry.replayed),(2,VIN,True))
        self.assertEqual(self.store.get(self.base.auth(),self.base.key).vin,OTHER)
        self.assertEqual(self.count(),3)

    def test_payload_and_revision_conflicts_do_not_write(self):
        self.save()
        with self.assertRaisesRegex(DraftConflict,'IDEMPOTENCY_CONFLICT'):self.save(vin=OTHER)
        with self.assertRaisesRegex(DraftConflict,'REVISION_CONFLICT'):self.save(request_id=str(uuid.uuid4()))
        self.assertEqual(self.count(),2)

    def test_other_tenant_cannot_read_or_save(self):
        for action in (lambda:self.store.get(self.base.auth(1),self.base.key),
                       lambda:self.store.save(self.base.auth(1),self.base.key,request_id=self.request,expected_revision=1,vin=VIN)):
            with self.assertRaises(CaptureSessionNotFound):action()
        self.assertEqual(self.count(),1)

    def test_other_actor_in_same_tenant_denied(self):
        first=self.base.credentials[0]
        binding=ActorBinding('different-controlled-test-actor',first.binding.tenant_id,first.binding.database_role)
        sessions=CaptureSessionStore(CredentialResolver([replace(first,binding=binding)]),self.base.dsns)
        store=IntakeDraftStore(sessions)
        with self.assertRaises(DraftAccessDenied):store.get(self.base.auth(),self.base.key)
        with self.assertRaises(DraftAccessDenied):store.save(self.base.auth(),self.base.key,request_id=self.request,expected_revision=1,vin=VIN)
        self.assertEqual(self.count(),1)

    def test_failure_after_append_rolls_back(self):
        with patch('database.intake_drafts.IntakeDraft',side_effect=RuntimeError('construction failure')):
            with self.assertRaises(RuntimeError):self.save()
        self.assertEqual(self.count(),1)
        self.assertEqual(self.save().revision,2)

    def test_two_connections_only_one_stale_writer_wins(self):
        gate=threading.Barrier(2)
        def worker(vin):
            gate.wait(timeout=10)
            try:return self.save(request_id=str(uuid.uuid4()),vin=vin).revision
            except DraftConflict as error:return str(error)
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures=[pool.submit(worker,v) for v in (VIN,OTHER)]
            results=[f.result(timeout=20) for f in futures]
        self.assertCountEqual(results,[2,'REVISION_CONFLICT'])
        self.assertEqual(self.count(),2)

    def test_concurrent_identical_retry_writes_once(self):
        gate=threading.Barrier(2)
        def worker():
            gate.wait(timeout=10)
            return self.save()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures=[pool.submit(worker) for _ in range(2)]
            results=[f.result(timeout=20) for f in futures]
        self.assertEqual([r.revision for r in results],[2,2])
        self.assertCountEqual([r.replayed for r in results],[False,True])
        self.assertEqual(self.count(),2)

    def test_invalid_vin_is_not_persisted(self):
        with self.assertRaises(ValueError):self.save(vin='1HGCM82643A004352')
        self.assertEqual(self.count(),1)

if __name__=='__main__':unittest.main()
