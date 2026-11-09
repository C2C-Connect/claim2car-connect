"""
55/45 Bayesian consensus + 2/3 model voting + sanity matrix.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from config import forensic_constants as C
from backend.app.physics.darci import DarciResult


@dataclass
class VisionSignal:
    """Aggregated visual / LMM total-loss probability and provenance."""
    p_tl_ai: float
    source: str
    confidence: float = 0.5
    model_votes: Optional[Dict[str, float]] = None
    disagreement: bool = False
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EnsembleResult:
    p_ensemble: float
    decision: str
    p_tl_physics: float
    p_tl_ai: float
    physics_weight: float
    ai_weight: float
    model_disagreement: bool
    entropy_override: bool
    overrides_applied: List[str]
    formula_version: str = C.VERSION


def blend_55_45(p_physics: float, p_ai: float) -> float:
    return (
        C.ENSEMBLE_PHYSICS_WEIGHT * p_physics
        + C.ENSEMBLE_AI_WEIGHT * p_ai
    )


def decide_commercial_fork(p_ensemble: float) -> str:
    if p_ensemble >= C.ENSEMBLE_TOTAL_LOSS_THRESHOLD:
        return "total_loss_dealer"
    return "repairable_shop"


def two_thirds_vote(votes: Dict[str, float], threshold: float = C.MODEL_VOTE_THRESHOLD) -> tuple[float, bool]:
    if not votes:
        return 0.5, True
    vals = list(votes.values())
    mean = sum(vals) / len(vals)
    agree = sum(1 for v in vals if abs(v - mean) <= 0.15)
    disagreement = (agree / len(vals)) < threshold
    return mean, disagreement


def run_ensemble(darci: DarciResult, vision: VisionSignal) -> EnsembleResult:
    p_phys = darci.p_tl_physics
    p_ai = vision.p_tl_ai
    overrides = list(darci.overrides_applied)
    if darci.entropy_override:
        overrides.append("entropy_flag_for_qc")
    if vision.disagreement:
        overrides.append("model_disagreement")
    if vision.source == "physics_fallback":
        p_ai = p_phys
        overrides.append("physics_fallback_timeout")
    p_ens = max(0.0, min(1.0, blend_55_45(p_phys, p_ai)))
    decision = decide_commercial_fork(p_ens)
    return EnsembleResult(
        p_ensemble=p_ens,
        decision=decision,
        p_tl_physics=p_phys,
        p_tl_ai=p_ai,
        physics_weight=C.ENSEMBLE_PHYSICS_WEIGHT,
        ai_weight=C.ENSEMBLE_AI_WEIGHT,
        model_disagreement=vision.disagreement,
        entropy_override=darci.entropy_override,
        overrides_applied=overrides,
    )
