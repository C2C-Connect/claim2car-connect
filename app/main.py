"""Health-only FastAPI foundation; no authenticated business API is exposed."""
from dataclasses import dataclass, field
from pathlib import Path
import os
import re
import stat
from uuid import uuid4
import psycopg
from fastapi import Depends, FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

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
       (SELECT count(*)=21 AND bool_and(c.relrowsecurity AND c.relforcerowsecurity)
        FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='faos' AND c.relkind='r'
        AND c.relname IN ('organizations','users','memberships','dealer_groups',
                         'dealer_locations','location_brands','sessions','events',
                         'manifest_roots','completion_receipts','financial_ledger_entries',
                         'financial_ledger_postings','claim_cases','claim_case_incident_intake',
                         'collision_lifecycle_records','vehicles','collision_vehicle_links',
                         'collision_participants','collision_claim_links','collision_events',
                         'collision_outbox')),
       (SELECT count(*)=3 AND bool_and(p.prosecdef AND pg_get_userbyid(p.proowner)='faos_writer')
        FROM pg_proc p
        WHERE p.oid IN (
          to_regprocedure('faos.create_collision_lifecycle_record(uuid,uuid,uuid,text,timestamptz)'),
          to_regprocedure('faos.append_collision_event(uuid,uuid,uuid,text,text,text,timestamptz,jsonb,uuid,uuid)'),
          to_regprocedure('faos.link_collision_claim(uuid,uuid,uuid,uuid,text,timestamptz)')
        ))
