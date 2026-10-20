"""Connected synthetic DB slice under staged authority; no live capture/cutover."""
from dataclasses import replace
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
import uuid
import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo
from database.completion import record_registered_completion
from database.eligibility import check_registered_completion
from database.journal import append, tenant_transaction
from database.receipts import inspect_completion_receipt

class TenantAuthorityVerticalSlice(unittest.TestCase):
    def setUp(self):
        import test_tenant_authority_integration as fixtures
        self.base = fixtures.TenantAuthorityIntegration()
        self.addCleanup(self.base.doCleanups)
        self.base.setUp()

    def test_evidence_receipt_restart_isolation_and_revocation(self):
        from test_completion_coverage import CompletionCoverage
        f = self.base
        tenant = f.tenants[0]
        app = f.connections[0]
        events,data,digest = CompletionCoverage().fixture()
        session = events[0].session_id
        seal = events[-1].event_id
        f.seed.execute('INSERT INTO faos.sessions(tenant_id,session_id) VALUES (%s,%s) ON CONFLICT DO NOTHING',(tenant,session))
        for event in events:
            self.assertEqual(append(app,tenant,event),'ACCEPTED')
        role = 'slice_writer_'+uuid.uuid4().hex
        password = uuid.uuid4().hex
        f.admin.execute(sql.SQL('CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS PASSWORD {}').format(sql.Identifier(role),sql.Literal(password)))
        self.addCleanup(f.drop_role,role)
        f.admin.execute(sql.SQL('GRANT faos_writer TO {}').format(sql.Identifier(role)))
        self.assertEqual(f.seed.execute('INSERT INTO faos.tenant_login_bindings(role_oid,role_name,tenant_id) SELECT oid,rolname,%s FROM pg_roles WHERE rolname=%s',(tenant,role)).rowcount,1)
        url = os.getenv('MIGRATION_TEST_ADMIN_URL','postgresql://postgres:synthetic-container-only@127.0.0.1:55432/claim2car_test')
        writer = psycopg.connect(make_conninfo(url,dbname=f.db,user=role,password=password),autocommit=True,connect_timeout=5)
        self.addCleanup(writer.close)
        writer.execute('SET ROLE faos_writer')
        self.assertEqual(writer.execute('SELECT session_user,current_user').fetchone(),(role,'faos_writer'))
        with tenant_transaction(writer,tenant):
            status = writer.execute('SELECT faos.register_manifest_root(%s::uuid,%s::text,%s::text,%s::text,%s::text)',
                                    (tenant,session,seal,digest,'claims2car-12-v1')).fetchone()[0]
        self.assertEqual(status,'REGISTERED')
        request = str(uuid.uuid4())
        result = record_registered_completion(writer,tenant,session,request,data)
        self.assertEqual((result.receipt_status,result.decision.status,result.event_sequence),('RECORDED','ELIGIBLE',len(events)))
        self.assertEqual(record_registered_completion(writer,tenant,session,request,data).receipt_status,'DUPLICATE')
        receipt = inspect_completion_receipt(app,tenant,session,request)
        self.assertEqual((receipt.manifest_digest,receipt.seal_event_id,receipt.event_sequence),(digest,seal,len(events)))
        self.assertTrue(receipt.snapshot_matches_current_history)
        child_password = uuid.uuid4().hex
        f.admin.execute(sql.SQL('ALTER ROLE {} PASSWORD {}').format(sql.Identifier(f.roles[0]),sql.Literal(child_password)))
        env = os.environ.copy()
        env['SLICE_DATABASE_URL'] = make_conninfo(url,dbname=f.db,user=f.roles[0],password=child_password)
        child = """import json,os,sys
import psycopg
from database.readback import load_journal
from database.receipts import inspect_completion_receipt
value=json.load(sys.stdin)
with psycopg.connect(os.environ['SLICE_DATABASE_URL'],autocommit=True,connect_timeout=5) as conn:
    history=load_journal(conn,value['tenant'],value['session'])
    receipt=inspect_completion_receipt(conn,value['tenant'],value['session'],value['request'])
print(json.dumps({'events':len(history.events),'sequence':receipt.event_sequence,'digest':receipt.manifest_digest,'request':receipt.request_id,'snapshot_matches':receipt.snapshot_matches_current_history}))
"""
        recovered = subprocess.run([sys.executable,'-c',child],input=json.dumps({'tenant':tenant,'session':session,'request':request}),
                                   cwd=Path(__file__).resolve().parents[2],env=env,text=True,capture_output=True,timeout=30)
        self.assertEqual(recovered.returncode,0,recovered.stderr)
        self.assertEqual(json.loads(recovered.stdout),{'events':len(events),'sequence':len(events),'digest':digest,'request':request,'snapshot_matches':True})
        with self.assertRaises(psycopg.errors.RaiseException) as denied:
            inspect_completion_receipt(f.connections[1],tenant,session,request)
        self.assertEqual(denied.exception.sqlstate,'P0001')
        self.assertEqual(denied.exception.diag.message_primary,'TENANT_CONTEXT_MISMATCH')
        with self.assertRaisesRegex(ValueError,'INTEGRITY_NOT_VERIFIED'):
            check_registered_completion(app,tenant,session,dict(data,front=b'tampered'))
        revoked = replace(events[1],event_id='slice-revocation',sequence=len(events)+1,
                          payload_json='{"disclosure_version":"synthetic-v1","evidence_scope":false}')
        self.assertEqual(append(app,tenant,revoked),'ACCEPTED')
        with self.assertRaisesRegex(ValueError,'REQUIRED_CONSENT_MISSING'):
            check_registered_completion(app,tenant,session,data)
        with self.assertRaisesRegex(ValueError,'REQUIRED_CONSENT_MISSING'):
            record_registered_completion(writer,tenant,session,str(uuid.uuid4()),data)
        historical = inspect_completion_receipt(app,tenant,session,request)
        self.assertEqual((historical.request_id,historical.event_sequence),(request,len(events)))
        self.assertFalse(historical.snapshot_matches_current_history)
        self.assertEqual(historical.current_event_sequence,len(events)+1)
        self.assertEqual(f.seed.execute('SELECT count(*) FROM faos.completion_receipts WHERE tenant_id=%s AND session_id=%s',(tenant,session)).fetchone()[0],1)

if __name__ == '__main__':
    unittest.main()
