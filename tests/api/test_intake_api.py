"""ASGI unit tests with mocked authorization/store/foundation factory; no PostgreSQL proof."""
from dataclasses import replace
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch
from uuid import UUID
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.intake_api import create_intake_app
from app.identity import AuthenticationError
from database.capture_sessions import CaptureAuthorizationError,CaptureSessionConflict,CaptureSessionNotFound,CaptureStorageUnavailable
from database.intake_drafts import DraftAccessDenied,DraftConflict,IntakeDraft

class IntakeRouteTests(unittest.TestCase):
    def setUp(self):
        self.key=str(UUID(int=2));self.request=str(UUID(int=3))
        self.path='/v1/capture-sessions/'+self.key+'/draft'
        self.headers={'Authorization':'Bearer fixture-only'}
        self.body={'request_id':self.request,'expected_revision':1,'vin':'1HGCM82633A004352'}
        self.store=Mock()
        self.store.get.return_value=IntakeDraft(self.key,1,None)
        self.store.save.return_value=IntakeDraft(self.key,2,self.body['vin'])
        resolver=Mock()
        def resolve(header):
            if header!=self.headers['Authorization']:raise AuthenticationError('private')
        resolver.resolve.side_effect=resolve
        self.runtime=SimpleNamespace(resolver=resolver,store=Mock())
        self.addCleanup(patch.stopall)
        patch('app.intake_api.create_capture_app',side_effect=lambda runtime:FastAPI()).start()
        patch('app.intake_api.IntakeDraftStore',return_value=self.store).start()
        self.client=TestClient(create_intake_app(self.runtime))
        self.addCleanup(self.client.close)

    def test_get_empty_draft(self):
        r=self.client.get(self.path,headers=self.headers)
        self.assertEqual((r.status_code,r.json()['revision'],r.json()['vin']),(200,1,None))
        self.assertEqual(r.headers['cache-control'],'no-store')
        self.store.get.assert_called_once_with(self.headers['Authorization'],self.key)

    def test_save_forwards_only_declared_fields(self):
        r=self.client.put(self.path,headers=self.headers,json=self.body)
        self.assertEqual((r.status_code,r.json()['revision']),(200,2))
        self.assertEqual(r.json()['scope'],'controlled-test-vin-draft')
        self.assertEqual(r.headers['cache-control'],'no-store')
        self.store.save.assert_called_once_with(self.headers['Authorization'],self.key,**self.body)

    def test_idempotent_receipt_flag_preserved(self):
        self.store.save.return_value=replace(self.store.save.return_value,replayed=True)
        r=self.client.put(self.path,headers=self.headers,json=self.body)
        self.assertTrue(r.json()['replayed'])

    def test_missing_and_unknown_credentials(self):
        for headers in ({},{'Authorization':'Bearer invalid'}):
            r=self.client.put(self.path,headers=headers,json=self.body)
            self.assertEqual(r.status_code,401)
            self.assertEqual(r.headers['www-authenticate'],'Bearer')
        self.store.save.assert_not_called()

    def test_get_requires_auth(self):
        self.assertEqual(self.client.get(self.path).status_code,401)
        self.store.get.assert_not_called()

    def test_extra_identity_fields_rejected_without_echo(self):
        for name in ('tenant_id','actor_id','database_role','database_url'):
            r=self.client.put(self.path,headers=self.headers,json={**self.body,name:'secret-input'})
            self.assertEqual((r.status_code,r.json()),(422,{'detail':'INVALID_INTAKE_REQUEST'}))
            self.assertNotIn('secret-input',r.text)
            self.assertEqual(r.headers['cache-control'],'no-store')
        self.store.save.assert_not_called()

    def test_revision_is_strict_positive_integer(self):
        for revision in (True,'1',0,-1,1.2):
            self.assertEqual(self.client.put(self.path,headers=self.headers,json={**self.body,'expected_revision':revision}).status_code,422)
        self.store.save.assert_not_called()

    def test_malformed_identifiers(self):
        self.assertEqual(self.client.get('/v1/capture-sessions/bad/draft',headers=self.headers).status_code,422)
        self.assertEqual(self.client.put(self.path,headers=self.headers,json={**self.body,'request_id':'bad'}).status_code,422)
        self.store.save.assert_not_called();self.store.get.assert_not_called()

    def test_malformed_json_not_echoed(self):
        r=self.client.put(self.path,headers={**self.headers,'Content-Type':'application/json'},content='{"secret-input":')
        self.assertEqual(r.status_code,422);self.assertNotIn('secret-input',r.text)

    def test_query_or_header_cannot_override_actor(self):
        r=self.client.get(self.path+'?tenant_id=other',headers={**self.headers,'X-Tenant-ID':'other'})
        self.assertEqual(r.status_code,200)
        self.store.get.assert_called_once_with(self.headers['Authorization'],self.key)

    def test_known_failures_are_sanitized(self):
        cases=[(AuthenticationError,401,'UNAUTHORIZED'),(CaptureAuthorizationError,403,'INTAKE_ACCESS_DENIED'),
               (DraftAccessDenied,403,'INTAKE_ACCESS_DENIED'),(CaptureSessionNotFound,404,'CAPTURE_SESSION_NOT_FOUND'),
               (DraftConflict,409,'INTAKE_DRAFT_CONFLICT'),(CaptureSessionConflict,409,'INTAKE_DRAFT_CONFLICT'),
               (CaptureStorageUnavailable,503,'CAPTURE_STORAGE_UNAVAILABLE'),(ValueError,422,'INVALID_INTAKE_REQUEST'),
               (RuntimeError,500,'INTAKE_OPERATION_FAILED')]
        for error,status,detail in cases:
            self.store.save.side_effect=error('secret-internal-detail')
            r=self.client.put(self.path,headers=self.headers,json=self.body)
            self.assertEqual((r.status_code,r.json()),(status,{'detail':detail}))
            self.assertNotIn('secret-internal-detail',r.text)
            self.assertEqual(r.headers['cache-control'],'no-store')

    def test_environment_configuration_required(self):
        with patch.dict('os.environ',{},clear=True):
            with self.assertRaisesRegex(ValueError,'CAPTURE_RUNTIME_CONFIGURATION_REQUIRED'):create_intake_app()

if __name__=='__main__':unittest.main()
