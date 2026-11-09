"""CV damage localization tests (Slice 10): input producer + benchmark gate."""
from __future__ import annotations

import pytest

from app.damage_localization import (
    ANNOTATION_VERSION,
    COSMETIC_AREA_MAX,
    DAMAGE_CLASSES,
    FUNCTIONAL_AREA_MAX,
    IOU_MATCH_THRESHOLD,
    MIN_LABELED_SAMPLES,
    MODEL_VERSION,
    AdoptionDecision,
    BenchmarkReport,
    DamageAnnotation,
    DamageLocalizationBenchmark,
    DamageLocalizationError,
    DamageRegion,
    HeuristicDamageDetector,
    ImpactGeometry,
    PhysicsInputAdapter,
    iou,
    zone_for_slot,
)

pytestmark = pytest.mark.subtests


def region(slot="front_left", x0=0.1, y0=0.1, x1=0.4, y1=0.5, cls="dent", conf=0.9, **kw):
    return DamageRegion(slot, x0, y0, x1, y1, cls, conf, **kw)


def annotation(session_id="s-1", slot="front_left", r=None, actor="reviewer-01"):
    return DamageAnnotation(session_id, slot, r or region(slot=slot), actor)


class TestDamageRegion:
    def test_valid_region_and_geometry(self):
        r = region()
        assert 0.0 < r.area_fraction < 1.0
        cx, cy = r.centroid
        assert 0.1 < cx < 0.4 and 0.1 < cy < 0.5

    def test_rejects_invalid_class(self):
        with pytest.raises(DamageLocalizationError, match="INVALID_DAMAGE_CLASS"):
            region(cls="total_loss")

    def test_rejects_out_of_range_coordinates(self):
        for bad in ({"x0": -0.1}, {"x1": 1.5}, {"y0": 2.0}):
            with pytest.raises(DamageLocalizationError, match="INVALID_COORDINATE"):
                region(**bad)

    def test_rejects_empty_region(self):
        with pytest.raises(DamageLocalizationError, match="EMPTY_REGION"):
            region(x0=0.3, x1=0.3)

    def test_rejects_invalid_confidence(self):
        with pytest.raises(DamageLocalizationError, match="INVALID_CONFIDENCE"):
            region(conf=1.5)

    def test_damage_classes_are_the_provisional_set(self):
        assert DAMAGE_CLASSES == {"scratch", "dent", "glass_damage", "structural_deformation"}


class TestIoU:
    def test_identical_regions_score_one(self):
        assert iou(region(), region()) == 1.0

    def test_disjoint_regions_score_zero(self):
        assert iou(region(), region(x0=0.6, x1=0.9)) == 0.0

    def test_different_slots_never_match(self):
        assert iou(region(), region(slot="rear")) == 0.0

    def test_partial_overlap(self):
        a = region(x0=0.0, y0=0.0, x1=0.5, y1=1.0)
        b = region(x0=0.25, y0=0.0, x1=0.75, y1=1.0)
        assert 0.0 < iou(a, b) < 1.0


class TestPhysicsSeam:
    adapter = PhysicsInputAdapter()

    def test_exterior_slot_maps_to_zone(self):
        assert zone_for_slot("front_left") == "front"
        assert zone_for_slot("rear") == "rear"
        assert zone_for_slot("driver_side") == "side"
        assert zone_for_slot("undercarriage_engine") == "underbody"

    def test_non_exterior_slots_refused(self):
        for slot in ("vin_ocr", "doc_ocr", "interior_front"):
            assert zone_for_slot(slot) is None
            with pytest.raises(DamageLocalizationError, match="NOT_AN_EXTERIOR_SLOT"):
                self.adapter.to_impact_geometry(region(slot=slot))

    def test_area_fraction_drives_severity_tier(self):
        cosmetic = self.adapter.to_impact_geometry(region(x0=0.0, y0=0.0, x1=0.1, y1=0.1))
        functional = self.adapter.to_impact_geometry(region())
        structural = self.adapter.to_impact_geometry(region(x0=0.0, y0=0.0, x1=0.9, y1=0.9))
        assert cosmetic.severity_tier == "cosmetic" and cosmetic.depth_cm == 0.5
        assert functional.severity_tier == "functional" and functional.depth_cm == 3.0
        assert structural.severity_tier == "structural" and structural.depth_cm == 12.0
        assert cosmetic.area_fraction <= COSMETIC_AREA_MAX < functional.area_fraction <= FUNCTIONAL_AREA_MAX

    def test_zone_input_bridge_is_constructible(self):
        geometry = self.adapter.to_impact_geometry(region())
        try:
            zone_input = geometry.to_zone_input()
            assert zone_input.zone == "front" and zone_input.material == "mild_steel"
        except DamageLocalizationError as exc:
            assert exc.code == "PHYSICS_ENGINE_UNAVAILABLE"


