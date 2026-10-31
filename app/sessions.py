"""Tenant-scoped session start that persists under RLS. Does not touch sealing or evidence."""
from uuid import uuid4
import os
import psycopg
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from app.identity import CredentialResolver, AuthenticationError

router = APIRouter()

class SessionStartResponse(BaseModel):
    session_id: str
    tenant_id: str

def get_resolver() -> CredentialResolver:
    # Production loads credentials out of band. Tests override this dependency.
    return CredentialResolver()

def get_db_url() -> str | None:
    return os.environ.get('APP_DATABASE_URL')

@router.post('/sessions', response_model=SessionStartResponse)
async def start_session(
    authorization: str = Header(None),
    resolver: CredentialResolver = Depends(get_resolver),
    db_url: str | None = Depends(get_db_url),
):
    if not authorization:
        raise HTTPException(status_code=401, detail='UNAUTHORIZED')
    try:
        binding = resolver.resolve(authorization)
    except AuthenticationError:
        raise HTTPException(status_code=401, detail='UNAUTHORIZED')
    session_id = str(uuid4())
    if not db_url:
        return SessionStartResponse(session_id=session_id, tenant_id=str(binding.tenant_id))
    try:
        with psycopg.connect(db_url, autocommit=False) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT set_config('faos.tenant_id', %s, true)", (str(binding.tenant_id),))
                cur.execute(
                    "INSERT INTO faos.sessions (tenant_id, session_id) VALUES (%s, %s)",
                    (binding.tenant_id, session_id),
                )
            conn.commit()
    except Exception:
        raise HTTPException(status_code=500, detail='SESSION_PERSIST_FAILED')
    return SessionStartResponse(session_id=session_id, tenant_id=str(binding.tenant_id))
