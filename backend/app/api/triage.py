"""
Layer 3 API — itemized estimate, valuation, adjudication.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from backend.app.triage.adjudicate import Adjudicator
from config import forensic_constants as C
from backend.app.security import require_internal_service

router = APIRouter(prefix="/api/v1/triage", tags=["triage"])
_adj = Adjudicator()


class DetectionIn(BaseModel):
    class_name: str = "dent"
    confidence: float = 0.7
    zone: str = "front"


class DepthIn(BaseModel):
    mean_depth_cm: float = 10.0
    volume_cm3: float = 2000.0
    zone: str = "front"


class AdjudicateRequest(BaseModel):
    session_id: str
    detections: List[DetectionIn] = Field(default_factory=list)
    depths: List[DepthIn] = Field(default_factory=list)
    r_struct: float = Field(0.3, ge=0, le=1)
    age_years: float = Field(5.0, ge=0, le=40)
    state_code: str = "TX"
    region: str = "TX"
    layer2_fork: Optional[str] = None
    layer2_notes: Optional[List[str]] = None
    physics_ai_disagree: bool = False
    gps_accuracy_m: Optional[float] = 15.0
    master_hash_valid: bool = True
    chain_coverage: float = 1.0
    chain_uniqueness: float = 1.0
    meta_completeness: float = 1.0
    internal_acv_a: Optional[float] = 18500.0
    internal_acv_b: Optional[float] = 17800.0
    internal_acv_c: Optional[float] = 19200.0
    salvage_estimate: float = 0.0
    prefer_capa: bool = True


@router.get("/health")
def triage_health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "layer": 3,
        "constants_version": C.VERSION,
        "modules": [
            "parts_catalog_resolver",
            "internal_acv",
            "rtv_51_jurisdictions",
            "s_i_geometric",
            "fraud_flags",
            "adjudicator",
        ],
    }


@router.post("/adjudicate", dependencies=[Depends(require_internal_service)])
def adjudicate(body: AdjudicateRequest) -> Dict[str, Any]:
    result = _adj.adjudicate(
        body.session_id,
        detections=[d.model_dump() for d in body.detections],
        depths=[d.model_dump() for d in body.depths],
        r_struct=body.r_struct,
        age_years=body.age_years,
        state_code=body.state_code,
        region=body.region,
        layer2_fork=body.layer2_fork,
        layer2_notes=body.layer2_notes,
        physics_ai_disagree=body.physics_ai_disagree,
        gps_accuracy_m=body.gps_accuracy_m,
        master_hash_valid=body.master_hash_valid,
        chain_coverage=body.chain_coverage,
        chain_uniqueness=body.chain_uniqueness,
        meta_completeness=body.meta_completeness,
        internal_acv_a=body.internal_acv_a,
        internal_acv_b=body.internal_acv_b,
        internal_acv_c=body.internal_acv_c,
        salvage_estimate=body.salvage_estimate,
        prefer_capa=body.prefer_capa,
    )
    est = result.estimate
    return {
        "session_id": result.session_id,
        "final_fork": result.final_fork,
        "final_tier": result.final_tier,
        "hold_for_review": result.hold_for_review,
        "plain_english": result.plain_english,
        "estimate": {
            "lines": [
                {
                    "part_number": ln.part_number,
                    "name": ln.name,
                    "zone": ln.zone,
                    "damage_type": ln.damage_type,
                    "repair_decision": ln.repair_decision,
                    "decision_reason": ln.decision_reason,
                    "oem_price_usd": ln.oem_price_usd,
                    "capa_price_usd": ln.capa_price_usd,
                    "chosen_price_usd": ln.chosen_price_usd,
                    "price_track": ln.price_track,
                    "labor_hours": ln.labor_hours,
                    "labor_cost_usd": ln.labor_cost_usd,
                    "paint_cost_usd": ln.paint_cost_usd,
                    "adas_usd": ln.adas_usd,
                    "hidden_damage_usd": ln.hidden_damage_usd,
                    "line_total_usd": ln.line_total_usd,
                    "catalog_priced": ln.catalog_priced,
                }
                for ln in est.lines
            ],
            "parts_subtotal": est.parts_subtotal,
            "labor_subtotal": est.labor_subtotal,
            "paint_subtotal": est.paint_subtotal,
            "materials_subtotal": est.materials_subtotal,
            "adas_subtotal": est.adas_subtotal,
            "hidden_damage_subtotal": est.hidden_damage_subtotal,
            "tax_usd": est.tax_usd,
            "total_repair_cost": est.total_repair_cost,
            "notes": est.notes,
        },
        "acv": {
            "acv_baseline": result.acv.acv_baseline,
            "acv_adjusted": result.acv.acv_adjusted,
            "p_s": result.acv.p_s,
            "r_struct": result.acv.r_struct,
            "claim2car_price": result.acv.claim2car_price,
            "method": result.acv.method,
            "comps": result.acv.comps,
        },
        "rtv": {
            "rtv_forensic": result.rtv.rtv_forensic,
            "state_code": result.rtv.state_code,
            "state_threshold": result.rtv.state_threshold,
            "mode": result.rtv.mode,
            "tier": result.rtv.tier,
            "commercial_fork": result.rtv.commercial_fork,
            "borderline": result.rtv.borderline,
            "reason": result.rtv.reason,
        },
        "integrity": {
            "s_i": result.integrity.s_i,
            "c_gps": result.integrity.c_gps,
            "c_hash": result.integrity.c_hash,
            "c_meta": result.integrity.c_meta,
            "tier": result.integrity.tier,
            "all_or_nothing_collapse": result.integrity.all_or_nothing_collapse,
        },
        "fraud": {
            "flags": result.fraud.flags,
            "risk_score": result.fraud.risk_score,
        },
        "trace": result.trace,
        "formula_version": result.formula_version,
    }
