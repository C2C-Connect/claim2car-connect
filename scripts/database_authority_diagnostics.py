"""Post-cutover synthetic assertions; not full 14-gate acceptance."""
import json
import os
from pathlib import Path
import subprocess
import uuid
import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from app.domain_events import DomainEvent
from database.journal import append, tenant_transaction
from database.readback import load_journal

APPEND = 'SELECT faos.append_event(%s::uuid,%s::text,%s::text,%s::bigint,%s::text,%s::text,%s::text,%s::text,%s::text,%s::text)'

def expect(value, message):
    if not value:
        raise AssertionError(message)

def denied(conn,tenant,event):
    with tenant_transaction(conn,tenant):
        expect(conn.execute('SELECT faos.tenant_id()').fetchone()[0] is None,'UNAUTHORIZED_CONTEXT_ACCEPTED')
        expect(conn.execute('SELECT 1 FROM faos.sessions WHERE session_id=%s',(event.session_id,)).fetchall()==[],'UNAUTHORIZED_SESSION_VISIBLE')
        expect(conn.execute('SELECT 1 FROM faos.events WHERE session_id=%s',(event.session_id,)).fetchall()==[],'UNAUTHORIZED_EVENT_VISIBLE')
    try:
        append(conn,tenant,event)
    except psycopg.errors.RaiseException as error:
        expect(error.sqlstate=='P0001' and error.diag.message_primary=='TENANT_CONTEXT_MISMATCH','WRONG_APPEND_REJECTION')
    else:
        raise AssertionError('UNAUTHORIZED_APPEND_ALLOWED')