class TestHeuristicBaseline:
    detector = HeuristicDamageDetector()

    def grid_with_damage_patch(self, size=36):
        grid = [[90] * size for _ in range(size)]
        for y in range(12, 20):
            for x in range(15, 22):
                grid[y][x] = 230
        return grid

    def test_detects_high_contrast_patch(self):
        found = self.detector.detect("front_left", self.grid_with_damage_patch())
        assert len(found) == 1
        r = found[0]
        assert 0.2 < r.x0 < 0.7 and 0.2 < r.y0 < 0.7
        assert r.model_version.endswith("heuristic-baseline")

    def test_uniform_frame_yields_no_regions(self):
        assert self.detector.detect("front_left", [[128] * 36 for _ in range(36)]) == ()

    def test_invalid_pixels_rejected(self):
        for bad in (None, [], [[1, 2], [3]]):
            with pytest.raises(DamageLocalizationError, match="INVALID_PIXELS"):
                self.detector.detect("s", bad)


class TestBenchmark:
    benchmark = DamageLocalizationBenchmark()

    def annotations(self, n, slot="front_left"):
        return [annotation(session_id=f"s-{i}", slot=slot) for i in range(n)]

    def test_perfect_predictions(self):
        truth = self.annotations(12)
        preds = [t.region for t in truth]
        report = self.benchmark.evaluate(preds, truth)
        assert report.matched == 12 and report.missed == 0 and report.false_positives == 0
        assert report.f1 == 1.0 and report.mean_iou == 1.0

    def test_class_mismatch_counts_as_miss(self):
        truth = [annotation(session_id="s-1")]
        preds = [region(slot="front_left", cls="scratch")]
        report = self.benchmark.evaluate(preds, truth)
        assert report.matched == 0 and report.missed == 1 and report.false_positives == 1

    def test_below_iou_threshold_counts_as_miss(self):
        truth = [annotation(session_id="s-1")]
        preds = [region(slot="front_left", x0=0.6, x1=0.9, y0=0.6, y1=0.9)]
        report = self.benchmark.evaluate(preds, truth)
        assert report.matched == 0 and report.precision == 0.0

    def test_empty_sets_report_none_metrics(self):
        report = self.benchmark.evaluate([], [])
        assert report.f1 is None and report.mean_iou is None

    def test_annotation_version_enforced(self):
        bad = DamageAnnotation("s", "front_left", region(), "r", schema_version="other-v2")
        with pytest.raises(DamageLocalizationError, match="ANNOTATION_VERSION_MISMATCH"):
            self.benchmark.evaluate([region()], [bad])

    def test_adoption_requires_strict_improvement(self):
        p, r = 10 / 11, 10 / 12
        f1 = 2 * p * r / (p + r)
        baseline = BenchmarkReport(12, 10, 2, 1, p, r, f1, 0.7)
        equal = BenchmarkReport(12, 10, 2, 1, p, r, f1, 0.7)
        worse_iou = BenchmarkReport(12, 12, 0, 0, 1.0, 1.0, 1.0, 0.6)
        better = BenchmarkReport(12, 12, 0, 0, 1.0, 1.0, 1.0, 0.95)
        assert not self.benchmark.adoption_gate(baseline, equal).adopt
        assert not self.benchmark.adoption_gate(baseline, worse_iou).adopt
        assert self.benchmark.adoption_gate(baseline, better).adopt

    def test_adoption_refuses_without_labels(self):
        thin = BenchmarkReport(2, 2, 0, 0, 1.0, 1.0, 1.0, 0.9)
        great = BenchmarkReport(2, 2, 0, 0, 1.0, 1.0, 1.0, 0.95)
        decision = self.benchmark.adoption_gate(thin, great)
        assert not decision.adopt
        assert any("INSUFFICIENT_LABELED_SAMPLES" in r for r in decision.reasons)

    def test_provisional_constants_are_explicit(self):
        assert IOU_MATCH_THRESHOLD == 0.50 and MIN_LABELED_SAMPLES == 10
        assert ANNOTATION_VERSION == "damage-annotation-v1"