FROM pg_roles r WHERE r.rolname=current_user
"""

def probe_database(url):
    with psycopg.connect(url,autocommit=True,connect_timeout=3,
                         options='-c statement_timeout=2000 -c default_transaction_read_only=on') as conn:
        return conn.execute(READINESS_SQL).fetchone()==(True,True,True,True,True)


def _evidence_root_is_mountpoint(root):
    """Return true only when root is an exact Linux mount point.

    /proc/self/mountinfo handles bind mounts as well as separate filesystems;
    os.path.ismount alone can miss same-device bind mounts.
    """
    target = os.path.realpath(root)
    try:
        with open('/proc/self/mountinfo', encoding='utf-8') as source:
            for line in source:
                fields = line.split()
                if len(fields) < 6:
                    continue
                mountpoint = re.sub(
                    r'\\([0-7]{3})',
                    lambda match: chr(int(match.group(1), 8)),
                    fields[4],
                )
                if mountpoint == target:
                    return True
    except OSError:
        return False
    return False


def probe_evidence_storage(root, *, require_mount=True):
    """Verify the evidence root is a real, writable directory.

    In integrated staging, require_mount must remain true so an accidentally
    missing volume cannot silently fall back to ephemeral container storage.
    The probe writes, fsyncs, removes, and directory-fsyncs a tiny disposable
    sentinel; it never reads or modifies claim evidence.
    """
    if not isinstance(root, str) or not root or not os.path.isabs(root):
        return False
    directory_fd = None
    probe_fd = None
    probe_name = None
    try:
        directory_fd = os.open(
            root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        )
        if not stat.S_ISDIR(os.fstat(directory_fd).st_mode):
            return False
        if require_mount and not _evidence_root_is_mountpoint(root):
            return False
        probe_name = '.claim2car-readiness-' + uuid4().hex
        probe_fd = os.open(
            probe_name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
            dir_fd=directory_fd,
        )
        payload = b'claim2car-persistent-storage-readiness\n'
        offset = 0
        while offset < len(payload):
            written = os.write(probe_fd, payload[offset:])
            if written <= 0:
                return False
            offset += written
        os.fsync(probe_fd)
        os.close(probe_fd)
        probe_fd = None
        os.unlink(probe_name, dir_fd=directory_fd)
        probe_name = None
        os.fsync(directory_fd)
        return True
    except OSError:
        return False
    finally:
        if probe_fd is not None:
            try:
                os.close(probe_fd)
            except OSError:
                pass
        if probe_name is not None and directory_fd is not None:
            try:
                os.unlink(probe_name, dir_fd=directory_fd)
                os.fsync(directory_fd)
            except OSError:
                pass
        if directory_fd is not None:
            os.close(directory_fd)


def _mount_internal_router(api, source_router, public_prefix, internal_prefix):
    """Expose an existing analytical router under its internal-only URL space."""
    from fastapi.routing import APIRoute
    from backend.app.security import require_internal_service

    for route in source_router.routes:
        if not isinstance(route, APIRoute):
            continue
        if not route.path.startswith(public_prefix):
            continue
        path = internal_prefix + route.path[len(public_prefix):]
        api.add_api_route(
            path,
            route.endpoint,
            methods=route.methods,
            response_model=route.response_model,
            status_code=route.status_code,
            response_class=route.response_class,
            dependencies=[Depends(require_internal_service)],
            tags=route.tags,
            name=f"internal_{route.name}",
            include_in_schema=False,
        )


def create_app(settings=None, runtime_mode=None):
    settings = settings if settings is not None else Settings.from_environment()
    api = FastAPI(title='Claim2Car Connect foundation',docs_url=None,redoc_url=None,openapi_url=None)

    # Staging stays fail-closed by default. The integrated surface is explicit
    # opt-in and composes the already tenant-authenticated intake app with
    # service-authenticated analytical routes.
    mode = (runtime_mode or os.environ.get('C2C_RUNTIME_MODE', 'restricted_staging')).strip().lower()
    if mode not in {'restricted_staging', 'integrated'}:
        raise ValueError('INVALID_C2C_RUNTIME_MODE')

    if mode == 'integrated':
        service_token = os.environ.get('C2C_INTERNAL_SERVICE_TOKEN', '')
        if re.fullmatch(r'[A-Za-z0-9_-]{43,128}', service_token) is None:
            raise ValueError('INTERNAL_SERVICE_AUTH_CONFIGURATION_REQUIRED')

        from app.intake_api import create_intake_app
        from backend.app.api.analysis import router as analysis_router
        from backend.app.api.triage import router as triage_router
        from backend.app.api.dispatch import router as dispatch_router

        intake_app = create_intake_app(enable_evidence=True)
        settings = getattr(intake_app.state, 'health_settings', settings)
        api.mount('/api', intake_app)
        _mount_internal_router(api, analysis_router, '/api/v1/analysis', '/internal/v1/analysis')
        _mount_internal_router(api, triage_router, '/api/v1/triage', '/internal/v1/triage')
        _mount_internal_router(api, dispatch_router, '/api/v1/dispatch', '/internal/v1/dispatch')

        # The operator/owner/reviewer shell is served only by the integrated
        # runtime. Restricted staging remains health-only and exposes no UI.
        web_root = Path(__file__).with_name('web')
        api.mount(
            '/assets',
            StaticFiles(directory=web_root / 'assets'),
            name='claim2car-web-assets',
        )

        @api.get('/', include_in_schema=False)
        def application_shell():
            return FileResponse(
                web_root / 'index.html',
                headers={'Cache-Control': 'no-store'},
            )

    @api.get('/health/build')
    def build():
        revision = 'unknown'
        try:
            revision = Path(__file__).with_name('_build_revision.txt').read_text(encoding='ascii').strip() or 'unknown'
        except OSError:
            pass
        return JSONResponse({'revision':revision,'runtime_mode':mode},headers={'Cache-Control':'no-store'})

    @api.get('/health/live')
    def live():
        return JSONResponse({'status':'alive'},headers={'Cache-Control':'no-store'})

    @api.get('/health/ready')
    def ready():
        try:
            database_healthy = bool(settings.database_url) and probe_database(settings.database_url) is True
            storage_healthy = True
            if mode == 'integrated':
                mount_setting = os.environ.get(
                    'C2C_REQUIRE_PERSISTENT_EVIDENCE_MOUNT', 'true'
                ).strip().lower()
                if mount_setting not in {'true', 'false'}:
                    storage_healthy = False
                else:
                    storage_healthy = probe_evidence_storage(
                        os.environ.get('C2C_ARTIFACT_STORAGE_ROOT'),
                        require_mount=mount_setting == 'true',
                    )
            healthy = database_healthy and storage_healthy
        except Exception:
            healthy = False
        return JSONResponse({'status':'ready' if healthy else 'not_ready','scope':'infrastructure-only'},
                            status_code=200 if healthy else 503,headers={'Cache-Control':'no-store'})

    if mode == 'integrated':
        frontend_root = Path(__file__).resolve().parents[1] / 'frontend' / 'app'
        if not frontend_root.is_dir():
            raise ValueError('INTEGRATED_FRONTEND_ASSETS_REQUIRED')
        source_root = Path(__file__).resolve().parents[1] / 'frontend' / 'src'
        if not source_root.is_dir():
            raise ValueError('INTEGRATED_FRONTEND_SOURCE_REQUIRED')
        api.mount('/src', StaticFiles(directory=str(source_root), html=False), name='claim2car-frontend-source')
        api.mount('/prototype', StaticFiles(directory=str(frontend_root), html=True), name='claim2car-workbench-prototype')

    return api
