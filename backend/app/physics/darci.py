"""
DARCI physics engine — deterministic crash energy / structural risk model.

Compiled later to WASM for on-device; this is the pure-Python server mirror
and the source of truth for unit tests.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

from config import forensic_constants as C


@dataclass
class ZoneInput:
    zone: str  # front | rear | side | roof | underbody
    depth_cm: float
    area_cm2: float = 0.0
    material: str = "mild_steel"  # key into SIGMA_YIELD_MPA


@dataclass
class DarciInput:
    mass_kg: float
    velocity_kph: float
    zones: Sequence[ZoneInput]
    # Optional strain-rate / temperature proxies for Johnson-Cook
    strain_rate_proxy: float = 1.0
    temperature_homologous: float = 0.0  # T* in [0,1]


@dataclass
class DarciResult:
    v_mps: float
    e_k_j: float
    e_k_kj: float
    ke_factor: float
    force_n: float
    peak_g: float
    zones: List[Dict]
    r_y_max: float
    p_brittle: float
    shannon_h: float
    p_struct: float
    r_struct: float
    p_tl_physics: float
    entropy_override: bool
    overrides_applied: List[str] = field(default_factory=list)
    formula_version: str = C.VERSION


def _clip(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def velocity_mps(v_kph: float) -> float:
    return v_kph * 1000.0 / 3600.0


def kinetic_energy_j(mass_kg: float, v_mps: float) -> float:
    return 0.5 * mass_kg * v_mps * v_mps


def ke_factor(e_k_kj: float) -> float:
    return min(e_k_kj / C.KE_FACTOR_DIVISOR_KJ, C.KE_FACTOR_CAP)


def impact_force_n(e_k_j: float, depth_m: float) -> float:
    d = max(depth_m, 0.005)
    return e_k_j / d


def peak_deceleration_g(force_n: float, mass_kg: float) -> float:
    if mass_kg <= 0:
        return 0.0
    return force_n / (mass_kg * 9.81)


def stress_mpa(force_n: float, area_m2: float) -> float:
    if area_m2 <= 0:
        return 0.0
    return (force_n / 1000.0) / area_m2  # kN / m² → MPa


def yield_ratio(sigma_mpa: float, material: str) -> float:
    sy = C.SIGMA_YIELD_MPA.get(material.lower(), C.SIGMA_YIELD_MPA["mild_steel"])
    if sy <= 0:
        return 0.0
    return sigma_mpa / sy


def johnson_cook_sigma(
    A: float = 250.0,
    B: float = 300.0,
    n: float = 0.3,
    C_jc: float = 0.02,
    m: float = 0.8,
    eps_p: float = 0.1,
    strain_rate: float = 1.0,
    strain_rate_0: float = 1.0,
    t_star: float = 0.0,
) -> float:
    """Simplified Johnson-Cook: σ = [A + B ε_p^n][1 + C ln(ε̇/ε̇₀)][1 − T*^m]."""
    term1 = A + B * (max(eps_p, 1e-9) ** n)
    term2 = 1.0 + C_jc * math.log(max(strain_rate / strain_rate_0, 1e-9))
    term3 = 1.0 - (max(min(t_star, 1.0), 0.0) ** m)
    return term1 * term2 * term3


def brittle_fracture_risk(r_y: float, strain_rate_proxy: float, beta: float = C.P_BRITTLE_BETA) -> float:
    """P_brittle = min(β · ε̇_proxy · min(r_y, 3) / 3, 0.99)."""
    return min(beta * strain_rate_proxy * min(r_y, 3.0) / 3.0, C.P_BRITTLE_CAP)


def shannon_entropy(depths: Sequence[float]) -> float:
    """H = −Σ p_i log2(p_i), p_i = d_i / Σ d_j."""
    total = sum(max(d, 0.0) for d in depths)
    if total <= 0:
        return 0.0
    h = 0.0
    for d in depths:
        p = max(d, 0.0) / total
        if p > 0:
            h -= p * math.log2(p)
    return h


def p_struct(r_y: float, p_brittle: float, w_zone: float = 1.0) -> float:
    """max(0,(r_y−0.6)·0.45) + 0.4·P_brittle, then × w_zone, capped at 0.99."""
    raw = max(0.0, (r_y - C.P_STRUCT_RY_THRESHOLD) * C.P_STRUCT_RY_SCALE) + C.P_STRUCT_BRITTLE_SCALE * p_brittle
    return min(raw * w_zone, C.P_STRUCT_CAP)


def r_struct(r_y: float, p_brittle: float, h: float, zone_factor: float = 1.0) -> float:
    """
    Weighted structural risk (Option B):
    0.48·(r_y/2.2) + 0.28·P_brittle + 0.14·min(H,1.0) + 0.10·zone_factor
    """
    term_ry = C.R_STRUCT_W_RY * (r_y / C.R_STRUCT_RY_DIVISOR)
    term_b = C.R_STRUCT_W_BRITTLE * p_brittle
    term_h = C.R_STRUCT_W_ENTROPY * min(h, 1.0)
    term_z = C.R_STRUCT_W_ZONE * zone_factor
    return _clip(term_ry + term_b + term_h + term_z, 0.0, 1.0)


def p_tl_physics(
    ke_f: float,
    v_kph: float,
    mean_depth_cm: float,
    zone_bonus: float,
    p_brittle: float,
) -> float:
    """
    Physics total-loss signal:
    clip(0.05 + ke + vel + deform + zone_bonus + fracture, 0, 0.99)
    """
    vel = min(v_kph / 120.0, 0.35)  # normalize
    deform = min(mean_depth_cm / 80.0, 0.30)
    fracture = 0.15 * p_brittle
    raw = 0.05 + ke_f + vel + deform + zone_bonus + fracture
    return _clip(raw, 0.0, 0.99)


def run_darci(inp: DarciInput) -> DarciResult:
    mass = _clip(inp.mass_kg, C.CURB_MASS_KG_MIN, C.CURB_MASS_KG_MAX)
    v_mps = velocity_mps(inp.velocity_kph)
    e_k_j = kinetic_energy_j(mass, v_mps)
    e_k_kj = e_k_j / 1000.0
    ke_f = ke_factor(e_k_kj)

    depths = [z.depth_cm for z in inp.zones] or [0.0]
    mean_depth_cm = sum(depths) / len(depths)
    max_depth_cm = max(depths)
    max_depth_m = max_depth_cm / 100.0

    force_n = impact_force_n(e_k_j, max_depth_m)
    peak_g = peak_deceleration_g(force_n, mass)

    zone_results = []
    r_y_values = []
    for z in inp.zones:
        area_m2 = C.A_ZONE_M2.get(z.zone.lower(), 0.50)
        if z.area_cm2 > 0:
            # prefer measured area when available
            area_m2 = max(z.area_cm2 / 10000.0, 0.01)
        sigma = stress_mpa(force_n, area_m2)
        r_y = yield_ratio(sigma, z.material)
        r_y_values.append(r_y)
        zone_results.append(
            {
                "zone": z.zone,
                "depth_cm": z.depth_cm,
                "area_cm2": z.area_cm2,
                "material": z.material,
                "area_m2": area_m2,
                "sigma_mpa": sigma,
                "r_y": r_y,
            }
        )

    r_y_max = max(r_y_values) if r_y_values else 0.0
    p_brit = brittle_fracture_risk(r_y_max, inp.strain_rate_proxy)
    h = shannon_entropy(depths)
    entropy_override = h > C.ENTROPY_AI_OVERRIDE_BITS

    # zone_bonus: higher for side (FMVSS 214 relevance) and multi-zone
    zone_bonus = 0.0
    zones_hit = {z.zone.lower() for z in inp.zones if z.depth_cm > 2.0}
    if "side" in zones_hit:
        zone_bonus += 0.08
    if len(zones_hit) >= 2:
        zone_bonus += 0.05

    p_s = p_struct(r_y_max, p_brit, w_zone=1.0 + zone_bonus)
    r_s = r_struct(r_y_max, p_brit, h, zone_factor=1.0 if zones_hit else 0.0)
    p_phys = p_tl_physics(ke_f, inp.velocity_kph, mean_depth_cm, zone_bonus, p_brit)

    overrides: List[str] = []
    # Severe absolute override
    if e_k_kj > C.SEVERE_EK_KJ and max_depth_cm > C.SEVERE_DEPTH_CM:
        p_phys = max(p_phys, C.SEVERE_P_PHYSICS_FLOOR)
        overrides.append("severe_energy_depth")
    # Low-impact absolute override
    if (
        e_k_kj < C.LOW_IMPACT_EK_KJ
        and r_y_max < C.LOW_IMPACT_RY
        and inp.velocity_kph < C.LOW_IMPACT_V_KPH
    ):
        p_phys = min(p_phys, C.LOW_IMPACT_P_PHYSICS_CEIL)
        overrides.append("low_impact_guard")

    if entropy_override:
        overrides.append("shannon_entropy_ai_override")

    return DarciResult(
        v_mps=v_mps,
        e_k_j=e_k_j,
        e_k_kj=e_k_kj,
        ke_factor=ke_f,
        force_n=force_n,
        peak_g=peak_g,
        zones=zone_results,
        r_y_max=r_y_max,
        p_brittle=p_brit,
        shannon_h=h,
        p_struct=p_s,
        r_struct=r_s,
        p_tl_physics=p_phys,
        entropy_override=entropy_override,
        overrides_applied=overrides,
    )
