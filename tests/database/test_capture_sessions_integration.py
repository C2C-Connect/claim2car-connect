"""Real PostgreSQL-backed service tests; not HTTP or real-image intake proof."""
from dataclasses import replace
import json
import hashlib
import base64
import time
import tempfile
import unittest
from unittest.mock import patch
import uuid
from psycopg import sql
from psycopg.conninfo import make_conninfo
from app.identity import ActorBinding, AuthenticationError, Credential, CredentialResolver
from database.capture_sessions import CaptureAuthorizationError, CaptureSessionConflict, CaptureSessionNotFound, CaptureSessionStore, CaptureStorageUnavailable
from database.claim_cases import ClaimCaseConflict, ClaimCaseNotFound, ClaimCaseStore
from database.financial_ledger import PersistentFinancialLedger
from backend.app.anchor.ledger import PartnerAcceptanceRecord
from app.artifact_storage import OriginalByteStore
from database.capture_evidence import CaptureEvidenceService
from app.evidence_manifest import CANONICAL_SLOTS, LEGACY_CANONICAL_SLOTS
from app.capture_protocols import DEFAULT_CAPTURE_PROTOCOL, LEGACY_CAPTURE_PROTOCOL, resolve_capture_protocol

class CaptureSessionIntegration(unittest.TestCase):
    def setUp(self):
        import test_tenant_authority_integration as fixtures
        self.f=fixtures.TenantAuthorityIntegration()
        self.addCleanup(self.f.doCleanups)
        self.f.setUp()
        self.tokens=['A'*43,'B'*43]
        self.credentials=[]
        self.dsns={}
        for index,role in enumerate(self.f.roles):
            password=uuid.uuid4().hex
            self.f.admin.execute(sql.SQL('ALTER ROLE {} PASSWORD {}').format(sql.Identifier(role),sql.Literal(password)))
            self.dsns[role]=make_conninfo(self.f.admin.info.dsn,dbname=self.f.db,user=role,password=password)
            binding=ActorBinding('capture-actor-'+str(index),uuid.UUID(self.f.tenants[index]),role)
            self.credentials.append(Credential(hashlib.sha256(self.tokens[index].encode()).hexdigest(),binding,int(time.time())+3600))
        self.owner_token='C'*43
        self.other_owner_token='D'*43
        self.reviewer_token='E'*43
        self.other_operator_token='F'*43
        self.credentials.extend([
            Credential(hashlib.sha256(self.owner_token.encode()).hexdigest(),
                ActorBinding('claim-owner-0',uuid.UUID(self.f.tenants[0]),self.f.roles[0],'owner'),int(time.time())+3600),
            Credential(hashlib.sha256(self.other_owner_token.encode()).hexdigest(),
                ActorBinding('claim-owner-1',uuid.UUID(self.f.tenants[0]),self.f.roles[0],'owner'),int(time.time())+3600),
            Credential(hashlib.sha256(self.reviewer_token.encode()).hexdigest(),
                ActorBinding('claim-reviewer-0',uuid.UUID(self.f.tenants[0]),self.f.roles[0],'reviewer'),int(time.time())+3600),
        ])
        self.credentials.append(Credential(hashlib.sha256(self.other_operator_token.encode()).hexdigest(),
            ActorBinding('other-operator-0',uuid.UUID(self.f.tenants[0]),self.f.roles[0],'operator'),int(time.time())+3600))
        self.store=CaptureSessionStore(CredentialResolver(self.credentials),self.dsns)
        self.claim_cases=ClaimCaseStore(self.store)
        self.key=str(uuid.uuid4())

    def auth(self,index=0):
        return 'Bearer '+self.tokens[index]

    def owner_auth(self,other=False):
        return 'Bearer '+(self.other_owner_token if other else self.owner_token)

    def reviewer_auth(self):
        return 'Bearer '+self.reviewer_token

    def other_operator_auth(self):
        return 'Bearer '+self.other_operator_token

    def test_claim_case_create_retry_and_owned_readback(self):
        claim_id, request_id = str(uuid.uuid4()), str(uuid.uuid4())
        first = self.claim_cases.create(self.auth(), claim_id=claim_id, request_id=request_id)
        retry = self.claim_cases.create(self.auth(), claim_id=claim_id, request_id=request_id)
        self.assertTrue(first.created)
        self.assertFalse(retry.created)
        self.assertEqual((first.claim_id, first.tenant_id, first.created_by, first.state,
                          first.capture_protocol_version),
                         (claim_id, self.f.tenants[0], 'capture-actor-0', 'INTAKE_OPEN', DEFAULT_CAPTURE_PROTOCOL))
        self.assertEqual(self.claim_cases.get(self.auth(), claim_id).claim_id, claim_id)
        self.assertEqual([item.claim_id for item in self.claim_cases.list_owned(self.auth())], [claim_id])
        self.assertEqual(self.f.seed.execute(
            'SELECT count(*) FROM faos.claim_cases WHERE tenant_id=%s AND claim_id=%s',
            (self.f.tenants[0], claim_id)).fetchone()[0], 1)
        payload = self.f.seed.execute(
            "SELECT payload_json FROM faos.events WHERE tenant_id=%s AND session_id=%s AND event_id='claim-created'",
            (self.f.tenants[0], first.capture_session_id)).fetchone()[0]
        self.assertEqual(json.loads(payload), {
            'capture_protocol_version': DEFAULT_CAPTURE_PROTOCOL,
            'claim_id': claim_id,
            'synthetic': False,
        })

    def test_claim_case_provisions_capture_session_and_binds_owner_once(self):
        claim_id, request_id = str(uuid.uuid4()), str(uuid.uuid4())
        case = self.claim_cases.create(self.auth(), claim_id=claim_id, request_id=request_id)
        retry = self.claim_cases.create(self.auth(), claim_id=claim_id, request_id=request_id)
        self.assertEqual(case.capture_session_id, retry.capture_session_id)
        session = self.store.get(self.auth(), case.capture_session_id)
        self.assertEqual((session.scope, session.claim_id, session.created_by, session.capture_protocol_version),
                         ('persistent-claim-case', claim_id, 'capture-actor-0', DEFAULT_CAPTURE_PROTOCOL))
        self.assertNotIn(case.capture_session_id,
                         {item.session_id for item in self.store.list_owned(self.auth())})
        with tempfile.TemporaryDirectory() as root:
            service = CaptureEvidenceService(self.store, OriginalByteStore(root), 'P'*43)
            service.record_consent(self.owner_auth(), case.capture_session_id,
                request_id=uuid.uuid4(), accepted=True, scope='capture_review')
            bound = self.store.get(self.auth(), case.capture_session_id)
            self.assertEqual(bound.owner_actor_id, 'claim-owner-0')
            with self.assertRaises(CaptureAuthorizationError):
                service.record_consent(self.owner_auth(other=True), case.capture_session_id,
                    request_id=uuid.uuid4(), accepted=True, scope='capture_review')
        self.assertEqual(self.f.seed.execute(
            "SELECT count(*) FROM faos.events WHERE tenant_id=%s AND session_id=%s AND kind='CONSENT_RECORDED'",
            (self.f.tenants[0],case.capture_session_id)).fetchone()[0], 1)

    def test_persistent_claim_capture_completes_original_evidence_and_review_path(self):
        claim_id = str(uuid.uuid4())
        case = self.claim_cases.create(self.auth(), claim_id=claim_id, request_id=str(uuid.uuid4()),
                                       capture_protocol_version=LEGACY_CAPTURE_PROTOCOL)
        with tempfile.TemporaryDirectory() as root:
            byte_store = OriginalByteStore(root)
            service = CaptureEvidenceService(self.store, byte_store, 'P'*43)
            service.record_consent(self.owner_auth(), case.capture_session_id,
                request_id=uuid.uuid4(), accepted=True, scope='capture_review')
            service.record_vehicle(self.auth(), case.capture_session_id,
                request_id=uuid.uuid4(), vin='1HGCM82633A004352')
            originals = {}
            for slot in LEGACY_CANONICAL_SLOTS:
                raw = ('claim-case-original:' + slot).encode('ascii')
                artifact_id = str(uuid.uuid4())
                originals[artifact_id] = raw
                service.register_artifact(self.auth(), case.capture_session_id,
                    request_id=uuid.uuid4(), artifact_id=artifact_id, slot=slot,
                    payload_base64=base64.b64encode(raw).decode('ascii'),
                    sha256_hex=hashlib.sha256(raw).hexdigest())
            quality = {slot: True for slot in LEGACY_CANONICAL_SLOTS}
            self.assertTrue(service.record_quality(self.auth(), case.capture_session_id,
                request_id=uuid.uuid4(), results=quality)['advisory_only'])
            sealed = service.seal_capture(self.auth(), case.capture_session_id, request_id=uuid.uuid4())
            queue = service.list_review_queue(self.reviewer_auth())
            self.assertIn(case.capture_session_id, {item['session_id'] for item in queue})
            details = service.get_review_details(self.reviewer_auth(), case.capture_session_id)
            self.assertEqual(details['manifest_digest'], sealed['manifest_digest'])
            self.assertEqual(len(details['artifacts']), len(CANONICAL_SLOTS))
            first_artifact = next(iter(originals))
            self.assertEqual(service.retrieve_for_review(
                self.reviewer_auth(), case.capture_session_id, first_artifact), originals[first_artifact])
            review = service.record_review(self.reviewer_auth(), case.capture_session_id,
                request_id=uuid.uuid4(), disposition='NOTE_ONLY',
                reason='Synthetic integration verification; no real claim decision.')
            self.assertEqual(review['manifest_digest'], sealed['manifest_digest'])
            self.assertNotIn('1HGCM82633A004352', str(details))
        persisted = self.store.get(self.auth(), case.capture_session_id)
        self.assertEqual((persisted.scope, persisted.claim_id, persisted.owner_actor_id),
                         ('persistent-claim-case', claim_id, 'claim-owner-0'))

    def test_claim_case_idempotency_conflict_is_rejected(self):
        request_id = str(uuid.uuid4())
        self.claim_cases.create(self.auth(), claim_id=str(uuid.uuid4()), request_id=request_id)
        with self.assertRaises(ClaimCaseConflict):
            self.claim_cases.create(self.auth(), claim_id=str(uuid.uuid4()), request_id=request_id)

    def test_claim_case_reads_are_tenant_and_creator_scoped(self):
        claim_id = str(uuid.uuid4())
        self.claim_cases.create(self.auth(), claim_id=claim_id, request_id=str(uuid.uuid4()))
        with self.assertRaises(ClaimCaseNotFound):
            self.claim_cases.get(self.auth(1), claim_id)
        self.assertEqual(self.claim_cases.list_owned(self.auth(1)), [])

    def test_create_retry_and_fresh_connection_readback(self):
        first=self.store.create(self.auth(),self.key,protocol_version=LEGACY_CAPTURE_PROTOCOL)
        self.assertTrue(first.created)
        self.assertEqual((first.tenant_id,first.created_by),(self.f.tenants[0],'capture-actor-0'))
        retry=self.store.create(self.auth(),self.key,protocol_version=LEGACY_CAPTURE_PROTOCOL)
        self.assertFalse(retry.created)
        reopened=self.store.get(self.auth(),self.key)
        self.assertEqual((reopened.session_id,reopened.tenant_id,reopened.created_by,reopened.created_at),(first.session_id,first.tenant_id,first.created_by,first.created_at))
        self.assertEqual(self.f.seed.execute('SELECT count(*) FROM faos.events WHERE tenant_id=%s AND session_id=%s',(self.f.tenants[0],self.key)).fetchone()[0],1)
        payload = self.f.seed.execute(
            "SELECT payload_json FROM faos.events WHERE tenant_id=%s AND session_id=%s AND event_id='capture-created'",
            (self.f.tenants[0],self.key)).fetchone()[0]
        self.assertEqual(json.loads(payload), {
            'capture_protocol_version': LEGACY_CAPTURE_PROTOCOL,
            'synthetic': True,
        })

    def test_historical_12_v1_creation_event_remains_readable_without_relabeling(self):
        self.f.seed.execute(
            'INSERT INTO faos.sessions(tenant_id,session_id,capture_protocol_version) VALUES (%s,%s,%s)',
            (self.f.tenants[0],self.key,LEGACY_CAPTURE_PROTOCOL))
        self.f.seed.execute(
            'INSERT INTO faos.events(tenant_id,session_id,event_id,sequence,kind,actor,occurred_at,reason,payload_json,schema_version) '
            'VALUES (%s,%s,%s,1,%s,%s,%s,%s,%s,%s)',
            (self.f.tenants[0],self.key,'capture-created','SESSION_CREATED','capture-actor-0',
             '2026-01-01T00:00:00Z','historical controlled capture session','{"synthetic":true}','0.1'))
        session = self.store.get(self.auth(),self.key)
        self.assertEqual(session.capture_protocol_version,LEGACY_CAPTURE_PROTOCOL)
        self.assertEqual(session.scope,'controlled-test')

    def test_operator_lists_only_own_sessions_within_tenant(self):
        own_ids=[str(uuid.uuid4()),str(uuid.uuid4())]
        other_id=str(uuid.uuid4())
        for session_id in own_ids:
            self.store.create(self.auth(),session_id)
        self.store.create(self.auth(1),other_id)
        listed=self.store.list_owned(self.auth(),limit=10)
        self.assertEqual({item.session_id for item in listed},set(own_ids))
        self.assertTrue(all(item.created_by=='capture-actor-0' for item in listed))
        self.assertNotIn(other_id,{item.session_id for item in listed})
        self.assertEqual(len(self.store.list_owned(self.auth(),limit=1)),1)

    def test_other_tenant_cannot_read_capture_session(self):
        self.store.create(self.auth(),self.key)
        with self.assertRaises(CaptureSessionNotFound):
            self.store.get(self.auth(1),self.key)
        self.assertEqual(self.store.get(self.auth(),self.key).tenant_id,self.f.tenants[0])

    def test_same_session_identifier_is_isolated_between_tenants(self):
        for index in range(2):
            result=self.store.create(self.auth(index),self.key)
            self.assertTrue(result.created)
            self.assertEqual(result.tenant_id,self.f.tenants[index])
            self.assertEqual(result.created_by,'capture-actor-'+str(index))

    def test_missing_unknown_and_expired_credentials_never_connect(self):
        expired=CaptureSessionStore(CredentialResolver([replace(self.credentials[0],expires_at=1)]),self.dsns)
        with patch('database.capture_sessions.psycopg.connect') as connect:
            for header in (None,'Bearer '+'Z'*43):
                with self.assertRaises(AuthenticationError):
                    self.store.create(header,self.key)
            with self.assertRaises(AuthenticationError):
                expired.create(self.auth(),self.key)
            connect.assert_not_called()

    def test_disabled_credential_never_connects(self):
        store=CaptureSessionStore(CredentialResolver([replace(self.credentials[0],enabled=False)]),self.dsns)
        with patch('database.capture_sessions.psycopg.connect') as connect:
            with self.assertRaises(AuthenticationError):
                store.get(self.auth(),self.key)
            connect.assert_not_called()

    def test_mismatched_configured_login_is_rejected_before_connect(self):
        bad=dict(self.dsns)
        bad[self.f.roles[0]]=self.dsns[self.f.roles[1]]
        store=CaptureSessionStore(CredentialResolver(self.credentials),bad)
        with patch('database.capture_sessions.psycopg.connect') as connect:
            with self.assertRaises(CaptureAuthorizationError):
                store.create(self.auth(),self.key)
            connect.assert_not_called()

    def test_database_binding_revocation_blocks_reads_and_creates(self):
        self.store.create(self.auth(),self.key)
        self.f.seed.execute('UPDATE faos.tenant_login_bindings SET enabled=false WHERE role_name=%s',(self.f.roles[0],))
        for action in (lambda:self.store.get(self.auth(),self.key),lambda:self.store.create(self.auth(),str(uuid.uuid4()))):
            with self.assertRaises(CaptureAuthorizationError):
                action()
        self.assertTrue(self.store.create(self.auth(1),self.key).created)

    def test_changed_database_tenant_binding_cannot_override_actor(self):
        self.f.seed.execute('UPDATE faos.tenant_login_bindings SET tenant_id=%s WHERE role_name=%s',(self.f.tenants[1],self.f.roles[0]))
        with self.assertRaises(CaptureAuthorizationError):
            self.store.create(self.auth(),self.key)

    def test_inherited_writer_privilege_is_rejected(self):
        self.f.admin.execute(sql.SQL('GRANT faos_writer TO {}').format(sql.Identifier(self.f.roles[0])))
        with self.assertRaises(CaptureAuthorizationError):
            self.store.create(self.auth(),self.key)

    def test_failure_before_commit_rolls_back_session_and_creation_event(self):
        with patch('database.capture_sessions.CaptureSession',side_effect=RuntimeError('synthetic construction failure')):
            with self.assertRaisesRegex(RuntimeError,'synthetic construction failure'):
                self.store.create(self.auth(),self.key)
        for table in ('sessions','events'):
            self.assertEqual(self.f.seed.execute(sql.SQL('SELECT count(*) FROM faos.{} WHERE tenant_id=%s AND session_id=%s').format(sql.Identifier(table)),(self.f.tenants[0],self.key)).fetchone()[0],0)
        self.assertTrue(self.store.create(self.auth(),self.key).created)

    def test_unmanaged_existing_session_is_not_adopted(self):
        self.f.seed.execute('INSERT INTO faos.sessions VALUES (%s,%s)',(self.f.tenants[0],self.key))
        with self.assertRaises(CaptureSessionConflict):
            self.store.create(self.auth(),self.key)

    def test_failed_database_login_does_not_expose_connection_details(self):
        bad=dict(self.dsns)
        bad[self.f.roles[0]]=make_conninfo(bad[self.f.roles[0]],password='synthetic-wrong-password')
        store=CaptureSessionStore(CredentialResolver(self.credentials),bad)
        with self.assertRaisesRegex(CaptureStorageUnavailable,'^CAPTURE_STORAGE_UNAVAILABLE$'):
            store.create(self.auth(),self.key)

    def test_protocol_registry_exposes_16_default_and_12_legacy_as_executable(self):
        default = resolve_capture_protocol(DEFAULT_CAPTURE_PROTOCOL)
        legacy = resolve_capture_protocol(LEGACY_CAPTURE_PROTOCOL)
        self.assertEqual((default.status, len(default.slots)), ("implemented", 16))
        self.assertEqual((legacy.status, len(legacy.slots)), ("implemented", 12))

    def test_claim_case_retry_cannot_change_protocol_version(self):
        claim_id, request_id = str(uuid.uuid4()), str(uuid.uuid4())
        self.claim_cases.create(self.auth(), claim_id=claim_id, request_id=request_id,
                                capture_protocol_version=DEFAULT_CAPTURE_PROTOCOL)
        with self.assertRaisesRegex(ClaimCaseConflict, "CAPTURE_PROTOCOL_VERSION_MISMATCH"):
            self.claim_cases.create(self.auth(), claim_id=claim_id, request_id=request_id,
                                    capture_protocol_version=LEGACY_CAPTURE_PROTOCOL)
    def test_capture_protocol_is_immutable_and_retry_must_match(self):
        created = self.store.create(self.auth(), self.key, protocol_version=DEFAULT_CAPTURE_PROTOCOL)
        self.assertEqual(created.capture_protocol_version, DEFAULT_CAPTURE_PROTOCOL)
        with self.assertRaisesRegex(CaptureSessionConflict, "CAPTURE_PROTOCOL_VERSION_MISMATCH"):
            self.store.create(self.auth(), self.key, protocol_version=LEGACY_CAPTURE_PROTOCOL)
        self.assertEqual(self.store.get(self.auth(), self.key).capture_protocol_version, DEFAULT_CAPTURE_PROTOCOL)
        self.assertEqual(self.f.seed.execute(
            "SELECT capture_protocol_version FROM faos.sessions WHERE tenant_id=%s AND session_id=%s",
            (self.f.tenants[0], self.key)).fetchone()[0], DEFAULT_CAPTURE_PROTOCOL)

    def test_default_16_protocol_rejects_legacy_12_slot_identifiers(self):
        claim = self.claim_cases.create(self.auth(), claim_id=str(uuid.uuid4()), request_id=str(uuid.uuid4()))
        with tempfile.TemporaryDirectory() as root:
            service = CaptureEvidenceService(self.store, OriginalByteStore(root), 'P'*43)
            service.record_consent(self.owner_auth(), claim.capture_session_id,
                request_id=uuid.uuid4(), accepted=True, scope='capture_review')
            service.record_vehicle(self.auth(), claim.capture_session_id,
                request_id=uuid.uuid4(), vin='1HGCM82633A004352')
            readiness = service.evidence_readiness(self.auth(), claim.capture_session_id)
            self.assertEqual(readiness["capture_protocol_version"], DEFAULT_CAPTURE_PROTOCOL)
            self.assertEqual(readiness["capture_protocol_status"], "implemented")
            self.assertTrue(readiness["capture_allowed"])
            raw = b"must-not-be-registered"
            with self.assertRaisesRegex(ValueError, "INVALID_CAPTURE_SLOT"):
                service.register_artifact(self.auth(), claim.capture_session_id,
                    request_id=uuid.uuid4(), artifact_id=uuid.uuid4(), slot=LEGACY_CANONICAL_SLOTS[0],
                    payload_base64=base64.b64encode(raw).decode("ascii"),
                    sha256_hex=hashlib.sha256(raw).hexdigest())

    def test_financial_ledger_persists_retries_reversals_and_verified_export(self):
        self.store.create(self.auth(),self.key)
        ledger=PersistentFinancialLedger(self.store)
        acceptance=PartnerAcceptanceRecord('shop-accept-1',uuid.UUID(self.f.tenants[0]),self.key,
            'shop','partner-shop-1','shop-actor','2026-11-09T00:00:00+00:00')
        entry=ledger.record_partner_acceptance_obligation(self.auth(),acceptance,
            idempotency_key='ledger-idem-1',actor_id='capture-actor-0',now_iso='2026-11-09T00:00:00+00:00')
        retry=ledger.record_partner_acceptance_obligation(self.auth(),acceptance,
            idempotency_key='ledger-idem-1',actor_id='capture-actor-0',now_iso='2026-11-09T00:00:00+00:00')
        self.assertEqual(entry,retry)
        self.assertEqual((entry.amount_cents,entry.lines[0].direction,entry.lines[1].direction),(27500,'DEBIT','CREDIT'))
        reversal=ledger.record_reversal_or_dispute_refund(self.auth(),entry.entry_id,
            idempotency_key='ledger-reversal-1',actor_id='capture-actor-0',reason='shop acceptance cancelled')
        exported=ledger.export_audit_ledger(self.auth())
        self.assertEqual((reversal.entry_kind,exported['entry_count'],exported['balanced']),("REVERSAL_BOOKED",2,True))
        self.assertEqual(self.f.seed.execute('SELECT count(*) FROM faos.financial_ledger_entries WHERE tenant_id=%s',(self.f.tenants[0],)).fetchone()[0],2)

    def test_financial_ledger_rejects_cross_tenant_acceptance(self):
        self.store.create(self.auth(),self.key)
        ledger=PersistentFinancialLedger(self.store)
        acceptance=PartnerAcceptanceRecord('shop-accept-other',uuid.UUID(self.f.tenants[1]),self.key,
            'shop','partner-shop-2','shop-actor','2026-11-09T00:00:00+00:00')
        with self.assertRaisesRegex(ValueError,'TENANT_CONTEXT_MISMATCH'):
            ledger.record_partner_acceptance_obligation(self.auth(),acceptance,
                idempotency_key='ledger-cross-tenant',actor_id='capture-actor-0')


    def test_incident_intake_requires_separate_owner_consent_and_withdrawal_deletes_details(self):
        from database.incident_intake import IncidentIntakeService
        claim_id = str(uuid.uuid4())
        case = self.claim_cases.create(self.auth(), claim_id=claim_id, request_id=str(uuid.uuid4()))
        with tempfile.TemporaryDirectory() as root:
            evidence = CaptureEvidenceService(self.store, OriginalByteStore(root), 'P'*43)
            incident = IncidentIntakeService(self.store)
            evidence.record_consent(self.owner_auth(), case.capture_session_id,
                request_id=uuid.uuid4(), accepted=True, scope='capture_review')
            with self.assertRaises(CaptureSessionConflict):
                incident.record_incident(self.owner_auth(), case.capture_session_id,
                    request_id=uuid.uuid4(), occurred_at='2026-11-08T09:30:00-06:00',
                    incident_type='collision', city='San Antonio', region='TX', postal_code='78201')
            incident.record_consent(self.owner_auth(), case.capture_session_id,
                request_id=uuid.uuid4(), accepted=True)
            result = incident.record_incident(self.owner_auth(), case.capture_session_id,
                request_id=uuid.uuid4(), occurred_at='2026-11-08T09:30:00-06:00',
                incident_type='collision', city='San Antonio', region='TX', postal_code='78201')
            self.assertEqual((result['incident_type'],result['incident_city'],result['incident_region']),
                             ('collision','San Antonio','TX'))
            persisted = self.f.seed.execute(
                'SELECT incident_city,incident_region,incident_postal_code FROM faos.claim_case_incident_intake WHERE tenant_id=%s AND claim_id=%s',
                (self.f.tenants[0],claim_id)).fetchone()
            self.assertEqual(persisted,('San Antonio','TX','78201'))
            operator_view = incident.get_incident(self.auth(), case.capture_session_id)
            owner_view = incident.get_incident(self.owner_auth(), case.capture_session_id)
            self.assertEqual(operator_view['incident_city'],'San Antonio')
            self.assertEqual(owner_view['incident_region'],'TX')
            with self.assertRaises(CaptureAuthorizationError):
                incident.get_incident(self.other_operator_auth(), case.capture_session_id)
            journal = self.f.seed.execute(
                "SELECT payload_json FROM faos.events WHERE tenant_id=%s AND session_id=%s AND kind='INCIDENT_INTAKE_RECORDED'",
                (self.f.tenants[0],case.capture_session_id)).fetchone()[0]
            self.assertNotIn('San Antonio',journal)
            withdrawn = incident.record_consent(self.owner_auth(), case.capture_session_id,
                request_id=uuid.uuid4(), accepted=False)
            self.assertTrue(withdrawn['incident_details_deleted'])
            with self.assertRaises(CaptureSessionNotFound):
                incident.get_incident(self.auth(), case.capture_session_id)
            self.assertIsNone(self.f.seed.execute(
                'SELECT 1 FROM faos.claim_case_incident_intake WHERE tenant_id=%s AND claim_id=%s',
                (self.f.tenants[0],claim_id)).fetchone())
            with self.assertRaises(CaptureSessionConflict):
                incident.record_incident(self.owner_auth(), case.capture_session_id,
                    request_id=uuid.uuid4(), occurred_at='2026-11-08T09:30:00-06:00',
                    incident_type='collision', city='San Antonio', region='TX', postal_code='78201')
            incident.record_consent(self.owner_auth(), case.capture_session_id,
                request_id=uuid.uuid4(), accepted=True)
            incident.record_incident(self.owner_auth(), case.capture_session_id,
                request_id=uuid.uuid4(), occurred_at='2026-11-08T09:30:00-06:00',
                incident_type='collision', city='San Antonio', region='TX', postal_code='78201')
            evidence.record_consent(self.owner_auth(), case.capture_session_id,
                request_id=uuid.uuid4(), accepted=False, scope='capture_review')
            self.assertIsNone(self.f.seed.execute(
                'SELECT 1 FROM faos.claim_case_incident_intake WHERE tenant_id=%s AND claim_id=%s',
                (self.f.tenants[0],claim_id)).fetchone())

if __name__=='__main__':
    unittest.main()
