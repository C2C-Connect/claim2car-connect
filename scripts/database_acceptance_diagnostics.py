"""Baseline diagnostics, not a complete 14-gate acceptance runner."""
import json
import os
from pathlib import Path
import subprocess
import uuid
import psycopg
from psycopg.conninfo import conninfo_to_dict
from app.domain_events import DomainEvent
from database.journal import tenant_transaction

class RollbackProbe(Exception):
    pass

def run():
    url = os.environ['APP_DATABASE_URL']
    config = conninfo_to_dict(url)
    expected = {'host':'127.0.0.1','port':'55432','dbname':'claim2car_test','user':'faos_app'}
    if any(config.get(key) != value for key,value in expected.items()):
        raise ValueError('EXPLICIT_SYNTHETIC_TARGET_REQUIRED')
    report = {'classification':'baseline-diagnostics-not-gate-certification',
              'commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
              'contract':'C2C-DB-AC-001 v1.0 proposed',
              'gate_passes_awarded':0,'checks':[]}
    sql = 'SELECT faos.append_event(%s::uuid,%s::text,%s::text,%s::bigint,%s::text,%s::text,%s::text,%s::text,%s::text,%s::text)'
    with psycopg.connect(url,autocommit=True,connect_timeout=5) as conn:
        conn.execute("SET statement_timeout='8s'")
        conn.execute("SET lock_timeout='5s'")
        role = conn.execute('SELECT current_user,rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user').fetchone()
        if role != ('faos_app',False,False):
            raise ValueError('RESTRICTED_APP_ROLE_REQUIRED')
        report['database'] = conn.execute('SELECT current_database(),version()').fetchone()
        report['extensions'] = conn.execute('SELECT extname,extversion FROM pg_extension ORDER BY extname').fetchall()
        tenants = [str(uuid.uuid4()),str(uuid.uuid4())]
        session = 'acceptance-probe-' + uuid.uuid4().hex
        for tenant in tenants:
            with tenant_transaction(conn,tenant):
                conn.execute('INSERT INTO faos.organizations(tenant_id,name) VALUES (%s,%s)',(tenant,'synthetic acceptance diagnostic'))
                conn.execute('INSERT INTO faos.sessions(tenant_id,session_id) VALUES (%s,%s)',(tenant,session))
        with tenant_transaction(conn,tenants[0]):
            conn.execute("SELECT set_config('faos.tenant_id',%s,true)",(tenants[1],))
            visible = conn.execute('SELECT tenant_id::text FROM faos.sessions WHERE session_id=%s',(session,)).fetchall()
        exposed = (tenants[1],) in visible
        report['checks'].append({'id':'G04-DIRECT-SQL-TENANT-SWITCH','status':'FAIL' if exposed else 'PASS',
                                'threat_model':'actor can execute arbitrary SQL as shared faos_app role',
                                'other_tenant_visible':exposed,
                                'scope':'diagnostic assertion only; not a complete gate result'})
        probes = [('timestamp','not-a-timestamp','{}'),
                  ('canonical_payload','2026-01-01T00:00:00Z','{"a": 1}'),
                  ('payload_leading','2026-01-01T00:00:00Z',' {"a":1}'),
                  ('payload_nested','2026-01-01T00:00:00Z','{"a":[1, 2]}')]
        for name,timestamp,payload in probes:
            event = DomainEvent(session,'probe-'+name,1,'SESSION_CREATED','synthetic-diagnostic',timestamp,'validation parity',payload)
            try:
                event.validate()
            except ValueError as error:
                python_error = str(error)
            else:
                raise AssertionError('PYTHON_INVALID_FIXTURE_REQUIRED')
            try:
                with tenant_transaction(conn,tenants[0]):
                    result = conn.execute(sql,(tenants[0],session,event.event_id,1,event.kind,event.actor,event.occurred_at,event.reason,event.payload_json,event.schema_version)).fetchone()[0]
                    report['checks'].append({'id':'G06-DIRECT-SQL-'+name,'status':'FAIL',
                                            'python_rejection':python_error,'sql_result':result,
                                            'scope':'invalid append succeeded then transaction rolled back'})
                    raise RollbackProbe()
            except RollbackProbe:
                pass
            except psycopg.Error as error:
                constraint = error.diag.constraint_name
                expected_constraint = 'event_timestamp_input_valid' if name == 'timestamp' else 'event_payload_compact'
                attributed = error.sqlstate == '23514' and constraint == expected_constraint
                report['checks'].append({'id':'G06-DIRECT-SQL-'+name,'status':'PASS' if attributed else 'UNVERIFIED',
                                        'python_rejection':python_error,'sqlstate':error.sqlstate,
                                        'constraint_name':constraint,
                                        'reason':'Expected named constraint rejection' if attributed else 'SQL rejection requires attribution to the intended validation rule',
                                        'scope':'diagnostic assertion only; not full canonicalization/timestamp parity or a gate result'})
            with tenant_transaction(conn,tenants[0]):
                remaining = conn.execute('SELECT count(*) FROM faos.events WHERE tenant_id=%s AND session_id=%s',(tenants[0],session)).fetchone()[0]
            if remaining != 0:
                raise AssertionError('PROBE_ROLLBACK_FAILED')
        payload = json.dumps({'message':'a b','quote':'a" b','nested':{'items':[1,2]}},sort_keys=True,separators=(',',':'))
        event = DomainEvent(session,'compact-control',1,'SESSION_CREATED','synthetic-diagnostic','2026-01-01T00:00:00Z','compact positive control',payload).validate()
        values = (tenants[0],session,event.event_id,1,event.kind,event.actor,event.occurred_at,event.reason,event.payload_json,event.schema_version)
        try:
            with tenant_transaction(conn,tenants[0]):
                first = conn.execute(sql,values).fetchone()[0]
                retry = conn.execute(sql,values).fetchone()[0]
                rows = conn.execute('SELECT event_id,payload_json FROM faos.events WHERE tenant_id=%s AND session_id=%s',(tenants[0],session)).fetchall()
                if (first,retry,rows) != ('ACCEPTED','DUPLICATE',[(event.event_id,payload)]):
                    raise AssertionError('COMPACT_JSON_POSITIVE_CONTROL_FAILED')
                raise RollbackProbe()
        except RollbackProbe:
            pass
        with tenant_transaction(conn,tenants[0]):
            if conn.execute('SELECT count(*) FROM faos.events WHERE tenant_id=%s AND session_id=%s',(tenants[0],session)).fetchone()[0] != 0:
                raise AssertionError('POSITIVE_CONTROL_ROLLBACK_FAILED')
        report['checks'].append({'id':'G06-COMPACT-JSON-POSITIVE-CONTROL','status':'PASS',
                                'first_append':first,'identical_retry':retry,'exact_payload_readback':True,'rollback_verified':True,
                                'scope':'spaces and escaped quotes inside strings preserved; no full canonicalization claim'})
    report['complete_gate_results'] = 'NOT RUN'
    report['overall_acceptance'] = 'NOT ACCEPTED'
    report['diagnostics_successful'] = all(check['status']=='PASS' for check in report['checks'])
    return report

if __name__ == '__main__':
    path = Path('output/acceptance-diagnostics/report.json')
    path.parent.mkdir(parents=True,exist_ok=True)
    try:
        report = run()
    except Exception as error:
        report = {'classification':'baseline-diagnostics-not-gate-certification','overall_acceptance':'NOT ACCEPTED',
                  'gate_passes_awarded':0,'diagnostics_successful':False,'execution_error_type':type(error).__name__}
    path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,sort_keys=True))
    raise SystemExit(0 if report['diagnostics_successful'] else 1)
