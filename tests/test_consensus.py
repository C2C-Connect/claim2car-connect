"""
Unit tests for 55/45 ensemble and commercial fork.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.analysis.consensus import (
    VisionSignal,
    blend_55_45,
    decide_commercial_fork,
    run_ensemble,
    two_thirds_vote,
)
from backend.app.physics.darci import DarciInput, ZoneInput, run_darci
from config import forensic_constants as C


def test_blend_weights():
    p = blend_55_45(0.8, 0.2)
    assert abs(p - 0.53) < 1e-9


def test_commercial_fork_threshold():
    assert decide_commercial_fork(0.55) == "total_loss_dealer"
    assert decide_commercial_fork(0.549) == "repairable_shop"
    assert decide_commercial_fork(0.0) == "repairable_shop"
    assert decide_commercial_fork(1.0) == "total_loss_dealer"


def test_two_thirds_agreement():
    mean, disagree = two_thirds_vote({"a": 0.6, "b": 0.62, "c": 0.58})
    assert not disagree
    assert 0.55 < mean < 0.65


def test_two_thirds_disagreement():
    mean, disagree = two_thirds_vote({"a": 0.1, "b": 0.9, "c": 0.5})
    assert disagree


def test_ensemble_physics_primary():
    darci = run_darci(
        DarciInput(
            mass_kg=1800.0,
            velocity_kph=55.0,
            zones=[ZoneInput(zone="front", depth_cm=25.0, material="mild_steel")],
        )
    )
    vision = VisionSignal(p_tl_ai=0.2, source="ensemble_vision", confidence=0.7)
    ens = run_ensemble(darci, vision)
    expected = blend_55_45(darci.p_tl_physics, 0.2)
    assert abs(ens.p_ensemble - expected) < 1e-9
    assert ens.physics_weight == C.ENSEMBLE_PHYSICS_WEIGHT
    assert ens.ai_weight == C.ENSEMBLE_AI_WEIGHT
    assert ens.decision in ("total_loss_dealer", "repairable_shop")


def test_physics_fallback_uses_physics_as_ai():
    darci = run_darci(
        DarciInput(
            mass_kg=1500.0,
            velocity_kph=40.0,
            zones=[ZoneInput(zone="rear", depth_cm=12.0)],
        )
    )
    vision = VisionSignal(p_tl_ai=0.99, source="physics_fallback", confidence=1.0)
    ens = run_ensemble(darci, vision)
    assert abs(ens.p_tl_ai - darci.p_tl_physics) < 1e-9
    assert "physics_fallback_timeout" in ens.overrides_applied
