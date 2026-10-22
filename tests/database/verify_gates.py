"""Synthetic database preflight, not certification of the 14 acceptance gates."""
import os
import uuid
import psycopg
from psycopg.rows import dict_row

DATABASE_URL = os.getenv(
    'APP_DATABASE_URL',
    'postgresql://faos_app:synthetic-app-only@127.0.0.1:55432/claim2car_test',
)
TENANT_TABLES = [
    'organizations', 'users', 'memberships', 'dealer_groups',
    'dealer_locations', 'location_brands', 'sessions', 'events',
    'manifest_roots', 'completion_receipts',
]


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def run_gate_verification():
    print('Starting Claim2Car Connect synthetic database preflight...')
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT current_user,rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user')
            role = cur.fetchone()
            require(role is not None and role['current_user'] == 'faos_app'
                    and role['rolsuper'] is False and role['rolbypassrls'] is False,
                    'RESTRICTED_APP_ROLE_REQUIRED')
            print('[PASS] restricted application role verified')
            cur.execute("SELECT 1 FROM information_schema.schemata WHERE schema_name='faos'")
            require(cur.fetchone() is not None, 'faos schema missing')
            cur.execute("SELECT c.relname,c.relrowsecurity,c.relforcerowsecurity FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='faos' AND c.relkind='r'")
            tables = {row['relname']: row for row in cur.fetchall()}
            for table in TENANT_TABLES:
                require(table in tables, 'missing tenant table: ' + table)
                require(tables[table]['relrowsecurity'], 'RLS not enabled: ' + table)
                require(tables[table]['relforcerowsecurity'], 'FORCE RLS not enabled: ' + table)
            print('[PASS] RLS and FORCE RLS verified for all expected tenant tables')
            for table in ('manifest_roots', 'completion_receipts'):
                for privilege in ('SELECT', 'INSERT', 'UPDATE', 'DELETE', 'TRUNCATE'):
                    cur.execute('SELECT has_table_privilege(current_user,%s,%s) AS allowed',
                                ('faos.' + table, privilege))
                    expected = privilege == 'SELECT'
                    require(cur.fetchone()['allowed'] is expected,
                            'UNEXPECTED_APP_TABLE_PRIVILEGE:' + table + ':' + privilege)
            print('[PASS] protected completion tables allow application SELECT but deny direct writes and TRUNCATE')
            cur.execute("SELECT 1 FROM information_schema.routines WHERE routine_schema='faos' AND routine_name='append_event'")
            require(cur.fetchone() is not None, 'faos.append_event missing')

        tenant_a, tenant_b = str(uuid.uuid4()), str(uuid.uuid4())
        with conn.cursor() as cur:
            cur.execute("SELECT set_config('faos.tenant_id',%s,true)", (tenant_a,))
            cur.execute('SELECT faos.tenant_id() AS tenant_id')
            require(str(cur.fetchone()['tenant_id']) == tenant_a, 'tenant context mismatch')
            cur.execute('INSERT INTO faos.organizations(tenant_id,name) VALUES (%s,%s)', (tenant_a, 'synthetic preflight fixture'))
        conn.commit()
        with conn.cursor() as cur:
            cur.execute('SELECT faos.tenant_id() AS tenant_id')
            require(cur.fetchone()['tenant_id'] is None, 'TENANT_CONTEXT_SURVIVED_COMMIT')
            cur.execute("SELECT set_config('faos.tenant_id',%s,true)", (tenant_b,))
            cur.execute('SELECT count(*) AS visible FROM faos.organizations WHERE tenant_id=%s', (tenant_a,))
            require(cur.fetchone()['visible'] == 0, 'cross-tenant row was visible')
        conn.commit()
        print('[PASS] tenant context reset and cross-tenant read isolation verified')

        with conn.cursor() as cur:
            cur.execute("SELECT set_config('faos.tenant_id',%s,true)", (tenant_b,))
            try:
                cur.execute(
                    'SELECT faos.append_event(%s::uuid,%s::text,%s::text,%s::bigint,%s::text,%s::text,%s::text,%s::text,%s::text,%s::text)',
                    (tenant_a, 'gate-session', 'gate-event', 1, 'SESSION_CREATED',
                     'synthetic-verifier', '2026-01-01T00:00:00Z', 'synthetic preflight',
                     '{"verification":true}', '0.1'),
                )
            except psycopg.errors.RaiseException as error:
                require(error.sqlstate == 'P0001' and error.diag.message_primary == 'TENANT_CONTEXT_MISMATCH',
                        'UNEXPECTED_APPEND_REJECTION')
            else:
                raise AssertionError('append_event accepted mismatched tenant context')
        conn.rollback()
        with conn.cursor() as cur:
            cur.execute('SELECT faos.tenant_id() AS tenant_id')
            require(cur.fetchone()['tenant_id'] is None, 'TENANT_CONTEXT_SURVIVED_ROLLBACK')
            cur.execute("SELECT set_config('faos.tenant_id',%s,true)", (tenant_a,))
            cur.execute('DELETE FROM faos.organizations WHERE tenant_id=%s', (tenant_a,))
            require(cur.rowcount == 1, 'FIXTURE_CLEANUP_FAILED')
        conn.commit()
        print('[PASS] exact tenant-context mismatch rejection and rollback reset verified')
    print('Synthetic database preflight completed; formal acceptance is not certified.')


if __name__ == '__main__':
    run_gate_verification()
