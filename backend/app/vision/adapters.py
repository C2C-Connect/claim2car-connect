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
from hashlib import sha256
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

from app.damage_localization import (
    DamageAnnotation,
    DamageLocalizationBenchmark,
    DamageRegion,
    HeuristicDamageDetector,
    PhysicsInputAdapter,
)
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


# Sovereign in-house vision artifact from the approved production engineering spec.
YOLO_CLASS_TO_CANONICAL_LABEL: dict[str, str] = {
    "dent": "dent", "minor_dent": "dent",
    "major_dent": "structural_deformation", "deformation": "structural_deformation",
    "crumple": "structural_deformation", "crush": "structural_deformation",
    "scratch": "scratch", "scuff": "scratch", "paint_damage": "scratch",
    "crack": "glass_damage", "lamp_broken": "glass_damage",
    "windshield_crack": "glass_damage", "shatter": "glass_damage",
    "broken_glass": "glass_damage", "glass_shatter": "glass_damage",
}


class VisionAdapterError(ValueError):
    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(code if not detail else f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class ModelWeightProvenance:
    model_id: str
    stage: str
    weights_path: str
    sha256_hex: str
    framework: str


@dataclass(frozen=True)
class AdvisoryVisionAnalysis:
    session_id: str
    slot: str
    model_version: str
    weight_digests: tuple[str, ...]
    regions: tuple[DamageRegion, ...]
    darci_physics_inputs: tuple[dict, ...]
    promoted_over_baseline: bool
    advisory_only: bool = True

    def assert_advisory_boundary(self, target_action: str) -> None:
        forbidden_actions = {
            "auto_approve_claim",
            "trigger_live_dispatch",
            "settle_payment_ledger",
            "override_human_reviewer",
        }
        if target_action in forbidden_actions:
            raise VisionAdapterError(
                "CONSEQUENTIAL_ACTION_BLOCKED_BY_S4_4B_13",
                f"Analytical output ({self.model_version}) is strictly advisory and cannot execute {target_action!r}",
            )


def compute_weight_provenance(
    model_id: str, stage: str, weights_path: Path | str, framework: str = "pytorch-yolo"
) -> ModelWeightProvenance:
    path = Path(weights_path)
    if not path.is_file():
        raise VisionAdapterError("WEIGHTS_FILE_NOT_FOUND", str(path))
    return ModelWeightProvenance(
        model_id=model_id,
        stage=stage,
        weights_path=str(path.resolve()),
        sha256_hex=sha256(path.read_bytes()).hexdigest(),
        framework=framework,
    )


class LocalYoloTwoStageDetector:
    def __init__(
        self,
        part_weights_path: Path | str | None = None,
        damage_weights_path: Path | str | None = None,
        inference_runner: Callable[[str, object], Sequence[dict]] | None = None,
        conf_threshold: float = 0.25,
    ) -> None:
        if not 0.0 < conf_threshold <= 1.0:
            raise VisionAdapterError("INVALID_CONFIDENCE_THRESHOLD")
        self.conf_threshold = conf_threshold
        self.part_weights_path = Path(part_weights_path) if part_weights_path else None
        self.damage_weights_path = Path(damage_weights_path) if damage_weights_path else None
        self._runner = inference_runner
        self._provenance: list[ModelWeightProvenance] = []
        if self.part_weights_path and self.part_weights_path.is_file():
            self._provenance.append(
                compute_weight_provenance("yolo-part-2_best", "part_localization", self.part_weights_path)
            )
        if self.damage_weights_path and self.damage_weights_path.is_file():
            self._provenance.append(
                compute_weight_provenance("yolo-damage-4_best", "damage_detection", self.damage_weights_path)
            )

    @property
    def model_version(self) -> str:
        if self._provenance:
            return "inhouse-yolo-2stage-" + "-".join(p.sha256_hex[:8] for p in self._provenance)
        return "inhouse-yolo-2stage-candidate-v1"

    @property
    def weight_digests(self) -> tuple[str, ...]:
        return tuple(p.sha256_hex for p in self._provenance)

    def load_ultralytics_runner_if_available(self) -> None:
        if self._runner is not None:
            return
        if (not self.part_weights_path or not self.part_weights_path.is_file()
                or not self.damage_weights_path or not self.damage_weights_path.is_file()):
            raise VisionAdapterError(
                "LOCAL_WEIGHTS_REQUIRED",
                "Mount 2_best.pt and 4_best.pt locally or supply an inference_runner",
            )
        try:
            from ultralytics import YOLO  # type: ignore[import-not-found]
        except ImportError as exc:
            raise VisionAdapterError(
                "ULTRALYTICS_RUNTIME_NOT_INSTALLED",
                "Install ultralytics/torch in the vision worker container",
            ) from exc

        part_model = YOLO(str(self.part_weights_path))
        damage_model = YOLO(str(self.damage_weights_path))

        def _local_pt_runner(slot: str, image_input: object) -> Sequence[dict]:
            part_results = part_model.predict(source=image_input, conf=self.conf_threshold, verbose=False)
            part_boxes: list[tuple[float, float, float, float]] = []
            for result in part_results:
                for box in result.boxes:
                    x1, y1, x2, y2 = box.xyxyn[0].tolist()
                    part_boxes.append((float(x1), float(y1), float(x2), float(y2)))
            if not part_boxes:
                return []

            results = damage_model.predict(source=image_input, conf=self.conf_threshold, verbose=False)
            out: list[dict] = []
            for res in results:
                names = res.names or {}
                for box in res.boxes:
                    x1, y1, x2, y2 = box.xyxyn[0].tolist()
                    center_x, center_y = (x1 + x2) / 2, (y1 + y2) / 2
                    if not any(px1 <= center_x <= px2 and py1 <= center_y <= py2
                               for px1, py1, px2, py2 in part_boxes):
                        continue
                    cls_id = int(box.cls[0].item())
                    out.append({
                        "x1": x1, "y1": y1, "x2": x2, "y2": y2,
                        "label": str(names.get(cls_id, "dent")).lower(),
                        "confidence": float(box.conf[0].item()),
                    })
            return out

        self._runner = _local_pt_runner

    def detect(self, slot: str, image_or_grid: object) -> list[DamageRegion]:
        if not isinstance(slot, str) or not slot.strip():
            raise VisionAdapterError("INVALID_SLOT")
        if self._runner is None:
            self.load_ultralytics_runner_if_available()
        assert self._runner is not None

        regions: list[DamageRegion] = []
        for pred in self._runner(slot, image_or_grid):
            conf = float(pred.get("confidence", 0.0))
            if conf < self.conf_threshold:
                continue
            x1 = max(0.0, min(1.0, float(pred["x1"])))
            y1 = max(0.0, min(1.0, float(pred["y1"])))
            x2 = max(0.0, min(1.0, float(pred["x2"])))
            y2 = max(0.0, min(1.0, float(pred["y2"])))
            if x2 <= x1 or y2 <= y1:
                continue
            raw_label = str(pred.get("label", "dent")).strip().lower()
            regions.append(DamageRegion(
                slot=slot, x0=round(x1, 4), y0=round(y1, 4),
                x1=round(x2, 4), y1=round(y2, 4),
                damage_class=YOLO_CLASS_TO_CANONICAL_LABEL.get(raw_label, "dent"),
                confidence=round(conf, 4), model_version=self.model_version,
            ))
        return regions


class GatedVisionPhysicsPipeline:
    def __init__(
        self,
        baseline_detector: HeuristicDamageDetector | None = None,
        candidate_detector: LocalYoloTwoStageDetector | None = None,
        physics_adapter: PhysicsInputAdapter | None = None,
        benchmark: DamageLocalizationBenchmark | None = None,
    ) -> None:
        self.baseline = baseline_detector or HeuristicDamageDetector()
        self.candidate = candidate_detector
        self.physics_adapter = physics_adapter or PhysicsInputAdapter()
        self.benchmark = benchmark or DamageLocalizationBenchmark()

    def evaluate_and_extract_physics(
        self,
        session_id: str,
        slot: str,
        grid_fixture: list[list[int]],
        image_input: object = None,
        ground_truth_annotations: Sequence[DamageAnnotation] | None = None,
    ) -> AdvisoryVisionAnalysis:
        baseline_regions = self.baseline.detect(slot, grid_fixture)
        chosen_regions = list(baseline_regions)
        chosen_version = self.baseline.model_version
        weight_digests: tuple[str, ...] = ()
        promoted = False

        if self.candidate is not None:
            candidate_regions = self.candidate.detect(
                slot, image_input if image_input is not None else grid_fixture
            )
            if ground_truth_annotations:
                anns = list(ground_truth_annotations)
                base_report = self.benchmark.evaluate(baseline_regions, anns)
                cand_report = self.benchmark.evaluate(candidate_regions, anns)
                if self.benchmark.adoption_gate(base_report, cand_report).adopt:
                    chosen_regions = list(candidate_regions)
                    chosen_version = self.candidate.model_version
                    weight_digests = self.candidate.weight_digests
                    promoted = True

        physics_inputs = []
        for reg in chosen_regions:
            geom = self.physics_adapter.to_impact_geometry(reg)
            physics_inputs.append({
                "zone": geom.zone,
                "severity_tier": geom.severity_tier,
                "area_fraction": geom.area_fraction,
                "source_label": reg.label,
                "source_confidence": reg.confidence,
            })

        return AdvisoryVisionAnalysis(
            session_id=session_id, slot=slot, model_version=chosen_version,
            weight_digests=weight_digests, regions=tuple(chosen_regions),
            darci_physics_inputs=tuple(physics_inputs),
            promoted_over_baseline=promoted, advisory_only=True,
        )
