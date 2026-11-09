"""
Internal ACV valuation module.

Tri-source blend (40/40/20) over admin-managed tables + fallback curve.
No Black Book / Manheim / NADA runtime dependency.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence, Tuple

from config import forensic_constants as C


@dataclass
class MarketComp:
    source: str  # internal_a | internal_b | internal_c | fallback
    value_usd: float
    weight: float = 0.0


@dataclass
class ACVResult:
    acv_baseline: float
    acv_adjusted: float
    p_s: float
    r_struct: float
    comps: list
    claim2car_price: float
    method: str
    formula_version: str = C.VERSION


def fallback_acv(age_years: float) -> float:
    """max(4000, 32000 · 0.86^age)."""
    age = max(0.0, age_years)
    return max(C.ACV_FALLBACK_FLOOR, C.ACV_FALLBACK_BASE * (C.ACV_FALLBACK_DECAY ** age))


def structural_penalty(r_struct: float) -> float:
    """P_s = min(0.45, R_struct · 0.6)."""
    return min(C.P_S_CAP, max(0.0, r_struct) * C.P_S_R_STRUCT_SCALE)


def blend_acv(
    source_values: Sequence[float],
    weights: Tuple[float, float, float] = C.ACV_BLEND_WEIGHTS,
) -> Tuple[float, list]:
    """
    40/40/20 blend over up to 3 internal sources.
    Missing sources are dropped and weights renormalized.
    """
    pairs = [(v, w) for v, w in zip(source_values, weights) if v is not None and v > 0]
    if not pairs:
        return 0.0, []
    total_w = sum(w for _, w in pairs)
    comps = []
    blended = 0.0
    labels = ("internal_a", "internal_b", "internal_c")
    for i, (v, w) in enumerate(pairs):
        nw = w / total_w
        blended += v * nw
        comps.append({"source": labels[i] if i < 3 else f"source_{i}", "value_usd": v, "weight": round(nw, 4)})
    return blended, comps


def compute_acv(
    r_struct: float,
    age_years: float,
    internal_a: Optional[float] = None,
    internal_b: Optional[float] = None,
    internal_c: Optional[float] = None,
) -> ACVResult:
    values = [internal_a, internal_b, internal_c]
    present = [v for v in values if v is not None and v > 0]
    if present:
        baseline, comps = blend_acv([v if v is not None else 0.0 for v in values])
        method = "tri_source_blend"
    else:
        baseline = fallback_acv(age_years)
        comps = [{"source": "fallback_curve", "value_usd": baseline, "weight": 1.0}]
        method = "fallback_curve"

    p_s = structural_penalty(r_struct)
    adjusted = baseline * (1.0 - p_s)
    c2c_price = baseline * C.CLAIM2CAR_PRICE_MULTIPLIER

    return ACVResult(
        acv_baseline=round(baseline, 2),
        acv_adjusted=round(adjusted, 2),
        p_s=round(p_s, 4),
        r_struct=round(r_struct, 4),
        comps=comps,
        claim2car_price=round(c2c_price, 2),
        method=method,
    )
