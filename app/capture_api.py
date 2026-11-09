"""Tenant-bound capture APIs over server-owned credentials and PostgreSQL RLS.

Session/draft routes support controlled tests. Consent, HMAC VIN-reference and
original-byte registration routes are added only by the integrated runtime,
which requires separately provisioned persistent storage and secrets. Service
credentials are not end-user sign-in; actor roles come from private config.
"""
from dataclasses import asdict, dataclass, field
import json
import os
from pathlib import Path
from typing import NoReturn
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field, StrictBool, StrictStr
from psycopg import ProgrammingError
from psycopg.conninfo import conninfo_to_dict

from app.identity import ActorBinding, AuthenticationError, Credential, CredentialResolver
from app.main import Settings, create_app
from database.capture_sessions import (
    CaptureAuthorizationError, CaptureSessionConflict, CaptureSessionNotFound,
    CaptureSessionStore, CaptureStorageUnavailable,
)
from app.artifact_storage import (
    ArtifactConflict, ArtifactIntegrityError, ArtifactNotFound,
    ArtifactStorageUnavailable, OriginalByteStore,
)
from database.capture_evidence import CaptureEvidenceService, MAX_EVIDENCE_BYTES

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

class ConsentRequest(BaseModel):
    request_id: UUID
    accepted: StrictBool
    scope: StrictStr = Field(min_length=1, max_length=128)
    class Config:
        extra = 'forbid'

class VehicleReferenceRequest(BaseModel):
    request_id: UUID
    vin: StrictStr = Field(min_length=17, max_length=17)
    class Config:
        extra = 'forbid'

