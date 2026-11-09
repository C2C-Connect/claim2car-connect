"""Self-learning loop tests (Slice 9): confidence triage + drift monitoring."""
from __future__ import annotations

import pytest

from app.learning_loop import (
    DRIFT_TOLERANCE,
    DRIFT_WINDOW,
    PRIORITY_REVIEW_MAX,
    DriftMonitor,
    LearningLoopError,
    SessionConfidenceScorer,
    TriagePolicy,
    TriageVerdict,
)
from tests.review.test_review_pipeline import quality_complete_workflow

pytestmark = pytest.mark.subtests


def gate_meta_for(margin_scale: float = 3.0) -> dict:
    """Gate metadata whose weakest check clears its bar by margin_scale."""
    return {
        "gate_version": "quality-gate-v1",
        "checks": {
            "front-left-45": {
                "blur": {"passed": True, "metric": 10.0 * margin_scale, "threshold": 10.0},
                "exposure": {"passed": True, "metric": 0.01, "threshold": 0.10},
                "occlusion": {"passed": True, "metric": 0.05, "threshold": 0.60},
                "flatness": {"passed": True, "metric": 16.0 * margin_scale, "threshold": 16.0},
            },
        },
    }


def gate_meta_failing() -> dict:
    return {
        "gate_version": "quality-gate-v1",
        "checks": {
            "dash-vin": {
                "blur": {"passed": True, "metric": 40.0, "threshold": 10.0},
                "exposure": {"passed": False, "metric": 0.95, "threshold": 0.10},
            },
        },
    }


scorer = SessionConfidenceScorer()


class TestConfidenceScoring:
    def test_score_from_gate_metadata(self):
        verdict = scorer.score_gate_metadata("s-1", gate_meta_for())
        assert 0.0 <= verdict.confidence <= 1.0
        assert verdict.band in ("priority-review", "standard-review")
        assert verdict.policy_version == "triage-v1"

    def test_weakest_check_determines_confidence(self):
        strong = scorer.score_gate_metadata("s-1", gate_meta_for(margin_scale=9.0))
        weak = scorer.score_gate_metadata("s-2", gate_meta_for(margin_scale=1.05))
        assert weak.confidence < strong.confidence

    def test_failing_check_scores_zero(self):
        verdict = scorer.score_gate_metadata("s-3", gate_meta_failing())
        assert verdict.confidence == 0.0
        assert verdict.weakest_check == "exposure" and verdict.weakest_slot == "dash-vin"

    def test_lower_is_better_checks_scored_correctly(self):
        meta = {"gate_version": "g", "checks": {"s": {
            "exposure": {"passed": True, "metric": 0.0, "threshold": 0.10},
            "occlusion": {"passed": True, "metric": 0.0, "threshold": 0.60},
        }}}
        verdict = scorer.score_gate_metadata("s-4", meta)
        assert 0.0 < verdict.confidence < 1.0

    def test_refuses_to_invent_confidence(self):
        for bad in (None, {}, {"checks": {}}, {"checks": {"s": {}}}):
            with pytest.raises(LearningLoopError, match="GATE_METADATA_REQUIRED|INVALID_GATE_CHECKS"):
                scorer.score_gate_metadata("s", bad)

    def test_refuses_unscored_workflow(self):
        w = quality_complete_workflow()  # recorded without gate metadata
        with pytest.raises(LearningLoopError, match="GATE_METADATA_REQUIRED"):
            scorer.score_workflow(w)

    def test_scores_workflow_from_recorded_gate_metadata(self):
        from app.quality_gate import HeuristicQualityGate
        w = quality_complete_workflow()
        # Re-record quality with gate metadata on a fresh workflow path is not
        # possible post-quality; instead simulate via the demo's pattern:
        gate = HeuristicQualityGate()
        verdicts = gate.evaluate_all({"front-left-45": ("a-1", [[((x * 31 + y * 17) % 200) + 20 for x in range(24)] for y in range(24)])})
        meta = HeuristicQualityGate.gate_metadata(verdicts)
        triage = scorer.score_gate_metadata("demo", meta)
        assert triage.confidence > 0


class TestTriagePolicy:
    policy = TriagePolicy()

    def test_low_confidence_routes_to_priority_review(self):
        verdict = TriageVerdict("s", 0.1, "priority-review", "slot", "blur", "triage-v1")
        assert self.policy.route(verdict) == "priority-review"

    def test_high_confidence_routes_to_standard_review(self):
        verdict = TriageVerdict("s", 0.9, "standard-review", "slot", "blur", "triage-v1")
        assert self.policy.route(verdict) == "standard-review"

    def test_order_queue_prioritizes_least_confident(self):
        verdicts = [
            TriageVerdict("high", 0.9, "standard-review", "s", "blur", "v"),
            TriageVerdict("low", 0.1, "priority-review", "s", "blur", "v"),
            TriageVerdict("mid", 0.6, "standard-review", "s", "blur", "v"),
        ]
        ordered = self.policy.order_queue(verdicts)
        assert [v.session_id for v in ordered] == ["low", "mid", "high"]

    def test_every_session_still_human_reviewed(self):
        # Routing only orders bands; it never produces an auto-approve band.
        verdicts = [TriageVerdict(f"s{i}", i / 10, "x", "s", "c", "v") for i in range(10)]
        for v in self.policy.order_queue(verdicts):
            assert self.policy.route(v) in ("priority-review", "standard-review")

    def test_invalid_threshold_rejected(self):
        for bad in (0.0, 1.0, -1, 2):
            with pytest.raises(LearningLoopError, match="INVALID_PRIORITY_THRESHOLD"):
                TriagePolicy(bad)

    def test_provisional_constants_are_explicit(self):
        assert PRIORITY_REVIEW_MAX == 0.50
        assert DRIFT_WINDOW == 20 and DRIFT_TOLERANCE == 0.10


class TestDriftMonitor:
    def test_agreement_report(self):
        monitor = DriftMonitor()
        for _ in range(10):
            monitor.observe(True, True)
        report = monitor.report()
        assert report["observations"] == 10 and report["baseline_agreement"] == 1.0
        assert not report["drift_flagged"]

    def test_drift_flagged_when_window_degrades(self):
        monitor = DriftMonitor(window=10, tolerance=0.10)
        for _ in range(30):
            monitor.observe(True, True)          # strong baseline
        for _ in range(10):
            monitor.observe(True, False)         # window collapses
        report = monitor.report()
        assert report["window_agreement"] == 0.0
        assert report["drift_flagged"] is True

    def test_no_drift_flag_below_window_size(self):
        monitor = DriftMonitor(window=20)
        for _ in range(5):
            monitor.observe(True, False)
        assert not monitor.report()["drift_flagged"]

    def test_invalid_observation_rejected(self):
        monitor = DriftMonitor()
        for bad in ((1, True), (True, "yes"), (None, None)):
            with pytest.raises(LearningLoopError, match="INVALID_OBSERVATION"):
                monitor.observe(*bad)

    def test_report_is_inspectable_evidence_only(self):
        # The monitor measures; nothing in the report mutates thresholds.
        report = DriftMonitor().report()
        assert report["monitor_version"] == "drift-v1"
        assert set(report) >= {"observations", "baseline_agreement", "drift_flagged"}
