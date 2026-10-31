"""Minimal tenant-scoped session start. Does not touch sealing or evidence."""
from uuid import uuid4
import psycopg
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from app.identity import CredentialResolver, AuthenticationError

router = APIRouter()

class SessionStartResponse(BaseModel):
    session_id: str
    tenant_id: str

def get_resolver() -> CredentialResolver:
    # Placeholder: real credentials loaded from environment or config in later slice.
    return CredentialResolver()

@router.post('/sessions', response_model=SessionStartResponse)
async def start_session(
    authorization: str = Header(None),
    resolver: CredentialResolver = Depends(get_resolver),
):
    if not authorization:
        raise HTTPException(status_code=401, detail='UNAUTHORIZED')
    try:
        binding = resolver.resolve(authorization)
    except AuthenticationError:
        raise HTTPException(status_code=401, detail='UNAUTHORIZED')
    session_id = str(uuid4())
    # Session row is written by the database layer in a later committed slice.
    # This endpoint only establishes the authenticated, tenant-bound session identifier.
    return SessionStartResponse(session_id=session_id, tenant_id=str(binding.tenant_id))
