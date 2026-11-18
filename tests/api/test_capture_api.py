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
from app.capture_protocols import DEFAULT_CAPTURE_PROTOCOL
from database.claim_cases import ClaimCase, ClaimCaseStore
from database.collision_lifecycle import CollisionLifecycleRecord, CollisionClaimLink, CollisionLifecycleStore
from app.identity import ActorBinding, Credential, CredentialResolver
from app.main import Settings
from database.capture_sessions import CaptureAuthorizationError, CaptureSession, CaptureSessionConflict, CaptureSessionNotFound, CaptureSessionStore, CaptureStorageUnavailable

class CaptureRouteTests(unittest.TestCase):
    def setUp(self):
        self.token='A'*43
        self.binding=ActorBinding('test-actor',UUID(int=1),'tenant_login_a')
        self.credential=Credential(hashlib.sha256(self.token.encode()).hexdigest(),self.binding,int(time.time())+3600)
        self.store=Mock(spec=CaptureSessionStore)
        self.claim_store=Mock(spec=ClaimCaseStore)
        self.collision_store=Mock(spec=CollisionLifecycleStore)
        self.collision_store.list_vehicles.return_value=[]
        self.session=CaptureSession(str(UUID(int=2)),str(self.binding.tenant_id),'test-actor','2026-10-22T00:00:00+00:00',True,capture_protocol_version=DEFAULT_CAPTURE_PROTOCOL)
        self.store.create.return_value=self.session
        self.store.get.return_value=replace(self.session,created=False)
        self.runtime=CaptureRuntime(CredentialResolver([self.credential]),self.store,Settings(),self.claim_store,self.collision_store)
        self.headers={'Authorization':'Bearer '+self.token}

    def client(self,runtime=None):
        return TestClient(create_capture_app(runtime if runtime is not None else self.runtime))

    def test_claim_case_create_list_and_get_are_authenticated(self):
        record = ClaimCase(str(UUID(int=3)), str(self.binding.tenant_id), 'test-actor',
                           '2026-11-10T00:00:00+00:00', 'INTAKE_OPEN', True, str(UUID(int=5)))
        self.claim_store.create.return_value = record
        self.claim_store.list_owned.return_value = [record]
        self.claim_store.get.return_value = replace(record, created=False)
        with self.client() as client:
            created = client.post('/v1/claim-cases',
                json={'claim_id':record.claim_id,'request_id':str(UUID(int=4))},headers=self.headers)
            listed = client.get('/v1/claim-cases?limit=25',headers=self.headers)
            opened = client.get('/v1/claim-cases/'+record.claim_id,headers=self.headers)
            unauthorized = client.get('/v1/claim-cases')
        self.assertEqual(created.status_code,201)
        self.assertEqual(created.json()['scope'],'persistent-claim-case')
        self.assertEqual(created.json()['state'],'INTAKE_OPEN')
        self.assertEqual(listed.status_code,200)
        self.assertEqual(listed.json()[0]['claim_id'],record.claim_id)
        self.assertEqual(opened.status_code,200)
        self.assertEqual(unauthorized.status_code,401)
        self.assertEqual(created.headers['cache-control'],'no-store')
        self.claim_store.create.assert_called_once()
        self.claim_store.list_owned.assert_called_once_with('Bearer '+self.token,limit=25)
        self.claim_store.get.assert_called_once_with('Bearer '+self.token,claim_id=record.claim_id)


    def test_collision_root_and_claim_link_expose_capture_session_reference(self):
        collision_id, claim_id, session_id = str(UUID(int=30)), str(UUID(int=31)), str(UUID(int=32))
        record = CollisionLifecycleRecord(
            collision_id, str(self.binding.tenant_id), str(UUID(int=33)), 'test-actor',
            '2026-11-18T00:00:00+00:00', 'OPEN', 1, True,
        )
        link = CollisionClaimLink(
            collision_id, claim_id, session_id, DEFAULT_CAPTURE_PROTOCOL, 'test-actor',
            '2026-11-18T00:00:00+00:00', True,
        )
        self.collision_store.create.return_value = record
        self.collision_store.link_claim.return_value = link
        self.collision_store.get.return_value = record
        self.collision_store.list_claims.return_value = [replace(link, created=False)]
        with self.client() as client:
            created = client.post('/v1/collisions', headers=self.headers,
                json={'collision_id':collision_id,'request_id':str(UUID(int=34))})
            linked = client.post('/v1/collisions/'+collision_id+'/claims', headers=self.headers,
                json={'claim_id':claim_id,'request_id':str(UUID(int=35))})
            opened = client.get('/v1/collisions/'+collision_id, headers=self.headers)
        self.assertEqual(created.status_code,201,created.text)
        self.assertEqual(linked.status_code,201,linked.text)
        self.assertEqual(opened.status_code,200,opened.text)
        self.assertEqual(opened.json()['claims'][0]['capture_session_id'],session_id)
        self.assertEqual(opened.json()['claims'][0]['claim_id'],claim_id)
        self.assertEqual(created.headers['cache-control'],'no-store')
        self.collision_store.link_claim.assert_called_once()


    def test_collision_vehicle_link_uses_capture_registry_and_is_returned_by_collision_view(self):
        collision_id, claim_id, vehicle_id = str(UUID(int=60)), str(UUID(int=61)), str(UUID(int=62))
        linked_vehicle = {
            'collision_id': collision_id, 'vehicle_id': vehicle_id,
            'relationship': 'INVOLVED', 'linked_by': 'test-actor',
            'linked_at': '2026-11-18T00:00:00+00:00',
            'vin_source': 'CONSENTED_CAPTURE_SESSION',
            'vin_validation_status': 'CAPTURE_GATE_VALIDATED',
            'source_session_id': str(UUID(int=63)),
            'source_event_id': 'vehicle:' + str(UUID(int=64)),
            'source_consent_status': 'ACTIVE',
            'created': True,
        }
        self.collision_store.link_vehicle_from_capture.return_value = linked_vehicle
        self.collision_store.get.return_value = CollisionLifecycleRecord(
            collision_id, str(self.binding.tenant_id), str(UUID(int=65)),
            'test-actor', '2026-11-18T00:00:00+00:00', 'OPEN', 1, False,
        )
        self.collision_store.list_vehicles.return_value = [{**linked_vehicle, 'created': False}]
        with self.client() as client:
            linked = client.post(
                '/v1/collisions/' + collision_id + '/vehicles',
                headers=self.headers,
                json={
                    'claim_id': claim_id, 'vehicle_id': vehicle_id,
                    'request_id': str(UUID(int=66)), 'relationship': 'INVOLVED',
                },
            )
            opened = client.get('/v1/collisions/' + collision_id, headers=self.headers)
        self.assertEqual(linked.status_code, 201, linked.text)
        self.assertEqual(linked.json()['vehicle_id'], vehicle_id)
        self.assertEqual(linked.json()['vin_source'], 'CONSENTED_CAPTURE_SESSION')
        self.assertEqual(linked.json()['source_consent_status'], 'ACTIVE')
        self.assertNotIn('vin_hmac_sha256', linked.json())
        self.assertEqual(opened.status_code, 200, opened.text)
        self.assertEqual(opened.json()['vehicles'][0]['vehicle_id'], vehicle_id)
        self.collision_store.link_vehicle_from_capture.assert_called_once()
        self.collision_store.list_vehicles.assert_called_once_with('Bearer ' + self.token, collision_id)

    def test_review_collision_returns_verified_manifest_without_copying_original_bytes(self):
        collision_id, claim_id, session_id = str(UUID(int=40)), str(UUID(int=41)), str(UUID(int=42))
        link = CollisionClaimLink(
            collision_id, claim_id, session_id, DEFAULT_CAPTURE_PROTOCOL, 'operator',
            '2026-11-18T00:00:00+00:00', False,
        )
        manifest = {
            'session_id': session_id,
            'manifest_digest': 'a' * 64,
            'shot_list_version': DEFAULT_CAPTURE_PROTOCOL,
            'consent_recorded': True,
            'artifacts': [{'artifact_id': str(UUID(int=43)), 'slot': '00_front_exterior',
                           'sha256': 'b' * 64, 'byte_length': 123}],
        }
        self.collision_store.list_review_claims.return_value = [link]
        with tempfile.TemporaryDirectory() as root, patch.dict(os.environ, {
            'C2C_ARTIFACT_STORAGE_ROOT': root, 'C2C_VIN_HMAC_PEPPER': 'P' * 43,
        }), patch('app.capture_api.CaptureEvidenceService') as service:
            service.return_value.get_review_details.return_value = manifest
            with TestClient(create_capture_app(self.runtime, enable_evidence=True)) as client:
                response = client.get('/v1/review-collisions/'+collision_id, headers=self.headers)
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['claims'][0]['evidence_status'],'READY')
        self.assertEqual(response.json()['claims'][0]['evidence']['manifest_digest'],'a'*64)
        self.assertNotIn('payload_base64',response.text)
        self.collision_store.list_review_claims.assert_called_once_with('Bearer '+self.token,collision_id)
        service.return_value.get_review_details.assert_called_once_with('Bearer '+self.token,session_id)

    def test_protocol_registry_is_authenticated_and_exposes_both_executable_versions(self):
        with self.client() as client:
            registry = client.get('/v1/capture-protocols',headers=self.headers)
            unauthorized = client.get('/v1/capture-protocols')
        self.assertEqual(registry.status_code,200)
        self.assertEqual(registry.json()['default_protocol_version'],DEFAULT_CAPTURE_PROTOCOL)
        by_version = {item['version']:item for item in registry.json()['protocols']}
        self.assertEqual(by_version['claims2car-16-v1']['status'],'implemented')
        self.assertTrue(by_version['claims2car-16-v1']['capture_enabled'])
        self.assertEqual(len(by_version['claims2car-16-v1']['required_slots']),16)
        self.assertEqual(by_version['claims2car-16-v1']['required_slots'][0],'00_front_exterior')
        self.assertEqual(by_version['claims2car-16-v1']['required_slots'][-1],'15_license_and_insurance_docs')
        self.assertEqual(len(by_version['claims2car-16-v1']['slot_descriptions']),16)
        self.assertEqual(by_version['claims2car-12-v1']['status'],'implemented')
        self.assertTrue(by_version['claims2car-12-v1']['capture_enabled'])
        self.assertEqual(len(by_version['claims2car-12-v1']['required_slots']),12)
        self.assertEqual(unauthorized.status_code,401)

    def test_claim_case_request_defaults_to_16_v1_and_allows_explicit_12_v1(self):
        record = ClaimCase(str(UUID(int=13)),str(self.binding.tenant_id),'test-actor',
                           '2026-11-10T00:00:00+00:00','INTAKE_OPEN',True,str(UUID(int=14)))
        self.claim_store.create.return_value = record
        with self.client() as client:
            client.post('/v1/claim-cases',json={'claim_id':record.claim_id,'request_id':str(UUID(int=15))},headers=self.headers)
            client.post('/v1/claim-cases',json={'claim_id':record.claim_id,'request_id':str(UUID(int=16)),
                        'capture_protocol_version':'claims2car-12-v1'},headers=self.headers)
        self.assertEqual(self.claim_store.create.call_args_list[0].kwargs['capture_protocol_version'],DEFAULT_CAPTURE_PROTOCOL)
        self.assertEqual(self.claim_store.create.call_args_list[1].kwargs['capture_protocol_version'],'claims2car-12-v1')
    def test_claim_case_list_rejects_invalid_limit(self):
        with self.client() as client:
            response=client.get('/v1/claim-cases?limit=0',headers=self.headers)
        self.assertEqual(response.status_code,422)
        self.claim_store.list_owned.assert_not_called()

    def test_persistent_capture_session_scope_is_returned_without_owner_identity(self):
        production = replace(self.session, scope='persistent-claim-case',
                             claim_id=str(UUID(int=6)), owner_actor_id='private-owner-actor')
        self.store.get.return_value = production
        with self.client() as client:
            response = client.get('/v1/capture-sessions/'+self.session.session_id,headers=self.headers)
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['scope'],'persistent-claim-case')
        self.assertEqual(response.json()['claim_id'],str(UUID(int=6)))
        self.assertNotIn('owner_actor_id',response.json())

    def test_create_returns_201_and_preserves_server_metadata(self):
        with self.client() as client:
            response=client.post('/v1/capture-sessions',json={'session_id':self.session.session_id},headers=self.headers)
        self.assertEqual(response.status_code,201)
        self.assertEqual(response.json()['created_by'],'test-actor')
        self.assertEqual(response.json()['tenant_id'],str(self.binding.tenant_id))
        self.assertEqual(response.json()['scope'],'controlled-test')
        self.assertEqual(response.headers['cache-control'],'no-store')
        self.store.create.assert_called_once_with('Bearer '+self.token,self.session.session_id,
                                                   protocol_version=DEFAULT_CAPTURE_PROTOCOL)

    def test_idempotent_retry_returns_200(self):
        self.store.create.return_value=replace(self.session,created=False)
        with self.client() as client:
            self.assertEqual(client.post('/v1/capture-sessions',json={'session_id':self.session.session_id},headers=self.headers).status_code,200)

    def test_operator_session_list_returns_server_owned_records(self):
        self.store.list_owned.return_value=[self.session]
        with self.client() as client:
            response=client.get('/v1/capture-sessions?limit=25',headers=self.headers)
        self.assertEqual(response.status_code,200)
        self.assertEqual(len(response.json()),1)
        self.assertEqual(response.json()[0]['session_id'],self.session.session_id)
        self.assertEqual(response.json()[0]['scope'],'controlled-test')
        self.assertEqual(response.headers['cache-control'],'no-store')
        self.store.list_owned.assert_called_once_with('Bearer '+self.token,limit=25)

    def test_operator_session_list_requires_authentication_and_valid_limit(self):
        with self.client() as client:
            self.assertEqual(client.get('/v1/capture-sessions').status_code,401)
            self.assertEqual(client.get('/v1/capture-sessions?limit=0',headers=self.headers).status_code,422)
        self.store.list_owned.assert_not_called()

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


    def test_capture_factory_accepts_sealed_environment_json_configuration(self):
        value=self.config()
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ,{
            'C2C_CAPTURE_CONFIG_JSON':json.dumps(value),
            'C2C_ARTIFACT_STORAGE_ROOT':directory,
            'C2C_VIN_HMAC_PEPPER':'P'*43,
        },clear=True):
            with patch('database.capture_sessions.psycopg.connect') as connect:
                app=create_capture_app(enable_evidence=True)
                with TestClient(app) as client:
                    self.assertEqual(client.get('/health/live').status_code,200)
                connect.assert_not_called()

    def test_runtime_role_is_server_configured_and_resolved_with_identity(self):
        value=self.config()
        value['credentials'][0]['actor_role']='owner'
        runtime=self.load(value)
        resolved=runtime.resolver.resolve('Bearer '+self.token)
        self.assertEqual(resolved.actor_id,'test-actor')
        self.assertEqual(resolved.actor_role,'owner')

    def test_evidence_routes_require_provisioned_storage_and_pepper(self):
        with patch.dict(os.environ,{},clear=True):
            with self.assertRaisesRegex(ValueError,'PERSISTENT_EVIDENCE_CONFIGURATION_REQUIRED'):
                create_capture_app(self.runtime,enable_evidence=True)
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            os.environ,{'C2C_ARTIFACT_STORAGE_ROOT':directory,'C2C_VIN_HMAC_PEPPER':'P'*43}
        ):
            app=create_capture_app(self.runtime,enable_evidence=True)
            paths={route.path for route in app.routes}
            self.assertIn('/v1/capture-sessions/{session_id}/consent',paths)
            self.assertIn('/v1/capture-sessions/{session_id}/vehicle-reference',paths)
            self.assertIn('/v1/capture-sessions/{session_id}/artifacts',paths)
            self.assertIn('/v1/capture-sessions/{session_id}/quality',paths)
            self.assertIn('/v1/capture-sessions/{session_id}/seal',paths)
            self.assertIn('/v1/capture-sessions/{session_id}/review',paths)
            self.assertIn('/v1/review-queue',paths)
            self.assertIn('/v1/review-sessions/{session_id}/artifacts/{artifact_id}',paths)
            self.assertIn('/v1/review-collisions/{collision_id}',paths)

    def test_child_capture_app_does_not_recursively_mount_integrated_runtime(self):
        with patch.dict(os.environ,{'C2C_RUNTIME_MODE':'integrated'}):
            app=create_capture_app(self.runtime)
        paths={route.path for route in app.routes if hasattr(route,'path')}
        self.assertNotIn('/internal/v1/analysis/health',paths)

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


    def test_incident_intake_routes_are_disabled_until_explicit_feature_enablement(self):
        with tempfile.TemporaryDirectory() as root, patch.dict(os.environ, {
            'C2C_ARTIFACT_STORAGE_ROOT': root, 'C2C_VIN_HMAC_PEPPER': 'P'*43,
        }):
            app = create_capture_app(self.runtime, enable_evidence=True)
            with TestClient(app) as client:
                response = client.post('/v1/capture-sessions/'+str(UUID(int=2))+'/incident-consent',
                    json={'request_id':str(UUID(int=7)),'accepted':True},headers=self.headers)
                read = client.get('/v1/capture-sessions/'+str(UUID(int=2))+'/incident-intake',headers=self.headers)
        self.assertEqual(response.status_code,503)
        self.assertEqual(read.status_code,503)
        self.assertEqual(response.json(),{'detail':'INCIDENT_INTAKE_NOT_ENABLED'})

    def test_incident_intake_routes_validate_payload_when_enabled(self):
        with tempfile.TemporaryDirectory() as root, patch.dict(os.environ, {
            'C2C_ARTIFACT_STORAGE_ROOT': root, 'C2C_VIN_HMAC_PEPPER': 'P'*43,
            'C2C_INCIDENT_INTAKE_ENABLED': 'true',
        }), patch('app.capture_api.IncidentIntakeService') as service_type:
            app = create_capture_app(self.runtime, enable_evidence=True)
            with TestClient(app) as client:
                service_type.return_value.get_incident.return_value = {'incident_type':'collision','incident_city':'San Antonio'}
                response = client.post('/v1/capture-sessions/'+str(UUID(int=2))+'/incident-consent',
                    json={'request_id':str(UUID(int=7)),'accepted':True},headers=self.headers)
                read = client.get('/v1/capture-sessions/'+str(UUID(int=2))+'/incident-intake',headers=self.headers)
                invalid = client.post('/v1/capture-sessions/'+str(UUID(int=2))+'/incident-intake',
                    json={'request_id':str(UUID(int=8)),'occurred_at':'2026-11-10T10:00:00Z','incident_type':'collision',
                          'city':'San Antonio','region':'Texas','postal_code':'78201'},headers=self.headers)
        self.assertEqual(response.status_code,200)
        self.assertEqual(read.status_code,200)
        self.assertEqual(read.json()['incident_city'],'San Antonio')
        self.assertEqual(invalid.status_code,422)
        service_type.return_value.record_consent.assert_called_once()
        service_type.return_value.record_incident.assert_not_called()
        service_type.return_value.get_incident.assert_called_once()

if __name__=='__main__':
    unittest.main()
