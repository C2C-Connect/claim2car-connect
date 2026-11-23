import os
import unittest
import uuid

import psycopg

from app.domain_events import DomainEvent
from database.event_hash_chain import event_hash, genesis_hash
from database.journal import append, tenant_transaction


class EventHashChainIntegration(unittest.TestCase):
    def setUp(self):
        self.app_url = os.getenv("APP_DATABASE_URL", "postgresql://faos_app:synthetic-app-only@127.0.0.1:55432/claim2car_test")
        self.admin_url = os.getenv("MIGRATION_TEST_ADMIN_URL", "postgresql://postgres:synthetic-container-only@127.0.0.1:55432/claim2car_test")
        self.tenant = str(uuid.uuid4())
        self.session = "chain-integration-" + uuid.uuid4().hex
        self.conn = psycopg.connect(self.app_url, autocommit=True)
        self.addCleanup(self.conn.close)
        with tenant_transaction(self.conn, self.tenant):
            self.conn.execute("INSERT INTO faos.organizations(tenant_id,name) VALUES (%s,%s)", (self.tenant,"synthetic event chain test tenant"))
            self.conn.execute("INSERT INTO faos.sessions(tenant_id,session_id) VALUES (%s,%s)", (self.tenant,self.session))
        self.event = DomainEvent(
            self.session,"chain-event-1",1,"SESSION_CREATED","synthetic-test",
            "2026-11-23T12:34:56.123456Z","chain integration test",'{"synthetic":true}'
        )

    def append(self, event):
        return append(self.conn, self.tenant, event)

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
        with psycopg.connect(self.admin_url,autocommit=True) as admin:
            self.assertEqual(admin.execute("SELECT faos.event_chain_genesis_hash(%s::uuid,%s)",(self.tenant,self.session)).fetchone()[0],expected_genesis)
            self.assertEqual(admin.execute(
                "SELECT faos.event_chain_entry_hash(%s::uuid,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (self.tenant,self.session,self.event.event_id,self.event.sequence,self.event.kind,self.event.actor,
                 self.event.occurred_at,self.event.reason,self.event.payload_json,self.event.schema_version,expected_genesis)
            ).fetchone()[0],expected_entry)

    def test_idempotent_retry_and_conflicting_retry(self):
        self.assertEqual(self.append(self.event),"ACCEPTED")
        self.assertEqual(self.append(self.event),"DUPLICATE")
        changed=self.event.__class__(**{**self.event.__dict__,"reason":"altered retry"})
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

    def test_direct_insert_is_guarded_and_auto_hashed_for_privileged_fixture_role(self):
        with psycopg.connect(self.admin_url,autocommit=True) as admin:
            admin.execute("INSERT INTO faos.events(tenant_id,session_id,event_id,sequence,kind,actor,occurred_at,reason,payload_json,schema_version) VALUES (%s,%s,%s,1,%s,%s,%s,%s,%s,%s)",
                (self.tenant,self.session,"admin-fixture-event",1,"SESSION_CREATED","synthetic-admin",
                 "2026-11-23T12:35:00Z","privileged fixture","{\"synthetic\":true}","0.1"))
            row=admin.execute("SELECT previous_hash,entry_hash,hash_version FROM faos.events WHERE tenant_id=%s AND session_id=%s AND event_id=%s",
                (self.tenant,self.session,"admin-fixture-event")).fetchone()
            self.assertEqual(row[0],genesis_hash(self.tenant,self.session))
            self.assertEqual(row[2],"event-hash-v1")
            self.assertEqual(row[1],event_hash(self.tenant,DomainEvent(self.session,"admin-fixture-event",1,"SESSION_CREATED","synthetic-admin",
                "2026-11-23T12:35:00Z","privileged fixture",'{"synthetic":true}'),row[0]))

    def test_mutation_rejected_by_trigger(self):
        self.assertEqual(self.append(self.event),"ACCEPTED")
        with psycopg.connect(self.admin_url,autocommit=True) as admin:
            with self.assertRaises(psycopg.errors.RaiseException) as raised:
                admin.execute("UPDATE faos.events SET reason='tampered' WHERE tenant_id=%s AND session_id=%s",(self.tenant,self.session))
            self.assertEqual(raised.exception.diag.message_primary,"EVENT_HISTORY_IMMUTABLE")


if __name__ == "__main__":
    unittest.main()
