"""Real PostgreSQL-backed service tests; not HTTP or real-image intake proof."""
from dataclasses import replace
import hashlib
import time
import unittest
from unittest.mock import patch
import uuid
from psycopg import sql
from psycopg.conninfo import make_conninfo
from app.identity import ActorBinding, AuthenticationError, Credential, CredentialResolver
from database.capture_sessions import CaptureAuthorizationError, CaptureSessionConflict, CaptureSessionNotFound, CaptureSessionStore, CaptureStorageUnavailable

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
        self.store=CaptureSessionStore(CredentialResolver(self.credentials),self.dsns)
        self.key=str(uuid.uuid4())

    def auth(self,index=0):
        return 'Bearer '+self.tokens[index]

    def test_create_retry_and_fresh_connection_readback(self):
        first=self.store.create(self.auth(),self.key)
        self.assertTrue(first.created)
        self.assertEqual((first.tenant_id,first.created_by),(self.f.tenants[0],'capture-actor-0'))
        retry=self.store.create(self.auth(),self.key)
        self.assertFalse(retry.created)
        reopened=self.store.get(self.auth(),self.key)
        self.assertEqual((reopened.session_id,reopened.tenant_id,reopened.created_by,reopened.created_at),(first.session_id,first.tenant_id,first.created_by,first.created_at))
        self.assertEqual(self.f.seed.execute('SELECT count(*) FROM faos.events WHERE tenant_id=%s AND session_id=%s',(self.f.tenants[0],self.key)).fetchone()[0],1)

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

if __name__=='__main__':
    unittest.main()
