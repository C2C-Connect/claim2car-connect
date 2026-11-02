"""ASGI route/configuration unit tests; capture store I/O is mocked."""
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import Mock, patch
from uuid import UUID
from fastapi.testclient import TestClient
from app.capture_api import CaptureRuntime, create_capture_app, load_runtime
from app.identity import ActorBinding, Credential, CredentialResolver
from app.main import Settings
from database.capture_sessions import CaptureAuthorizationError, CaptureSession, CaptureSessionConflict, CaptureSessionNotFound, CaptureSessionStore, CaptureStorageUnavailable

class CaptureRouteTests(unittest.TestCase):
    def setUp(self):
        self.token='A'*43
        self.binding=ActorBinding('test-actor',UUID(int=1),'tenant_login_a')
        self.credential=Credential(hashlib.sha256(self.token.encode()).hexdigest(),self.binding,int(time.time())+3600)
        self.store=Mock(spec=CaptureSessionStore)
        self.session=CaptureSession(str(UUID(int=2)),str(self.binding.tenant_id),'test-actor','2026-10-22T00:00:00+00:00',True)
        self.store.create.return_value=self.session
        self.store.get.return_value=replace(self.session,created=False)
        self.runtime=CaptureRuntime(CredentialResolver([self.credential]),self.store,Settings())
        self.headers={'Authorization':'Bearer '+self.token}

    def client(self,runtime=None):
        return TestClient(create_capture_app(runtime if runtime is not None else self.runtime))

    def test_create_returns_201_and_preserves_server_metadata(self):
        with self.client() as client:
            response=client.post('/v1/capture-sessions',json={'session_id':self.session.session_id},headers=self.headers)
        self.assertEqual(response.status_code,201)
        self.assertEqual(response.json()['created_by'],'test-actor')
        self.assertEqual(response.json()['tenant_id'],str(self.binding.tenant_id))
        self.assertEqual(response.json()['scope'],'controlled-test')
        self.assertEqual(response.headers['cache-control'],'no-store')
        self.store.create.assert_called_once_with('Bearer '+self.token,self.session.session_id)

    def test_idempotent_retry_returns_200(self):
        self.store.create.return_value=replace(self.session,created=False)
        with self.client() as client:
            self.assertEqual(client.post('/v1/capture-sessions',json={'session_id':self.session.session_id},headers=self.headers).status_code,200)

    def test_get_ignores_attempted_query_and_header_tenant_override(self):
        with self.client() as client:
            response=client.get('/v1/capture-sessions/'+self.session.session_id+'?tenant_id=other',headers={**self.headers,'X-Tenant-ID':'other'})
        self.assertEqual(response.status_code,200)
        self.store.get.assert_called_once_with('Bearer '+self.token,self.session.session_id)

    def test_missing_unknown_expired_and_disabled_credentials_do_not_call_store(self):
        for record,headers in [(self.credential,{}),(self.credential,{'Authorization':'Bearer '+'Z'*43}),(replace(self.credential,expires_at=1),self.headers),(replace(self.credential,enabled=False),self.headers)]:
            with self.subTest(headers_present=bool(headers)),self.client(replace(self.runtime,resolver=CredentialResolver([record]))) as client:
                response=client.post('/v1/capture-sessions',json={'session_id':self.session.session_id},headers=headers)
                self.assertEqual(response.status_code,401)
                self.assertEqual(response.headers['www-authenticate'],'Bearer')
        self.store.create.assert_not_called()

    def test_body_cannot_choose_tenant_actor_or_database_login(self):
        for field in ('tenant_id','actor_id','database_role','database_url'):
            with self.subTest(field=field),self.client() as client:
                response=client.post('/v1/capture-sessions',json={'session_id':self.session.session_id,field:'attacker'},headers=self.headers)
                self.assertEqual(response.status_code,422)
        self.store.create.assert_not_called()

    def test_malformed_session_identifier_is_rejected(self):
        with self.client() as client:
            self.assertEqual(client.get('/v1/capture-sessions/not-a-uuid',headers=self.headers).status_code,422)
        self.store.get.assert_not_called()

    def test_known_errors_have_attributed_status_without_internal_detail(self):
        cases=[(CaptureAuthorizationError,403,'CAPTURE_AUTHORITY_DENIED'),(CaptureSessionNotFound,404,'CAPTURE_SESSION_NOT_FOUND'),(CaptureSessionConflict,409,'CAPTURE_SESSION_CONFLICT'),(CaptureStorageUnavailable,503,'CAPTURE_STORAGE_UNAVAILABLE'),(RuntimeError,500,'CAPTURE_OPERATION_FAILED')]
        for error,status,detail in cases:
            with self.subTest(error=error.__name__),self.client() as client:
                self.store.get.side_effect=error('synthetic-private-connection-detail')
                response=client.get('/v1/capture-sessions/'+self.session.session_id,headers=self.headers)
                self.assertEqual((response.status_code,response.json()),(status,{'detail':detail}))
                self.assertNotIn('synthetic-private-connection-detail',response.text)
                self.assertEqual(response.headers['cache-control'],'no-store')

    def test_capture_factory_requires_explicit_server_configuration(self):
        with patch.dict(os.environ,{},clear=True):
            with self.assertRaisesRegex(ValueError,'^CAPTURE_RUNTIME_CONFIGURATION_REQUIRED$'):
                create_capture_app()

    def config(self):
        return {'health_database_url':'postgresql://faos_app:synthetic@127.0.0.1:55432/claim2car_test','dsn_by_role':{'tenant_login_a':'postgresql://tenant_login_a:synthetic@127.0.0.1:55432/claim2car_test'},'credentials':[{'actor_id':'test-actor','tenant_id':str(self.binding.tenant_id),'database_role':'tenant_login_a','token_sha256':self.credential.token_sha256,'expires_at':self.credential.expires_at,'enabled':True}]}

    def load(self,value):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'private-config.json'
            path.write_text(json.dumps(value))
            return load_runtime(path)

    def test_valid_config_builds_runtime_without_connecting(self):
        with patch('database.capture_sessions.psycopg.connect') as connect:
            runtime=self.load(self.config())
            self.assertEqual(runtime.resolver.resolve('Bearer '+self.token),self.binding)
            with TestClient(create_capture_app(runtime)) as client:
                self.assertEqual(client.get('/health/live').status_code,200)
            connect.assert_not_called()

    def test_config_database_target_and_login_must_match(self):
        for dsn in ('postgresql://tenant_login_a:synthetic@127.0.0.1:55432/other','postgresql://postgres:synthetic@127.0.0.1:55432/claim2car_test'):
            value=self.config()
            value['dsn_by_role']['tenant_login_a']=dsn
            with self.subTest(dsn_case=dsn.split('@')[0].split(':')[1]),self.assertRaisesRegex(ValueError,'^INVALID_CAPTURE_RUNTIME_CONFIGURATION$'):
                self.load(value)

    def test_invalid_and_duplicate_config_keys_fail_without_secrets(self):
        value=self.config()
        value['raw_token']='synthetic-secret-do-not-disclose'
        with self.assertRaisesRegex(ValueError,'^INVALID_CAPTURE_RUNTIME_CONFIGURATION$'):
            self.load(value)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'private-config.json'
            path.write_text('{"credentials":[],"credentials":[]}')
            with self.assertRaisesRegex(ValueError,'^INVALID_CAPTURE_RUNTIME_CONFIGURATION$'):
                load_runtime(path)

if __name__=='__main__':
    unittest.main()
