"""Tenant-scoped session start, list, retrieve, event list, and consent record under RLS.
Does not touch sealing or evidence.
"""
from uuid import uuid4
import json
import os
import psycopg
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from app.identity import CredentialResolver, AuthenticationError

router = APIRouter()

class SessionStartResponse(BaseModel):
    session_id: str
    tenant_id: str

class SessionListResponse(BaseModel):
    sessions: list[SessionStartResponse]

class EventItem(BaseModel):
    event_id: str
    kind: str
    actor_id: str

class EventListResponse(BaseModel):
    session_id: str
    events: list[EventItem]

class TenantHealthResponse(BaseModel):
    status: str
    tenant_id: str
    actor_id: str

class ConsentRecordResponse(BaseModel):
    session_id: str
    event_id: str
    kind: str

def get_resolver() -> CredentialResolver:
    return CredentialResolver()

def get_db_url() -> str | None:
    return os.environ.get('APP_DATABASE_URL')

@router.get('/health/tenant', response_model=TenantHealthResponse)
async def tenant_health(
    authorization: str = Header(None),
    resolver: CredentialResolver = Depends(get_resolver),
):
    if not authorization:
        raise HTTPException(status_code=401, detail='UNAUTHORIZED')
    try:
        binding = resolver.resolve(authorization)
    except AuthenticationError:
        raise HTTPException(status_code=401, detail='UNAUTHORIZED')
    return TenantHealthResponse(
        status='ok',
        tenant_id=str(binding.tenant_id),
        actor_id=binding.actor_id,
    )

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
                event_id = str(uuid4())
                payload = json.dumps({"actor_id": binding.actor_id})
                cur.execute(
                    "SELECT faos.append_event(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (
                        binding.tenant_id,
                        session_id,
                        event_id,
                        1,
                        "SESSION_CREATED",
                        binding.actor_id,
                        "2026-10-31T00:00:00Z",
                        "session_start",
                        payload,
                        "0.1",
                    ),
                )
            conn.commit()
    except Exception:
        raise HTTPException(status_code=500, detail='SESSION_PERSIST_FAILED')
    return SessionStartResponse(session_id=session_id, tenant_id=str(binding.tenant_id))

@router.post('/sessions/{session_id}/consent', response_model=ConsentRecordResponse)
async def record_consent(
    session_id: str,
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
    if not db_url:
        raise HTTPException(status_code=500, detail='NO_DATABASE')
    try:
        with psycopg.connect(db_url, autocommit=False) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT set_config('faos.tenant_id', %s, true)", (str(binding.tenant_id),))
                cur.execute(
                    "SELECT COALESCE(MAX(sequence), 0) FROM faos.events WHERE session_id = %s",
                    (session_id,),
                )
                next_seq = cur.fetchone()[0] + 1
                event_id = str(uuid4())
                payload = json.dumps({"actor_id": binding.actor_id, "consent": "recorded"})
                cur.execute(
                    "SELECT faos.append_event(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (
                        binding.tenant_id,
                        session_id,
                        event_id,
                        next_seq,
                        "CONSENT_RECORDED",
                        binding.actor_id,
                        "2026-10-31T00:00:00Z",
                        "consent_recorded",
                        payload,
                        "0.1",
                    ),
                )
            conn.commit()
    except Exception:
        raise HTTPException(status_code=500, detail='CONSENT_RECORD_FAILED')
    return ConsentRecordResponse(session_id=session_id, event_id=event_id, kind="CONSENT_RECORDED")

@router.get('/sessions', response_model=SessionListResponse)
async def list_sessions(
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
    if not db_url:
        return SessionListResponse(sessions=[])
    try:
        with psycopg.connect(db_url, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT set_config('faos.tenant_id', %s, true)", (str(binding.tenant_id),))
                cur.execute("SELECT tenant_id, session_id FROM faos.sessions ORDER BY session_id")
                rows = cur.fetchall()
                sessions = [SessionStartResponse(session_id=r[1], tenant_id=str(r[0])) for r in rows]
                return SessionListResponse(sessions=sessions)
    except Exception:
        raise HTTPException(status_code=500, detail='SESSIONS_LIST_FAILED')

@router.get('/sessions/{session_id}', response_model=SessionStartResponse)
async def get_session(
    session_id: str,
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
    if not db_url:
        return SessionStartResponse(session_id=session_id, tenant_id=str(binding.tenant_id))
    try:
        with psycopg.connect(db_url, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT set_config('faos.tenant_id', %s, true)", (str(binding.tenant_id),))
                cur.execute(
                    "SELECT tenant_id, session_id FROM faos.sessions WHERE session_id = %s",
                    (session_id,),
                )
                row = cur.fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail='SESSION_NOT_FOUND')
                return SessionStartResponse(session_id=row[1], tenant_id=str(row[0]))
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail='SESSION_READ_FAILED')

@router.get('/sessions/{session_id}/events', response_model=EventListResponse)
async def get_session_events(
    session_id: str,
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
    if not db_url:
        return EventListResponse(session_id=session_id, events=[])
    try:
        with psycopg.connect(db_url, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT set_config('faos.tenant_id', %s, true)", (str(binding.tenant_id),))
                cur.execute(
                    "SELECT event_id, kind, actor FROM faos.events WHERE session_id = %s ORDER BY sequence",
                    (session_id,),
                )
                rows = cur.fetchall()
                events = [EventItem(event_id=r[0], kind=r[1], actor_id=r[2]) for r in rows]
                return EventListResponse(session_id=session_id, events=events)
    except Exception:
        raise HTTPException(status_code=500, detail='EVENTS_READ_FAILED')
