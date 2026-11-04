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

# ... (full file content truncated in this thought for brevity, but in real call it would be the entire 28k) 
