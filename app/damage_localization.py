"""CV damage localization as a physics-engine input producer (Slice 10; Tier 2 #8).

Recalibration brief position: our differentiator is the physics engine;
CV is an *input producer* (damage region → geometry → E_k / r_y /
P_brittle), benchmarked against our own reviewer-labeled data before it
is ever trusted. No published damage-detection accuracy is banked on.

What this module lands:
- ``DamageRegion``: the versioned localization contract any detector
  (YOLO-family, Masked R-CNN, a future calibrated model) must produce.
- ``DamageAnnotation``: reviewer-labeled ground truth — the labeled data
  the benchmark demands. Without labeled data there is no adoption.
- ``HeuristicDamageDetector``: the deterministic, dependency-free
  baseline detector (high-contrast patch scan). THE BASELINE any real
  model must beat on our labeled set — not a production detector.
- ``PhysicsInputAdapter``: the CV→physics seam. Maps a DamageRegion on
  an exterior slot to impact geometry (zone, area fraction, severity
  tier, provisional depth) consumable by ``backend/app/physics``'s
  ZoneInput. Refuses to fabricate geometry for non-exterior slots.
- ``DamageLocalizationBenchmark``: IoU-based evaluation against
  reviewer annotations, and an adoption gate that only passes a
  candidate detector that STRICTLY beats the baseline on both F1 and
  mean IoU over a minimum labeled set.

All provisional constants (IoU threshold, severity tier boundaries,
depth estimates) are explicit and pending calibration against reviewer
labels.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable
from app.capture_protocols import DEFAULT_CAPTURE_PROTOCOL, LEGACY_CAPTURE_PROTOCOL, require_implemented_protocol

MODEL_VERSION = "damage-localization-v1"
ANNOTATION_VERSION = "damage-annotation-v1"

DAMAGE_CLASSES = frozenset({"scratch", "dent", "glass_damage", "structural_deformation"})
# Matches the physics engine's ZoneInput vocabulary.
IMPACT_ZONES = frozenset({"front", "rear", "side", "roof", "underbody"})
ZONE_BY_SLOT_PREFIX = (
    ("undercarriage", "underbody"),
    ("front_right", "front"), ("front_left", "front"), ("front", "front"),
    ("rear_left", "rear"), ("rear_right", "rear"), ("rear", "rear"),
    ("driver_side", "side"), ("passenger_side", "side"),
)

# Provisional constants (calibration against reviewer labels pending).
IOU_MATCH_THRESHOLD = 0.50
MIN_LABELED_SAMPLES = 10
COSMETIC_AREA_MAX = 0.05      # area fraction below this = cosmetic
FUNCTIONAL_AREA_MAX = 0.25    # below this = functional; above = structural
COSMETIC_DEPTH_CM = 0.5
FUNCTIONAL_DEPTH_CM = 3.0
STRUCTURAL_DEPTH_CM = 12.0
BASE_MATERIAL = "mild_steel"


class DamageLocalizationError(ValueError):
    """Stable-code localization failures. Codes are API surface."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(code if not detail else f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class DamageRegion:
    """Normalized bounding region on one slot's capture. Detector output contract."""
    slot: str
    x0: float
    y0: float
    x1: float
    y1: float
    damage_class: str
    confidence: float
    model_version: str = MODEL_VERSION
    protocol_version: str = LEGACY_CAPTURE_PROTOCOL

    def __post_init__(self):
        if not isinstance(self.slot, str) or not self.slot.strip():
            raise DamageLocalizationError("INVALID_SLOT")
        if self.damage_class not in DAMAGE_CLASSES:
            raise DamageLocalizationError("INVALID_DAMAGE_CLASS", self.damage_class)
        for name in ("x0", "y0", "x1", "y1"):
            v = getattr(self, name)
            if not isinstance(v, (int, float)) or not 0.0 <= v <= 1.0:
                raise DamageLocalizationError("INVALID_COORDINATE", name)
        if self.x1 <= self.x0 or self.y1 <= self.y0:
            raise DamageLocalizationError("EMPTY_REGION")
        if not isinstance(self.confidence, (int, float)) or not 0.0 <= self.confidence <= 1.0:
            raise DamageLocalizationError("INVALID_CONFIDENCE")

    @property
    def area_fraction(self) -> float:
        return (self.x1 - self.x0) * (self.y1 - self.y0)

    @property
    def centroid(self) -> tuple[float, float]:
        return ((self.x0 + self.x1) / 2, (self.y0 + self.y1) / 2)


