import unittest
import uuid

import psycopg

from app.domain_events import DomainEvent
from database.event_hash_chain import event_hash, genesis_hash
from database.journal import append, tenant_transaction


class EventHashChainIntegration(unittest.TestCase):
    def setUp(self):
        # Reuse the established isolated PostgreSQL authority fixture, including
        # temporary login roles and tenant bindings. Never mutate shared test DB.
        import test_tenant_authority_integration as fixtures
        self.fixture=fixtures.TenantAuthorityIntegration()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.setUp()
        self.tenant=self.fixture.tenants[0]
        self.session="chain-integration-"+uuid.uuid4().hex
        self.conn=self.fixture.connections[0]
        self.admin=self.fixture.seed
        self.admin_url=psycopg.conninfo.make_conninfo(self.fixture.admin.info.dsn,dbname=self.fixture.db)
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

    def test_persisted_hash_fields_match_python_known_algorithm(self):
        self.assertEqual(self.append(self.event),"ACCEPTED")
        r=self.rows()[0]
        expected_genesis=genesis_hash(self.tenant,self.session)
        expected_entry=event_hash(self.tenant,self.event,expected_genesis)
        self.assertEqual(r[10],expected_genesis)
        self.assertEqual(r[11],expected_entry)
        self.assertEqual(r[12],"event-hash-v1")
        self.assertEqual(self.admin.execute("SELECT faos.event_chain_genesis_hash(%s::uuid,%s)",(self.tenant,self.session)).fetchone()[0],expected_genesis)
        self.assertEqual(self.admin.execute(
            "SELECT faos.event_chain_entry_hash(%s::uuid,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (self.tenant,self.session,self.event.event_id,self.event.sequence,self.event.kind,self.event.actor,
             self.event.occurred_at,self.event.reason,self.event.payload_json,self.event.schema_version,expected_genesis)
        ).fetchone()[0],expected_entry)

    def test_idempotent_retry_and_conflicting_retry(self):
        self.assertEqual(self.append(self.event),"ACCEPTED")
        self.assertEqual(self.append(self.event),"DUPLICATE")
        changed=DomainEvent(self.session,self.event.event_id,self.event.sequence,self.event.kind,self.event.actor,
            self.event.occurred_at,"altered retry",self.event.payload_json,self.event.schema_version)
        with self.assertRaises(psycopg.errors.RaiseException) as raised:
            self.append(changed)
        self.assertEqual(raised.exception.diag.message_primary,"CONFLICTING_EVENT_DUPLICATE")
        self.assertEqual(len(self.rows()),1)

    def test_next_append_commits_previous_tip(self):
        self.assertEqual(self.append(self.event),"ACCEPTED")
        second=DomainEvent(self.session,"chain-event-2",2,"CONSENT_RECORDED","synthetic-test",
            "2026-11-23T12:35:00Z","second event",'{"consent":true}')
        self.assertEqual(self.append(second),"ACCEPTED")
        rows=self.rows()
        self.assertEqual(len(rows),2)
        self.assertEqual(rows[1][10],rows[0][11])
        self.assertEqual(rows[1][11],event_hash(self.tenant,second,rows[0][11]))

    def test_direct_privileged_fixture_insert_is_auto_hashed(self):
        self.admin.execute("INSERT INTO faos.events(tenant_id,session_id,event_id,sequence,kind,actor,occurred_at,reason,payload_json,schema_version) VALUES (%s,%s,%s,1,%s,%s,%s,%s,%s,%s)",
            (self.tenant,self.session,"admin-fixture-event","SESSION_CREATED","synthetic-admin",
             "2026-11-23T12:35:00Z","privileged fixture",'{"synthetic":true}',"0.1"))
        row=self.admin.execute("SELECT previous_hash,entry_hash,hash_version FROM faos.events WHERE tenant_id=%s AND session_id=%s AND event_id=%s",
            (self.tenant,self.session,"admin-fixture-event")).fetchone()
        self.assertEqual(row[0],genesis_hash(self.tenant,self.session))
        self.assertEqual(row[2],"event-hash-v1")
        event=DomainEvent(self.session,"admin-fixture-event",1,"SESSION_CREATED","synthetic-admin",
            "2026-11-23T12:35:00Z","privileged fixture",'{"synthetic":true}')
        self.assertEqual(row[1],event_hash(self.tenant,event,row[0]))

    def test_privileged_payload_tampering_is_detected_on_next_append(self):
        self.assertEqual(self.append(self.event),"ACCEPTED")
        self.admin.execute("ALTER TABLE faos.events DISABLE TRIGGER faos_event_chain_guard_mutation")
        try:
            self.admin.execute("UPDATE faos.events SET payload_json='{\"synthetic\":false}' WHERE tenant_id=%s AND session_id=%s",
                (self.tenant,self.session))
        finally:
            self.admin.execute("ALTER TABLE faos.events ENABLE TRIGGER faos_event_chain_guard_mutation")
        next_event=DomainEvent(self.session,"chain-event-2",2,"CONSENT_RECORDED","synthetic-test",
            "2026-11-23T12:35:00Z","append after tamper",'{"consent":true}')
        with self.assertRaises(psycopg.errors.RaiseException) as raised:
            self.append(next_event)
        self.assertEqual(raised.exception.diag.message_primary,"EVENT_HASH_MISMATCH")

    def test_update_delete_rejected_by_trigger(self):
        self.assertEqual(self.append(self.event),"ACCEPTED")
        with self.assertRaises(psycopg.errors.RaiseException) as raised:
            self.admin.execute("UPDATE faos.events SET reason='tampered' WHERE tenant_id=%s AND session_id=%s",(self.tenant,self.session))
        self.assertEqual(raised.exception.diag.message_primary,"EVENT_HISTORY_IMMUTABLE")
        with self.assertRaises(psycopg.errors.RaiseException) as raised:
            self.admin.execute("DELETE FROM faos.events WHERE tenant_id=%s AND session_id=%s",(self.tenant,self.session))
        self.assertEqual(raised.exception.diag.message_primary,"EVENT_HISTORY_IMMUTABLE")


if __name__ == "__main__":
    unittest.main()
