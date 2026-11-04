"""Foundation FastAPI with health probes and minimal tenant-scoped session start.
Sealing and evidence routes remain absent.
"""
from dataclasses import dataclass, field
import os
import psycopg
from fastapi.responses import FileResponse
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.sessions import router as sessions_router

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
    api.include_router(sessions_router)

    @api.get('/packets/print')
    def printable_packet():
        return FileResponse("app/printable_packet.html")

    @api.get('/sessions/{session_id}/exhibit')
    def exhibit_page(session_id: str):
        return FileResponse("app/exhibit.html")

    @api.get('/sessions/{session_id}/reconstruction')
    def reconstruction_page(session_id: str):
        return FileResponse("app/reconstruction.html")

    @api.get('/sessions/{session_id}/dossier')
    def dossier_page(session_id: str):
        return FileResponse("app/dossier.html")

    @api.get('/sessions/{session_id}/capture-progress')
    def capture_progress_page(session_id: str):
        return FileResponse("app/capture_progress.html")

    @api.get('/sessions/{session_id}/packet')
    def packet_page(session_id: str):
        return FileResponse("app/packet.html")

    @api.get('/sessions/{session_id}/timeline')
    def timeline_page(session_id: str):
        return FileResponse("app/timeline.html")

    @api.get('/command')
    def command():
        return FileResponse("app/command.html")

    @api.get('/packets')
    def packets():
        return FileResponse("app/packets.html")

    @api.get('/sessions/{session_id}/consumer-packet')
    def consumer_packet_page(session_id: str):
        return FileResponse("app/consumer_packet.html")

    @api.get('/sessions/{session_id}/shop-packet')
    def shop_packet_page(session_id: str):
        return FileResponse("app/shop_packet.html")

    @api.get('/sessions/{session_id}/carrier-packet')
    def carrier_packet_page(session_id: str):
        return FileResponse("app/carrier_packet.html")

    @api.get('/sessions/{session_id}/dealer-packet')
    def dealer_packet_page(session_id: str):
        return FileResponse("app/dealer_packet.html")

    @api.get('/settlements/history')
    def settlement_history():
        return FileResponse("app/settlement_history.html")

    @api.get('/settlements/{session_id}')
    def settlement_detail(session_id: str):
        return FileResponse("app/settlement_detail.html")

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
