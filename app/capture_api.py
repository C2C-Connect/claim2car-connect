"""Explicit controlled-test capture API; existing health-only factory is unchanged.

Run app.capture_api:create_capture_app with --factory. C2C_CAPTURE_CONFIG_FILE
must name a private server-owned JSON file with health_database_url, dsn_by_role,
and credentials. Each credential requires actor_id, tenant_id, database_role,
token_sha256, expires_at and enabled. Never put raw tokens in that file or Git.
This exposes session metadata only: no image, consent or diagnostic endpoint.
HTTP/PostgreSQL end-to-end verification remains separate from mocked route tests.
"""
from dataclasses import asdict, dataclass, field
import json
import os
from pathlib import Path
from uuid import UUID
from fastapi import Depends, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from psycopg.conninfo import conninfo_to_dict
from app.identity import ActorBinding, AuthenticationError, Credential, CredentialResolver
from app.main import Settings, create_app
from database.capture_sessions import CaptureAuthorizationError, CaptureSessionConflict, CaptureSessionNotFound, CaptureSessionStore, CaptureStorageUnavailable

@dataclass(frozen=True)
class CaptureRuntime:
    resolver: CredentialResolver = field(repr=False)
    store: CaptureSessionStore = field(repr=False)
    health_settings: Settings = field(repr=False)

class SessionRequest(BaseModel):
    session_id: UUID
    class Config:
        extra='forbid'

def _unique(pairs):
    value={}
    for key,item in pairs:
        if key in value:
            raise ValueError('DUPLICATE_CONFIGURATION_KEY')
        value[key]=item
    return value

def _target(dsn):
    info=conninfo_to_dict(dsn)
    if any(not info.get(key) for key in ('host','port','dbname','user')) or ',' in info['host']:
        raise ValueError('EXPLICIT_SINGLE_DATABASE_TARGET_REQUIRED')
    return tuple(info.get(key,'') for key in ('host','hostaddr','port','dbname'))

def load_runtime(path):
    try:
        with Path(path).open('rb') as source:
            raw=source.read(65537)
        if len(raw)>65536:
            raise ValueError('CONFIGURATION_TOO_LARGE')
        value=json.loads(raw.decode('utf-8'),object_pairs_hook=_unique)
        if type(value) is not dict or set(value)!={'health_database_url','dsn_by_role','credentials'}:
            raise ValueError('INVALID_CONFIGURATION_FIELDS')
        health=value['health_database_url']
        dsns=value['dsn_by_role']
        records=value['credentials']
        if not isinstance(health,str) or type(dsns) is not dict or type(records) is not list or len(records)>128:
            raise ValueError('INVALID_CONFIGURATION_TYPES')
        target=_target(health)
        if any(_target(dsn)!=target or conninfo_to_dict(dsn).get('user')!=role for role,dsn in dsns.items()):
            raise ValueError('DATABASE_TARGET_OR_LOGIN_MISMATCH')
        credentials=[]
        for record in records:
            if type(record) is not dict or set(record)!={'actor_id','tenant_id','database_role','token_sha256','expires_at','enabled'}:
                raise ValueError('INVALID_CREDENTIAL_FIELDS')
            binding=ActorBinding(record['actor_id'],UUID(record['tenant_id']),record['database_role'])
            if binding.database_role not in dsns:
                raise ValueError('MISSING_SERVER_LOGIN')
            credentials.append(Credential(record['token_sha256'],binding,record['expires_at'],record['enabled']))
        resolver=CredentialResolver(credentials)
        return CaptureRuntime(resolver,CaptureSessionStore(resolver,dsns),Settings(health))
    except Exception:
        raise ValueError('INVALID_CAPTURE_RUNTIME_CONFIGURATION') from None

def _fail(status,detail):
    headers={'Cache-Control':'no-store'}
    if status==401:
        headers['WWW-Authenticate']='Bearer'
    raise HTTPException(status_code=status,detail=detail,headers=headers)

def create_capture_app(runtime=None):
    if runtime is None:
        path=os.environ.get('C2C_CAPTURE_CONFIG_FILE')
        if not path:
            raise ValueError('CAPTURE_RUNTIME_CONFIGURATION_REQUIRED')
        runtime=load_runtime(path)
    api=create_app(runtime.health_settings)

    def authorize(authorization: str | None = Header(default=None)):
        try:
            runtime.resolver.resolve(authorization)
        except AuthenticationError:
            _fail(401,'UNAUTHORIZED')
        return authorization

    def invoke(action,authorization,session_id,creating=False):
        try:
            result=action(authorization,str(session_id))
        except AuthenticationError:
            _fail(401,'UNAUTHORIZED')
        except CaptureAuthorizationError:
            _fail(403,'CAPTURE_AUTHORITY_DENIED')
        except CaptureSessionNotFound:
            _fail(404,'CAPTURE_SESSION_NOT_FOUND')
        except CaptureSessionConflict:
            _fail(409,'CAPTURE_SESSION_CONFLICT')
        except CaptureStorageUnavailable:
            _fail(503,'CAPTURE_STORAGE_UNAVAILABLE')
        except Exception:
            _fail(500,'CAPTURE_OPERATION_FAILED')
        return JSONResponse({**asdict(result),'scope':'controlled-test'},status_code=201 if creating and result.created else 200,headers={'Cache-Control':'no-store'})

    @api.post('/v1/capture-sessions')
    def create_session(body: SessionRequest,authorization: str = Depends(authorize)):
        return invoke(runtime.store.create,authorization,body.session_id,creating=True)

    @api.get('/v1/capture-sessions/{session_id}')
    def get_session(session_id: UUID,authorization: str = Depends(authorize)):
        return invoke(runtime.store.get,authorization,session_id)

    return api
