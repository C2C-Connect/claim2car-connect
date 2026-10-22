"""Pure unit tests using synthetic tokens; not HTTP/DB authentication evidence."""
from dataclasses import FrozenInstanceError, replace
import hashlib
import unittest
from unittest.mock import patch
from uuid import UUID
from app.identity import ActorBinding, AuthenticationError, Credential, CredentialResolver

class IdentityBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.a,self.b='A'*43,'B'*43
        self.first=ActorBinding('actor-a',UUID(int=1),'tenant_login_a')
        self.second=ActorBinding('actor-b',UUID(int=2),'tenant_login_b')
        self.record=Credential(hashlib.sha256(self.a.encode()).hexdigest(),self.first,2000)
        self.other=Credential(hashlib.sha256(self.b.encode()).hexdigest(),self.second,2000)
        clock=patch('app.identity.time.time',return_value=1000)
        clock.start()
        self.addCleanup(clock.stop)

    def test_valid_token_returns_server_binding(self):
        self.assertEqual(CredentialResolver([self.record]).resolve('Bearer '+self.a),self.first)

    def test_distinct_credentials_resolve_distinct_tenants(self):
        resolver=CredentialResolver([self.record,self.other])
        self.assertEqual(resolver.resolve('Bearer '+self.a),self.first)
        self.assertEqual(resolver.resolve('Bearer '+self.b),self.second)

    def test_missing_malformed_and_injected_headers_are_rejected(self):
        for value in (None,'','Bearer','Basic '+self.a,'Bearer short','Bearer '+self.a+' tenant=other','Bearer '+self.a+'\n'):
            with self.subTest(value=value),self.assertRaisesRegex(AuthenticationError,'^UNAUTHORIZED$'):
                CredentialResolver([self.record]).resolve(value)

    def test_unknown_token_is_rejected_without_identity_details(self):
        with self.assertRaisesRegex(AuthenticationError,'^UNAUTHORIZED$'):
            CredentialResolver([self.record]).resolve('Bearer '+self.b)

    def test_no_configured_credentials_means_no_authority(self):
        with self.assertRaises(AuthenticationError):
            CredentialResolver().resolve('Bearer '+self.a)

    def test_disabled_expired_and_exact_expiry_are_rejected(self):
        for record in (replace(self.record,enabled=False),replace(self.record,expires_at=999),replace(self.record,expires_at=1000)):
            with self.subTest(record=record),self.assertRaises(AuthenticationError):
                CredentialResolver([record]).resolve('Bearer '+self.a)

    def test_invalid_digest_expiry_and_binding_configuration_are_rejected(self):
        for record in (replace(self.record,token_sha256='bad'),replace(self.record,expires_at=True),replace(self.record,binding=replace(self.first,tenant_id='not-a-uuid')),replace(self.record,binding=replace(self.first,actor_id=' ')),replace(self.record,binding=replace(self.first,database_role='postgres')),replace(self.record,binding=replace(self.first,database_role='role;DROP TABLE x'))):
            with self.subTest(record=record),self.assertRaisesRegex(ValueError,'^INVALID_IDENTITY_CONFIGURATION$'):
                CredentialResolver([record])

    def test_duplicate_digest_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'^AMBIGUOUS_IDENTITY_CONFIGURATION$'):
            CredentialResolver([self.record,replace(self.other,token_sha256=self.record.token_sha256)])

    def test_actor_cannot_have_conflicting_tenant_bindings(self):
        with self.assertRaisesRegex(ValueError,'^AMBIGUOUS_IDENTITY_CONFIGURATION$'):
            CredentialResolver([self.record,replace(self.other,binding=replace(self.second,actor_id='actor-a'))])

    def test_database_login_cannot_map_to_conflicting_tenants(self):
        with self.assertRaisesRegex(ValueError,'^AMBIGUOUS_IDENTITY_CONFIGURATION$'):
            CredentialResolver([self.record,replace(self.other,binding=replace(self.second,database_role='tenant_login_a'))])

    def test_caller_list_mutation_cannot_change_active_configuration(self):
        values=[self.record]
        resolver=CredentialResolver(values)
        values.append(self.other)
        with self.assertRaises(AuthenticationError):
            resolver.resolve('Bearer '+self.b)

    def test_resolved_binding_is_frozen_and_digest_is_not_in_repr(self):
        with self.assertRaises(FrozenInstanceError):
            self.first.database_role='postgres'
        self.assertNotIn(self.record.token_sha256,repr(self.record))
        self.assertEqual(CredentialResolver([self.record]).resolve('bEaReR '+self.a),self.first)

if __name__=='__main__':
    unittest.main()
