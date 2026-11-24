"""Tenant-bound capture APIs over server-owned credentials and PostgreSQL RLS.

The standalone session-create route remains controlled-test only. Persistent
claim-case creation provisions its own production-scoped capture session; the
integrated evidence routes then require consent, keyed VIN references, and
separately provisioned original-byte storage. Service credentials are not
end-user sign-in; actor roles come from private config.
"""
from dataclasses import asdict, dataclass, field
from decimal import Decimal
from hashlib import sha256
import json
import base64
import binascii
import os
from pathlib import Path
from typing import Literal, NoReturn
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
from database.claim_cases import ClaimCaseConflict, ClaimCaseNotFound, ClaimCaseStore
from database.collision_lifecycle import CollisionLifecycleConflict, CollisionLifecycleNotFound, CollisionLifecycleStore
from database.incident_intake import IncidentIntakeService
from database.capture_sessions import (
    CaptureAuthorizationError, CaptureSessionConflict, CaptureSessionNotFound,
    CaptureSessionStore, CaptureStorageUnavailable,
)
from app.artifact_storage import (
    ArtifactConflict, ArtifactIntegrityError, ArtifactNotFound,
    ArtifactStorageUnavailable, OriginalByteStore,
)
from database.capture_evidence import CaptureEvidenceService, MAX_EVIDENCE_BYTES
from app.capture_protocols import DEFAULT_CAPTURE_PROTOCOL, FAOS_CAPTURE_PROTOCOL, LEGACY_CAPTURE_PROTOCOL, resolve_capture_protocol
from app.damage_localization import zone_for_slot
from app.vision.photo_baseline import PhotoBaselineError, analyze_photo_bytes
from app.vehicle_intelligence.vpic import VpicClient
from backend.app.reports.damage_assessment import (
    CameraAngle, DamageAssessment, DamageEvidenceImage, DamageFinding,
    DamageReportError, RepairEstimateLine, render_damage_assessment_pdf,
)

NO_STORE_HEADERS = {'Cache-Control': 'no-store'}
CONFIGURATION_SIZE_LIMIT = 65536
MAX_CREDENTIALS = 128
_vpic_client = VpicClient()

@dataclass(frozen=True)
class CaptureRuntime:
    resolver: CredentialResolver = field(repr=False)
    store: CaptureSessionStore = field(repr=False)
    health_settings: Settings = field(repr=False)
    claim_store: ClaimCaseStore | None = field(default=None, repr=False)
    collision_store: CollisionLifecycleStore | None = field(default=None, repr=False)

class ClaimCaseRequest(BaseModel):
    claim_id: UUID
    request_id: UUID
    capture_protocol_version: StrictStr = DEFAULT_CAPTURE_PROTOCOL
    class Config:
        extra = 'forbid'

class CollisionRecordRequest(BaseModel):
    collision_id: UUID
    request_id: UUID
    class Config:
        extra = 'forbid'

class CollisionClaimLinkRequest(BaseModel):
    claim_id: UUID
    request_id: UUID
    class Config:
        extra = 'forbid'

class CollisionVehicleLinkRequest(BaseModel):
    claim_id: UUID
    vehicle_id: UUID
    request_id: UUID
    relationship: StrictStr = Field(default='INVOLVED', min_length=1, max_length=16)
    class Config:
        extra = 'forbid'

class IncidentConsentRequest(BaseModel):
    request_id: UUID
    accepted: StrictBool
    class Config:
        extra = 'forbid'

class IncidentIntakeRequest(BaseModel):
    request_id: UUID
    occurred_at: StrictStr = Field(min_length=20, max_length=40)
    incident_type: StrictStr = Field(min_length=1, max_length=16)
    city: StrictStr = Field(min_length=2, max_length=80)
    region: StrictStr = Field(min_length=2, max_length=2)
    postal_code: StrictStr = Field(min_length=5, max_length=10)
    class Config:
        extra = 'forbid'

class SessionRequest(BaseModel):
    session_id: UUID
    capture_protocol_version: StrictStr = DEFAULT_CAPTURE_PROTOCOL
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

class VehicleDecodeConsentRequest(BaseModel):
    request_id: UUID
    accepted: StrictBool
    scope: StrictStr = Field(min_length=1, max_length=64)
    disclosure_version: StrictStr = Field(min_length=1, max_length=64)
    class Config:
        extra = 'forbid'

class VehicleProfileRequest(BaseModel):
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

class CaptureExceptionRequest(BaseModel):
    request_id: UUID
    slot: StrictStr = Field(min_length=1, max_length=64)
    reason_code: StrictStr = Field(min_length=1, max_length=64)
    explanation: StrictStr = Field(min_length=1, max_length=500)
    class Config:
        extra = 'forbid'