def run(report):
    admin_url = os.environ['MIGRATION_TEST_ADMIN_URL']
    app_url = os.environ['APP_DATABASE_URL']
    for url,user in ((admin_url,'postgres'),(app_url,'faos_app')):
        config = conninfo_to_dict(url)
        expect(all(config.get(k)==v for k,v in {'host':'127.0.0.1','port':'55432','dbname':'claim2car_test','user':user}.items()),'EXPLICIT_SYNTHETIC_TARGET_REQUIRED')
    tenants = [str(uuid.uuid4()),str(uuid.uuid4())]
    roles = []
    connections = []
    session = 'cutover-'+uuid.uuid4().hex
    with psycopg.connect(admin_url,autocommit=True,connect_timeout=5) as admin:
        report['migration_inventory'] = admin.execute('SELECT name,sha256 FROM public.faos_migration_history ORDER BY ordinal').fetchall()
        expect(report['migration_inventory'][-1][0]=='0008_tenant_login_authority.sql','AUTHORITY_MIGRATION_REQUIRED')
        report['database'] = admin.execute('SELECT current_database(),version()').fetchone()
        report['extensions'] = admin.execute('SELECT extname,extversion FROM pg_extension ORDER BY extname').fetchall()
        try:
            for tenant in tenants:
                admin.execute('INSERT INTO faos.organizations VALUES (%s,%s)',(tenant,'synthetic post-cutover diagnostic'))
                admin.execute('INSERT INTO faos.sessions VALUES (%s,%s)',(tenant,session))
                role,password = 'cutover_'+uuid.uuid4().hex,uuid.uuid4().hex
                admin.execute(sql.SQL('CREATE ROLE {} LOGIN INHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS PASSWORD {}').format(sql.Identifier(role),sql.Literal(password)))
                roles.append(role)
                admin.execute(sql.SQL('GRANT faos_app TO {}').format(sql.Identifier(role)))
                expect(admin.execute('INSERT INTO faos.tenant_login_bindings(role_oid,role_name,tenant_id) SELECT oid,rolname,%s FROM pg_roles WHERE rolname=%s',(tenant,role)).rowcount==1,'BINDING_NOT_CREATED')
                conn = psycopg.connect(make_conninfo(admin_url,user=role,password=password),autocommit=True,connect_timeout=5)
                connections.append(conn)
                expect(conn.execute('SELECT session_user,current_user,rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user').fetchone()==(role,role,False,False),'RESTRICTED_BOUND_ROLE_REQUIRED')
                conn.execute("SET statement_timeout='8s'")
                conn.execute("SET lock_timeout='5s'")
            event = DomainEvent(session,'event-1',1,'SESSION_CREATED','synthetic-test','2026-01-01T00:00:00Z','post-cutover diagnostic','{}')
            for conn,tenant in zip(connections,tenants):
                expect(append(conn,tenant,event)=='ACCEPTED','VALID_APPEND_FAILED')
                expect(append(conn,tenant,event)=='DUPLICATE','IDENTICAL_RETRY_FAILED')
                expect(load_journal(conn,tenant,session).events==(event,),'COMMITTED_READBACK_FAILED')
            report['checks'].append({'id':'BOUND-APPEND-RETRY-READBACK','status':'PASS'})
            denied(connections[0],tenants[1],event)
            report['checks'].append({'id':'G04-DIRECT-SQL-TENANT-SWITCH','status':'PASS','other_tenant_visible':False})
            with psycopg.connect(app_url,autocommit=True,connect_timeout=5) as unbound:
                for tenant in tenants:
                    denied(unbound,tenant,event)
            report['checks'].append({'id':'UNBOUND-SHARED-LOGIN-DENIED','status':'PASS'})
            for statement in ('SELECT * FROM faos.tenant_login_bindings','UPDATE faos.tenant_login_bindings SET enabled=enabled'):
                try:
                    with connections[0].transaction():
                        connections[0].execute(statement)
                        raise AssertionError('AUTHORITY_REGISTRY_ACCESS_ALLOWED')
                except psycopg.errors.InsufficientPrivilege as error:
                    expect(error.sqlstate=='42501','WRONG_REGISTRY_REJECTION')
            report['checks'].append({'id':'PRIVATE-AUTHORITY-REGISTRY','status':'PASS'})
            for name,timestamp,payload,constraint in [('timestamp','not-a-timestamp','{}','event_timestamp_input_valid'),('compact_payload','2026-01-01T00:00:00Z','{"a": 1}','event_payload_compact')]:
                try:
                    with tenant_transaction(connections[0],tenants[0]):
                        connections[0].execute(APPEND,(tenants[0],session,'invalid-'+name,2,'SESSION_CREATED','synthetic-test',timestamp,'validation diagnostic',payload,'0.1'))
                        raise AssertionError('INVALID_EVENT_ACCEPTED')
                except psycopg.errors.CheckViolation as error:
                    expect(error.sqlstate=='23514' and error.diag.constraint_name==constraint,'WRONG_VALIDATION_REJECTION')
                expect(load_journal(connections[0],tenants[0],session).events==(event,),'REJECTED_EVENT_CHANGED_HISTORY')
                report['checks'].append({'id':'G06-'+name,'status':'PASS','constraint_name':constraint})
            payload = json.dumps({'message':'a b','quote':'a" b'},sort_keys=True,separators=(',',':'))
            positive = DomainEvent(session,'event-2',2,'SESSION_CREATED','synthetic-test','2026-01-01T00:00:00Z','compact positive control',payload)
            expect(append(connections[0],tenants[0],positive)=='ACCEPTED','COMPACT_APPEND_FAILED')
            expect(append(connections[0],tenants[0],positive)=='DUPLICATE','COMPACT_RETRY_FAILED')
            expect(load_journal(connections[0],tenants[0],session).events==(event,positive),'COMPACT_READBACK_FAILED')
            report['checks'].append({'id':'COMPACT-JSON-POSITIVE-CONTROL','status':'PASS'})
            expect(admin.execute('UPDATE faos.tenant_login_bindings SET enabled=false WHERE role_name=%s',(roles[0],)).rowcount==1,'REVOCATION_FAILED')
            denied(connections[0],tenants[0],event)
            expect(load_journal(connections[1],tenants[1],session).events==(event,),'OTHER_TENANT_DISRUPTED')
            report['checks'].append({'id':'BINDING-REVOCATION-NEXT-TRANSACTION','status':'PASS'})
        finally:
            for conn in connections:
                conn.close()
            for tenant in tenants:
                for table in ('events','sessions','tenant_login_bindings','organizations'):
                    admin.execute(sql.SQL('DELETE FROM faos.{} WHERE tenant_id=%s').format(sql.Identifier(table)),(tenant,))
            for role in roles:
                admin.execute(sql.SQL('DROP ROLE {}').format(sql.Identifier(role)))
    report['diagnostics_successful'] = len(report['checks'])==8 and all(row['status']=='PASS' for row in report['checks'])

if __name__ == '__main__':
    report = {'classification':'post-cutover-authority-diagnostics-not-gate-certification',
              'commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
              'contract':'C2C-DB-AC-001 v1.0 proposed','gate_passes_awarded':0,'checks':[],
              'complete_gate_results':'NOT RUN','overall_acceptance':'NOT ACCEPTED','diagnostics_successful':False}
    try:
        run(report)
    except Exception as error:
        report['diagnostics_successful'] = False
        report['execution_error_type'] = type(error).__name__
    path = Path('output/acceptance-diagnostics/report.json')
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,sort_keys=True))
    raise SystemExit(0 if report['diagnostics_successful'] else 1)
