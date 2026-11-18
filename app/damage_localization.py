"""Damage localization observations and reviewer-label benchmarking.

A detector may identify a candidate region in an image. That normalized
image-space region is not a physical measurement and cannot establish
damage severity, crush depth, structural condition, or repair scope.
Raw detector scores are not calibrated probabilities.

This module deliberately keeps localization separate from physics:
- DamageRegion is a versioned, image-space detector output.
- DamageAnnotation is reviewer-labeled localization ground truth.
- HeuristicDamageDetector is a deterministic test baseline, not production AI.
- DamageObservationAdapter maps a valid exterior capture slot to a broad
  vehicle zone while preserving image-space measurements as image-space data.
- Conversion to DARCI ZoneInput fails closed until independently sourced
  physical area, depth, material, and measurement provenance are supplied.
- DamageLocalizationBenchmark measures localization agreement only; it does
  not validate severity, structural damage, safety, or repair outcomes.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable
from app.capture_protocols import DEFAULT_CAPTURE_PROTOCOL, LEGACY_CAPTURE_PROTOCOL, require_implemented_protocol

MODEL_VERSION = "damage-localization-v1"
ANNOTATION_VERSION = "damage-annotation-v1"

DAMAGE_CLASSES = frozenset({"scratch", "dent", "glass_damage", "structural_deformation", "unknown"})
# Matches the physics engine's ZoneInput vocabulary.
IMPACT_ZONES = frozenset({"front", "rear", "side", "roof", "underbody"})
ZONE_BY_SLOT_PREFIX = (
    ("undercarriage", "underbody"),
    ("front_right", "front"), ("front_left", "front"), ("front", "front"),
    ("rear_left", "rear"), ("rear_right", "rear"), ("rear", "rear"),
    ("driver_side", "side"), ("passenger_side", "side"),
)

# Localization benchmark constants only. These do not calibrate severity.
IOU_MATCH_THRESHOLD = 0.50
MIN_LABELED_SAMPLES = 10


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

    @property
    def score_semantics(self) -> str:
        """The detector score is uncalibrated and must not be read as probability."""
        return "uncalibrated_detector_score"


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
class LocalizedDamageObservation:
    """Image-space localization with no inferred physical severity or depth."""
    slot: str
    zone: str
    normalized_region_area_fraction: float
    predicted_damage_class: str
    raw_detector_score: float
    score_semantics: str
    model_version: str
    protocol_version: str


class DamageObservationAdapter:
    """Maps capture views to broad zones without inventing physical measurements."""

    def to_observation(self, region: DamageRegion) -> LocalizedDamageObservation:
        zone = zone_for_slot(region.slot, region.protocol_version)
        if zone is None:
            raise DamageLocalizationError(
                "NOT_AN_EXTERIOR_SLOT",
                f"{region.slot} does not map to an exterior vehicle zone",
            )
        return LocalizedDamageObservation(
            slot=region.slot,
            zone=zone,
            normalized_region_area_fraction=round(region.area_fraction, 6),
            predicted_damage_class=region.damage_class,
            raw_detector_score=float(region.confidence),
            score_semantics=region.score_semantics,
            model_version=region.model_version,
            protocol_version=region.protocol_version,
        )

    def to_impact_geometry(self, region: DamageRegion):
        """Legacy physics conversion is intentionally disabled.

        A normalized 2-D bounding-box area is not cm², and it contains no
        depth or material measurement. Callers must obtain independently
        sourced physical measurements before constructing a DARCI ZoneInput.
        """
        self.to_observation(region)  # retain slot/protocol validation
        raise DamageLocalizationError(
            "PHYSICAL_MEASUREMENTS_REQUIRED",
            "Image localization cannot establish physical area, depth, or material",
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
            damage_class="unknown", confidence=round(min(len(flagged) / 16.0, 1.0), 4),
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
