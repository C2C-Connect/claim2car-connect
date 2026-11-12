"""Post-cutover synthetic assertions; not full 14-gate acceptance."""
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid
import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from app.domain_events import DomainEvent
from database.journal import append, tenant_transaction
from database.readback import load_journal

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests' / 'database'))
from verify_gates import run_all_gate_verifiers

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

TABLES = ('organizations','users','memberships','dealer_groups','dealer_locations','location_brands','sessions','events','manifest_roots','completion_receipts','financial_ledger_entries','financial_ledger_postings','claim_cases','claim_case_incident_intake')
CHECKS = ('rls_flags','own_read','cross_read','cross_insert','cross_update','cross_delete','tenant_reassignment','spoofed_context','missing_context','malformed_context')

def reject_mutation(conn,tenant,statement,parameters):
    try:
        with tenant_transaction(conn,tenant):
            conn.execute(statement,parameters)
            raise AssertionError('MUTATION_NOT_DENIED')
    except psycopg.errors.InsufficientPrivilege as error:
        expect(error.sqlstate=='42501','WRONG_AUTHORIZATION_SQLSTATE')
        return {'status':'PASS','sqlstate':'42501'}

def verify(report,admin,connections,tenants,session):
    matrix = {'id':'POSTCUTOVER-PER-TABLE-ISOLATION','status':'RUNNING','table_count':len(TABLES),'tenant_directions':2,
              'fixture_classification':'admin-provisioned storage-isolation fixtures; not evidence evaluation or accepted completion',
              'results':[]}
    report['checks'].append(matrix)
    actual = admin.execute("SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace JOIN pg_attribute a ON a.attrelid=c.oid WHERE n.nspname='faos' AND c.relkind IN ('r','p') AND a.attname='tenant_id' AND NOT a.attisdropped AND c.relname<>'tenant_login_bindings'").fetchall()
    expect({row[0] for row in actual}==set(TABLES),'TENANT_TABLE_SCOPE_CHANGED')
    ids = {key:str(uuid.uuid4()) for key in ('user','membership','group','location','brand','extra_brand','request','claim')}
    seal = 'matrix-seal-'+uuid.uuid4().hex
    digest = '0'*64
    try:
        for brand in ('brand','extra_brand'):
            admin.execute('INSERT INTO faos.brands VALUES (%s,%s)',(ids[brand],'matrix-'+ids[brand]))
        for tenant in tenants:
            admin.execute('INSERT INTO faos.claim_cases(tenant_id,claim_id,request_id,created_by,owner_actor_id) VALUES (%s,%s,%s,%s,%s)',(tenant,ids['claim'],ids['request'],'synthetic-matrix','synthetic-matrix'))
            admin.execute('INSERT INTO faos.claim_case_incident_intake(tenant_id,claim_id,owner_actor_id,request_id,incident_occurred_at,incident_type,incident_city,incident_region,incident_postal_code) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)',(tenant,ids['claim'],'synthetic-matrix',ids['request'],'2026-01-01T00:00:00Z','collision','San Antonio','TX','78201'))
            admin.execute('INSERT INTO faos.users VALUES (%s,%s,%s)',(tenant,ids['user'],'matrix-subject'))
            admin.execute('INSERT INTO faos.memberships VALUES (%s,%s,%s,%s)',(tenant,ids['user'],ids['membership'],'synthetic-matrix'))
            admin.execute('INSERT INTO faos.dealer_groups VALUES (%s,%s,%s)',(tenant,ids['group'],'synthetic matrix'))
            admin.execute('INSERT INTO faos.dealer_locations(tenant_id,location_id,group_id,name) VALUES (%s,%s,%s,%s)',(tenant,ids['location'],ids['group'],'synthetic matrix'))
            admin.execute('INSERT INTO faos.location_brands VALUES (%s,%s,%s)',(tenant,ids['location'],ids['brand']))
            sequence = admin.execute('SELECT max(sequence)+1 FROM faos.events WHERE tenant_id=%s AND session_id=%s',(tenant,session)).fetchone()[0]
            payload = json.dumps({'schema_version':'0.1','manifest_digest':digest,'shot_list_version':'claims2car-12-v1'},sort_keys=True,separators=(',',':'))
            admin.execute('INSERT INTO faos.events VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',(tenant,session,seal,sequence,'MANIFEST_SEALED','synthetic-matrix','2026-01-01T00:00:00Z','storage isolation fixture only',payload,'0.1'))
            admin.execute('INSERT INTO faos.manifest_roots(tenant_id,session_id,seal_event_id,manifest_digest,shot_list_version) VALUES (%s,%s,%s,%s,%s)',(tenant,session,seal,digest,'claims2car-12-v1'))
            admin.execute('INSERT INTO faos.completion_receipts(tenant_id,session_id,request_id,seal_event_id,event_sequence) VALUES (%s,%s,%s,%s,%s)',(tenant,session,ids['request'],seal,sequence))
            ledger_id='matrix-ledger-'+uuid.uuid4().hex
            admin.execute('INSERT INTO faos.financial_ledger_entries(tenant_id,entry_id,sequence,idempotency_key,session_id,entry_kind,fee_type,partner_org_id,acceptance_id,amount_cents,currency,actor_id,occurred_at,reason,previous_hash,entry_hash) VALUES (%s,%s,1,%s,%s,%s,%s,%s,%s,37500,%s,%s,%s,%s,%s,%s)',
                (tenant,ledger_id,'matrix-ledger-idem-'+uuid.uuid4().hex,session,'OBLIGATION_BOOKED','DEALER_ACQUISITION_FEE','matrix-partner','matrix-acceptance','USD_CENTS','diagnostics','2026-01-01T00:00:00Z','diagnostic storage fixture','0'*64,'1'*64))
            admin.execute('INSERT INTO faos.financial_ledger_postings VALUES (%s,%s,1,%s,%s,37500),(%s,%s,2,%s,%s,37500)',
                (tenant,ledger_id,'AR:DEALER:matrix-partner','DEBIT',tenant,ledger_id,'REV:DEALER_ACQUISITION','CREDIT'))
        for index,conn in enumerate(connections):
            own,other = tenants[index],tenants[1-index]
            for table in TABLES:
                target = sql.SQL('faos.{}').format(sql.Identifier(table))
                select = sql.SQL('SELECT tenant_id::text FROM {} WHERE tenant_id IN (%s::uuid,%s::uuid)').format(target)
                row = {'tenant_index':index,'table':table,'checks':{}}
                matrix['results'].append(row)
                results = row['checks']
                flags = conn.execute("SELECT c.relrowsecurity,c.relforcerowsecurity FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='faos' AND c.relname=%s",(table,)).fetchone()
                policies = conn.execute("SELECT policyname,cmd,roles::text,qual,with_check FROM pg_policies WHERE schemaname='faos' AND tablename=%s ORDER BY policyname",(table,)).fetchall()
                expect(flags==(True,True) and bool(policies),'RLS_CONFIGURATION_MISSING')
                results['rls_flags'] = {'status':'PASS','enabled':True,'forced':True,'policies':policies}
                expected = admin.execute(sql.SQL('SELECT count(*) FROM {} WHERE tenant_id=%s').format(target),(own,)).fetchone()[0]
                with tenant_transaction(conn,own):
                    if table=='claim_case_incident_intake':
                        try:
                            with conn.transaction():
                                conn.execute('SELECT * FROM faos.claim_case_incident_intake').fetchall()
                                raise AssertionError('DIRECT_INCIDENT_TABLE_READ_ALLOWED')
                        except psycopg.errors.InsufficientPrivilege as error:
                            expect(error.sqlstate=='42501','WRONG_DIRECT_READ_DENIAL')
                        visible = conn.execute('SELECT * FROM faos.read_claim_case_incident(%s::uuid,%s::uuid,%s::text)',
                            (own,ids['claim'],'synthetic-matrix')).fetchall()
                        expect(expected>0 and len(visible)==expected,'AUTHORIZED_READ_CONTROL_FAILED')
                        results['own_read'] = {'status':'PASS','rows':len(visible),'path':'actor-filtered-function','direct_table_select':'DENIED'}
                        hidden = conn.execute('SELECT * FROM faos.read_claim_case_incident(%s::uuid,%s::uuid,%s::text)',
                            (own,ids['claim'],'unrelated-actor')).fetchall()
                        expect(hidden==[],'UNAUTHORIZED_ACTOR_READ_ALLOWED')
                        results['cross_read'] = {'status':'PASS','path':'actor-filtered-function'}
                    else:
                        visible = conn.execute(select,tenants).fetchall()
                        expect(expected>0 and len(visible)==expected and all(value[0]==own for value in visible),'AUTHORIZED_READ_CONTROL_FAILED')
                        results['own_read'] = {'status':'PASS','rows':len(visible)}
                        expect(conn.execute(sql.SQL('SELECT 1 FROM {} WHERE tenant_id=%s').format(target),(other,)).fetchall()==[],'CROSS_TENANT_ROWS_VISIBLE')
                        results['cross_read'] = {'status':'PASS'}
                privileges = conn.execute("SELECT has_table_privilege(current_user,%s,'INSERT'),has_table_privilege(current_user,%s,'UPDATE'),has_table_privilege(current_user,%s,'DELETE')",('faos.'+table,)*3).fetchone()
                cursor = admin.execute(sql.SQL('SELECT * FROM {} WHERE tenant_id=%s LIMIT 1').format(target),(other,))
                values = dict(zip((column.name for column in cursor.description),cursor.fetchone()))
                key = {'users':'user_id','memberships':'membership_id','dealer_groups':'group_id','dealer_locations':'location_id','sessions':'session_id','events':'event_id','completion_receipts':'request_id','claim_cases':'claim_id','claim_case_incident_intake':'request_id'}.get(table)
                if key:
                    values[key] = str(uuid.uuid4())
                if table=='claim_case_incident_intake':
                    values['claim_id'] = ids['claim']
                    values['owner_actor_id'] = 'synthetic-matrix'
                if table=='users':
                    values['external_subject'] = 'new-'+uuid.uuid4().hex
                if table=='location_brands':
                    values['brand_id'] = ids['extra_brand']
                if table=='events':
                    values['sequence'] = 99
                insert = sql.SQL('INSERT INTO {} ({}) VALUES ({})').format(target,sql.SQL(',').join(map(sql.Identifier,values)),sql.SQL(',').join(sql.Placeholder() for _ in values))
                results['cross_insert'] = reject_mutation(conn,own,insert,tuple(values.values()))
                results['cross_insert']['layer'] = 'rls' if privileges[0] else 'table_privilege'
                for operation,allowed in (('UPDATE',privileges[1]),('DELETE',privileges[2])):
                    statement = (sql.SQL('UPDATE {} SET tenant_id=tenant_id WHERE tenant_id=%s') if operation=='UPDATE' else sql.SQL('DELETE FROM {} WHERE tenant_id=%s')).format(target)
                    if allowed:
                        with tenant_transaction(conn,own):
                            expect(conn.execute(statement,(other,)).rowcount==0,'CROSS_TENANT_MUTATION_OCCURRED')
                        result = {'status':'PASS','layer':'rls','affected_rows':0}
                    else:
                        result = reject_mutation(conn,own,statement,(other,))
                        result['layer'] = 'table_privilege'
                    results['cross_'+operation.lower()] = result
                move = sql.SQL('UPDATE {} SET tenant_id=%s WHERE tenant_id=%s').format(target)
                results['tenant_reassignment'] = reject_mutation(conn,own,move,(other,own))
                results['tenant_reassignment']['layer'] = 'rls' if privileges[1] else 'table_privilege'
                with tenant_transaction(conn,other):
                    if table=='claim_case_incident_intake':
                        try:
                            with conn.transaction():
                                conn.execute('SELECT * FROM faos.read_claim_case_incident(%s::uuid,%s::uuid,%s::text)',
                                    (own,ids['claim'],'synthetic-matrix')).fetchall()
                                raise AssertionError('SPOOFED_CONTEXT_ALLOWED')
                        except psycopg.errors.RaiseException as error:
                            expect(error.diag.message_primary=='TENANT_CONTEXT_MISMATCH','WRONG_SPOOFED_CONTEXT_REJECTION')
                    else:
                        expect(conn.execute('SELECT faos.tenant_id()').fetchone()[0] is None and conn.execute(select,tenants).fetchall()==[],'SPOOFED_CONTEXT_ALLOWED')
                results['spoofed_context'] = {'status':'PASS'}
                with conn.transaction():
                    conn.execute("SELECT set_config('faos.tenant_id','',true)")
                    if table=='claim_case_incident_intake':
                        try:
                            with conn.transaction():
                                conn.execute('SELECT * FROM faos.read_claim_case_incident(%s::uuid,%s::uuid,%s::text)',
                                    (own,ids['claim'],'synthetic-matrix')).fetchall()
                                raise AssertionError('MISSING_CONTEXT_ALLOWED')
                        except psycopg.errors.RaiseException as error:
                            expect(error.diag.message_primary=='TENANT_CONTEXT_MISMATCH','WRONG_MISSING_CONTEXT_REJECTION')
                    else:
                        expect(conn.execute('SELECT faos.tenant_id()').fetchone()[0] is None and conn.execute(select,tenants).fetchall()==[],'MISSING_CONTEXT_ALLOWED')
                results['missing_context'] = {'status':'PASS'}
                try:
                    with conn.transaction():
                        conn.execute("SELECT set_config('faos.tenant_id','not-a-uuid',true)")
                        if table=='claim_case_incident_intake':
                            conn.execute('SELECT * FROM faos.read_claim_case_incident(%s::uuid,%s::uuid,%s::text)',
                                (own,ids['claim'],'synthetic-matrix')).fetchall()
                        else:
                            conn.execute(select,tenants).fetchall()
                        raise AssertionError('MALFORMED_CONTEXT_NOT_REJECTED')
                except psycopg.errors.InvalidTextRepresentation as error:
                    expect(error.sqlstate=='22P02','WRONG_MALFORMED_CONTEXT_SQLSTATE')
                results['malformed_context'] = {'status':'PASS','sqlstate':'22P02'}
        expect(len(matrix['results'])==2*len(TABLES) and all(set(row['checks'])==set(CHECKS) and all(item['status']=='PASS' for item in row['checks'].values()) for row in matrix['results']),'INCOMPLETE_ISOLATION_MATRIX')
        matrix['assertion_count'] = sum(len(row['checks']) for row in matrix['results'])
        matrix['status'] = 'PASS'
    finally:
        for tenant in tenants:
            admin.execute('DELETE FROM faos.financial_ledger_postings WHERE tenant_id=%s AND entry_id LIKE %s',(tenant,'matrix-ledger-%'))
            admin.execute('DELETE FROM faos.financial_ledger_entries WHERE tenant_id=%s AND entry_id LIKE %s',(tenant,'matrix-ledger-%'))
            for table in ('claim_case_incident_intake','claim_cases','completion_receipts','manifest_roots','location_brands'):
                admin.execute(sql.SQL('DELETE FROM faos.{} WHERE tenant_id=%s').format(sql.Identifier(table)),(tenant,))
            admin.execute('DELETE FROM faos.events WHERE tenant_id=%s AND session_id=%s AND event_id=%s',(tenant,session,seal))
        for brand in ('brand','extra_brand'):
            admin.execute('DELETE FROM faos.brands WHERE brand_id=%s',(ids[brand],))

