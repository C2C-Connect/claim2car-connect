"""Dispatch API: HTTP package construction disabled pending trusted provenance."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.app.anchor.ledger import LEDGER
from backend.app.dispatch.dispatcher import build_dispatch
from backend.app.dispatch.redaction import redact_payload
from backend.app.security import require_service_token
from config import forensic_constants as C

router = APIRouter(tags=["dispatch"])


class VehicleIn(BaseModel):
    year: Optional[int] = None
    make: Optional[str] = None
    model: Optional[str] = None
    trim: Optional[str] = None


class DispatchRequest(BaseModel):
    adjudication: Dict[str, Any]
    vin: str = ""
    vehicle: Optional[VehicleIn] = None
    photo_hashes: Optional[List[str]] = None


class VerifyRequest(BaseModel):
    session_id: str
    merkle_root: str
    master_hash: str


class RedactRequest(BaseModel):
    role: str = Field(..., min_length=1, max_length=32)
    payload: Dict[str, Any]


@router.get("/api/v1/dispatch/health")
def dispatch_health() -> Dict[str, Any]:
    return {
        "status": "disabled",
        "layer": "6/7",
        "constants_version": C.VERSION,
        "packages": ["owner", "dealer", "shop", "carrier"],
        "verify": "/api/v1/verify/",
        "anchor": "internal_ledger",
        "build_enabled": False,
        "redact_auth": "bearer_required",
        "reason": "trusted_provenance_not_integrated",
    }


@router.post("/api/v1/dispatch/build")
def dispatch_build(body: DispatchRequest) -> Dict[str, Any]:
    raise HTTPException(
        status_code=503,
        detail={
            "code": "dispatch_build_disabled",
            "message": "HTTP package construction is disabled pending server-owned authorization and trusted provenance integration.",
        },
        headers={"Cache-Control": "no-store"},
    )


@router.post("/api/v1/dispatch/redact")
def dispatch_redact(
    body: RedactRequest,
    _token: str = Depends(require_service_token),
) -> Dict[str, Any]:
    role = (body.role or "").strip().lower()
    if role not in {"owner", "dealer", "shop", "carrier", "qc", "admin"}:
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_role", "message": f"Unsupported role: {body.role}"},
            headers={"Cache-Control": "no-store"},
        )
    return redact_payload(role, body.payload)


@router.post("/api/v1/verify/")
@router.post("/api/verify/")
def public_verify(body: VerifyRequest) -> Dict[str, Any]:
    result = LEDGER.verify(body.session_id, body.merkle_root, body.master_hash)
    result["kill_switch"] = LEDGER.kill_switch
    result["formula_version"] = C.VERSION
    return result


@router.get("/api/v1/verify/{session_id}")
def public_verify_get(session_id: str) -> Dict[str, Any]:
    rec = LEDGER.get(session_id)
    if not rec:
        raise HTTPException(status_code=404, detail="session not anchored")
    return {
        "session_id": session_id,
        "anchored": True,
        "merkle_root": rec.merkle_root,
        "master_hash": rec.master_hash,
        "anchored_at": rec.timestamp_unix,
        "entry_hash": rec.entry_hash,
        "kill_switch": LEDGER.kill_switch,
        "note": "POST /api/v1/verify/ with recomputed hashes to validate",
    }
