"""
Dispatch + public verify API (Layers 6/7).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.app.anchor.ledger import LEDGER
from backend.app.dispatch.dispatcher import build_dispatch
from backend.app.dispatch.redaction import redact_payload
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


@router.get("/api/v1/dispatch/health")
def dispatch_health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "layer": "6/7",
        "constants_version": C.VERSION,
        "packages": ["owner", "dealer", "shop", "carrier"],
        "verify": "/api/v1/verify/",
        "anchor": "internal_ledger",
    }


@router.post("/api/v1/dispatch/build")
def dispatch_build(body: DispatchRequest) -> Dict[str, Any]:
    try:
        result = build_dispatch(
            body.adjudication,
            photo_hashes=body.photo_hashes,
            vin=body.vin,
            vehicle=body.vehicle.model_dump() if body.vehicle else None,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    packages = []
    for p in result.packages:
        packages.append(
            {
                "role": p.role,
                "label": p.label,
                "payload": p.payload,
                "dossier_text": p.dossier.plain_text[:4000],
                "dossier_pages": [
                    {"number": pg.number, "title": pg.title} for pg in p.dossier.pages
                ],
                "has_acord_xml": p.acord_xml is not None,
                "acord_xml_preview": (p.acord_xml[:1500] if p.acord_xml else None),
            }
        )
    return {
        "session_id": result.session_id,
        "anchor": result.anchor,
        "public_verify_path": result.public_verify_path,
        "packages": packages,
        "formula_version": C.VERSION,
        "owner_payout": None,
        "operator_payout_usd": C.OPERATOR_PAYOUT_USD,
    }


@router.post("/api/v1/dispatch/redact")
def dispatch_redact(role: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    return redact_payload(role, payload)


@router.post("/api/v1/verify/")
@router.post("/api/verify/")
def public_verify(body: VerifyRequest) -> Dict[str, Any]:
    """Public verification endpoint — no auth."""
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
