"""
Unit tests for DARCI physics engine — worked examples and sanity guards.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.physics.darci import (  # noqa: E402
    DarciInput,
    ZoneInput,
    brittle_fracture_risk,
    impact_force_n,
    ke_factor,
    kinetic_energy_j,
    p_struct,
    p_tl_physics,
    peak_deceleration_g,
    r_struct,
    run_darci,
    shannon_entropy,
    stress_mpa,
    velocity_mps,
    yield_ratio,
)
from config import forensic_constants as C  # noqa: E402


def test_velocity_conversion():
    # 36 kph = 10 m/s
    assert abs(velocity_mps(36.0) - 10.0) < 1e-9
    # 0
    assert velocity_mps(0.0) == 0.0


def test_kinetic_energy_worked_example():
    # m=1500 kg, v=10 m/s → E_k = 0.5*1500*100 = 75000 J = 75 kJ
    e = kinetic_energy_j(1500.0, 10.0)
    assert abs(e - 75000.0) < 1e-6
    assert abs(e / 1000.0 - 75.0) < 1e-6


def test_ke_factor_cap():
    assert ke_factor(0.0) == 0.0
    assert ke_factor(250.0) == 0.5  # 250/500
    assert ke_factor(1000.0) == C.KE_FACTOR_CAP  # capped


def test_impact_force_min_depth():
    # depth clamped to 0.005 m
    f = impact_force_n(1000.0, 0.0)
    assert abs(f - 1000.0 / 0.005) < 1e-6


def test_peak_g():
    # F=14715 N, m=1500 → G = 14715/(1500*9.81) ≈ 1.0
    g = peak_deceleration_g(14715.0, 1500.0)
    assert abs(g - 1.0) < 0.01


def test_stress_and_yield():
    # 100 kN over 0.5 m² → 200 MPa; mild steel 250 → r_y=0.8
    sigma = stress_mpa(100_000.0, 0.5)
    assert abs(sigma - 200.0) < 1e-6
    r_y = yield_ratio(200.0, "mild_steel")
    assert abs(r_y - 200.0 / 250.0) < 1e-9


def test_brittle_and_p_struct():
    pb = brittle_fracture_risk(1.5, 1.0)
    assert 0 < pb <= C.P_BRITTLE_CAP
    ps = p_struct(1.0, 0.5)
    assert 0 < ps <= C.P_STRUCT_CAP


def test_shannon_entropy_uniform():
    # two equal depths → H = 1 bit
    h = shannon_entropy([10.0, 10.0])
    assert abs(h - 1.0) < 1e-9


def test_shannon_entropy_single():
    assert shannon_entropy([5.0]) == 0.0


def test_r_struct_bounds():
    r = r_struct(2.0, 0.9, 3.0, zone_factor=1.0)
    assert 0.0 <= r <= 1.0


def test_low_impact_guard():
    """E_k low, r_y low, v < 25 → p_physics ≤ 0.15.

    Gentle impact: low speed + larger crumple distance + large area so stress/r_y stay low.
    """
    result = run_darci(
        DarciInput(
            mass_kg=1400.0,
            velocity_kph=12.0,
            zones=[
                ZoneInput(
                    zone="front",
                    depth_cm=25.0,
                    area_cm2=12000.0,
                    material="mild_steel",
                )
            ],
        )
    )
    assert result.e_k_kj < C.LOW_IMPACT_EK_KJ
    assert result.r_y_max < C.LOW_IMPACT_RY
    assert "low_impact_guard" in result.overrides_applied
    assert result.p_tl_physics <= C.LOW_IMPACT_P_PHYSICS_CEIL


def test_severe_override():
    """High energy + deep crush → p_physics ≥ 0.75."""
    result = run_darci(
        DarciInput(
            mass_kg=2000.0,
            velocity_kph=120.0,
            zones=[ZoneInput(zone="front", depth_cm=50.0, area_cm2=5000.0, material="mild_steel")],
        )
    )
    assert result.e_k_kj > C.SEVERE_EK_KJ
    assert "severe_energy_depth" in result.overrides_applied
    assert result.p_tl_physics >= C.SEVERE_P_PHYSICS_FLOOR


def test_full_run_produces_all_fields():
    result = run_darci(
        DarciInput(
            mass_kg=1600.0,
            velocity_kph=45.0,
            zones=[
                ZoneInput(zone="front", depth_cm=18.0, area_cm2=3000.0, material="ahss"),
                ZoneInput(zone="side", depth_cm=8.0, area_cm2=1500.0, material="mild_steel"),
            ],
        )
    )
    assert result.v_mps > 0
    assert result.e_k_kj > 0
    assert 0 <= result.p_tl_physics <= 0.99
    assert 0 <= result.p_struct <= 0.99
    assert 0 <= result.r_struct <= 1.0
    assert len(result.zones) == 2
    assert result.formula_version == C.VERSION


def test_no_owner_payout_constant():
    assert not hasattr(C, "OPERATOR_PAYOUT_USD")
    assert not hasattr(C, "OWNER_PAYOUT_USD")
    assert not hasattr(C, "OWNER_CONSENT_PAYOUT_USD")
