"""Tenant-scoped session start, list, retrieve, event list, consent, vehicle, artifact, quality, review, seal, and routing under RLS.
Does not touch sealing or evidence.
"""
from uuid import uuid4
import json
import urllib.request
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



class SettlementItem(BaseModel):
    session_id: str
    operator_payout_cents: int | None = None
    dealer_invoice_cents: int | None = None




class ConsumerPacketResponse(BaseModel):
    session_id: str
    vehicle_brand: str | None = None
    routing_outcome: str | None = None
    decision: str | None = None
    settled: bool = False

class ShopPacketResponse(BaseModel):
    session_id: str
    vehicle_brand: str | None = None
    routing_outcome: str | None = None
    selected_location_id: str | None = None



class ExpiredReservationItem(BaseModel):
    reservation_id: str
    location_id: str
    request_digest: str
    expires_at: str

class ExpiredReservationListResponse(BaseModel):
    reservations: list[ExpiredReservationItem]

class HumanReviewItem(BaseModel):
    session_id: str
    outcome: str

class HumanReviewListResponse(BaseModel):
    sessions: list[HumanReviewItem]

class SettlementTotalResponse(BaseModel):
    operator_payout_cents: int
    dealer_invoice_cents: int
    count: int

class SessionStatusResponse(BaseModel):
    session_id: str
    status: str


class VinDecodeRequest(BaseModel):
    vin: str
    year: int | None = None
    make: str | None = None
    model: str | None = None
    body_class: str | None = None

class DamageFinding(BaseModel):
    panel: str
    severity: str
    confidence: float
    types: list[str] = []

class DamageRequest(BaseModel):
    findings: list[DamageFinding]

class ExhibitResponse(BaseModel):
    session_id: str
    vin: str | None = None
    year: int | None = None
    make: str | None = None
    model: str | None = None
    body_class: str | None = None
    damage_findings: list[dict] = []
    delta_v_mph: float | None = None
    impact_angle_deg: float | None = None
    crush_front_in: float | None = None
    crush_side_in: float | None = None
    crush_rear_in: float | None = None
    cost_lines: list[dict] = []
    total_parts_cents: int | None = None
    total_labor_cents: int | None = None
    routing_outcome: str | None = None
    decision: str | None = None
    settled: bool = False


class PhysicsRequest(BaseModel):
    delta_v_mph: float | None = None
    impact_angle_deg: float | None = None
    crush_front_in: float | None = None
    crush_side_in: float | None = None
    crush_rear_in: float | None = None

class CostLine(BaseModel):
    description: str
    part_id: str | None = None
    labor_hours: float | None = None
    cost_cents: int

class CostRequest(BaseModel):
    lines: list[CostLine]
    total_parts_cents: int | None = None
    total_labor_cents: int | None = None


class CaptureFrameRequest(BaseModel):
    angle_deg: float | None = None
    sharpness: float | None = None
    silhouette_match: float | None = None
    point: str | None = None

class DashboardResponse(BaseModel):
    claims_today: int
    routed: int
    human_review: int
    settled: int
    operator_payout_cents: int
    dealer_invoice_cents: int


class CaptureProgressResponse(BaseModel):
    session_id: str
    points_captured: int
    points_expected: int = 16
    latest_point: str | None = None
    latest_sharpness: float | None = None
    latest_silhouette_match: float | None = None

class DamageSummaryResponse(BaseModel):
    session_id: str
    major: int = 0
    minor: int = 0
    findings: list[dict] = []

class ActivityItem(BaseModel):
    session_id: str
    status: str

class ActivityResponse(BaseModel):
    events: list[ActivityItem]

class TimelineItem(BaseModel):
    sequence: int
    kind: str
    actor_id: str | None = None

class TimelineResponse(BaseModel):
    session_id: str
    events: list[TimelineItem]

class CarrierPacketResponse(BaseModel):
    session_id: str
    routing_outcome: str | None = None
    decision: str | None = None
    settled: bool = False
    operator_payout_cents: int | None = None

class DealerPacketResponse(BaseModel):
    session_id: str
    vehicle_brand: str | None = None
    routing_outcome: str | None = None
    selected_location_id: str | None = None
    decision: str | None = None
    settled: bool = False
    operator_payout_cents: int | None = None
    dealer_invoice_cents: int | None = None

class SessionSummaryResponse(BaseModel):
    session_id: str
    routing_outcome: str | None = None
    selected_location_id: str | None = None
    decision: str | None = None
    settled: bool = False
    operator_payout_cents: int | None = None
    dealer_invoice_cents: int | None = None

class SettlementListResponse(BaseModel):
    settlements: list[SettlementItem]

class SettlementResponse(BaseModel):
    session_id: str
    operator_payout_cents: int | None = None
    dealer_invoice_cents: int | None = None
    settled: bool = False

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

