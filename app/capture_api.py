"""Controlled-test capture API. No images, consent or diagnosis endpoints.

Run app.capture_api:create_capture_app --factory using a private server-owned
C2C_CAPTURE_CONFIG_FILE. Service credentials are not end-user sign-in.
"""
from dataclasses import asdict, dataclass, field
import json
import os
from pathlib import Path
from typing import NoReturn
from uuid import UUID

from fastapi import Depends, Header, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from psycopg import ProgrammingError
from psycopg.conninfo import conninfo_to_dict

from app.identity import ActorBinding, AuthenticationError, Credential, CredentialResolver
from app.main import Settings, create_app
from database.capture_sessions import (
    CaptureAuthorizationError, CaptureSessionConflict, CaptureSessionNotFound,
    CaptureSessionStore, CaptureStorageUnavailable,
)

NO_STORE_HEADERS = {'Cache-Control': 'no-store'}
CONFIGURATION_SIZE_LIMIT = 65536
MAX_CREDENTIALS = 128

@dataclass(frozen=True)
class CaptureRuntime:
    resolver: CredentialResolver = field(repr=False)
    store: CaptureSessionStore = field(repr=False)
    health_settings: Settings = field(repr=False)

class SessionRequest(BaseModel):
    session_id: UUID
    class Config:
        extra = 'forbid'

def _unique(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError('DUPLICATE_CONFIGURATION_KEY')
        value[key] = item
    return value

def _reject_constant(value):
    raise ValueError('INVALID_JSON_CONSTANT')

def _target(dsn):
    if not isinstance(dsn, str) or not dsn.strip():
        raise ValueError('INVALID_DATABASE_URL')
    try:
        info = conninfo_to_dict(dsn)
    except (ProgrammingError, TypeError, ValueError) as exc:
        raise ValueError('INVALID_DATABASE_URL') from exc
    if any(not info.get(key) or not info[key].strip() for key in ('host', 'port', 'dbname', 'user')):
        raise ValueError('EXPLICIT_SINGLE_DATABASE_TARGET_REQUIRED')
    if any(',' in info.get(key, '') for key in ('host', 'hostaddr', 'port')):
        raise ValueError('EXPLICIT_SINGLE_DATABASE_TARGET_REQUIRED')
    return tuple(info.get(key, '') for key in ('host', 'hostaddr', 'port', 'dbname'))

def load_runtime(path):
    try:
        with Path(path).open('rb') as source:
            raw = source.read(CONFIGURATION_SIZE_LIMIT + 1)
        if len(raw) > CONFIGURATION_SIZE_LIMIT:
            raise ValueError('CONFIGURATION_TOO_LARGE')
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=_unique, parse_constant=_reject_constant)
        if type(value) is not dict or set(value) != {'health_database_url', 'dsn_by_role', 'credentials'}:
            raise ValueError('INVALID_CONFIGURATION_FIELDS')
        health = value['health_database_url']
        dsns = value['dsn_by_role']
        records = value['credentials']
        if not isinstance(health, str) or type(dsns) is not dict or type(records) is not list or len(records) > MAX_CREDENTIALS:
            raise ValueError('INVALID_CONFIGURATION_TYPES')
        if any(not isinstance(role, str) or not role.strip() for role in dsns):
            raise ValueError('INVALID_DATABASE_ROLE')
        target = _target(health)
        for role, dsn in dsns.items():
            if _target(dsn) != target or conninfo_to_dict(dsn).get('user') != role:
                raise ValueError('DATABASE_TARGET_OR_LOGIN_MISMATCH')
        credentials = []
        for record in records:
            if type(record) is not dict or set(record) != {'actor_id', 'tenant_id', 'database_role', 'token_sha256', 'expires_at', 'enabled'}:
                raise ValueError('INVALID_CREDENTIAL_FIELDS')
            if not isinstance(record['tenant_id'], str) or not isinstance(record['database_role'], str) or not isinstance(record['token_sha256'], str) or type(record['enabled']) is not bool:
                raise ValueError('INVALID_CREDENTIAL_TYPES')
            binding = ActorBinding(record['actor_id'], UUID(record['tenant_id']), record['database_role'])
            if binding.database_role not in dsns:
                raise ValueError('MISSING_SERVER_LOGIN')
            credentials.append(Credential(record['token_sha256'], binding, record['expires_at'], record['enabled']))
        resolver = CredentialResolver(credentials)
        return CaptureRuntime(resolver, CaptureSessionStore(resolver, dsns), Settings(health))
    except Exception:
        # Preserve the existing opaque configuration boundary.
        raise ValueError('INVALID_CAPTURE_RUNTIME_CONFIGURATION') from None

def _fail(status, detail) -> NoReturn:
    headers = dict(NO_STORE_HEADERS)
    if status == 401:
        headers['WWW-Authenticate'] = 'Bearer'
    raise HTTPException(status_code=status, detail=detail, headers=headers)

def create_capture_app(runtime=None):
    if runtime is None:
        path = os.environ.get('C2C_CAPTURE_CONFIG_FILE')
        if not path:
            raise ValueError('CAPTURE_RUNTIME_CONFIGURATION_REQUIRED')
        runtime = load_runtime(path)
    api = create_app(runtime.health_settings)

    @api.exception_handler(RequestValidationError)
    async def invalid_capture_request(request, error):
        # Never echo rejected tokens, VINs or client identity fields.
        return JSONResponse({'detail': 'INVALID_CAPTURE_REQUEST'}, status_code=422, headers=dict(NO_STORE_HEADERS))

    def authorize(authorization: str | None = Header(default=None)):
        if authorization is None:
            _fail(401, 'UNAUTHORIZED')
        try:
            runtime.resolver.resolve(authorization)
        except AuthenticationError:
            _fail(401, 'UNAUTHORIZED')
        return authorization

    def invoke(action, authorization, session_id, creating=False):
        try:
            result = action(authorization, str(session_id))
            payload = jsonable_encoder({**asdict(result), 'scope': 'controlled-test'})
            return JSONResponse(payload, status_code=201 if creating and result.created else 200, headers=dict(NO_STORE_HEADERS))
        except AuthenticationError:
            _fail(401, 'UNAUTHORIZED')
        except CaptureAuthorizationError:
            _fail(403, 'CAPTURE_AUTHORITY_DENIED')
        except CaptureSessionNotFound:
            _fail(404, 'CAPTURE_SESSION_NOT_FOUND')
        except CaptureSessionConflict:
            _fail(409, 'CAPTURE_SESSION_CONFLICT')
        except CaptureStorageUnavailable:
            _fail(503, 'CAPTURE_STORAGE_UNAVAILABLE')
        except Exception:
            _fail(500, 'CAPTURE_OPERATION_FAILED')

    @api.post('/v1/capture-sessions')
    def create_session(body: SessionRequest, authorization: str = Depends(authorize)):
        return invoke(runtime.store.create, authorization, body.session_id, creating=True)

    @api.get('/v1/capture-sessions/{session_id}')
    def get_session(session_id: UUID, authorization: str = Depends(authorize)):
        return invoke(runtime.store.get, authorization, session_id)

    return api
