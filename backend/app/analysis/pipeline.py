"""
Layer 2 end-to-end analysis pipeline:
  pre-flight gate → YOLO → SAM2 → Depth → LMM → DARCI → 55/45 ensemble
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from backend.app.analysis.consensus import EnsembleResult, VisionSignal, run_ensemble, two_thirds_vote
from backend.app.physics.darci import DarciInput, DarciResult, ZoneInput, run_darci
from backend.app.vision.adapters import (
    CognitiveLMMAdapter,
    DamageGate,
    DepthAdapter,
    Detection,
    SAM2Adapter,
    YOLOAdapter,
    nms_dedupe,
)
from config import forensic_constants as C


@dataclass
class AnalysisRequest:
    session_id: str
    mass_kg: float
    velocity_kph: float
    photos: Sequence[bytes]  # one or more images
    zone_hints: Optional[Sequence[str]] = None
    materials: Optional[Sequence[str]] = None
    lidar_sparse: Optional[Sequence[float]] = None
    strain_rate_proxy: float = 1.0


@dataclass
class AnalysisResult:
    session_id: str
    darci: DarciResult
    ensemble: EnsembleResult
    detections: List[Dict[str, Any]]
    masks: List[Dict[str, Any]]
    depths: List[Dict[str, Any]]
    lmm_panels: List[Dict[str, Any]]
    segmentation_source: str
    formula_version: str = C.VERSION
    notes: List[str] = field(default_factory=list)


class AnalysisPipeline:
    def __init__(self) -> None:
        self.gate = DamageGate()
        self.yolo = YOLOAdapter()
        self.sam2 = SAM2Adapter()
        self.depth = DepthAdapter()
        self.lmm = CognitiveLMMAdapter()

    def run(self, req: AnalysisRequest) -> AnalysisResult:
        notes: List[str] = []
        photos = list(req.photos) or [b""]
        zone_hints = list(req.zone_hints or ["front"] * len(photos))
        materials = list(req.materials or ["mild_steel"] * len(photos))

        # Pre-flight
        all_dets: List[Detection] = []
        for i, img in enumerate(photos):
            is_car, is_damaged, gconf = self.gate.is_car_and_damaged(img)
            if not is_car or not is_damaged:
                notes.append(f"photo[{i}] skipped by damage_gate conf={gconf:.2f}")
                continue
            zh = zone_hints[i] if i < len(zone_hints) else "unknown"
            dets = self.yolo.detect(img, zone_hint=zh)
            all_dets.extend(dets)

        all_dets = nms_dedupe(all_dets)
        notes.append(f"yolo_detections={len(all_dets)}")

        # SAM2 + Depth on first photo for stub simplicity
        primary = photos[0]
        masks = self.sam2.segment(primary, all_dets)
        depths = self.depth.fuse(primary, masks, lidar_sparse=req.lidar_sparse)

        # Build zone inputs for DARCI from depth results
        zones: List[ZoneInput] = []
        for i, d in enumerate(depths):
            mat = materials[i] if i < len(materials) else "mild_steel"
            area = masks[i].area_cm2 if i < len(masks) else 0.0
            zones.append(
                ZoneInput(
                    zone=d.zone or "front",
                    depth_cm=d.mean_depth_cm,
                    area_cm2=area,
                    material=mat,
                )
            )
        if not zones:
            # physics still runs with zero-depth front zone
            zones = [ZoneInput(zone="front", depth_cm=0.0, material="mild_steel")]

        darci_in = DarciInput(
            mass_kg=req.mass_kg,
            velocity_kph=req.velocity_kph,
            zones=zones,
            strain_rate_proxy=req.strain_rate_proxy,
        )
        darci = run_darci(darci_in)

        # LMM with physics injection
        darci_vars = {
            "e_k_kj": darci.e_k_kj,
            "r_y_max": darci.r_y_max,
            "p_tl_physics": darci.p_tl_physics,
            "p_struct": darci.p_struct,
            "shannon_h": darci.shannon_h,
            "peak_g": darci.peak_g,
        }
        seg_source = "vision_stack"
        try:
            lmm = self.lmm.reason(photos, darci_vars, all_dets, timeout_s=C.INFERENCE_TIMEOUT_S)
            if lmm.latency_s > C.INFERENCE_TIMEOUT_S:
                seg_source = "physics_fallback"
                notes.append("lmm_timeout_physics_fallback")
                vision = VisionSignal(
                    p_tl_ai=darci.p_tl_physics,
                    source="physics_fallback",
                    confidence=1.0,
                    disagreement=False,
                )
            else:
                # simulate multi-model votes from yolo conf + lmm
                votes = {
                    "lmm": lmm.p_tl_ai,
                    "yolo_proxy": min(0.95, 0.3 + 0.5 * (all_dets[0].confidence if all_dets else 0.5)),
                    "depth_proxy": min(0.95, 0.2 + darci.p_tl_physics * 0.7),
                }
                mean_ai, disagree = two_thirds_vote(votes)
                vision = VisionSignal(
                    p_tl_ai=mean_ai,
                    source="ensemble_vision",
                    confidence=0.7,
                    model_votes=votes,
                    disagreement=disagree,
                    details={"lmm_panels": len(lmm.panels)},
                )
        except Exception as exc:  # noqa: BLE001
            notes.append(f"lmm_error:{type(exc).__name__}")
            seg_source = "physics_fallback"
            lmm = None
            vision = VisionSignal(
                p_tl_ai=darci.p_tl_physics,
                source="physics_fallback",
                confidence=1.0,
                disagreement=False,
            )

        ensemble = run_ensemble(darci, vision)

        return AnalysisResult(
            session_id=req.session_id,
            darci=darci,
            ensemble=ensemble,
            detections=[
                {
                    "class_name": d.class_name,
                    "confidence": d.confidence,
                    "zone": d.zone,
                    "bbox_xyxy": d.bbox_xyxy,
                }
                for d in all_dets
            ],
            masks=[
                {"area_cm2": m.area_cm2, "zone": m.detection.zone, "class_name": m.detection.class_name}
                for m in masks
            ],
            depths=[
                {"mean_depth_cm": d.mean_depth_cm, "volume_cm3": d.volume_cm3, "zone": d.zone}
                for d in depths
            ],
            lmm_panels=[asdict(p) for p in (lmm.panels if lmm else [])],
            segmentation_source=seg_source,
            notes=notes,
        )