class CaptureExceptionResolutionRequest(BaseModel):
    request_id: UUID
    slot: StrictStr = Field(min_length=1, max_length=64)
    resolution_code: StrictStr = Field(min_length=1, max_length=64)
    explanation: StrictStr = Field(min_length=1, max_length=500)
    class Config:
        extra = 'forbid'

class CapturePauseRequest(BaseModel):
    request_id: UUID
    reason: StrictStr = Field(min_length=1, max_length=500)
    class Config:
        extra = 'forbid'

class HumanReviewRequest(BaseModel):
    request_id: UUID
    disposition: StrictStr = Field(min_length=1, max_length=64)
    reason: StrictStr = Field(min_length=1, max_length=1000)
    class Config:
        extra = 'forbid'

class DamageFindingRequest(BaseModel):
    finding_id: StrictStr = Field(min_length=1, max_length=64)
    component: StrictStr = Field(min_length=1, max_length=128)
    vehicle_location: StrictStr = Field(min_length=1, max_length=160)
    damage_type: StrictStr = Field(min_length=1, max_length=96)
    observation: StrictStr = Field(min_length=1, max_length=1200)
    evidence_artifact_id: UUID
    bbox_normalized: tuple[float, float, float, float]
    status: Literal["CONFIRMED_BY_REVIEWER", "PROVISIONAL", "INCONCLUSIVE", "REJECTED"] = "PROVISIONAL"
    limitations: StrictStr = Field(default="", max_length=1200)
    class Config:
        extra = "forbid"


class CameraAngleRequest(BaseModel):
    yaw_degrees: float | None = Field(default=None, ge=-360, le=360)
    pitch_degrees: float | None = Field(default=None, ge=-360, le=360)
    roll_degrees: float | None = Field(default=None, ge=-360, le=360)
    class Config:
        extra = "forbid"


class RepairEstimateLineRequest(BaseModel):
    line_id: StrictStr = Field(min_length=1, max_length=64)
    category: Literal["PART", "BODY_LABOR", "PAINT_LABOR", "MATERIAL", "DIAGNOSTIC", "CALIBRATION", "SUBLET", "TAX", "OTHER"]
    description: StrictStr = Field(min_length=1, max_length=240)
    quantity: Decimal = Field(gt=0, le=100000)
    unit: StrictStr = Field(min_length=1, max_length=24)
    unit_price_cents: int = Field(ge=0, le=1000000000)
    source_name: StrictStr = Field(min_length=1, max_length=120)
    source_reference: StrictStr = Field(min_length=1, max_length=160)
    effective_date: StrictStr = Field(min_length=10, max_length=10)
    related_finding_id: StrictStr | None = Field(default=None, max_length=64)
    class Config:
        extra = "forbid"


class DamageAssessmentReportRequest(BaseModel):
    request_id: UUID
    vehicle_description: StrictStr = Field(min_length=1, max_length=256)
    findings: list[DamageFindingRequest] = Field(min_items=1, max_items=64)
    estimate_lines: list[RepairEstimateLineRequest] = Field(default_factory=list, max_items=256)
    camera_angles: dict[str, CameraAngleRequest] = Field(default_factory=dict)
    class Config:
        extra = "forbid"



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

