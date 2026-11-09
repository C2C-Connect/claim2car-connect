"""
Forensic Integrity Score S_i — weighted geometric mean (All-or-Nothing Trap).

S_i = C_gps^0.30 × C_hash^0.45 × C_meta^0.25
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

from config import forensic_constants as C


@dataclass
class IntegrityInputs:
    gps_accuracy_m: Optional[float] = None
    master_hash_valid: bool = True
    chain_coverage: float = 1.0  # 0..1 fraction of expected photos present
    chain_uniqueness: float = 1.0  # 0..1 unique hashes / total
    meta_completeness: float = 1.0  # 0..1 required metadata fields present
    # Hard fail switches (All-or-Nothing)
    gps_spoof_suspected: bool = False
    hash_tamper_suspected: bool = False


@dataclass
class IntegrityResult:
    s_i: float
    c_gps: float
    c_hash: float
    c_meta: float
    tier: str  # pass | review | reject
    all_or_nothing_collapse: bool
    formula_version: str = C.VERSION


def c_gps_from_accuracy(accuracy_m: Optional[float], spoof: bool = False) -> float:
    if spoof:
        return 0.0
    if accuracy_m is None:
        return 0.5  # unknown
    for limit, coef in C.GPS_TIERS:
        if accuracy_m <= limit:
            return coef
    return C.GPS_TIER_FLOOR


def c_hash(master_valid: bool, coverage: float, uniqueness: float, tamper: bool = False) -> float:
    if tamper or not master_valid:
        return 0.0
    cov = max(0.0, min(1.0, coverage))
    uni = max(0.0, min(1.0, uniqueness))
    c_chain = math.sqrt(cov * uni)
    return 0.5 * (1.0 if master_valid else 0.0) + 0.5 * c_chain


def c_meta(completeness: float) -> float:
    return max(0.0, min(1.0, completeness))


def compute_s_i(inp: IntegrityInputs) -> IntegrityResult:
    cg = c_gps_from_accuracy(inp.gps_accuracy_m, inp.gps_spoof_suspected)
    ch = c_hash(inp.master_hash_valid, inp.chain_coverage, inp.chain_uniqueness, inp.hash_tamper_suspected)
    cm = c_meta(inp.meta_completeness)

    w = C.S_I_WEIGHTS
    # Weighted geometric mean: exp(Σ w_i * ln(c_i)) with guard for zeros
    collapse = False
    if cg <= 0 or ch <= 0 or cm <= 0:
        s_i = 0.0
        collapse = True
    else:
        s_i = math.exp(
            w["gps"] * math.log(cg)
            + w["hash"] * math.log(ch)
            + w["meta"] * math.log(cm)
        )

    if s_i >= C.S_I_PASS:
        tier = "pass"
    elif s_i >= C.S_I_REJECT:
        tier = "review"
    else:
        tier = "reject"

    return IntegrityResult(
        s_i=round(s_i, 4),
        c_gps=round(cg, 4),
        c_hash=round(ch, 4),
        c_meta=round(cm, 4),
        tier=tier,
        all_or_nothing_collapse=collapse,
    )
