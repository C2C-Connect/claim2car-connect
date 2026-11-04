"""Tenant-scoped session start, list, retrieve, event list, consent, vehicle, artifact, quality, review, seal, and routing under RLS.
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

class VehicleRecordResponse(BaseModel):
    session_id: str
    event_id: str
    kind: str
    vin: str

class ArtifactRecordResponse(BaseModel):
    session_id: str
    event_id: str
    kind: str
    artifact_id: str
    content_hash: str

class QualityRecordResponse(BaseModel):
    session_id: str
    event_id: str
    kind: str
    score: float
    shot_slot: str

class ReviewRecordResponse(BaseModel):
    session_id: str
    event_id: str
    kind: str
    note: str

class SealRecordResponse(BaseModel):
    session_id: str
    event_id: str
    kind: str
    seal_hash: str

class RoutingRecordResponse(BaseModel):
    session_id: str
    event_id: str
    kind: str
    dealer_shortlist: list[str]

class RoutingResultResponse(BaseModel):
    session_id: str
    outcome: str
    selected_location_id: str | None
    candidates: list[str]

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

@router.post('/sessions/{session_id}/vehicle', response_model=VehicleRecordResponse)
async def record_vehicle(
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
    synthetic_vin = "1HGCM82633A004352"
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
                payload = json.dumps({"actor_id": binding.actor_id, "vin": synthetic_vin})
                cur.execute(
                    "SELECT faos.append_event(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (
                        binding.tenant_id,
                        session_id,
                        event_id,
                        next_seq,
                        "VEHICLE_RECORDED",
                        binding.actor_id,
                        "2026-10-31T00:00:00Z",
                        "vehicle_recorded",
                        payload,
                        "0.1",
                    ),
                )
            conn.commit()
    except Exception:
        raise HTTPException(status_code=500, detail='VEHICLE_RECORD_FAILED')
    return VehicleRecordResponse(session_id=session_id, event_id=event_id, kind="VEHICLE_RECORDED", vin=synthetic_vin)

@router.post('/sessions/{session_id}/artifact', response_model=ArtifactRecordResponse)
async def record_artifact(
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
    synthetic_artifact_id = str(uuid4())
    synthetic_hash = "sha256:9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"
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
                payload = json.dumps({
                    "actor_id": binding.actor_id,
                    "artifact_id": synthetic_artifact_id,
                    "content_hash": synthetic_hash,
                })
                cur.execute(
                    "SELECT faos.append_event(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (
                        binding.tenant_id,
                        session_id,
                        event_id,
                        next_seq,
                        "ARTIFACT_REGISTERED",
                        binding.actor_id,
                        "2026-10-31T00:00:00Z",
                        "artifact_registered",
                        payload,
                        "0.1",
                    ),
                )
            conn.commit()
    except Exception:
        raise HTTPException(status_code=500, detail='ARTIFACT_RECORD_FAILED')
    return ArtifactRecordResponse(
        session_id=session_id,
        event_id=event_id,
        kind="ARTIFACT_REGISTERED",
        artifact_id=synthetic_artifact_id,
        content_hash=synthetic_hash,
    )

@router.post('/sessions/{session_id}/quality', response_model=QualityRecordResponse)
async def record_quality(
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
    synthetic_score = 0.87
    synthetic_slot = "front-left-damage"
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
                payload = json.dumps({
                    "actor_id": binding.actor_id,
                    "score": synthetic_score,
                    "shot_slot": synthetic_slot,
                })
                cur.execute(
                    "SELECT faos.append_event(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (
                        binding.tenant_id,
                        session_id,
                        event_id,
                        next_seq,
                        "QUALITY_RECORDED",
                        binding.actor_id,
                        "2026-10-31T00:00:00Z",
                        "quality_recorded",
                        payload,
                        "0.1",
                    ),
                )
            conn.commit()
    except Exception:
        raise HTTPException(status_code=500, detail='QUALITY_RECORD_FAILED')
    return QualityRecordResponse(
        session_id=session_id,
        event_id=event_id,
        kind="QUALITY_RECORDED",
        score=synthetic_score,
        shot_slot=synthetic_slot,
    )

@router.post('/sessions/{session_id}/review', response_model=ReviewRecordResponse)
async def record_review(
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
    synthetic_note = "human-review-required"
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
                payload = json.dumps({
                    "actor_id": binding.actor_id,
                    "note": synthetic_note,
                })
                cur.execute(
                    "SELECT faos.append_event(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (
                        binding.tenant_id,
                        session_id,
                        event_id,
                        next_seq,
                        "REVIEW_RECORDED",
                        binding.actor_id,
                        "2026-10-31T00:00:00Z",
                        "review_recorded",
                        payload,
                        "0.1",
                    ),
                )
            conn.commit()
    except Exception:
        raise HTTPException(status_code=500, detail='REVIEW_RECORD_FAILED')
    return ReviewRecordResponse(
        session_id=session_id,
        event_id=event_id,
        kind="REVIEW_RECORDED",
        note=synthetic_note,
    )

@router.post('/sessions/{session_id}/seal', response_model=SealRecordResponse)
async def record_seal(
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
    synthetic_seal_hash = "sha256:seal-synthetic-0000000000000000000000000000000000000000000000000000000000000000"
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
                payload = json.dumps({
                    "actor_id": binding.actor_id,
                    "seal_hash": synthetic_seal_hash,
                })
                cur.execute(
                    "SELECT faos.append_event(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (
                        binding.tenant_id,
                        session_id,
                        event_id,
                        next_seq,
                        "MANIFEST_SEALED",
                        binding.actor_id,
                        "2026-10-31T00:00:00Z",
                        "manifest_sealed",
                        payload,
                        "0.1",
                    ),
                )
            conn.commit()
    except Exception:
        raise HTTPException(status_code=500, detail='SEAL_RECORD_FAILED')
    return SealRecordResponse(
        session_id=session_id,
        event_id=event_id,
        kind="MANIFEST_SEALED",
        seal_hash=synthetic_seal_hash,
    )

@router.post('/sessions/{session_id}/routing', response_model=RoutingRecordResponse)
async def record_routing(
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
                # Select locations with remaining capacity, inside policy radius, ordered by distance
                cur.execute("""
                    SELECT lc.location_id
                    FROM faos.location_capacity lc
                    JOIN faos.dealer_locations dl ON dl.location_id = lc.location_id AND dl.tenant_id = lc.tenant_id
                    LEFT JOIN (
                        SELECT location_id, COUNT(*) AS active_count
                        FROM faos.capacity_reservations
                        WHERE status = 'ACTIVE'
                        GROUP BY location_id
                    ) cr ON cr.location_id = lc.location_id
                    CROSS JOIN (
                        SELECT service_radius_meters
                        FROM faos.routing_policies
                        WHERE tenant_id = %s
                        ORDER BY created_at DESC
                        LIMIT 1
                    ) rp
                    WHERE lc.tenant_id = %s
                      AND (lc.capacity - COALESCE(cr.active_count, 0)) > 0
                      AND dl.geom IS NOT NULL
                      AND ST_DWithin(
                            dl.geom::geography,
                            ST_SetSRID(ST_MakePoint(-98.55, 29.45), 4326)::geography,
                            rp.service_radius_meters
                          )
                    ORDER BY dl.geom <-> ST_SetSRID(ST_MakePoint(-98.55, 29.45), 4326)
                    LIMIT 2
                """, (binding.tenant_id, binding.tenant_id))
                available = [str(row[0]) for row in cur.fetchall()]
                # Create reservations for the selected locations
                request_digest = f"routing-{session_id}"
                for loc_id in available:
                    cur.execute("""
                        INSERT INTO faos.capacity_reservations
                            (tenant_id, reservation_id, location_id, request_digest, status, expires_at)
                        VALUES (%s, %s, %s, %s, 'ACTIVE', now() + interval '4 hours')
                        ON CONFLICT (tenant_id, location_id, request_digest) DO NOTHING
                    """, (binding.tenant_id, str(uuid4()), loc_id, request_digest))
                # Persist the routing result
                outcome = "ROUTED" if available else "HUMAN_REVIEW"
                selected = available[0] if available else None
                cur.execute("""
                    INSERT INTO faos.routing_results
                        (tenant_id, result_id, request_digest, policy_version, outcome, selected_location_id, candidates_json, exclusion_reasons_json)
                    VALUES (%s, %s, %s, 'v1-synthetic', %s, %s, %s, %s)
                    ON CONFLICT (tenant_id, request_digest) DO NOTHING
                """, (
                    binding.tenant_id,
                    str(uuid4()),
                    request_digest,
                    outcome,
                    selected,
                    json.dumps(available),
                    json.dumps([]),
                ))
                # Append the event
                cur.execute(
                    "SELECT COALESCE(MAX(sequence), 0) FROM faos.events WHERE session_id = %s",
                    (session_id,),
                )
                next_seq = cur.fetchone()[0] + 1
                event_id = str(uuid4())
                payload = json.dumps({
                    "actor_id": binding.actor_id,
                    "dealer_shortlist": available,
                })
                cur.execute(
                    "SELECT faos.append_event(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (
                        binding.tenant_id,
                        session_id,
                        event_id,
                        next_seq,
                        "ROUTING_REQUESTED",
                        binding.actor_id,
                        "2026-10-31T00:00:00Z",
                        "routing_requested",
                        payload,
                        "0.1",
                    ),
                )
            conn.commit()
    except Exception:
        raise HTTPException(status_code=500, detail='ROUTING_RECORD_FAILED')
    return RoutingRecordResponse(
        session_id=session_id,
        event_id=event_id,
        kind="ROUTING_REQUESTED",
        dealer_shortlist=available,
    )

@router.get('/sessions/{session_id}/routing', response_model=RoutingResultResponse)
async def get_routing(
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
        with psycopg.connect(db_url, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT set_config('faos.tenant_id', %s, true)", (str(binding.tenant_id),))
                request_digest = f"routing-{session_id}"
                cur.execute("""
                    SELECT outcome, selected_location_id, candidates_json
                    FROM faos.routing_results
                    WHERE tenant_id = %s AND request_digest = %s
                """, (binding.tenant_id, request_digest))
                row = cur.fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail='ROUTING_NOT_FOUND')
                candidates = json.loads(row[2]) if row[2] else []
                return RoutingResultResponse(
                    session_id=session_id,
                    outcome=row[0],
                    selected_location_id=str(row[1]) if row[1] else None,
                    candidates=candidates,
                )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail='ROUTING_READ_FAILED')

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
