import unittest
import uuid

import psycopg
from psycopg.conninfo import make_conninfo

from app.domain_events import DomainEvent
from database.event_hash_chain import event_hash, genesis_hash
from database.journal import append, tenant_transaction


class EventHashChainIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Reuse one disposable authority DB/tenant/login fixture for all tests.
        # It creates a private database and temporary tenant-bound roles.
        import test_tenant_authority_integration as fixtures
        cls.fixture=fixtures.TenantAuthorityIntegration()
        cls.fixture.setUp()
        cls.tenant=cls.fixture.tenants[0]
        cls.conn=cls.fixture.connections[0]
        cls.admin=cls.fixture.seed
        cls.admin_url=make_conninfo(cls.fixture.admin.info.dsn,dbname=cls.fixture.db)

    @classmethod
    def tearDownClass(cls):
        cls.fixture.doCleanups()

    def setUp(self):
        self.session="chain-integration-"+uuid.uuid4().hex
        self.admin.execute("INSERT INTO faos.sessions(tenant_id,session_id) VALUES (%s,%s)",(self.tenant,self.session))
        self.event=DomainEvent(
            self.session,"chain-event-1",1,"SESSION_CREATED","synthetic-test",
            "2026-11-23T12:34:56.123456Z","chain integration test",'{"synthetic":true}'
        )

    def append(self,event):
        return append(self.conn,self.tenant,event)

    def rows(self):
        with tenant_transaction(self.conn,self.tenant):
            return self.conn.execute(
                "SELECT tenant_id::text,session_id,event_id,sequence,kind,actor,occurred_at,reason,payload_json,schema_version,previous_hash,entry_hash,hash_version "
                "FROM faos.events WHERE tenant_id=%s AND session_id=%s ORDER BY sequence",
                (self.tenant,self.session)
            ).fetchall()

    def test_persisted_hash_parity_retry_direct_insert_tamper_and_immutability(self):
        # Python and PostgreSQL reproduce identical known inputs and stored links.
        self.assertEqual(self.append(self.event),"ACCEPTED")
        first=self.rows()[0]
        genesis=genesis_hash(self.tenant,self.session)
        first_hash=event_hash(self.tenant,self.event,genesis)
        self.assertEqual((first[10],first[11],first[12]),(genesis,first_hash,"event-hash-v1"))
        self.assertEqual(self.admin.execute(
            "SELECT faos.event_chain_genesis_hash(%s::uuid,%s)",(self.tenant,self.session)
        ).fetchone()[0],genesis)
        self.assertEqual(self.admin.execute(
            "SELECT faos.event_chain_entry_hash(%s::uuid,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (self.tenant,self.session,self.event.event_id,self.event.sequence,self.event.kind,self.event.actor,
             self.event.occurred_at,self.event.reason,self.event.payload_json,self.event.schema_version,genesis)
        ).fetchone()[0],first_hash)

        self.assertEqual(self.append(self.event),"DUPLICATE")
        changed=DomainEvent(self.session,self.event.event_id,self.event.sequence,self.event.kind,self.event.actor,
            self.event.occurred_at,"altered retry",self.event.payload_json,self.event.schema_version)
        with self.assertRaises(psycopg.errors.RaiseException) as raised:
            self.append(changed)
        self.assertEqual(raised.exception.diag.message_primary,"CONFLICTING_EVENT_DUPLICATE")

        second=DomainEvent(self.session,"chain-event-2",2,"CONSENT_RECORDED","synthetic-test",
            "2026-11-23T12:35:00Z","second event",'{"consent":true}')
        self.assertEqual(self.append(second),"ACCEPTED")
        rows=self.rows()
        self.assertEqual(rows[1][10],rows[0][11])
        self.assertEqual(rows[1][11],event_hash(self.tenant,second,rows[0][11]))

        # Privileged fixture inserts still use the guard and receive hashes.
        self.admin.execute("INSERT INTO faos.events(tenant_id,session_id,event_id,sequence,kind,actor,occurred_at,reason,payload_json,schema_version) VALUES (%s,%s,%s,3,%s,%s,%s,%s,%s,%s)",
            (self.tenant,self.session,"admin-fixture-event","SESSION_CREATED","synthetic-admin",
             "2026-11-23T12:35:30Z","privileged fixture",'{"synthetic":true}',"0.1"))
        direct=self.admin.execute("SELECT previous_hash,entry_hash,hash_version FROM faos.events WHERE tenant_id=%s AND session_id=%s AND event_id=%s",
            (self.tenant,self.session,"admin-fixture-event")).fetchone()
        direct_event=DomainEvent(self.session,"admin-fixture-event",3,"SESSION_CREATED","synthetic-admin",
            "2026-11-23T12:35:30Z","privileged fixture",'{"synthetic":true}')
        self.assertEqual(direct[0],rows[1][11])
        self.assertEqual(direct[2],"event-hash-v1")
        self.assertEqual(direct[1],event_hash(self.tenant,direct_event,direct[0]))

        # Simulate privileged row tampering with trigger disabled. The next
        # append must recompute the existing chain and fail closed.
        self.admin.execute("ALTER TABLE faos.events DISABLE TRIGGER faos_event_chain_guard_mutation")
        try:
            self.admin.execute("UPDATE faos.events SET payload_json='{\"synthetic\":false}' WHERE tenant_id=%s AND session_id=%s AND event_id=%s",
                (self.tenant,self.session,second.event_id))
        finally:
            self.admin.execute("ALTER TABLE faos.events ENABLE TRIGGER faos_event_chain_guard_mutation")
        fourth=DomainEvent(self.session,"chain-event-4",4,"CONSENT_RECORDED","synthetic-test",
            "2026-11-23T12:36:00Z","append after tamper",'{"consent":false}')
        with self.assertRaises(psycopg.errors.RaiseException) as raised:
            self.append(fourth)
        self.assertEqual(raised.exception.diag.message_primary,"EVENT_HASH_MISMATCH")

        with self.assertRaises(psycopg.errors.RaiseException) as raised:
            self.admin.execute("UPDATE faos.events SET reason='tampered' WHERE tenant_id=%s AND session_id=%s",(self.tenant,self.session))
        self.assertEqual(raised.exception.diag.message_primary,"EVENT_HISTORY_IMMUTABLE")
        with self.assertRaises(psycopg.errors.RaiseException) as raised:
            self.admin.execute("DELETE FROM faos.events WHERE tenant_id=%s AND session_id=%s",(self.tenant,self.session))
        self.assertEqual(raised.exception.diag.message_primary,"EVENT_HISTORY_IMMUTABLE")


if __name__ == "__main__":
    unittest.main()