def run(report):
    admin_url = os.environ['MIGRATION_TEST_ADMIN_URL']
    app_url = os.environ['APP_DATABASE_URL']
    migrator_url = os.environ['MIGRATION_DATABASE_URL']
    connection_urls = {
        'admin': (admin_url, 'postgres'),
        'application': (app_url, 'faos_app'),
        'migrator': (migrator_url, 'faos_migrator'),
    }
    sanitized = {}
    for name,(url,user) in connection_urls.items():
        config = conninfo_to_dict(url)
        expect(all(config.get(k)==v for k,v in {'host':'127.0.0.1','port':'55432','dbname':'claim2car_test','user':user}.items()),'EXPLICIT_SYNTHETIC_TARGET_REQUIRED')
        sanitized[name] = {key:config.get(key) for key in ('user','host','port','dbname')}
    report['environment'] = {'classification':'synthetic_isolated','connections':sanitized}
    tenants = [str(uuid.uuid4()),str(uuid.uuid4())]
    roles = []
    connections = []
    session = 'cutover-'+uuid.uuid4().hex
    with psycopg.connect(admin_url,autocommit=True,connect_timeout=5) as admin:
        report['migration_inventory'] = admin.execute('SELECT name,sha256 FROM public.faos_migration_history ORDER BY ordinal').fetchall()
        expect(report['migration_inventory'][-1][0]=='0018_capture_protocol_session_binding.sql','EVENT_CONTRACT_PARITY_MIGRATION_REQUIRED')
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
            for name,timestamp,payload,constraint in [
                ('timestamp','not-a-timestamp','{}','event_timestamp_input_valid'),
                ('naive_timestamp','2026-01-01T00:00:00','{}','event_timestamp_rfc3339'),
                ('compact_payload','2026-01-01T00:00:00Z','{"a": 1}','event_payload_compact'),
                ('key_order','2026-01-01T00:00:00Z','{"z":1,"a":2}','event_payload_python_canonical'),
                ('numeric_exponent','2026-01-01T00:00:00Z','{"value":1e0}','event_payload_python_canonical'),
                ('unicode_escape','2026-01-01T00:00:00Z','{"label":"\\u00e9"}','event_payload_python_canonical'),
            ]:
                try:
                    with tenant_transaction(connections[0],tenants[0]):
                        connections[0].execute(APPEND,(tenants[0],session,'invalid-'+name,2,'SESSION_CREATED','synthetic-test',timestamp,'validation diagnostic',payload,'0.1'))
                        raise AssertionError('INVALID_EVENT_ACCEPTED')
                except psycopg.errors.CheckViolation as error:
                    expect(error.sqlstate=='23514' and error.diag.constraint_name==constraint,'WRONG_VALIDATION_REJECTION')
                expect(load_journal(connections[0],tenants[0],session).events==(event,),'REJECTED_EVENT_CHANGED_HISTORY')
                report['checks'].append({'id':'G06-'+name,'status':'PASS','constraint_name':constraint})
            unicode_payload = '{"label":"é","metric":0.00001}'
            canonical_unicode = connections[0].execute(
                'SELECT faos.canonical_event_jsonb(%s::jsonb)', (unicode_payload,)
            ).fetchone()[0]
            expect(canonical_unicode == unicode_payload, 'SQL_UNICODE_OR_NUMERIC_CANONICALIZATION_MISMATCH')
            unicode_event = DomainEvent(session,'event-unicode',2,'SESSION_CREATED','synthetic-test',
                                        '2026-01-01T00:00:00Z','unicode and decimal positive control',unicode_payload)
            expect(append(connections[0],tenants[0],unicode_event)=='ACCEPTED','UNICODE_APPEND_FAILED')
            expect(load_journal(connections[0],tenants[0],session).events==(event,unicode_event),'UNICODE_READBACK_CHANGED_BYTES')
            report['checks'].append({'id':'G06-unicode-positive-control','status':'PASS'})
            payload = json.dumps({'message':'a b','quote':'a" b'},sort_keys=True,separators=(',',':'))
            positive = DomainEvent(session,'event-3',3,'SESSION_CREATED','synthetic-test','2026-01-01T00:00:00Z','compact positive control',payload)
            expect(append(connections[0],tenants[0],positive)=='ACCEPTED','COMPACT_APPEND_FAILED')
            expect(append(connections[0],tenants[0],positive)=='DUPLICATE','COMPACT_RETRY_FAILED')
            expect(load_journal(connections[0],tenants[0],session).events==(event,unicode_event,positive),'COMPACT_READBACK_FAILED')
            report['checks'].append({'id':'COMPACT-JSON-POSITIVE-CONTROL','status':'PASS'})
            verify(report,admin,connections,tenants,session)
            expect(admin.execute('UPDATE faos.tenant_login_bindings SET enabled=false WHERE role_name=%s',(roles[0],)).rowcount==1,'REVOCATION_FAILED')
            denied(connections[0],tenants[0],event)
            expect(load_journal(connections[1],tenants[1],session).events==(event,),'OTHER_TENANT_DISRUPTED')
            report['checks'].append({'id':'BINDING-REVOCATION-NEXT-TRANSACTION','status':'PASS'})
        finally:
            for conn in connections:
                conn.close()
            for tenant in tenants:
                for table in ('claim_case_incident_intake','claim_cases','completion_receipts','manifest_roots','events','sessions','location_brands','dealer_locations','dealer_groups','memberships','users','tenant_login_bindings','organizations'):
                    admin.execute(sql.SQL('DELETE FROM faos.{} WHERE tenant_id=%s').format(sql.Identifier(table)),(tenant,))
            for role in roles:
                admin.execute(sql.SQL('DROP ROLE {}').format(sql.Identifier(role)))
    report['diagnostics_successful'] = len(report['checks'])==14 and all(row['status']=='PASS' for row in report['checks'])

