"""
Vision tier adapters — self-hosted model interfaces.

Real weights (YOLOv11, SAM2, Depth Anything V2, open-weight LMM) are loaded
behind these interfaces. Until model artifacts are present, each adapter
returns a deterministic physics-aware stub so the pipeline is testable end-to-end.
"""

from __future__ import annotations

import hashlib
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from config import forensic_constants as C


@dataclass
class Detection:
    class_id: int
    class_name: str
    confidence: float
    bbox_xyxy: tuple[float, float, float, float]  # normalized or pixel
    zone: str = "unknown"


@dataclass
class MaskResult:
    detection: Detection
    polygon: List[tuple[float, float]]
    area_cm2: float
    source: str = "sam2"


@dataclass
class DepthResult:
    mean_depth_cm: float
    volume_cm3: float
    zone: str
    source: str = "depth_anything_v2"


@dataclass
class LMMPanel:
    panel: str
    severity: float
    repair_decision: str  # pdr | repair | section | replace
    labor_hours: float
    paint_hours: float
    fraud_indicators: List[str] = field(default_factory=list)


@dataclass
class LMMResult:
    panels: List[LMMPanel]
    p_tl_ai: float
    fraud_flags: List[str]
    raw_json: Dict[str, Any]
    source: str = "cognitive_lmm"
    latency_s: float = 0.0


class VisionAdapter(ABC):
    name: str

    @abstractmethod
    def available(self) -> bool:
        ...


class DamageGate(VisionAdapter):
    name = "damage_gate"

    def available(self) -> bool:
        return True

    def is_car_and_damaged(self, image_bytes: bytes) -> tuple[bool, bool, float]:
        """Return (is_car, is_damaged, confidence). Stub: always car+damaged."""
        h = int(hashlib.sha256(image_bytes[:64] or b"empty").hexdigest()[:8], 16)
        conf = 0.7 + (h % 30) / 100.0
        return True, True, min(conf, 0.99)


class YOLOAdapter(VisionAdapter):
    name = "yolov11"
    CLASS_NAMES = [
        "dent", "scratch", "crease", "tear", "puncture", "crush", "misalignment",
        "broken_glass", "missing_part", "paint_chip", "rust", "fold", "buckle",
        "airbag_deployed", "fluid_leak", "battery_shift", "frame_rail", "apron",
        "quarter_panel", "door_intrusion", "roof_crush", "underbody", "bumper_cover",
        "grille", "headlamp", "taillamp", "fender", "hood", "decklid", "rocker",
        "pillar_a", "pillar_b", "pillar_c", "sill", "floor_pan", "radiator_support",
        "strut_tower", "wheel_damage", "tire", "sensor_adas", "mirror", "trim",
        "corrosion", "weld_failure", "section_damage", "blend_required", "pdr_candidate",
        "structural_fold", "crush_can", "subframe", "unibody_rail", "unknown_damage",
    ]

    def available(self) -> bool:
        return True

    def detect(self, image_bytes: bytes, zone_hint: str = "unknown") -> List[Detection]:
        h = int(hashlib.sha256(image_bytes[:128] or b"x").hexdigest()[:8], 16)
        conf = 0.55 + (h % 40) / 100.0
        if conf < C.YOLO_CONF_MIN:
            return []
        cid = h % len(self.CLASS_NAMES)
        return [
            Detection(
                class_id=cid,
                class_name=self.CLASS_NAMES[cid],
                confidence=min(conf, 0.99),
                bbox_xyxy=(0.2, 0.2, 0.8, 0.8),
                zone=zone_hint,
            )
        ]


class SAM2Adapter(VisionAdapter):
    name = "sam2"

    def available(self) -> bool:
        return True

    def segment(self, image_bytes: bytes, detections: Sequence[Detection]) -> List[MaskResult]:
        results = []
        for d in detections:
            x1, y1, x2, y2 = d.bbox_xyxy
            area_norm = max(0.0, (x2 - x1) * (y2 - y1))
            area_cm2 = area_norm * 8000.0
            results.append(
                MaskResult(
                    detection=d,
                    polygon=[(x1, y1), (x2, y1), (x2, y2), (x1, y2)],
                    area_cm2=area_cm2,
                    source="sam2_stub",
                )
            )
        return results


class DepthAdapter(VisionAdapter):
    name = "depth_anything_v2"

    def available(self) -> bool:
        return True

    def fuse(
        self,
        image_bytes: bytes,
        masks: Sequence[MaskResult],
        lidar_sparse: Optional[Sequence[float]] = None,
    ) -> List[DepthResult]:
        out = []
        for i, m in enumerate(masks):
            h = int(hashlib.sha256(image_bytes[i : i + 32] or b"d").hexdigest()[:6], 16)
            d_cm = 5.0 + (h % 50)
            if lidar_sparse:
                d_cm = 0.6 * d_cm + 0.4 * (sum(lidar_sparse) / len(lidar_sparse))
            vol = m.area_cm2 * d_cm
            out.append(
                DepthResult(
                    mean_depth_cm=d_cm,
                    volume_cm3=vol,
                    zone=m.detection.zone,
                    source="depth_stub",
                )
            )
        return out


class CognitiveLMMAdapter(VisionAdapter):
    name = "cognitive_lmm"

    def available(self) -> bool:
        return True

    def reason(
        self,
        photo_set: Sequence[bytes],
        darci_vars: Dict[str, Any],
        detections: Sequence[Detection],
        timeout_s: float = C.INFERENCE_TIMEOUT_S,
    ) -> LMMResult:
        t0 = time.time()
        panels: List[LMMPanel] = []
        fraud: List[str] = []
        for d in detections:
            sev = min(1.0, d.confidence * (0.5 + darci_vars.get("r_y_max", 0.0) * 0.5))
            decision = "replace" if sev > 0.7 else ("repair" if sev > 0.4 else "pdr")
            panels.append(
                LMMPanel(
                    panel=d.class_name,
                    severity=sev,
                    repair_decision=decision,
                    labor_hours=2.0 + sev * 6.0,
                    paint_hours=1.0 + sev * 3.0,
                )
            )
        p_tl = 0.2 + 0.6 * darci_vars.get("p_tl_physics", 0.3)
        p_tl = max(0.05, min(0.95, p_tl))
        latency = time.time() - t0
        return LMMResult(
            panels=panels,
            p_tl_ai=p_tl,
            fraud_flags=fraud,
            raw_json={"panels": [p.__dict__ for p in panels], "p_tl_ai": p_tl},
            source="cognitive_lmm_stub",
            latency_s=latency,
        )


def nms_dedupe(dets: List[Detection], iou_thresh: float = 0.5) -> List[Detection]:
    """Simple multi-angle dedupe by IoU + class."""
    if not dets:
        return []
    ordered = sorted(dets, key=lambda d: d.confidence, reverse=True)
    kept: List[Detection] = []

    def iou(a: Detection, b: Detection) -> float:
        ax1, ay1, ax2, ay2 = a.bbox_xyxy
        bx1, by1, bx2, by2 = b.bbox_xyxy
        ix1, iy1 = max(ax1, bx1), max(ay1, by1)
        ix2, iy2 = min(ax2, bx2), min(ay2, by2)
        inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
        area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
        area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
        union = area_a + area_b - inter
        return inter / union if union > 0 else 0.0

    for d in ordered:
        if any(d.class_name == k.class_name and iou(d, k) >= iou_thresh for k in kept):
            continue
        kept.append(d)
    return kept