def load_runtime(path=None, *, configuration_json=None):
    try:
        if configuration_json is not None:
            if not isinstance(configuration_json, str):
                raise ValueError('INVALID_CONFIGURATION_TYPES')
            raw = configuration_json.encode('utf-8')
        else:
            if not path:
                raise ValueError('CAPTURE_RUNTIME_CONFIGURATION_REQUIRED')
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
        configuration_json = os.environ.get('C2C_CAPTURE_CONFIG_JSON')
        if configuration_json:
            runtime = load_runtime(configuration_json=configuration_json)
        else:
            path = os.environ.get('C2C_CAPTURE_CONFIG_FILE')
            if not path:
                raise ValueError('CAPTURE_RUNTIME_CONFIGURATION_REQUIRED')
            runtime = load_runtime(path)
    # Child intake apps carry only the health handlers they have always owned;
    # never recursively compose the integrated parent when C2C_RUNTIME_MODE is set.
    api = create_app(runtime.health_settings, runtime_mode='restricted_staging')
    api.state.health_settings = runtime.health_settings
    claim_cases = getattr(runtime, 'claim_store', None)
    collisions = getattr(runtime, 'collision_store', None)
    if collisions is None and isinstance(runtime.store, CaptureSessionStore):
        collisions = CollisionLifecycleStore(runtime.store)
    if claim_cases is None and isinstance(runtime.store, CaptureSessionStore):
        claim_cases = ClaimCaseStore(runtime.store)
    evidence = None
    incident_intake = None
    if enable_evidence:
        root = os.environ.get('C2C_ARTIFACT_STORAGE_ROOT')
        pepper = os.environ.get('C2C_VIN_HMAC_PEPPER')
        if not root or not Path(root).is_absolute() or not pepper:
            raise ValueError('PERSISTENT_EVIDENCE_CONFIGURATION_REQUIRED')
        evidence = CaptureEvidenceService(
            runtime.store, OriginalByteStore(root, max_bytes=MAX_EVIDENCE_BYTES), pepper
        )
        incident_intake = IncidentIntakeService(runtime.store)

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

    def invoke(action, authorization, session_id, creating=False, **kwargs):
        try:
            result = action(authorization, str(session_id), **kwargs)
            payload_data = asdict(result)
            payload_data.pop('owner_actor_id', None)
            payload_data['scope'] = getattr(result, 'scope', 'controlled-test')
            payload = jsonable_encoder(payload_data)
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

    def invoke_claim(action, authorization, **kwargs):
        try:
            result = action(authorization, **kwargs)
            payload = {**asdict(result), 'scope': 'persistent-claim-case'}
            return JSONResponse(jsonable_encoder(payload), status_code=201 if result.created else 200,
                                headers=dict(NO_STORE_HEADERS))
        except AuthenticationError:
            _fail(401, 'UNAUTHORIZED')
        except CaptureAuthorizationError:
            _fail(403, 'CLAIM_CASE_AUTHORITY_DENIED')
        except ClaimCaseNotFound:
            _fail(404, 'CLAIM_CASE_NOT_FOUND')
        except ClaimCaseConflict:
            _fail(409, 'CLAIM_CASE_CONFLICT')
        except CaptureStorageUnavailable:
            _fail(503, 'CAPTURE_STORAGE_UNAVAILABLE')
        except ValueError:
            _fail(422, 'INVALID_CLAIM_CASE_REQUEST')
        except Exception:
            _fail(500, 'CLAIM_CASE_OPERATION_FAILED')

    @api.get('/v1/capture-protocols')
    def capture_protocol_registry(authorization: str = Depends(authorize)):
        protocols = []
        for version in (DEFAULT_CAPTURE_PROTOCOL, FAOS_CAPTURE_PROTOCOL, LEGACY_CAPTURE_PROTOCOL):
            definition = resolve_capture_protocol(version)
            protocols.append({
                "version": definition.version,
                "status": definition.status,
                "selectable_for_new_sessions": True,
                "capture_enabled": definition.status == "implemented",
                "required_slots": list(definition.slots),
                "slot_descriptions": definition.descriptions,
            })
        return JSONResponse({
            "default_protocol_version": DEFAULT_CAPTURE_PROTOCOL,
            "protocols": protocols,
        }, headers=dict(NO_STORE_HEADERS))

    def invoke_collision(action, authorization, **kwargs):
        try:
            result = action(authorization, **kwargs)
            result_data = asdict(result) if hasattr(result, '__dataclass_fields__') else dict(result)
            payload = {**result_data, 'scope': 'collision-lifecycle'}
            return JSONResponse(jsonable_encoder(payload), status_code=201 if result_data.get('created', False) else 200,
                                headers=dict(NO_STORE_HEADERS))
        except AuthenticationError:
            _fail(401, 'UNAUTHORIZED')
        except CaptureAuthorizationError:
            _fail(403, 'COLLISION_AUTHORITY_DENIED')
        except CollisionLifecycleNotFound:
            _fail(404, 'COLLISION_NOT_FOUND')
        except CollisionLifecycleConflict:
            _fail(409, 'COLLISION_LIFECYCLE_CONFLICT')
        except CaptureStorageUnavailable:
            _fail(503, 'COLLISION_STORAGE_UNAVAILABLE')
        except ValueError:
            _fail(422, 'INVALID_COLLISION_REQUEST')
        except Exception:
            _fail(500, 'COLLISION_OPERATION_FAILED')

    @api.post('/v1/collisions')
    def create_collision(body: CollisionRecordRequest, authorization: str = Depends(authorize)):
        if collisions is None:
            _fail(503, 'COLLISION_STORAGE_UNAVAILABLE')
        return invoke_collision(collisions.create, authorization,
                                collision_id=str(body.collision_id), request_id=str(body.request_id))

    @api.get('/v1/collisions/{collision_id}')
    def get_collision(collision_id: UUID, authorization: str = Depends(authorize)):
        if collisions is None:
            _fail(503, 'COLLISION_STORAGE_UNAVAILABLE')
        try:
            record = collisions.get(authorization, str(collision_id))
            claims = collisions.list_claims(authorization, str(collision_id))
            vehicles = collisions.list_vehicles(authorization, str(collision_id))
            return JSONResponse(jsonable_encoder({
                'collision': asdict(record),
                'claims': [asdict(item) for item in claims],
                'vehicles': vehicles,
                'scope': 'collision-lifecycle',
            }), headers=dict(NO_STORE_HEADERS))
        except AuthenticationError:
            _fail(401, 'UNAUTHORIZED')
        except CaptureAuthorizationError:
            _fail(403, 'COLLISION_AUTHORITY_DENIED')
        except CollisionLifecycleNotFound:
            _fail(404, 'COLLISION_NOT_FOUND')
        except ValueError:
            _fail(422, 'INVALID_COLLISION_REQUEST')
        except Exception:
            _fail(500, 'COLLISION_OPERATION_FAILED')

    @api.post('/v1/collisions/{collision_id}/claims')
    def link_collision_claim(collision_id: UUID, body: CollisionClaimLinkRequest,
                             authorization: str = Depends(authorize)):
        if collisions is None:
            _fail(503, 'COLLISION_STORAGE_UNAVAILABLE')
        return invoke_collision(collisions.link_claim, authorization,
                                collision_id=str(collision_id), claim_id=str(body.claim_id),
                                request_id=str(body.request_id))

    @api.post('/v1/collisions/{collision_id}/vehicles')
    def link_collision_vehicle(collision_id: UUID, body: CollisionVehicleLinkRequest,
                               authorization: str = Depends(authorize)):
        if collisions is None:
            _fail(503, 'COLLISION_STORAGE_UNAVAILABLE')
        return invoke_collision(
            collisions.link_vehicle_from_capture, authorization,
            collision_id=str(collision_id), claim_id=str(body.claim_id),
            vehicle_id=str(body.vehicle_id), request_id=str(body.request_id),
            relationship=body.relationship,
        )

    @api.post('/v1/claim-cases')
    def create_claim_case(body: ClaimCaseRequest, authorization: str = Depends(authorize)):
        if claim_cases is None:
            _fail(503, 'CLAIM_CASE_STORAGE_UNAVAILABLE')
        return invoke_claim(claim_cases.create, authorization,
                            claim_id=str(body.claim_id), request_id=str(body.request_id),
                            capture_protocol_version=body.capture_protocol_version)

    @api.get('/v1/claim-cases')
    def list_claim_cases(limit: int = Query(default=50, ge=1, le=100),
                         authorization: str = Depends(authorize)):
        if claim_cases is None:
            _fail(503, 'CLAIM_CASE_STORAGE_UNAVAILABLE')
        try:
            records = claim_cases.list_owned(authorization, limit=limit)
            payload = [{**asdict(item), 'scope': 'persistent-claim-case'} for item in records]
            return JSONResponse(jsonable_encoder(payload), headers=dict(NO_STORE_HEADERS))
        except AuthenticationError:
            _fail(401, 'UNAUTHORIZED')
        except CaptureAuthorizationError:
            _fail(403, 'CLAIM_CASE_AUTHORITY_DENIED')
        except CaptureStorageUnavailable:
            _fail(503, 'CAPTURE_STORAGE_UNAVAILABLE')
        except ValueError:
            _fail(422, 'INVALID_CLAIM_CASE_REQUEST')
        except Exception:
            _fail(500, 'CLAIM_CASE_OPERATION_FAILED')

    @api.get('/v1/claim-cases/{claim_id}')
    def get_claim_case(claim_id: UUID, authorization: str = Depends(authorize)):
        if claim_cases is None:
            _fail(503, 'CLAIM_CASE_STORAGE_UNAVAILABLE')
        return invoke_claim(claim_cases.get, authorization, claim_id=str(claim_id))

    @api.post('/v1/capture-sessions')
    def create_session(body: SessionRequest, authorization: str = Depends(authorize)):
        return invoke(runtime.store.create, authorization, body.session_id, creating=True,
                      protocol_version=body.capture_protocol_version)

    @api.get('/v1/capture-sessions')
    def list_sessions(limit: int = Query(default=100, ge=1, le=100), authorization: str = Depends(authorize)):
        try:
            sessions=runtime.store.list_owned(authorization,limit=limit)
            payload=[{**asdict(item),'scope':'controlled-test'} for item in sessions]
            return JSONResponse(jsonable_encoder(payload),headers=dict(NO_STORE_HEADERS))
        except AuthenticationError:
            _fail(401,'UNAUTHORIZED')
        except CaptureAuthorizationError:
            _fail(403,'CAPTURE_AUTHORITY_DENIED')
        except CaptureStorageUnavailable:
            _fail(503,'CAPTURE_STORAGE_UNAVAILABLE')
        except ValueError:
            _fail(422,'INVALID_CAPTURE_SESSION_REQUEST')
        except Exception:
            _fail(500,'CAPTURE_OPERATION_FAILED')

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
            except CollisionLifecycleNotFound:
                _fail(404, 'COLLISION_NOT_FOUND')
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

        @api.get('/v1/capture-sessions/{session_id}/evidence-readiness')
        def evidence_readiness(session_id: UUID, authorization: str = Depends(authorize)):
            return invoke_evidence(evidence.evidence_readiness, authorization, session_id)
        @api.post('/v1/capture-sessions/{session_id}/consent')
        def record_consent(session_id: UUID, body: ConsentRequest, authorization: str = Depends(authorize)):
            return invoke_evidence(evidence.record_consent, authorization, session_id,
                                   request_id=body.request_id, accepted=body.accepted, scope=body.scope)

        @api.get('/v1/capture-sessions/{session_id}/incident-intake')
        def get_incident_intake(session_id: UUID, authorization: str = Depends(authorize)):
            if os.environ.get('C2C_INCIDENT_INTAKE_ENABLED', '').lower() != 'true':
                _fail(503, 'INCIDENT_INTAKE_NOT_ENABLED')
            return invoke_evidence(incident_intake.get_incident, authorization, session_id)

        @api.post('/v1/capture-sessions/{session_id}/incident-consent')
        def record_incident_consent(session_id: UUID, body: IncidentConsentRequest, authorization: str = Depends(authorize)):
            if os.environ.get('C2C_INCIDENT_INTAKE_ENABLED', '').lower() != 'true':
                _fail(503, 'INCIDENT_INTAKE_NOT_ENABLED')
            return invoke_evidence(incident_intake.record_consent, authorization, session_id,
                                   request_id=body.request_id, accepted=body.accepted)

        @api.post('/v1/capture-sessions/{session_id}/incident-intake')
        def record_incident_intake(session_id: UUID, body: IncidentIntakeRequest, authorization: str = Depends(authorize)):
            if os.environ.get('C2C_INCIDENT_INTAKE_ENABLED', '').lower() != 'true':
                _fail(503, 'INCIDENT_INTAKE_NOT_ENABLED')
            return invoke_evidence(
                incident_intake.record_incident, authorization, session_id,
                request_id=body.request_id, occurred_at=body.occurred_at,
                incident_type=body.incident_type, city=body.city,
                region=body.region, postal_code=body.postal_code,
            )

        @api.post('/v1/capture-sessions/{session_id}/vehicle-reference')
        def record_vehicle(session_id: UUID, body: VehicleReferenceRequest, authorization: str = Depends(authorize)):
            return invoke_evidence(evidence.record_vehicle, authorization, session_id,
                                   request_id=body.request_id, vin=body.vin)

        @api.post('/v1/capture-sessions/{session_id}/vehicle-decode-consent')
        def record_vehicle_decode_consent(session_id: UUID, body: VehicleDecodeConsentRequest,
                                           authorization: str = Depends(authorize)):
            return invoke_evidence(
                evidence.record_vehicle_decode_consent, authorization, session_id,
                request_id=body.request_id, accepted=body.accepted, scope=body.scope,
                disclosure_version=body.disclosure_version,
            )

        @api.get('/v1/vehicle-decode-disclosure')
        def vehicle_decode_disclosure(authorization: str = Depends(authorize)):
            path = Path(__file__).resolve().parents[1] / 'contracts' / 'vehicle-decode-disclosure-v1.json'
            try:
                disclosure = json.loads(path.read_text(encoding='utf-8'))
            except (OSError, ValueError):
                _fail(503, 'VEHICLE_DECODE_DISCLOSURE_UNAVAILABLE')
            return JSONResponse(disclosure, headers=dict(NO_STORE_HEADERS))

        @api.post('/v1/capture-sessions/{session_id}/vehicle-profile')
        def decode_vehicle_profile(session_id: UUID, body: VehicleProfileRequest,
                                   authorization: str = Depends(authorize)):
            return invoke_evidence(
                evidence.decode_vehicle_profile, authorization, session_id,
                request_id=body.request_id, vin=body.vin, decoder=_vpic_client,
            )

        @api.post('/v1/capture-sessions/{session_id}/artifacts')
        def register_artifact(session_id: UUID, body: EvidenceArtifactRequest, authorization: str = Depends(authorize)):
            registered = invoke_evidence(
                evidence.register_artifact, authorization, session_id, request_id=body.request_id,
                artifact_id=body.artifact_id, slot=body.slot, payload_base64=body.payload_base64,
                sha256_hex=body.sha256,
            )
            if not isinstance(registered, JSONResponse) or registered.status_code != 200:
                return registered
            result = json.loads(registered.body)
            localization = {"status": "NOT_APPLICABLE", "reason": "capture_slot_not_exterior", "image": {"sha256": body.sha256, "byte_length": result.get("byte_length", 0), "persisted": True}}
            protocol_version = next(
                (version for version in (DEFAULT_CAPTURE_PROTOCOL, LEGACY_CAPTURE_PROTOCOL)
                 if body.slot in resolve_capture_protocol(version).slots and zone_for_slot(body.slot, version)),
                None,
            )
            if protocol_version:
                try:
                    raw = base64.b64decode(body.payload_base64, validate=True)
                    localization = analyze_photo_bytes(raw, body.slot, protocol_version)
                    localization["image"]["persisted"] = True
                except (binascii.Error, PhotoBaselineError) as error:
                    code = error.code if isinstance(error, PhotoBaselineError) else "INVALID_ARTIFACT_ENCODING"
                    localization = {"status": "UNAVAILABLE", "code": code, "model_status": "BASELINE_NOT_AI", "image": {"sha256": body.sha256, "byte_length": result.get("byte_length", 0), "persisted": True}}
            result["localization"] = localization
            return JSONResponse(jsonable_encoder(result), headers=dict(NO_STORE_HEADERS))

        @api.post('/v1/capture-sessions/{session_id}/exceptions')
        def record_capture_exception(session_id: UUID, body: CaptureExceptionRequest, authorization: str = Depends(authorize)):
            return invoke_evidence(evidence.record_capture_exception, authorization, session_id,
                                   request_id=body.request_id, slot=body.slot,
                                   reason_code=body.reason_code, explanation=body.explanation)

        @api.post('/v1/capture-sessions/{session_id}/exceptions/resolve')
        def resolve_capture_exception(session_id: UUID, body: CaptureExceptionResolutionRequest,
                                       authorization: str = Depends(authorize)):
            return invoke_evidence(evidence.resolve_capture_exception, authorization, session_id,
                                   request_id=body.request_id, slot=body.slot,
                                   resolution_code=body.resolution_code, explanation=body.explanation)

        @api.post('/v1/capture-sessions/{session_id}/pause')
        def pause_capture_session(session_id: UUID, body: CapturePauseRequest, authorization: str = Depends(authorize)):
            return invoke_evidence(evidence.pause_capture_session, authorization, session_id,
                                   request_id=body.request_id, reason=body.reason)

        @api.post('/v1/capture-sessions/{session_id}/resume')
        def resume_capture_session(session_id: UUID, body: CapturePauseRequest, authorization: str = Depends(authorize)):
            return invoke_evidence(evidence.resume_capture_session, authorization, session_id,
                                   request_id=body.request_id, reason=body.reason)

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

        @api.get('/v1/review-sessions/{session_id}')
        def review_session_details(session_id: UUID, authorization: str = Depends(authorize)):
            return invoke_evidence(evidence.get_review_details, authorization, session_id)


        @api.post('/v1/review-sessions/{session_id}/damage-assessment-report')
        def generate_damage_assessment_report(
            session_id: UUID, body: DamageAssessmentReportRequest,
            authorization: str = Depends(authorize),
        ):
            try:
                request_bytes = json.dumps(
                    body.dict(), sort_keys=True, separators=(",", ":"), default=str,
                ).encode("utf-8")
                request_digest = sha256(request_bytes).hexdigest()
                try:
                    existing = evidence.retrieve_damage_assessment_report(
                        authorization, str(session_id), str(body.request_id),
                    )
                except CaptureSessionNotFound:
                    existing = None
                if existing is not None:
                    metadata = existing["metadata"]
                    if metadata.get("request_payload_sha256") != request_digest:
                        _fail(409, "DAMAGE_REPORT_IDEMPOTENCY_CONFLICT")
                    return Response(
                        content=existing["pdf_bytes"], media_type="application/pdf",
                        headers={
                            **NO_STORE_HEADERS,
                            "Content-Disposition": f'attachment; filename="claim2car-damage-report-{session_id}-r{metadata["report_revision"]}.pdf"',
                            "X-Report-Artifact-ID": metadata["report_artifact_id"],
                            "X-Report-SHA256": metadata["report_sha256"],
                            "X-Report-Revision": str(metadata["report_revision"]),
                        },
                    )

                details = evidence.get_review_details(authorization, str(session_id))
                review = details.get("review")
                if not review or not review.get("reviewed_at"):
                    _fail(409, "INDEPENDENT_REVIEW_REQUIRED_BEFORE_REPORT")
                artifacts_by_id = {item["artifact_id"]: item for item in details["artifacts"]}
                referenced_ids = sorted({str(item.evidence_artifact_id) for item in body.findings})
                if set(body.camera_angles) - set(referenced_ids):
                    _fail(422, "CAMERA_ANGLE_REFERENCES_UNATTACHED_IMAGE")
                evidence_images = []
                for artifact_id in referenced_ids:
                    metadata = artifacts_by_id.get(artifact_id)
                    if metadata is None:
                        _fail(409, "DAMAGE_FINDING_IMAGE_NOT_IN_SEALED_MANIFEST")
                    original = evidence.retrieve_for_review(authorization, str(session_id), artifact_id)
                    supplied_angle = body.camera_angles.get(artifact_id)
                    if supplied_angle and any(
                        value is not None for value in (
                            supplied_angle.yaw_degrees, supplied_angle.pitch_degrees, supplied_angle.roll_degrees,
                        )
                    ):
                        camera_angle = CameraAngle(
                            yaw_degrees=supplied_angle.yaw_degrees,
                            pitch_degrees=supplied_angle.pitch_degrees,
                            roll_degrees=supplied_angle.roll_degrees,
                            source="MANUAL_ENTRY",
                        )
                    else:
                        camera_angle = CameraAngle()
                    evidence_images.append(DamageEvidenceImage(
                        artifact_id=artifact_id,
                        capture_slot=metadata["slot"],
                        original_bytes=original,
                        expected_sha256=metadata["sha256"],
                        registered_at=metadata.get("registered_at") or "NOT_RECORDED",
                        camera_angle=camera_angle,
                    ))

                findings = tuple(DamageFinding(
                    finding_id=item.finding_id,
                    component=item.component,
                    vehicle_location=item.vehicle_location,
                    damage_type=item.damage_type,
                    observation=item.observation,
                    evidence_artifact_id=str(item.evidence_artifact_id),
                    bbox_normalized=item.bbox_normalized,
                    status=item.status,
                    reviewer_actor_id=review["actor_id"],
                    reviewed_at=review["reviewed_at"],
                    limitations=item.limitations,
                ) for item in body.findings)
                estimate_lines = tuple(RepairEstimateLine(
                    line_id=item.line_id,
                    category=item.category,
                    description=item.description,
                    quantity=item.quantity,
                    unit=item.unit,
                    unit_price_cents=item.unit_price_cents,
                    source_name=item.source_name,
                    source_reference=item.source_reference,
                    effective_date=item.effective_date,
                    related_finding_id=item.related_finding_id,
                ) for item in body.estimate_lines)
                assessment = DamageAssessment(
                    session_id=str(session_id),
                    vehicle_description=body.vehicle_description,
                    report_revision=details["next_report_revision"],
                    findings=findings,
                    evidence_images=tuple(evidence_images),
                    estimate_lines=estimate_lines,
                    prepared_at=review["reviewed_at"],
                )
                pdf_bytes = render_damage_assessment_pdf(assessment)
                report_sha256 = sha256(pdf_bytes).hexdigest()
                stored = evidence.record_damage_assessment_report(
                    authorization, str(session_id),
                    request_id=str(body.request_id),
                    pdf_bytes=pdf_bytes,
                    report_sha256=report_sha256,
                    report_revision=assessment.report_revision,
                    finding_ids=[item.finding_id for item in findings],
                    estimate_total_cents=sum(item.amount_cents for item in estimate_lines),
                    request_payload_sha256=request_digest,
                )
                return Response(
                    content=pdf_bytes, media_type="application/pdf",
                    headers={
                        **NO_STORE_HEADERS,
                        "Content-Disposition": f'attachment; filename="claim2car-damage-report-{session_id}-r{assessment.report_revision}.pdf"',
                        "X-Report-Artifact-ID": stored["report_artifact_id"],
                        "X-Report-SHA256": report_sha256,
                        "X-Report-Revision": str(assessment.report_revision),
                    },
                )
            except HTTPException:
                raise
            except AuthenticationError:
                _fail(401, "UNAUTHORIZED")
            except CaptureAuthorizationError:
                _fail(403, "REVIEWER_IDENTITY_REQUIRED")
            except CaptureSessionNotFound:
                _fail(404, "CAPTURE_SESSION_OR_REPORT_NOT_FOUND")
            except CaptureSessionConflict as error:
                _fail(409, str(error))
            except (CaptureStorageUnavailable, ArtifactStorageUnavailable):
                _fail(503, "CAPTURE_STORAGE_UNAVAILABLE")
            except (ArtifactConflict, ArtifactIntegrityError, ArtifactNotFound):
                _fail(409, "EVIDENCE_ARTIFACT_CONFLICT")
            except DamageReportError as error:
                _fail(422, error.code)
            except ValueError:
                _fail(422, "INVALID_DAMAGE_ASSESSMENT_REPORT_REQUEST")
            except Exception:
                _fail(500, "DAMAGE_ASSESSMENT_REPORT_GENERATION_FAILED")

        @api.get('/v1/review-sessions/{session_id}/damage-assessment-reports/{report_artifact_id}')
        def download_damage_assessment_report(
            session_id: UUID, report_artifact_id: UUID, authorization: str = Depends(authorize),
        ):
            try:
                result = evidence.retrieve_damage_assessment_report(
                    authorization, str(session_id), str(report_artifact_id),
                )
                metadata = result["metadata"]
                return Response(
                    content=result["pdf_bytes"], media_type="application/pdf",
                    headers={
                        **NO_STORE_HEADERS,
                        "Content-Disposition": f'attachment; filename="claim2car-damage-report-{session_id}-r{metadata["report_revision"]}.pdf"',
                        "X-Report-Artifact-ID": metadata["report_artifact_id"],
                        "X-Report-SHA256": metadata["report_sha256"],
                        "X-Report-Revision": str(metadata["report_revision"]),
                    },
                )
            except HTTPException:
                raise
            except AuthenticationError:
                _fail(401, "UNAUTHORIZED")
            except CaptureAuthorizationError:
                _fail(403, "REVIEWER_IDENTITY_REQUIRED")
            except CaptureSessionNotFound:
                _fail(404, "DAMAGE_REPORT_NOT_FOUND")
            except CaptureSessionConflict as error:
                _fail(409, str(error))
            except (CaptureStorageUnavailable, ArtifactStorageUnavailable):
                _fail(503, "CAPTURE_STORAGE_UNAVAILABLE")
            except (ArtifactIntegrityError, ArtifactNotFound):
                _fail(409, "DAMAGE_REPORT_ARTIFACT_INTEGRITY_FAILURE")
            except Exception:
                _fail(500, "DAMAGE_ASSESSMENT_REPORT_DOWNLOAD_FAILED")


        @api.get('/v1/review-collisions/{collision_id}')
        def review_collision(collision_id: UUID, authorization: str = Depends(authorize)):
            if collisions is None or evidence is None:
                _fail(503, 'COLLISION_EVIDENCE_UNAVAILABLE')
            try:
                links = collisions.list_review_claims(authorization, str(collision_id))
                claims = []
                for link in links:
                    try:
                        details = evidence.get_review_details(authorization, link.capture_session_id)
                        evidence_status = 'READY'
                    except CaptureSessionConflict as error:
                        if str(error) not in (
                            'ACTIVE_OWNER_CONSENT_REQUIRED',
                            'SEALED_SESSION_REQUIRED_FOR_REVIEW',
                            'CAPTURE_SET_INCOMPLETE',
                        ):
                            raise
                        details = None
                        evidence_status = 'NOT_REVIEWABLE'
                    claims.append({
                        'claim_id': link.claim_id,
                        'capture_session_id': link.capture_session_id,
                        'capture_protocol_version': link.capture_protocol_version,
                        'evidence_status': evidence_status,
                        'evidence': details,
                    })
                return JSONResponse(jsonable_encoder({
                    'collision_id': str(collision_id),
                    'claims': claims,
                    'scope': 'independent-collision-evidence-review',
                }), headers=dict(NO_STORE_HEADERS))
            except AuthenticationError:
                _fail(401, 'UNAUTHORIZED')
            except CaptureAuthorizationError:
                _fail(403, 'COLLISION_REVIEW_AUTHORITY_DENIED')
            except CaptureSessionNotFound:
                _fail(404, 'CAPTURE_SESSION_NOT_FOUND')
            except CaptureStorageUnavailable:
                _fail(503, 'CAPTURE_STORAGE_UNAVAILABLE')
            except ArtifactStorageUnavailable:
                _fail(503, 'CAPTURE_STORAGE_UNAVAILABLE')
            except (ArtifactConflict, ArtifactIntegrityError, ArtifactNotFound):
                _fail(409, 'EVIDENCE_ARTIFACT_CONFLICT')
            except ValueError:
                _fail(422, 'INVALID_COLLISION_REVIEW_REQUEST')
            except Exception:
                _fail(500, 'COLLISION_REVIEW_OPERATION_FAILED')

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

    @api.get('/v1/identity')
    def current_identity(authorization: str = Depends(authorize)):
        # Expose only the authenticated actor context needed by the application
        # shell. Never return credential material or database connection data.
        actor = runtime.resolver.resolve(authorization)
        return JSONResponse(
            {
                'actor_id': actor.actor_id,
                'tenant_id': str(actor.tenant_id),
                'actor_role': actor.actor_role,
            },
            headers=dict(NO_STORE_HEADERS),
        )

    return api