@dataclass(frozen=True)
class DamageAnnotation:
    """Reviewer-labeled ground truth: one annotated region per record."""
    session_id: str
    slot: str
    region: DamageRegion
    annotated_by: str
    schema_version: str = ANNOTATION_VERSION

    def __post_init__(self):
        if not isinstance(self.annotated_by, str) or not self.annotated_by.strip():
            raise DamageLocalizationError("INVALID_ANNOTATOR")
        if self.region.slot != self.slot:
            raise DamageLocalizationError("ANNOTATION_SLOT_MISMATCH")


def iou(a: DamageRegion, b: DamageRegion) -> float:
    if a.slot != b.slot:
        return 0.0
    ix0, iy0 = max(a.x0, b.x0), max(a.y0, b.y0)
    ix1, iy1 = min(a.x1, b.x1), min(a.y1, b.y1)
    inter = max(0.0, ix1 - ix0) * max(0.0, iy1 - iy0)
    if inter <= 0:
        return 0.0
    return inter / (a.area_fraction + b.area_fraction - inter)


def zone_for_slot(slot: str, protocol_version: str = LEGACY_CAPTURE_PROTOCOL) -> str | None:
    """Map only the eight 16-v1 exterior views to crush zones.

    Wheel, cabin, odometer, VIN and identity-document slots are deliberately
    excluded from crush physics. Legacy 12-v1 mappings remain available for
    historical callers and are never reinterpreted as 16-v1.
    """
    protocol = require_implemented_protocol(protocol_version)
    if slot not in protocol.slots:
        return None
    if protocol_version == DEFAULT_CAPTURE_PROTOCOL:
        exterior = {
            "00_front_exterior": "front",
            "01_front_right_exterior": "front",
            "02_right_side_exterior": "side",
            "03_rear_right_exterior": "rear",
            "04_rear_exterior": "rear",
            "05_rear_left_exterior": "rear",
            "06_left_side_exterior": "side",
            "07_front_left_exterior": "front",
        }
        return exterior.get(slot)
    lowered = slot.lower()
    for prefix, zone in ZONE_BY_SLOT_PREFIX:
        if lowered == prefix or lowered.startswith(prefix):
            return zone
    return None


@dataclass(frozen=True)
class ImpactGeometry:
    """Physics-engine input produced from a localized damage region."""
    slot: str
    zone: str
    area_fraction: float
    severity_tier: str          # cosmetic | functional | structural
    depth_cm: float             # provisional estimate pending calibration
    material: str = BASE_MATERIAL
    model_version: str = MODEL_VERSION

    def to_zone_input(self):
        """Backend physics seam: builds the engine's ZoneInput if importable."""
        try:
            from backend.app.physics.darci import ZoneInput
        except ImportError:  # pragma: no cover - backend not on path
            raise DamageLocalizationError("PHYSICS_ENGINE_UNAVAILABLE")
        return ZoneInput(zone=self.zone, depth_cm=self.depth_cm,
                         area_cm2=self.area_fraction * 10000.0, material=self.material)


class PhysicsInputAdapter:
    """DamageRegion on an exterior slot → ImpactGeometry. Refuses the rest."""

    def to_impact_geometry(self, region: DamageRegion) -> ImpactGeometry:
        zone = zone_for_slot(region.slot, region.protocol_version)
        if zone is None:
            raise DamageLocalizationError("NOT_AN_EXTERIOR_SLOT",
                                          f"{region.slot} does not map to an impact zone")
        area = region.area_fraction
        if area <= COSMETIC_AREA_MAX:
            tier, depth = "cosmetic", COSMETIC_DEPTH_CM
        elif area <= FUNCTIONAL_AREA_MAX:
            tier, depth = "functional", FUNCTIONAL_DEPTH_CM
        else:
            tier, depth = "structural", STRUCTURAL_DEPTH_CM
        return ImpactGeometry(
            slot=region.slot, zone=zone, area_fraction=round(area, 6),
            severity_tier=tier, depth_cm=depth,
        )