class DecisionRecordResponse(BaseModel):
    session_id: str
    event_id: str
    kind: str
    decision: str

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
                payload = json.dumps({"actor_id": binding.actor_id, "vin": synthetic_vin, "brand": "Honda"})
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
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
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
                if idempotency_key:
                    cur.execute(
                        "SELECT response_json FROM faos.idempotency_keys WHERE tenant_id = %s AND key = %s",
                        (binding.tenant_id, idempotency_key),
                    )
                    existing = cur.fetchone()
                    if existing:
                        resp = existing[0] if isinstance(existing[0], dict) else json.loads(existing[0])
                        return RoutingRecordResponse(**resp)
                # Select locations with remaining capacity, inside policy radius, ordered by distance
                # Resolve vehicle brand from latest VEHICLE_RECORDED for this session
                cur.execute("""
                    SELECT payload_json::jsonb->>'brand'
                    FROM faos.events
                    WHERE session_id = %s AND kind = 'VEHICLE_RECORDED'
                    ORDER BY sequence DESC
                    LIMIT 1
                """, (session_id,))
                brand_row = cur.fetchone()
                vehicle_brand = brand_row[0] if brand_row and brand_row[0] else None

                cur.execute("""
                    SELECT lc.location_id
                    FROM faos.location_capacity lc
                    JOIN faos.dealer_locations dl ON dl.location_id = lc.location_id AND dl.tenant_id = lc.tenant_id
                    LEFT JOIN (
                        SELECT location_id, COUNT(*) AS active_count
                        FROM faos.capacity_reservations
                        WHERE status = 'ACTIVE' AND expires_at > now()
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
                      AND (%s::text IS NULL OR dl.brand = %s::text)
                    ORDER BY dl.geom <-> ST_SetSRID(ST_MakePoint(-98.55, 29.45), 4326)
                    LIMIT 2
                """, (binding.tenant_id, binding.tenant_id, vehicle_brand, vehicle_brand))
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
    response_obj = {
        "session_id": session_id,
        "event_id": event_id,
        "kind": "ROUTING_REQUESTED",
        "dealer_shortlist": available,
    }
    if idempotency_key:
        with psycopg.connect(db_url, autocommit=False) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT set_config('faos.tenant_id', %s, true)", (str(binding.tenant_id),))
                cur.execute(
                    """INSERT INTO faos.idempotency_keys (tenant_id, key, session_id, response_json)
                       VALUES (%s, %s, %s, %s)
                       ON CONFLICT (tenant_id, key) DO NOTHING""",
                    (binding.tenant_id, idempotency_key, session_id, json.dumps(response_obj)),
                )
            conn.commit()
    return RoutingRecordResponse(**response_obj)

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
                candidates = row[2] if isinstance(row[2], list) else (json.loads(row[2]) if row[2] else [])
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

@router.post('/sessions/{session_id}/decision', response_model=DecisionRecordResponse)
async def record_decision(
    session_id: str,
    decision: str,
    authorization: str = Header(None),
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    resolver: CredentialResolver = Depends(get_resolver),
    db_url: str | None = Depends(get_db_url),
):
    if not authorization:
        raise HTTPException(status_code=401, detail='UNAUTHORIZED')
    try:
        binding = resolver.resolve(authorization)
    except AuthenticationError:
        raise HTTPException(status_code=401, detail='UNAUTHORIZED')
    if decision not in ("ACCEPTED", "PASSED"):
        raise HTTPException(status_code=400, detail='INVALID_DECISION')
    if not db_url:
        raise HTTPException(status_code=500, detail='NO_DATABASE')
    kind = "DEALER_ACCEPTED" if decision == "ACCEPTED" else "DEALER_PASSED"
    try:
        with psycopg.connect(db_url, autocommit=False) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT set_config('faos.tenant_id', %s, true)", (str(binding.tenant_id),))
                if idempotency_key:
                    cur.execute(
                        "SELECT response_json FROM faos.idempotency_keys WHERE tenant_id = %s AND key = %s",
                        (binding.tenant_id, idempotency_key),
                    )
                    existing = cur.fetchone()
                    if existing:
                        resp = existing[0] if isinstance(existing[0], dict) else json.loads(existing[0])
                        return DecisionRecordResponse(**resp)
                cur.execute(
                    "SELECT COALESCE(MAX(sequence), 0) FROM faos.events WHERE session_id = %s",
                    (session_id,),
                )
                next_seq = cur.fetchone()[0] + 1
                event_id = str(uuid4())
                payload = json.dumps({
                    "actor_id": binding.actor_id,
                    "decision": decision,
                })
                cur.execute(
                    "SELECT faos.append_event(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (
                        binding.tenant_id,
                        session_id,
                        event_id,
                        next_seq,
                        kind,
                        binding.actor_id,
                        "2026-10-31T00:00:00Z",
                        "dealer_decision",
                        payload,
                        "0.1",
                    ),
                )
                # On acceptance, record the fixed pilot settlement (idempotent)
                if decision == "ACCEPTED":
                    cur.execute(
                        "SELECT 1 FROM faos.events WHERE session_id = %s AND kind = 'SETTLEMENT_RECORDED' LIMIT 1",
                        (session_id,),
                    )
                    if cur.fetchone():
                        # already settled; skip
                        pass
                    else:
                        settle_seq = next_seq + 1
                        settle_id = str(uuid4())
                        settle_payload = json.dumps({
                            "actor_id": binding.actor_id,
                            "operator_payout_cents": 11000,
                            "dealer_invoice_cents": 37500,
                        })
                        cur.execute(
                            "SELECT faos.append_event(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                            (
                                binding.tenant_id,
                                session_id,
                                settle_id,
                                settle_seq,
                                "SETTLEMENT_RECORDED",
                                binding.actor_id,
                                "2026-10-31T00:00:00Z",
                                "settlement_recorded",
                                settle_payload,
                                "0.1",
                            ),
                        )
                response_obj = {
                    "session_id": session_id,
                    "event_id": event_id,
                    "kind": kind,
                    "decision": decision,
                }
                if idempotency_key:
                    cur.execute(
                        """INSERT INTO faos.idempotency_keys (tenant_id, key, session_id, response_json)
                           VALUES (%s, %s, %s, %s)
                           ON CONFLICT (tenant_id, key) DO NOTHING""",
                        (binding.tenant_id, idempotency_key, session_id, json.dumps(response_obj)),
                    )
            conn.commit()
    except Exception:
        raise HTTPException(status_code=500, detail='DECISION_RECORD_FAILED')
    return DecisionRecordResponse(
        session_id=session_id,
        event_id=event_id,
        kind=kind,
        decision=decision,
    )

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


