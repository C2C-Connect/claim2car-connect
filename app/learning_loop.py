"""Self-learning loop from reviewer decisions (Slice 9; recalibration Tier 2 #7).

Human-in-the-loop research distinguishes active learning (the system
selects uncertain cases for review) from machine teaching (experts
correct outputs). We already record attributed decisions; this module
closes the loop on top of the Slice 8 dataset:

- ``SessionConfidenceScorer`` scores a reviewed-or-reviewable session
  from its recorded quality-gate margins (weakest slot wins — a session
  is only as trustworthy as its weakest capture).
- ``TriagePolicy`` routes by confidence: LOW confidence bands the
  session for PRIORITY human review (active learning — reviewers see
  the uncertain cases first); higher confidence bands it STANDARD.
  Nothing is ever auto-approved: the recalibration brief explicitly
  rejects fully automated decisions, so confidence only orders the
  human queue.
- ``DriftMonitor`` watches any predictor (today: the quality gate vs.
  reviewer outcomes) and flags agreement drift. Flags are inspectable
  evidence for humans; the loop never adjusts its own thresholds.

No model adoption here: the loop is the measurement and routing layer.
Any future model must beat this baseline on the reviewer-decision
dataset before it is trusted (same rule as CV damage localization).
"""
from __future__ import annotations

from dataclasses import dataclass, field

# Provisional constants (calibration against real reviewer outcomes pending).
PRIORITY_REVIEW_MAX = 0.50   # sessions scoring below this go to priority review
DRIFT_WINDOW = 20            # observations in the rolling drift window
DRIFT_TOLERANCE = 0.10       # window agreement this far below baseline = drift

# Checks where a LOWER metric is better (metric must stay under threshold).
LOWER_IS_BETTER = frozenset({"exposure", "occlusion"})


class LearningLoopError(ValueError):
    """Stable-code loop failures. Codes are API surface."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(code if not detail else f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class TriageVerdict:
    session_id: str
    confidence: float
    band: str          # "priority-review" | "standard-review"
    weakest_slot: str
    weakest_check: str
    policy_version: str


def _check_confidence(name: str, metric: float, threshold: float) -> float:
    """Normalized margin in [0, 1): how far a passing check clears its bar.

    Failing checks contribute 0.0 — the session cannot look more
    confident than its worst check.
    """
    if threshold <= 0:
        return 0.0
    if name in LOWER_IS_BETTER:
        margin = (threshold - metric) / threshold
    else:
        margin = (metric - threshold) / threshold
    if margin <= 0:
        return 0.0
    return margin / (1.0 + margin)


class SessionConfidenceScorer:
    """Scores sessions from recorded quality-gate margins.

    Operates on the gate metadata embedded in QUALITY_RECORDED (Slice 8)
    or supplied directly. Sessions without gate metadata cannot be
    scored — the loop refuses to invent confidence.
    """

    policy_version = "triage-v1"

    def score_gate_metadata(self, session_id: str, gate: dict) -> TriageVerdict:
        if not isinstance(session_id, str) or not session_id.strip():
            raise LearningLoopError("INVALID_SESSION_ID")
        if (not isinstance(gate, dict) or not isinstance(gate.get("checks"), dict)
                or not gate["checks"]):
            raise LearningLoopError("GATE_METADATA_REQUIRED",
                                    "confidence is computed from recorded gate checks, never invented")
        weakest_slot, weakest_check, weakest = None, None, 1.0
        for slot, checks in gate["checks"].items():
            if not isinstance(checks, dict) or not checks:
                raise LearningLoopError("INVALID_GATE_CHECKS", slot)
            for name, check in checks.items():
                if not isinstance(check, dict) or "metric" not in check or "threshold" not in check:
                    raise LearningLoopError("INVALID_GATE_CHECKS", f"{slot}:{name}")
                confidence = _check_confidence(name, float(check["metric"]), float(check["threshold"]))
                if confidence < weakest:
                    weakest, weakest_slot, weakest_check = confidence, slot, name
        band = "priority-review" if weakest < PRIORITY_REVIEW_MAX else "standard-review"
        return TriageVerdict(
            session_id=session_id,
            confidence=round(weakest, 4),
            band=band,
            weakest_slot=weakest_slot,
            weakest_check=weakest_check,
            policy_version=self.policy_version,
        )

    def score_workflow(self, workflow) -> TriageVerdict:
        """Scores a workflow from its recorded QUALITY_RECORDED gate metadata."""
        import json

        for event in reversed(workflow.history):
            if event.kind == "QUALITY_RECORDED":
                payload = json.loads(event.payload_json)
                gate = payload.get("gate")
                if gate is None:
                    raise LearningLoopError("GATE_METADATA_REQUIRED",
                                            "session was quality-recorded without gate metadata")
                return self.score_gate_metadata(workflow.session_id, gate)
        raise LearningLoopError("QUALITY_NOT_RECORDED")


class TriagePolicy:
    """Routes sessions into human-review bands by confidence. Never automates."""

    def __init__(self, priority_max: float = PRIORITY_REVIEW_MAX):
        if not 0.0 < priority_max < 1.0:
            raise LearningLoopError("INVALID_PRIORITY_THRESHOLD")
        self.priority_max = priority_max

    def route(self, verdict: TriageVerdict) -> str:
        if not isinstance(verdict, TriageVerdict):
            raise LearningLoopError("INVALID_VERDICT")
        return "priority-review" if verdict.confidence < self.priority_max else "standard-review"

    def order_queue(self, verdicts) -> tuple:
        """Priority-band sessions first, then by ascending confidence.

        Active learning: the least confident sessions reach human
        reviewers first. Ordering only — every session is still
        human-reviewed.
        """
        ranked = sorted(verdicts, key=lambda v: v.confidence)
        priority = tuple(v for v in ranked if self.route(v) == "priority-review")
        standard = tuple(v for v in ranked if self.route(v) == "standard-review")
        return priority + standard


@dataclass
class DriftMonitor:
    """Agreement monitor between a predictor and reviewer outcomes.

    The loop measures; it never self-adjusts. A drift flag is evidence
    for humans to recalibrate thresholds or retrain a model.
    """

    window: int = DRIFT_WINDOW
    tolerance: float = DRIFT_TOLERANCE
    _observations: list = field(default_factory=list, init=False)

    def observe(self, predicted: bool, actual: bool) -> None:
        if not isinstance(predicted, bool) or not isinstance(actual, bool):
            raise LearningLoopError("INVALID_OBSERVATION", "boolean predicted/actual required")
        self._observations.append((predicted, actual))

    def observations(self) -> int:
        return len(self._observations)

    def _agreement(self, slice_) -> float | None:
        if not slice_:
            return None
        agree = sum(1 for p, a in slice_ if p == a)
        return agree / len(slice_)

    def report(self) -> dict:
        total = len(self._observations)
        baseline = self._agreement(self._observations)
        window = self._observations[-self.window:] if self.window else []
        window_agreement = self._agreement(window)
        drift = (
            baseline is not None and window_agreement is not None
            and len(window) >= self.window
            and window_agreement < baseline - self.tolerance
        )
        return {
            "observations": total,
            "baseline_agreement": round(baseline, 4) if baseline is not None else None,
            "window_size": len(window),
            "window_agreement": round(window_agreement, 4) if window_agreement is not None else None,
            "drift_flagged": drift,
            "monitor_version": "drift-v1",
        }