class EvidenceArtifactRequest(BaseModel):
    request_id: UUID
    artifact_id: UUID
    slot: StrictStr = Field(min_length=1, max_length=64)
    payload_base64: StrictStr = Field(min_length=4, max_length=((MAX_EVIDENCE_BYTES + 2) // 3) * 4)
    sha256: StrictStr = Field(min_length=64, max_length=64)
    class Config:
        extra = 'forbid'

class AdvisoryQualityRequest(BaseModel):
    request_id: UUID
    results: dict[StrictStr, StrictBool]
    class Config:
        extra = 'forbid'

class SealRequest(BaseModel):
    request_id: UUID
    class Config:
        extra = 'forbid'

class HumanReviewRequest(BaseModel):
    request_id: UUID
    disposition: StrictStr = Field(min_length=1, max_length=64)
    reason: StrictStr = Field(min_length=1, max_length=1000)
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
            if type(record) is not dict or set(record) not in (
                {'actor_id', 'tenant_id', 'database_role', 'token_sha256', 'expires_at', 'enabled'},
                {'actor_id', 'tenant_id', 'database_role', 'token_sha256', 'expires_at', 'enabled', 'actor_role'},
            ):
                raise ValueError('INVALID_CREDENTIAL_FIELDS')
            if (not isinstance(record['tenant_id'], str) or not isinstance(record['database_role'], str)
                    or not isinstance(record['token_sha256'], str) or type(record['enabled']) is not bool
                    or ('actor_role' in record and not isinstance(record['actor_role'], str))):
                raise ValueError('INVALID_CREDENTIAL_TYPES')
            binding = ActorBinding(record['actor_id'], UUID(record['tenant_id']), record['database_role'],
                                   record.get('actor_role', 'operator'))
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

def create_capture_app(runtime=None, *, enable_evidence=False):
    if runtime is None:
        path = os.environ.get('C2C_CAPTURE_CONFIG_FILE')
        if not path:
            raise ValueError('CAPTURE_RUNTIME_CONFIGURATION_REQUIRED')
        runtime = load_runtime(path)
    # Child intake apps carry only the health handlers they have always owned;
    # never recursively compose the integrated parent when C2C_RUNTIME_MODE is set.
    api = create_app(runtime.health_settings, runtime_mode='restricted_staging')
    api.state.health_settings = runtime.health_settings
    evidence = None
    if enable_evidence:
        root = os.environ.get('C2C_ARTIFACT_STORAGE_ROOT')
        pepper = os.environ.get('C2C_VIN_HMAC_PEPPER')
        if not root or not Path(root).is_absolute() or not pepper:
            raise ValueError('PERSISTENT_EVIDENCE_CONFIGURATION_REQUIRED')
        evidence = CaptureEvidenceService(
            runtime.store, OriginalByteStore(root, max_bytes=MAX_EVIDENCE_BYTES), pepper
        )

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

    if evidence is not None:
        def invoke_evidence(action, authorization, session_id=None, **kwargs):
            try:
                result = action(authorization, **kwargs) if session_id is None else action(
                    authorization, str(session_id), **kwargs
                )
                return JSONResponse(jsonable_encoder(result), headers=dict(NO_STORE_HEADERS))
            except AuthenticationError:
                _fail(401, 'UNAUTHORIZED')
            except CaptureAuthorizationError:
                _fail(403, 'CAPTURE_AUTHORITY_DENIED')
            except CaptureSessionConflict:
                _fail(409, 'CAPTURE_SESSION_CONFLICT')
            except CaptureSessionNotFound:
                _fail(404, 'CAPTURE_SESSION_NOT_FOUND')
            except (CaptureStorageUnavailable, ArtifactStorageUnavailable):
                _fail(503, 'CAPTURE_STORAGE_UNAVAILABLE')
            except (ArtifactConflict, ArtifactIntegrityError, ArtifactNotFound):
                _fail(409, 'EVIDENCE_ARTIFACT_CONFLICT')
            except ValueError:
                _fail(422, 'INVALID_CAPTURE_EVIDENCE_REQUEST')
            except Exception:
                _fail(500, 'CAPTURE_EVIDENCE_OPERATION_FAILED')

        @api.post('/v1/capture-sessions/{session_id}/consent')
        def record_consent(session_id: UUID, body: ConsentRequest, authorization: str = Depends(authorize)):
            return invoke_evidence(evidence.record_consent, authorization, session_id,
                                   request_id=body.request_id, accepted=body.accepted, scope=body.scope)

        @api.post('/v1/capture-sessions/{session_id}/vehicle-reference')
        def record_vehicle(session_id: UUID, body: VehicleReferenceRequest, authorization: str = Depends(authorize)):
            return invoke_evidence(evidence.record_vehicle, authorization, session_id,
                                   request_id=body.request_id, vin=body.vin)

        @api.post('/v1/capture-sessions/{session_id}/artifacts')
        def register_artifact(session_id: UUID, body: EvidenceArtifactRequest, authorization: str = Depends(authorize)):
            return invoke_evidence(
                evidence.register_artifact, authorization, session_id, request_id=body.request_id,
                artifact_id=body.artifact_id, slot=body.slot, payload_base64=body.payload_base64,
                sha256_hex=body.sha256,
            )

        @api.post('/v1/capture-sessions/{session_id}/quality')
        def record_quality(session_id: UUID, body: AdvisoryQualityRequest, authorization: str = Depends(authorize)):
            return invoke_evidence(evidence.record_quality, authorization, session_id,
                                   request_id=body.request_id, results=body.results)

        @api.post('/v1/capture-sessions/{session_id}/seal')
        def seal_capture(session_id: UUID, body: SealRequest, authorization: str = Depends(authorize)):
            return invoke_evidence(evidence.seal_capture, authorization, session_id,
                                   request_id=body.request_id)

        @api.get('/v1/review-queue')
        def review_queue(limit: int = Query(default=100, ge=1, le=200), authorization: str = Depends(authorize)):
            return invoke_evidence(evidence.list_review_queue, authorization, limit=limit)

        @api.post('/v1/capture-sessions/{session_id}/review')
        def record_review(session_id: UUID, body: HumanReviewRequest, authorization: str = Depends(authorize)):
            return invoke_evidence(
                evidence.record_review, authorization, session_id, request_id=body.request_id,
                disposition=body.disposition, reason=body.reason,
            )

        @api.get('/v1/review-sessions/{session_id}/artifacts/{artifact_id}')
        def review_artifact(session_id: UUID, artifact_id: UUID, authorization: str = Depends(authorize)):
            try:
                raw = evidence.retrieve_for_review(authorization, str(session_id), str(artifact_id))
                return Response(
                    content=raw,
                    media_type='application/octet-stream',
                    headers={'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'},
                )
            except AuthenticationError:
                _fail(401, 'UNAUTHORIZED')
            except CaptureAuthorizationError:
                _fail(403, 'CAPTURE_AUTHORITY_DENIED')
            except CaptureSessionNotFound:
                _fail(404, 'CAPTURE_SESSION_NOT_FOUND')
            except CaptureSessionConflict:
                _fail(409, 'CAPTURE_SESSION_CONFLICT')
            except (CaptureStorageUnavailable, ArtifactStorageUnavailable):
                _fail(503, 'CAPTURE_STORAGE_UNAVAILABLE')
            except (ArtifactIntegrityError, ArtifactNotFound):
                _fail(409, 'EVIDENCE_INTEGRITY_FAILED')
            except ValueError:
                _fail(422, 'INVALID_REVIEW_ARTIFACT_REQUEST')
            except Exception:
                _fail(500, 'REVIEW_ARTIFACT_OPERATION_FAILED')

    return api