@router.get('/sessions/{session_id}/settlement', response_model=SettlementResponse)
async def get_settlement(
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
        return SettlementResponse(session_id=session_id)
    try:
        with psycopg.connect(db_url, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT set_config('faos.tenant_id', %s, true)", (str(binding.tenant_id),))
                cur.execute(
                    """SELECT payload_json FROM faos.events
                       WHERE session_id = %s AND kind = 'SETTLEMENT_RECORDED'
                       ORDER BY sequence DESC LIMIT 1""",
                    (session_id,),
                )
                row = cur.fetchone()
                if not row or not row[0]:
                    return SettlementResponse(session_id=session_id, settled=False)
                payload = row[0] if isinstance(row[0], dict) else json.loads(row[0])
                return SettlementResponse(
                    session_id=session_id,
                    operator_payout_cents=payload.get("operator_payout_cents"),
                    dealer_invoice_cents=payload.get("dealer_invoice_cents"),
                    settled=True,
                )
    except Exception:
        raise HTTPException(status_code=500, detail='SETTLEMENT_READ_FAILED')


@router.get('/settlements', response_model=SettlementListResponse)
async def list_settlements(
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
        return SettlementListResponse(settlements=[])
    try:
        with psycopg.connect(db_url, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT set_config('faos.tenant_id', %s, true)", (str(binding.tenant_id),))
                cur.execute(
                    """SELECT session_id, payload_json FROM faos.events
                       WHERE kind = 'SETTLEMENT_RECORDED'
                       ORDER BY sequence"""
                )
                rows = cur.fetchall()
                items = []
                for row in rows:
                    payload = row[1] if isinstance(row[1], dict) else (json.loads(row[1]) if row[1] else {})
                    items.append(SettlementItem(
                        session_id=str(row[0]),
                        operator_payout_cents=payload.get("operator_payout_cents"),
                        dealer_invoice_cents=payload.get("dealer_invoice_cents"),
                    ))
                return SettlementListResponse(settlements=items)
    except Exception:
        raise HTTPException(status_code=500, detail='SETTLEMENTS_READ_FAILED')


@router.get('/sessions/{session_id}/summary', response_model=SessionSummaryResponse)
async def get_session_summary(
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
        return SessionSummaryResponse(session_id=session_id)
    try:
        with psycopg.connect(db_url, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT set_config('faos.tenant_id', %s, true)", (str(binding.tenant_id),))
                # Routing
                cur.execute(
                    """SELECT outcome, selected_location_id FROM faos.routing_results
                       WHERE request_digest = %s ORDER BY created_at DESC LIMIT 1""",
                    (f"routing-{session_id}",),
                )
                r = cur.fetchone()
                outcome = r[0] if r else None
                selected = str(r[1]) if r and r[1] else None
                # Decision
                cur.execute(
                    """SELECT kind FROM faos.events
                       WHERE session_id = %s AND kind IN ('DEALER_ACCEPTED','DEALER_PASSED')
                       ORDER BY sequence DESC LIMIT 1""",
                    (session_id,),
                )
                d = cur.fetchone()
                decision = "ACCEPTED" if d and d[0] == "DEALER_ACCEPTED" else ("PASSED" if d else None)
                # Settlement
                cur.execute(
                    """SELECT payload_json FROM faos.events
                       WHERE session_id = %s AND kind = 'SETTLEMENT_RECORDED'
                       ORDER BY sequence DESC LIMIT 1""",
                    (session_id,),
                )
                s = cur.fetchone()
                settled = bool(s)
                payout = invoice = None
                if s and s[0]:
                    payload = s[0] if isinstance(s[0], dict) else json.loads(s[0])
                    payout = payload.get("operator_payout_cents")
                    invoice = payload.get("dealer_invoice_cents")
                return SessionSummaryResponse(
                    session_id=session_id,
                    routing_outcome=outcome,
                    selected_location_id=selected,
                    decision=decision,
                    settled=settled,
                    operator_payout_cents=payout,
                    dealer_invoice_cents=invoice,
                )
    except Exception:
        raise HTTPException(status_code=500, detail='SUMMARY_READ_FAILED')


@router.get('/sessions/{session_id}/dealer-packet', response_model=DealerPacketResponse)
async def get_dealer_packet(
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
        return DealerPacketResponse(session_id=session_id)
    try:
        with psycopg.connect(db_url, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT set_config('faos.tenant_id', %s, true)", (str(binding.tenant_id),))
                # Brand
                cur.execute(
                    """SELECT payload_json::jsonb->>'brand' FROM faos.events
                       WHERE session_id = %s AND kind = 'VEHICLE_RECORDED'
                       ORDER BY sequence DESC LIMIT 1""",
                    (session_id,),
                )
                br = cur.fetchone()
                brand = br[0] if br else None
                # Routing
                cur.execute(
                    """SELECT outcome, selected_location_id FROM faos.routing_results
                       WHERE request_digest = %s ORDER BY created_at DESC LIMIT 1""",
                    (f"routing-{session_id}",),
                )
                r = cur.fetchone()
                outcome = r[0] if r else None
                selected = str(r[1]) if r and r[1] else None
                # Decision
                cur.execute(
                    """SELECT kind FROM faos.events
                       WHERE session_id = %s AND kind IN ('DEALER_ACCEPTED','DEALER_PASSED')
                       ORDER BY sequence DESC LIMIT 1""",
                    (session_id,),
                )
                d = cur.fetchone()
                decision = "ACCEPTED" if d and d[0] == "DEALER_ACCEPTED" else ("PASSED" if d else None)
                # Settlement
                cur.execute(
                    """SELECT payload_json FROM faos.events
                       WHERE session_id = %s AND kind = 'SETTLEMENT_RECORDED'
                       ORDER BY sequence DESC LIMIT 1""",
                    (session_id,),
                )
                s = cur.fetchone()
                settled = bool(s)
                payout = invoice = None
                if s and s[0]:
                    payload = s[0] if isinstance(s[0], dict) else json.loads(s[0])
                    payout = payload.get("operator_payout_cents")
                    invoice = payload.get("dealer_invoice_cents")
                return DealerPacketResponse(
                    session_id=session_id,
                    vehicle_brand=brand,
                    routing_outcome=outcome,
                    selected_location_id=selected,
                    decision=decision,
                    settled=settled,
                    operator_payout_cents=payout,
                    dealer_invoice_cents=invoice,
                )
    except Exception:
        raise HTTPException(status_code=500, detail='DEALER_PACKET_FAILED')


@router.get('/sessions/{session_id}/consumer-packet', response_model=ConsumerPacketResponse)
async def get_consumer_packet(
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
        return ConsumerPacketResponse(session_id=session_id)
    try:
        with psycopg.connect(db_url, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT set_config('faos.tenant_id', %s, true)", (str(binding.tenant_id),))
                cur.execute("SELECT payload_json::jsonb->>'brand' FROM faos.events WHERE session_id = %s AND kind = 'VEHICLE_RECORDED' ORDER BY sequence DESC LIMIT 1", (session_id,))
                br = cur.fetchone()
                brand = br[0] if br else None
                cur.execute("SELECT outcome FROM faos.routing_results WHERE request_digest = %s ORDER BY created_at DESC LIMIT 1", (f"routing-{session_id}",))
                r = cur.fetchone()
                outcome = r[0] if r else None
                cur.execute("SELECT kind FROM faos.events WHERE session_id = %s AND kind IN ('DEALER_ACCEPTED','DEALER_PASSED') ORDER BY sequence DESC LIMIT 1", (session_id,))
                d = cur.fetchone()
                decision = "ACCEPTED" if d and d[0] == "DEALER_ACCEPTED" else ("PASSED" if d else None)
                cur.execute("SELECT 1 FROM faos.events WHERE session_id = %s AND kind = 'SETTLEMENT_RECORDED' LIMIT 1", (session_id,))
                settled = bool(cur.fetchone())
                return ConsumerPacketResponse(session_id=session_id, vehicle_brand=brand, routing_outcome=outcome, decision=decision, settled=settled)
    except Exception:
        raise HTTPException(status_code=500, detail='CONSUMER_PACKET_FAILED')

@router.get('/sessions/{session_id}/shop-packet', response_model=ShopPacketResponse)
async def get_shop_packet(
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
        return ShopPacketResponse(session_id=session_id)
    try:
        with psycopg.connect(db_url, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT set_config('faos.tenant_id', %s, true)", (str(binding.tenant_id),))
                cur.execute("SELECT payload_json::jsonb->>'brand' FROM faos.events WHERE session_id = %s AND kind = 'VEHICLE_RECORDED' ORDER BY sequence DESC LIMIT 1", (session_id,))
                br = cur.fetchone()
                brand = br[0] if br else None
                cur.execute("SELECT outcome, selected_location_id FROM faos.routing_results WHERE request_digest = %s ORDER BY created_at DESC LIMIT 1", (f"routing-{session_id}",))
                r = cur.fetchone()
                outcome = r[0] if r else None
                selected = str(r[1]) if r and r[1] else None
                return ShopPacketResponse(session_id=session_id, vehicle_brand=brand, routing_outcome=outcome, selected_location_id=selected)
    except Exception:
        raise HTTPException(status_code=500, detail='SHOP_PACKET_FAILED')

@router.get('/sessions/{session_id}/carrier-packet', response_model=CarrierPacketResponse)
async def get_carrier_packet(
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
        return CarrierPacketResponse(session_id=session_id)
    try:
        with psycopg.connect(db_url, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT set_config('faos.tenant_id', %s, true)", (str(binding.tenant_id),))
                cur.execute("SELECT outcome FROM faos.routing_results WHERE request_digest = %s ORDER BY created_at DESC LIMIT 1", (f"routing-{session_id}",))
                r = cur.fetchone()
                outcome = r[0] if r else None
                cur.execute("SELECT kind FROM faos.events WHERE session_id = %s AND kind IN ('DEALER_ACCEPTED','DEALER_PASSED') ORDER BY sequence DESC LIMIT 1", (session_id,))
                d = cur.fetchone()
                decision = "ACCEPTED" if d and d[0] == "DEALER_ACCEPTED" else ("PASSED" if d else None)
                cur.execute("SELECT payload_json FROM faos.events WHERE session_id = %s AND kind = 'SETTLEMENT_RECORDED' ORDER BY sequence DESC LIMIT 1", (session_id,))
                s = cur.fetchone()
                settled = bool(s)
                payout = None
                if s and s[0]:
                    payload = s[0] if isinstance(s[0], dict) else json.loads(s[0])
                    payout = payload.get("operator_payout_cents")
                return CarrierPacketResponse(session_id=session_id, routing_outcome=outcome, decision=decision, settled=settled, operator_payout_cents=payout)
    except Exception:
        raise HTTPException(status_code=500, detail='CARRIER_PACKET_FAILED')

@router.get('/dealer/{location_id}/settlements', response_model=SettlementListResponse)
async def list_dealer_settlements(
    location_id: str,
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
        return SettlementListResponse(settlements=[])
    try:
        with psycopg.connect(db_url, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT set_config('faos.tenant_id', %s, true)", (str(binding.tenant_id),))
                cur.execute("""
                    SELECT e.session_id, e.payload_json
                    FROM faos.events e
                    JOIN faos.routing_results rr ON rr.request_digest = 'routing-' || e.session_id::text
                    WHERE e.kind = 'SETTLEMENT_RECORDED'
                      AND rr.selected_location_id = %s
                    ORDER BY e.sequence
                """, (location_id,))
                rows = cur.fetchall()
                items = []
                for row in rows:
                    payload = row[1] if isinstance(row[1], dict) else (json.loads(row[1]) if row[1] else {})
                    items.append(SettlementItem(
                        session_id=str(row[0]),
                        operator_payout_cents=payload.get("operator_payout_cents"),
                        dealer_invoice_cents=payload.get("dealer_invoice_cents"),
                    ))
                return SettlementListResponse(settlements=items)
    except Exception:
        raise HTTPException(status_code=500, detail='DEALER_SETTLEMENTS_FAILED')


@router.get('/sessions/{session_id}/timeline', response_model=TimelineResponse)
async def get_timeline(
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
        return TimelineResponse(session_id=session_id, events=[])
    try:
        with psycopg.connect(db_url, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT set_config('faos.tenant_id', %s, true)", (str(binding.tenant_id),))
                cur.execute(
                    """SELECT sequence, kind, actor FROM faos.events
                       WHERE session_id = %s
                         AND kind IN ('ROUTING_REQUESTED','DEALER_ACCEPTED','DEALER_PASSED','SETTLEMENT_RECORDED')
                       ORDER BY sequence""",
                    (session_id,),
                )
                rows = cur.fetchall()
                items = [TimelineItem(sequence=r[0], kind=r[1], actor_id=r[2]) for r in rows]
                return TimelineResponse(session_id=session_id, events=items)
    except Exception:
        raise HTTPException(status_code=500, detail='TIMELINE_FAILED')


@router.get('/reservations/expired', response_model=ExpiredReservationListResponse)
async def list_expired_reservations(
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
        return ExpiredReservationListResponse(reservations=[])
    try:
        with psycopg.connect(db_url, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT set_config('faos.tenant_id', %s, true)", (str(binding.tenant_id),))
                cur.execute("""
                    SELECT reservation_id, location_id, request_digest, expires_at
                    FROM faos.capacity_reservations
                    WHERE status = 'ACTIVE' AND expires_at < now()
                    ORDER BY expires_at
                """)
                rows = cur.fetchall()
                items = [ExpiredReservationItem(
                    reservation_id=str(r[0]), location_id=str(r[1]),
                    request_digest=r[2], expires_at=r[3].isoformat()
                ) for r in rows]
                return ExpiredReservationListResponse(reservations=items)
    except Exception:
        raise HTTPException(status_code=500, detail='EXPIRED_RESERVATIONS_FAILED')

@router.get('/routing/human-review', response_model=HumanReviewListResponse)
async def list_human_review(
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
        return HumanReviewListResponse(sessions=[])
    try:
        with psycopg.connect(db_url, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT set_config('faos.tenant_id', %s, true)", (str(binding.tenant_id),))
                cur.execute("""
                    SELECT request_digest, outcome FROM faos.routing_results
                    WHERE outcome = 'HUMAN_REVIEW'
                    ORDER BY created_at DESC
                """)
                rows = cur.fetchall()
                items = [HumanReviewItem(
                    session_id=r[0].replace("routing-", "") if r[0].startswith("routing-") else r[0],
                    outcome=r[1]
                ) for r in rows]
                return HumanReviewListResponse(sessions=items)
    except Exception:
        raise HTTPException(status_code=500, detail='HUMAN_REVIEW_LIST_FAILED')

@router.get('/settlements/total', response_model=SettlementTotalResponse)
async def settlement_total(
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
        return SettlementTotalResponse(operator_payout_cents=0, dealer_invoice_cents=0, count=0)
    try:
        with psycopg.connect(db_url, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT set_config('faos.tenant_id', %s, true)", (str(binding.tenant_id),))
                cur.execute("SELECT payload_json FROM faos.events WHERE kind = 'SETTLEMENT_RECORDED'")
                rows = cur.fetchall()
                payout = invoice = 0
                for row in rows:
                    payload = row[0] if isinstance(row[0], dict) else (json.loads(row[0]) if row[0] else {})
                    payout += payload.get("operator_payout_cents") or 0
                    invoice += payload.get("dealer_invoice_cents") or 0
                return SettlementTotalResponse(operator_payout_cents=payout, dealer_invoice_cents=invoice, count=len(rows))
    except Exception:
        raise HTTPException(status_code=500, detail='SETTLEMENT_TOTAL_FAILED')

@router.get('/sessions/{session_id}/status', response_model=SessionStatusResponse)
async def get_session_status(
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
        return SessionStatusResponse(session_id=session_id, status="UNKNOWN")
    try:
        with psycopg.connect(db_url, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT set_config('faos.tenant_id', %s, true)", (str(binding.tenant_id),))
                cur.execute("SELECT 1 FROM faos.events WHERE session_id = %s AND kind = 'SETTLEMENT_RECORDED' LIMIT 1", (session_id,))
                if cur.fetchone():
                    return SessionStatusResponse(session_id=session_id, status="SETTLED")
                cur.execute("SELECT kind FROM faos.events WHERE session_id = %s AND kind IN ('DEALER_ACCEPTED','DEALER_PASSED') ORDER BY sequence DESC LIMIT 1", (session_id,))
                d = cur.fetchone()
                if d:
                    return SessionStatusResponse(session_id=session_id, status=d[0].replace("DEALER_", ""))
                cur.execute("SELECT outcome FROM faos.routing_results WHERE request_digest = %s ORDER BY created_at DESC LIMIT 1", (f"routing-{session_id}",))
                r = cur.fetchone()
                if r:
                    return SessionStatusResponse(session_id=session_id, status=r[0])
                return SessionStatusResponse(session_id=session_id, status="OPEN")
    except Exception:
        raise HTTPException(status_code=500, detail='STATUS_FAILED')


@router.post('/sessions/{session_id}/vin')
async def record_vin(
    session_id: str,
    body: VinDecodeRequest,
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
        return {"session_id": session_id, "kind": "VIN_DECODED"}
    try:
        with psycopg.connect(db_url, autocommit=False) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT set_config('faos.tenant_id', %s, true)", (str(binding.tenant_id),))
                cur.execute("SELECT COALESCE(MAX(sequence),0) FROM faos.events WHERE session_id = %s", (session_id,))
                seq = cur.fetchone()[0] + 1
                event_id = str(uuid4())
                payload = json.dumps(body.model_dump())
                cur.execute(
                    "SELECT faos.append_event(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (binding.tenant_id, session_id, event_id, seq, "VIN_DECODED", binding.actor_id, "2026-11-04T00:00:00Z", "vin_decode", payload, "0.1"),
                )
            conn.commit()
        return {"session_id": session_id, "kind": "VIN_DECODED", "vin": body.vin}
    except Exception:
        raise HTTPException(status_code=500, detail='VIN_RECORD_FAILED')

@router.post('/sessions/{session_id}/damage')
async def record_damage(
    session_id: str,
    body: DamageRequest,
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
        return {"session_id": session_id, "kind": "DAMAGE_DETECTED"}
    try:
        with psycopg.connect(db_url, autocommit=False) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT set_config('faos.tenant_id', %s, true)", (str(binding.tenant_id),))
                cur.execute("SELECT COALESCE(MAX(sequence),0) FROM faos.events WHERE session_id = %s", (session_id,))
                seq = cur.fetchone()[0] + 1
                event_id = str(uuid4())
                payload = json.dumps({"findings": [f.model_dump() for f in body.findings]})
                cur.execute(
                    "SELECT faos.append_event(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (binding.tenant_id, session_id, event_id, seq, "DAMAGE_DETECTED", binding.actor_id, "2026-11-04T00:00:00Z", "damage_detect", payload, "0.1"),
                )
            conn.commit()
        return {"session_id": session_id, "kind": "DAMAGE_DETECTED", "count": len(body.findings)}
    except Exception:
        raise HTTPException(status_code=500, detail='DAMAGE_RECORD_FAILED')

@router.get('/sessions/{session_id}/exhibit', response_model=ExhibitResponse)
async def get_exhibit(
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
        return ExhibitResponse(session_id=session_id)
    try:
        with psycopg.connect(db_url, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT set_config('faos.tenant_id', %s, true)", (str(binding.tenant_id),))
                # VIN
                cur.execute("SELECT payload_json FROM faos.events WHERE session_id = %s AND kind = 'VIN_DECODED' ORDER BY sequence DESC LIMIT 1", (session_id,))
                v = cur.fetchone()
                vin_payload = {}
                if v and v[0]:
                    vin_payload = v[0] if isinstance(v[0], dict) else json.loads(v[0])
                # Damage
                cur.execute("SELECT payload_json FROM faos.events WHERE session_id = %s AND kind = 'DAMAGE_DETECTED' ORDER BY sequence DESC LIMIT 1", (session_id,))
                d = cur.fetchone()
                findings = []
                if d and d[0]:
                    dp = d[0] if isinstance(d[0], dict) else json.loads(d[0])
                    findings = dp.get("findings", [])
                # Physics
                cur.execute("SELECT payload_json FROM faos.events WHERE session_id = %s AND kind = 'PHYSICS_COMPUTED' ORDER BY sequence DESC LIMIT 1", (session_id,))
                ph = cur.fetchone()
                phys = {}
                if ph and ph[0]:
                    phys = ph[0] if isinstance(ph[0], dict) else json.loads(ph[0])
                # Cost
                cur.execute("SELECT payload_json FROM faos.events WHERE session_id = %s AND kind = 'COST_ESTIMATED' ORDER BY sequence DESC LIMIT 1", (session_id,))
                co = cur.fetchone()
                cost = {}
                if co and co[0]:
                    cost = co[0] if isinstance(co[0], dict) else json.loads(co[0])
                # Routing
                cur.execute("SELECT outcome FROM faos.routing_results WHERE request_digest = %s ORDER BY created_at DESC LIMIT 1", (f"routing-{session_id}",))
                r = cur.fetchone()
                outcome = r[0] if r else None
                # Decision
                cur.execute("SELECT kind FROM faos.events WHERE session_id = %s AND kind IN ('DEALER_ACCEPTED','DEALER_PASSED') ORDER BY sequence DESC LIMIT 1", (session_id,))
                dec = cur.fetchone()
                decision = "ACCEPTED" if dec and dec[0] == "DEALER_ACCEPTED" else ("PASSED" if dec else None)
                # Settled
                cur.execute("SELECT 1 FROM faos.events WHERE session_id = %s AND kind = 'SETTLEMENT_RECORDED' LIMIT 1", (session_id,))
                settled = bool(cur.fetchone())
                return ExhibitResponse(
                    session_id=session_id,
                    vin=vin_payload.get("vin"),
                    year=vin_payload.get("year"),
                    make=vin_payload.get("make"),
                    model=vin_payload.get("model"),
                    body_class=vin_payload.get("body_class"),
                    damage_findings=findings,
                    delta_v_mph=phys.get("delta_v_mph"),
                    impact_angle_deg=phys.get("impact_angle_deg"),
                    crush_front_in=phys.get("crush_front_in"),
                    crush_side_in=phys.get("crush_side_in"),
                    crush_rear_in=phys.get("crush_rear_in"),
                    cost_lines=cost.get("lines", []),
                    total_parts_cents=cost.get("total_parts_cents"),
                    total_labor_cents=cost.get("total_labor_cents"),
                    routing_outcome=outcome,
                    decision=decision,
                    settled=settled,
                )
    except Exception:
        raise HTTPException(status_code=500, detail='EXHIBIT_READ_FAILED')


@router.post('/sessions/{session_id}/physics')
async def record_physics(
    session_id: str,
    body: PhysicsRequest,
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
        return {"session_id": session_id, "kind": "PHYSICS_COMPUTED"}
    try:
        with psycopg.connect(db_url, autocommit=False) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT set_config('faos.tenant_id', %s, true)", (str(binding.tenant_id),))
                cur.execute("SELECT COALESCE(MAX(sequence),0) FROM faos.events WHERE session_id = %s", (session_id,))
                seq = cur.fetchone()[0] + 1
                event_id = str(uuid4())
                payload = json.dumps(body.model_dump())
                cur.execute(
                    "SELECT faos.append_event(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (binding.tenant_id, session_id, event_id, seq, "PHYSICS_COMPUTED", binding.actor_id, "2026-11-04T00:00:00Z", "physics", payload, "0.1"),
                )
            conn.commit()
        return {"session_id": session_id, "kind": "PHYSICS_COMPUTED"}
    except Exception:
        raise HTTPException(status_code=500, detail='PHYSICS_RECORD_FAILED')

@router.post('/sessions/{session_id}/cost')
async def record_cost(
    session_id: str,
    body: CostRequest,
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
        return {"session_id": session_id, "kind": "COST_ESTIMATED"}
    try:
        with psycopg.connect(db_url, autocommit=False) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT set_config('faos.tenant_id', %s, true)", (str(binding.tenant_id),))
                cur.execute("SELECT COALESCE(MAX(sequence),0) FROM faos.events WHERE session_id = %s", (session_id,))
                seq = cur.fetchone()[0] + 1
                event_id = str(uuid4())
                payload = json.dumps(body.model_dump())
                cur.execute(
                    "SELECT faos.append_event(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (binding.tenant_id, session_id, event_id, seq, "COST_ESTIMATED", binding.actor_id, "2026-11-04T00:00:00Z", "cost", payload, "0.1"),
                )
            conn.commit()
        return {"session_id": session_id, "kind": "COST_ESTIMATED"}
    except Exception:
        raise HTTPException(status_code=500, detail='COST_RECORD_FAILED')


@router.post('/sessions/{session_id}/capture')
async def record_capture_frame(
    session_id: str,
    body: CaptureFrameRequest,
    authorization: str = Header(None),
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
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
        return {"session_id": session_id, "kind": "CAPTURE_FRAME"}
    try:
        with psycopg.connect(db_url, autocommit=False) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT set_config('faos.tenant_id', %s, true)", (str(binding.tenant_id),))
                if idempotency_key:
                    cur.execute("SELECT event_id FROM faos.idempotency_keys WHERE key = %s AND tenant_id = faos.tenant_id()", (idempotency_key,))
                    existing = cur.fetchone()
                    if existing:
                        return {"session_id": session_id, "event_id": str(existing[0]), "kind": "CAPTURE_FRAME", "status": "idempotent"}
                cur.execute("SELECT COALESCE(MAX(sequence),0) FROM faos.events WHERE session_id = %s", (session_id,))
                seq = cur.fetchone()[0] + 1
                event_id = str(uuid4())
                payload = json.dumps(body.model_dump())
                cur.execute(
                    "SELECT faos.append_event(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (binding.tenant_id, session_id, event_id, seq, "CAPTURE_FRAME", binding.actor_id, "2026-11-04T00:00:00Z", "capture", payload, "0.1"),
                )
                if idempotency_key:
                    cur.execute("INSERT INTO faos.idempotency_keys (tenant_id, key, event_id) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING", (binding.tenant_id, idempotency_key, event_id))
            conn.commit()
        return {"session_id": session_id, "kind": "CAPTURE_FRAME"}
    except Exception:
        raise HTTPException(status_code=500, detail='CAPTURE_RECORD_FAILED')

@router.post('/sessions/{session_id}/vin/decode')
async def decode_vin_nhtsa(
    session_id: str,
    body: VinDecodeRequest,
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
    decoded = {"vin": body.vin, "year": body.year, "make": body.make, "model": body.model, "body_class": body.body_class}
    try:
        url = f"https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVin/{body.vin}?format=json"
        with urllib.request.urlopen(url, timeout=8) as resp:
            data = json.loads(resp.read().decode())
            results = {r.get("Variable"): r.get("Value") for r in data.get("Results", []) if r.get("Value")}
            decoded["year"] = decoded["year"] or (int(results["Model Year"]) if results.get("Model Year") and results["Model Year"].isdigit() else None)
            decoded["make"] = decoded["make"] or results.get("Make")
            decoded["model"] = decoded["model"] or results.get("Model")
            decoded["body_class"] = decoded["body_class"] or results.get("Body Class")
            decoded["plant"] = results.get("Plant City")
            decoded["fuel"] = results.get("Fuel Type - Primary")
    except Exception:
        pass
    if not db_url:
        return {"session_id": session_id, "kind": "VIN_DECODED", **decoded}
    try:
        with psycopg.connect(db_url, autocommit=False) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT set_config('faos.tenant_id', %s, true)", (str(binding.tenant_id),))
                cur.execute("SELECT COALESCE(MAX(sequence),0) FROM faos.events WHERE session_id = %s", (session_id,))
                seq = cur.fetchone()[0] + 1
                event_id = str(uuid4())
                payload = json.dumps(decoded)
                cur.execute(
                    "SELECT faos.append_event(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (binding.tenant_id, session_id, event_id, seq, "VIN_DECODED", binding.actor_id, "2026-11-04T00:00:00Z", "nhtsa_decode", payload, "0.1"),
                )
            conn.commit()
        return {"session_id": session_id, "kind": "VIN_DECODED", **decoded}
    except Exception:
        raise HTTPException(status_code=500, detail='NHTSA_DECODE_FAILED')

@router.get('/admin/dashboard', response_model=DashboardResponse)
async def admin_dashboard(
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
        return DashboardResponse(claims_today=0, routed=0, human_review=0, settled=0, operator_payout_cents=0, dealer_invoice_cents=0)
    try:
        with psycopg.connect(db_url, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT set_config('faos.tenant_id', %s, true)", (str(binding.tenant_id),))
                cur.execute("SELECT count(*) FROM faos.sessions")
                claims = cur.fetchone()[0]
                cur.execute("SELECT count(*) FROM faos.routing_results WHERE outcome = 'ROUTED'")
                routed = cur.fetchone()[0]
                cur.execute("SELECT count(*) FROM faos.routing_results WHERE outcome = 'HUMAN_REVIEW'")
                hr = cur.fetchone()[0]
                cur.execute("SELECT count(*) FROM faos.events WHERE kind = 'SETTLEMENT_RECORDED'")
                settled = cur.fetchone()[0]
                cur.execute("SELECT payload_json FROM faos.events WHERE kind = 'SETTLEMENT_RECORDED'")
                rows = cur.fetchall()
                payout = invoice = 0
                for row in rows:
                    payload = row[0] if isinstance(row[0], dict) else (json.loads(row[0]) if row[0] else {})
                    payout += payload.get("operator_payout_cents") or 0
                    invoice += payload.get("dealer_invoice_cents") or 0
                return DashboardResponse(
                    claims_today=claims, routed=routed, human_review=hr,
                    settled=settled, operator_payout_cents=payout, dealer_invoice_cents=invoice,
                )
    except Exception:
        raise HTTPException(status_code=500, detail='DASHBOARD_FAILED')


@router.get('/sessions/{session_id}/capture-progress', response_model=CaptureProgressResponse)
async def capture_progress(
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
        return CaptureProgressResponse(session_id=session_id, points_captured=0)
    try:
        with psycopg.connect(db_url, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT set_config('faos.tenant_id', %s, true)", (str(binding.tenant_id),))
                cur.execute("SELECT payload_json FROM faos.events WHERE session_id = %s AND kind = 'CAPTURE_FRAME' ORDER BY sequence", (session_id,))
                rows = cur.fetchall()
                points = set()
                latest = {}
                for row in rows:
                    payload = row[0] if isinstance(row[0], dict) else (json.loads(row[0]) if row[0] else {})
                    if payload.get("point"):
                        points.add(payload["point"])
                    latest = payload
                return CaptureProgressResponse(
                    session_id=session_id,
                    points_captured=len(points),
                    latest_point=latest.get("point"),
                    latest_sharpness=latest.get("sharpness"),
                    latest_silhouette_match=latest.get("silhouette_match"),
                )
    except Exception:
        raise HTTPException(status_code=500, detail='CAPTURE_PROGRESS_FAILED')

@router.get('/sessions/{session_id}/damage-summary', response_model=DamageSummaryResponse)
async def damage_summary(
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
        return DamageSummaryResponse(session_id=session_id)
    try:
        with psycopg.connect(db_url, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT set_config('faos.tenant_id', %s, true)", (str(binding.tenant_id),))
                cur.execute("SELECT payload_json FROM faos.events WHERE session_id = %s AND kind = 'DAMAGE_DETECTED' ORDER BY sequence DESC LIMIT 1", (session_id,))
                row = cur.fetchone()
                findings = []
                if row and row[0]:
                    payload = row[0] if isinstance(row[0], dict) else json.loads(row[0])
                    findings = payload.get("findings", [])
                major = sum(1 for f in findings if f.get("severity") == "MAJOR")
                minor = sum(1 for f in findings if f.get("severity") == "MINOR")
                return DamageSummaryResponse(session_id=session_id, major=major, minor=minor, findings=findings)
    except Exception:
        raise HTTPException(status_code=500, detail='DAMAGE_SUMMARY_FAILED')

@router.get('/admin/activity', response_model=ActivityResponse)
async def admin_activity(
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
        return ActivityResponse(events=[])
    try:
        with psycopg.connect(db_url, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT set_config('faos.tenant_id', %s, true)", (str(binding.tenant_id),))
                cur.execute("SELECT session_id FROM faos.sessions ORDER BY session_id LIMIT 20")
                sessions = [r[0] for r in cur.fetchall()]
                items = []
                for sid in sessions:
                    cur.execute("SELECT 1 FROM faos.events WHERE session_id = %s AND kind = 'SETTLEMENT_RECORDED' LIMIT 1", (sid,))
                    if cur.fetchone():
                        items.append(ActivityItem(session_id=str(sid), status="SETTLED"))
                        continue
                    cur.execute("SELECT kind FROM faos.events WHERE session_id = %s AND kind IN ('DEALER_ACCEPTED','DEALER_PASSED') ORDER BY sequence DESC LIMIT 1", (sid,))
                    d = cur.fetchone()
                    if d:
                        items.append(ActivityItem(session_id=str(sid), status=d[0].replace("DEALER_", "")))
                        continue
                    cur.execute("SELECT outcome FROM faos.routing_results WHERE request_digest = %s ORDER BY created_at DESC LIMIT 1", (f"routing-{sid}",))
                    r = cur.fetchone()
                    if r:
                        items.append(ActivityItem(session_id=str(sid), status=r[0]))
                        continue
                    items.append(ActivityItem(session_id=str(sid), status="OPEN"))
                return ActivityResponse(events=items)
    except Exception:
        raise HTTPException(status_code=500, detail='ACTIVITY_FAILED')
