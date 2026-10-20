"""Health-only FastAPI foundation; no authenticated business API is exposed."""
from dataclasses import dataclass, field
import os
import psycopg
from fastapi import FastAPI
from fastapi.responses import JSONResponse

@dataclass(frozen=True)
class Settings:
    database_url: str | None = field(default=None,repr=False)

    @classmethod
    def from_environment(cls):
        return cls(database_url=os.environ.get('APP_DATABASE_URL') or None)

READINESS_SQL = """
SELECT NOT r.rolsuper AND NOT r.rolbypassrls
       AND pg_has_role(current_user,'faos_app','MEMBER'),
       to_regclass('faos.tenant_login_bindings') IS NOT NULL,
       EXISTS(SELECT 1 FROM pg_proc p WHERE p.oid=to_regprocedure('faos.tenant_id()')
              AND p.prosecdef AND pg_get_userbyid(p.proowner)='faos_writer'),
       (SELECT count(*)=10 AND bool_and(c.relrowsecurity AND c.relforcerowsecurity)
        FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='faos' AND c.relkind='r'
        AND c.relname IN ('organizations','users','memberships','dealer_groups',
                         'dealer_locations','location_brands','sessions','events',
                         'manifest_roots','completion_receipts'))
FROM pg_roles r WHERE r.rolname=current_user
"""

def probe_database(url):
    with psycopg.connect(url,autocommit=True,connect_timeout=3,
                         options='-c statement_timeout=2000 -c default_transaction_read_only=on') as conn:
        return conn.execute(READINESS_SQL).fetchone()==(True,True,True,True)


def create_app(settings=None):
    settings = settings if settings is not None else Settings.from_environment()
    api = FastAPI(title='Claim2Car Connect foundation',docs_url=None,redoc_url=None,openapi_url=None)

    @api.get('/health/live')
    def live():
        return JSONResponse({'status':'alive'},headers={'Cache-Control':'no-store'})

    @api.get('/health/ready')
    def ready():
        try:
            healthy = bool(settings.database_url) and probe_database(settings.database_url) is True
        except Exception:
            healthy = False
        return JSONResponse({'status':'ready' if healthy else 'not_ready','scope':'infrastructure-only'},
                            status_code=200 if healthy else 503,headers={'Cache-Control':'no-store'})

    return api