def load_counted_database_report():
    candidates = sorted(Path('output/database-runs').glob('*/database-evidence/counted-tests.json'))
    if len(candidates) != 1:
        raise RuntimeError('EXACTLY_ONE_COUNTED_DATABASE_TEST_REPORT_REQUIRED')
    return candidates[0], json.loads(candidates[0].read_text(encoding='utf-8'))


if __name__ == '__main__':
    report = {'classification':'post-cutover-executable-db-gate-verification',
              'commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
              'contract':'C2C-DB-AC-001 v1.0 proposed','contract_status':'PROPOSED_PENDING_OWNER_ADOPTION',
              'gate_passes_awarded':0,'checks':[],'complete_gate_results':[],
              'overall_acceptance':'NOT ACCEPTED','diagnostics_successful':False}
    try:
        run(report)
    except Exception as error:
        report['diagnostics_successful'] = False
        report['execution_error_type'] = type(error).__name__
    try:
        counted_path, counted_tests = load_counted_database_report()
        report['counted_test_report_path'] = str(counted_path)
        import hashlib
        report['counted_test_report_sha256'] = hashlib.sha256(counted_path.read_bytes()).hexdigest()
        run_all_gate_verifiers(report, counted_tests, environment_is_synthetic=(report.get('environment', {}).get('classification') == 'synthetic_isolated'))
    except Exception as error:
        report['gate_verification_successful'] = False
        report['gate_passes_awarded'] = 0
        report['complete_gate_results'] = [
            {'id':f'DB-{number:02d}','status':'BLOCKED','reason':type(error).__name__}
            for number in range(1,15)
        ]
        report['overall_acceptance'] = 'NOT ACCEPTED'
        report['acceptance_blockers'] = ['COUNTED_TEST_OR_GATE_EVIDENCE_UNAVAILABLE']
    path = Path('output/acceptance-diagnostics/report.json')
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,sort_keys=True))
    raise SystemExit(0 if report.get('diagnostics_successful') and report.get('gate_verification_successful') else 1)
