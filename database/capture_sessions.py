"""Controlled-test capture sessions; service methods only, no HTTP routes.

Server-owned credentials/DSNs are required. This creates synthetic draft sessions,
not consent records, uploaded evidence, diagnoses, or production-ready intake.
"""
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID
import psycopg
from psycopg.conninfo import conninfo_to_dict
from app.identity import CredentialResolver
from database.journal import tenant_transaction

class CaptureAuthorizationError(PermissionError):
    pass
class CaptureStorageUnavailable(RuntimeError):
    pass
class CaptureSessionNotFound(LookupError):
    pass
class CaptureSessionConflict(ValueError):
    pass

@dataclass(frozen=True)
class CaptureSession:
    session_id: str
    tenant_id: str
    created_by: str
    created_at: str
    created: bool

PROFILE_SQL = """
SELECT session_user::text,current_user::text,r.rolsuper,r.rolbypassrls,
 r.rolcreaterole,r.rolcreatedb,r.rolreplication,
 pg_has_role(current_user,'faos_app','MEMBER'),
 EXISTS(SELECT 1 FROM pg_roles p WHERE p.rolname IN
 ('postgres','faos_writer','faos_migrator','faos_fixture','rds_superuser')
 AND pg_has_role(current_user,p.oid,'MEMBER')),
 has_schema_privilege(current_user,'faos','CREATE') OR has_schema_privilege(current_user,'public','CREATE'),
 EXISTS(SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
 WHERE n.nspname='faos' AND pg_has_role(current_user,c.relowner,'MEMBER'))
FROM pg_roles r WHERE r.rolname=current_user
"""

class CaptureSessionStore:
    def __init__(self,resolver,dsn_by_role):
        if not isinstance(resolver,CredentialResolver):
            raise ValueError('INVALID_CAPTURE_CONFIGURATION')
        self._resolver=resolver
        self._dsns=dict(dsn_by_role)
        if any(not isinstance(k,str) or not isinstance(v,str) or not v for k,v in self._dsns.items()):
            raise ValueError('INVALID_CAPTURE_CONFIGURATION')

    @contextmanager
    def _authorized(self,authorization):
        actor=self._resolver.resolve(authorization)
        dsn=self._dsns.get(actor.database_role)
        if dsn is None:
            raise CaptureStorageUnavailable('CAPTURE_STORAGE_UNAVAILABLE')
        try:
            configured_user=conninfo_to_dict(dsn).get('user')
        except (psycopg.Error,TypeError,ValueError):
            raise CaptureStorageUnavailable('CAPTURE_STORAGE_UNAVAILABLE') from None
        if configured_user!=actor.database_role:
            raise CaptureAuthorizationError('CAPTURE_AUTHORITY_DENIED')
        try:
            with psycopg.connect(dsn,autocommit=True,connect_timeout=5,options='-c statement_timeout=5000 -c lock_timeout=3000') as conn:
                expected=(actor.database_role,actor.database_role,False,False,False,False,False,True,False,False,False)
                if conn.execute(PROFILE_SQL).fetchone()!=expected:
                    raise CaptureAuthorizationError('CAPTURE_AUTHORITY_DENIED')
                with tenant_transaction(conn,actor.tenant_id):
                    if conn.execute('SELECT faos.tenant_id()').fetchone()[0]!=actor.tenant_id:
                        raise CaptureAuthorizationError('CAPTURE_AUTHORITY_DENIED')
                    yield conn,actor
        except psycopg.Error:
            raise CaptureStorageUnavailable('CAPTURE_STORAGE_UNAVAILABLE') from None

    @staticmethod
    def _identifier(value):
        try:
            return str(UUID(str(value)))
        except (ValueError,TypeError,AttributeError):
            raise ValueError('INVALID_CAPTURE_SESSION_ID') from None

    @staticmethod
    def _read(conn,actor,session_id,created=False):
        row=conn.execute('SELECT e.actor,e.occurred_at,e.event_id,e.kind,e.payload_json,e.schema_version '
                         'FROM faos.sessions s LEFT JOIN faos.events e ON e.tenant_id=s.tenant_id '
                         'AND e.session_id=s.session_id AND e.sequence=1 '
                         'WHERE s.tenant_id=%s AND s.session_id=%s',(actor.tenant_id,session_id)).fetchone()
        if row is None:
            raise CaptureSessionNotFound('CAPTURE_SESSION_NOT_FOUND')
        if row[2:]!=('capture-created','SESSION_CREATED','{"synthetic":true}','0.1'):
            raise CaptureSessionConflict('UNMANAGED_CAPTURE_SESSION')
        return CaptureSession(session_id,str(actor.tenant_id),row[0],row[1],created)

    def create(self,authorization,session_id):
        session_id=self._identifier(session_id)
        with self._authorized(authorization) as (conn,actor):
            inserted=conn.execute('INSERT INTO faos.sessions(tenant_id,session_id) VALUES (%s,%s) '
                                  'ON CONFLICT DO NOTHING RETURNING session_id',(actor.tenant_id,session_id)).fetchone() is not None
            if inserted:
                timestamp=datetime.now(timezone.utc).isoformat()
                result=conn.execute('SELECT faos.append_event(%s::uuid,%s::text,%s::text,%s::bigint,%s::text,%s::text,%s::text,%s::text,%s::text,%s::text)',
                                    (actor.tenant_id,session_id,'capture-created',1,'SESSION_CREATED',actor.actor_id,timestamp,'controlled test capture session','{"synthetic":true}','0.1')).fetchone()[0]
                if result!='ACCEPTED':
                    raise RuntimeError('CAPTURE_CREATION_FAILED')
            return self._read(conn,actor,session_id,created=inserted)

    def get(self,authorization,session_id):
        session_id=self._identifier(session_id)
        with self._authorized(authorization) as (conn,actor):
            return self._read(conn,actor,session_id)