class HeuristicDamageDetector:
    """Baseline detector: deterministic high-contrast patch scan.

    Not a production detector — it is the BASELINE. Any real model must
    beat it on the reviewer-labeled set before adoption (see
    DamageLocalizationBenchmark.adoption_gate).
    """

    model_version = MODEL_VERSION + "/heuristic-baseline"
    contrast_threshold = 60.0  # pixel deviation from neighborhood mean

    def detect(self, slot: str, pixels, cell: int = 6, protocol_version: str = LEGACY_CAPTURE_PROTOCOL) -> tuple[DamageRegion, ...]:
        if not isinstance(pixels, (list, tuple)) or not pixels or not pixels[0]:
            raise DamageLocalizationError("INVALID_PIXELS")
        height, width = len(pixels), len(pixels[0])
        if any(len(r) != width for r in pixels):
            raise DamageLocalizationError("INVALID_PIXELS")
        flagged: set[tuple[int, int]] = set()
        for y in range(0, height - cell, cell):
            for x in range(0, width - cell, cell):
                patch = [pixels[yy][xx] for yy in range(y, y + cell) for xx in range(x, x + cell)]
                mean = sum(patch) / len(patch)
                if any(abs(v - mean) > self.contrast_threshold for v in patch):
                    flagged.add((x, y))
        if not flagged:
            return ()
        xs = [x for x, _ in flagged]
        ys = [y for _, y in flagged]
        x0, x1 = min(xs) / width, (min(xs) + cell) / width
        y0, y1 = min(ys) / height, (min(ys) + cell) / height
        return (DamageRegion(
            slot=slot, x0=round(x0, 4), y0=round(y0, 4),
            x1=round(min(x1, 1.0), 4), y1=round(min(y1, 1.0), 4),
            damage_class="dent", confidence=round(min(len(flagged) / 16.0, 1.0), 4),
            model_version=self.model_version,
            protocol_version=protocol_version,
        ),)


@dataclass(frozen=True)
class BenchmarkReport:
    labeled_samples: int
    matched: int
    missed: int
    false_positives: int
    precision: float | None
    recall: float | None
    f1: float | None
    mean_iou: float | None
    iou_threshold: float = IOU_MATCH_THRESHOLD


@dataclass(frozen=True)
class AdoptionDecision:
    adopt: bool
    reasons: tuple[str, ...]
    baseline_f1: float | None
    candidate_f1: float | None
    baseline_mean_iou: float | None
    candidate_mean_iou: float | None


class DamageLocalizationBenchmark:
    """Evaluates detectors against reviewer annotations. No labels, no adoption."""

    def evaluate(self, predictions: Iterable[DamageRegion],
                 ground_truth: Iterable[DamageAnnotation]) -> BenchmarkReport:
        preds = tuple(predictions)
        truth = tuple(ground_truth)
        for annotation in truth:
            if annotation.schema_version != ANNOTATION_VERSION:
                raise DamageLocalizationError("ANNOTATION_VERSION_MISMATCH")
        used: set[int] = set()
        matched_ious: list[float] = []
        for p in preds:
            for i, t in enumerate(truth):
                if i in used or t.region.slot != p.slot:
                    continue
                if t.region.damage_class == p.damage_class and iou(p, t.region) >= IOU_MATCH_THRESHOLD:
                    used.add(i)
                    matched_ious.append(iou(p, t.region))
                    break
        matched = len(matched_ious)
        false_positives = len(preds) - matched
        missed = len(truth) - matched
        precision = matched / len(preds) if preds else None
        recall = matched / len(truth) if truth else None
        f1 = (2 * precision * recall / (precision + recall)) if precision and recall else None
        mean_iou = sum(matched_ious) / len(matched_ious) if matched_ious else None
        return BenchmarkReport(
            labeled_samples=len(truth), matched=matched, missed=missed,
            false_positives=false_positives, precision=precision, recall=recall,
            f1=f1, mean_iou=mean_iou,
        )

    def adoption_gate(self, baseline: BenchmarkReport, candidate: BenchmarkReport) -> AdoptionDecision:
        """A candidate detector is adopted ONLY if it strictly beats the baseline
        on both F1 and mean IoU over at least MIN_LABELED_SAMPLES annotations."""
        reasons = []
        if baseline.labeled_samples < MIN_LABELED_SAMPLES or candidate.labeled_samples < MIN_LABELED_SAMPLES:
            reasons.append(f"INSUFFICIENT_LABELED_SAMPLES: need >= {MIN_LABELED_SAMPLES} reviewer annotations")
        if candidate.f1 is None or baseline.f1 is None:
            reasons.append("F1_NOT_MEASURABLE")
        elif candidate.f1 <= baseline.f1:
            reasons.append(f"CANDIDATE_F1_NOT_BETTER: {candidate.f1} vs {baseline.f1}")
        if candidate.mean_iou is None or baseline.mean_iou is None:
            reasons.append("MEAN_IOU_NOT_MEASURABLE")
        elif candidate.mean_iou <= baseline.mean_iou:
            reasons.append(f"CANDIDATE_IOU_NOT_BETTER: {candidate.mean_iou} vs {baseline.mean_iou}")
        return AdoptionDecision(
            adopt=not reasons, reasons=tuple(reasons),
            baseline_f1=baseline.f1, candidate_f1=candidate.f1,
            baseline_mean_iou=baseline.mean_iou, candidate_mean_iou=candidate.mean_iou,
        )
