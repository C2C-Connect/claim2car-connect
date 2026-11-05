"""Controlled-test VIN intake; no driver sign-in, images, consent or submission."""
from dataclasses import asdict
import os
from uuid import UUID
from fastapi import Depends, Header
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, StrictStr, conint
from app.capture_api import create_capture_app, load_runtime, _fail, NO_STORE_HEADERS
from app.identity import AuthenticationError
from database.capture_sessions import CaptureAuthorizationError, CaptureSessionConflict, CaptureSessionNotFound, CaptureStorageUnavailable
from database.intake_drafts import DraftAccessDenied, DraftConflict, IntakeDraftStore

class DraftRequest(BaseModel):
    request_id: UUID
    expected_revision: conint(strict=True, ge=1)
    vin: StrictStr = Field(min_length=17, max_length=17)
    class Config:
        extra = 'forbid'

def create_intake_app(runtime=None):
    if runtime is None:
        path = os.environ.get('C2C_CAPTURE_CONFIG_FILE')
        if not path:
            raise ValueError('CAPTURE_RUNTIME_CONFIGURATION_REQUIRED')
        runtime = load_runtime(path)
    api = create_capture_app(runtime)
    drafts = IntakeDraftStore(runtime.store)

    @api.exception_handler(RequestValidationError)
    async def invalid_request(request, error):
        return JSONResponse({'detail': 'INVALID_INTAKE_REQUEST'}, status_code=422, headers=dict(NO_STORE_HEADERS))

    def authorize(authorization: str | None = Header(default=None)):
        if authorization is None:
            _fail(401, 'UNAUTHORIZED')
        try:
            runtime.resolver.resolve(authorization)
        except AuthenticationError:
            _fail(401, 'UNAUTHORIZED')
        return authorization

    def invoke(action, authorization, session_id, **kwargs):
        try:
            result = action(authorization, str(session_id), **kwargs)
        except AuthenticationError:
            _fail(401, 'UNAUTHORIZED')
        except (CaptureAuthorizationError, DraftAccessDenied):
            _fail(403, 'INTAKE_ACCESS_DENIED')
        except CaptureSessionNotFound:
            _fail(404, 'CAPTURE_SESSION_NOT_FOUND')
        except (CaptureSessionConflict, DraftConflict):
            _fail(409, 'INTAKE_DRAFT_CONFLICT')
        except CaptureStorageUnavailable:
            _fail(503, 'CAPTURE_STORAGE_UNAVAILABLE')
        except ValueError:
            _fail(422, 'INVALID_INTAKE_REQUEST')
        except Exception:
            _fail(500, 'INTAKE_OPERATION_FAILED')
        try:
            return JSONResponse(jsonable_encoder(asdict(result)), headers=dict(NO_STORE_HEADERS))
        except Exception:
            _fail(500, 'INTAKE_OPERATION_FAILED')

    @api.get('/v1/capture-sessions/{session_id}/draft')
    def get_draft(session_id: UUID, authorization: str = Depends(authorize)):
        return invoke(drafts.get, authorization, session_id)

    @api.put('/v1/capture-sessions/{session_id}/draft')
    def save_draft(session_id: UUID, body: DraftRequest, authorization: str = Depends(authorize)):
        return invoke(drafts.save, authorization, session_id, request_id=str(body.request_id), expected_revision=body.expected_revision, vin=body.vin)

    return api
