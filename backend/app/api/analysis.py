"""
Analysis API routes — Layer 2.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.app.analysis.pipeline import AnalysisPipeline, AnalysisRequest
from backend.app.physics.darci import DarciInput, ZoneInput, run_darci
from config import forensic_constants as C

router = APIRouter(prefix="/api/v1/analysis", tags=["analysis"])
_pipeline = AnalysisPipeline()


class ZoneIn(BaseModel):
    zone: str = "front"
    depth_cm: float = 0.0
    area_cm2: float = 0.0
    material: str = "mild_steel"


class PhysicsOnlyRequest(BaseModel):
    mass_kg: float = Field(..., ge=500, le=5000)
    velocity_kph: float = Field(..., ge=0, le=250)
    zones: List[ZoneIn] = Field(default_factory=lambda: [ZoneIn()])
    strain_rate_proxy: float = 1.0


class AnalyzeRequest(BaseModel):
    session_id: str
    mass_kg: float = Field(..., ge=500, le=5000)
    velocity_kph: float = Field(..., ge=0, le=250)
    # base64 images optional in M3; empty list runs physics + stub vision
    photo_count: int = Field(default=1, ge=0, le=32)
    zone_hints: Optional[List[str]] = None
    materials: Optional[List[str]] = None
    strain_rate_proxy: float = 1.0


@router.get("/health")
def analysis_health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "layer": 2,
        "constants_version": C.VERSION,
        "ensemble_weights": {
            "physics": C.ENSEMBLE_PHYSICS_WEIGHT,
            "ai": C.ENSEMBLE_AI_WEIGHT,
        },
        "adapters": ["damage_gate", "yolov11", "sam2", "depth_anything_v2", "cognitive_lmm"],
        "mode": "stub_models_physics_primary",
    }


@router.post("/physics")
def physics_only(body: PhysicsOnlyRequest) -> Dict[str, Any]:
    """Run DARCI only (no vision). Useful for unit tests and adjuster tools."""
    zones = [
        ZoneInput(
            zone=z.zone,
            depth_cm=z.depth_cm,
            area_cm2=z.area_cm2,
            material=z.material,
        )
        for z in body.zones
    ]
    result = run_darci(
        DarciInput(
            mass_kg=body.mass_kg,
            velocity_kph=body.velocity_kph,
            zones=zones,
            strain_rate_proxy=body.strain_rate_proxy,
        )
    )
    return {
        "v_mps": result.v_mps,
        "e_k_j": result.e_k_j,
        "e_k_kj": result.e_k_kj,
        "ke_factor": result.ke_factor,
        "force_n": result.force_n,
        "peak_g": result.peak_g,
        "r_y_max": result.r_y_max,
        "p_brittle": result.p_brittle,
        "shannon_h": result.shannon_h,
        "p_struct": result.p_struct,
        "r_struct": result.r_struct,
        "p_tl_physics": result.p_tl_physics,
        "entropy_override": result.entropy_override,
        "overrides_applied": result.overrides_applied,
        "zones": result.zones,
        "formula_version": result.formula_version,
    }


@router.post("/run")
def run_analysis(body: AnalyzeRequest) -> Dict[str, Any]:
    """
    Full Layer 2 pipeline with stub vision models.
    Photos are synthetic placeholders when not provided (M3).
    """
    photos = [f"photo-{i}-{body.session_id}".encode() for i in range(max(1, body.photo_count))]
    try:
        result = _pipeline.run(
            AnalysisRequest(
                session_id=body.session_id,
                mass_kg=body.mass_kg,
                velocity_kph=body.velocity_kph,
                photos=photos,
                zone_hints=body.zone_hints,
                materials=body.materials,
                strain_rate_proxy=body.strain_rate_proxy,
            )
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    d = result.darci
    e = result.ensemble
    return {
        "session_id": result.session_id,
        "decision": e.decision,
        "p_ensemble": e.p_ensemble,
        "p_tl_physics": e.p_tl_physics,
        "p_tl_ai": e.p_tl_ai,
        "model_disagreement": e.model_disagreement,
        "entropy_override": e.entropy_override,
        "overrides_applied": e.overrides_applied,
        "physics": {
            "e_k_kj": d.e_k_kj,
            "ke_factor": d.ke_factor,
            "force_n": d.force_n,
            "peak_g": d.peak_g,
            "r_y_max": d.r_y_max,
            "p_brittle": d.p_brittle,
            "shannon_h": d.shannon_h,
            "p_struct": d.p_struct,
            "r_struct": d.r_struct,
        },
        "detections": result.detections,
        "masks": result.masks,
        "depths": result.depths,
        "lmm_panels": result.lmm_panels,
        "segmentation_source": result.segmentation_source,
        "notes": result.notes,
        "formula_version": result.formula_version,
    }
