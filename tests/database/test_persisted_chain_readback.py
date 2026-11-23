import unittest
import uuid

import psycopg

from app.domain_events import DomainEvent
from database.journal import append
from database.readback import (
    load_journal,
    locked_journal,
    read_persisted_journal,
    verify_persisted_event_chain,
)


class PersistedChainReadbackIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import test_tenant_authority_integration as fixtures
        cls.fixture=fixtures.TenantAuthorityIntegration()
        cls.fixture.setUp()
        cls.tenant=cls.fixture.tenants[0]
        cls.conn=cls.fixture.connections[0]
        cls.admin=cls.fixture.seed
        cls.other_conn=cls.fixture.connections[1]
        cls.other_tenant=cls.fixture.tenants[1]

    @classmethod
    def tearDownClass(cls):
        cls.fixture.doCleanups()

    def setUp(self):
        self.session="readback-"+uuid.uuid4().hex
        self.admin.execute("INSERT INTO faos.sessions(tenant_id,session_id) VALUES (%s,%s)",(self.tenant,self.session))
        self.event=DomainEvent(
            self.session,"readback-event-1",1,"SESSION_CREATED","synthetic-readback",
            "2026-11-23T13:00:00Z","persisted readback test",'{"synthetic":true}'
        )

    def test_readback_recomputes_chain_from_database_rows(self):
        self.assertEqual(append(self.conn,self.tenant,self.event),"ACCEPTED")
        result=read_persisted_journal(self.conn,self.tenant,self.session)
        self.assertTrue(result.verified)
        self.assertEqual(result.status,"CHAIN_VERIFIED")
        self.assertEqual(result.chain_verification["reason"],"CHAIN_VALID")
        self.assertEqual(result.chain_verification["event_count"],1)
        self.assertEqual(result.journal.events,(self.event,))
        self.assertEqual(result.journal.integrity_status,"CHAIN_VERIFIED")
        self.assertEqual(result.journal.chain_verification,result.chain_verification)
        self.assertEqual(verify_persisted_event_chain(self.conn,self.tenant,self.session),result.chain_verification)
        loaded=load_journal(self.conn,self.tenant,self.session)
        self.assertEqual(loaded.events,(self.event,))
        self.assertTrue(loaded.chain_verification["valid"])

    def test_privileged_payload_tamper_fails_readback_and_locked_consumers(self):
        self.assertEqual(append(self.conn,self.tenant,self.event),"ACCEPTED")
        self.admin.execute("ALTER TABLE faos.events DISABLE TRIGGER faos_event_chain_guard_mutation")
        try:
            self.admin.execute(
                "UPDATE faos.events SET payload_json='{\"synthetic\":false}' WHERE tenant_id=%s AND session_id=%s",
                (self.tenant,self.session),
            )
        finally:
            self.admin.execute("ALTER TABLE faos.events ENABLE TRIGGER faos_event_chain_guard_mutation")
        result=read_persisted_journal(self.conn,self.tenant,self.session)
        self.assertFalse(result.verified)
        self.assertEqual(result.status,"CHAIN_INVALID")
        self.assertEqual(result.chain_verification["reason"],"EVENT_HASH_MISMATCH")
        self.assertIsNone(result.journal)
        with self.assertRaisesRegex(ValueError,"^EVENT_CHAIN_INVALID:EVENT_HASH_MISMATCH$"):
            load_journal(self.conn,self.tenant,self.session)
        with self.assertRaisesRegex(ValueError,"^EVENT_CHAIN_INVALID:EVENT_HASH_MISMATCH$"):
            with locked_journal(self.conn,self.tenant,self.session):
                self.fail("tampered history must not yield a locked journal")

    def test_cross_tenant_readback_is_not_visible(self):
        self.assertEqual(append(self.conn,self.tenant,self.event),"ACCEPTED")
        with self.assertRaisesRegex(ValueError,"^SESSION_NOT_FOUND_OR_NOT_VISIBLE$"):
            read_persisted_journal(self.other_conn,self.tenant,self.session)


if __name__ == "__main__":
    unittest.main()
