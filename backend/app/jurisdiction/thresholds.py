"""
51-jurisdiction total-loss thresholds (50 states + DC).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from config import forensic_constants as C


@dataclass
class JurisdictionRule:
    code: str
    name: str
    mode: str  # percent | tlf
    threshold: float
    structural_guideline: Optional[float] = None
    notes: str = ""


JURISDICTIONS: Dict[str, JurisdictionRule] = {
    "AL": JurisdictionRule("AL", "Alabama", "percent", 0.75),
    "AK": JurisdictionRule("AK", "Alaska", "percent", 0.75),
    "AZ": JurisdictionRule("AZ", "Arizona", "tlf", 1.0, notes="TLF formula state"),
    "AR": JurisdictionRule("AR", "Arkansas", "percent", 0.70),
    "CA": JurisdictionRule("CA", "California", "percent", 0.80),
    "CO": JurisdictionRule("CO", "Colorado", "percent", 1.00),
    "CT": JurisdictionRule("CT", "Connecticut", "percent", 0.75),
    "DE": JurisdictionRule("DE", "Delaware", "percent", 0.75),
    "DC": JurisdictionRule("DC", "District of Columbia", "percent", 0.75),
    "FL": JurisdictionRule("FL", "Florida", "percent", 0.80),
    "GA": JurisdictionRule("GA", "Georgia", "tlf", 1.0, notes="TLF"),
    "HI": JurisdictionRule("HI", "Hawaii", "percent", 0.75),
    "ID": JurisdictionRule("ID", "Idaho", "percent", 1.00),
    "IL": JurisdictionRule("IL", "Illinois", "percent", 0.67),
    "IN": JurisdictionRule("IN", "Indiana", "percent", 0.70),
    "IA": JurisdictionRule("IA", "Iowa", "percent", 0.75),
    "KS": JurisdictionRule("KS", "Kansas", "percent", 0.75),
    "KY": JurisdictionRule("KY", "Kentucky", "percent", 0.75),
    "LA": JurisdictionRule("LA", "Louisiana", "percent", 0.75),
    "ME": JurisdictionRule("ME", "Maine", "percent", 0.75),
    "MD": JurisdictionRule("MD", "Maryland", "percent", 0.75),
    "MA": JurisdictionRule("MA", "Massachusetts", "percent", 0.75),
    "MI": JurisdictionRule("MI", "Michigan", "percent", 0.75),
    "MN": JurisdictionRule("MN", "Minnesota", "percent", 0.70),
    "MS": JurisdictionRule("MS", "Mississippi", "percent", 0.70),
    "MO": JurisdictionRule("MO", "Missouri", "percent", 0.75),
    "MT": JurisdictionRule("MT", "Montana", "percent", 1.00),
    "NE": JurisdictionRule("NE", "Nebraska", "percent", 0.75),
    "NV": JurisdictionRule("NV", "Nevada", "percent", 0.65),
    "NH": JurisdictionRule("NH", "New Hampshire", "percent", 0.75),
    "NJ": JurisdictionRule("NJ", "New Jersey", "percent", 0.75),
    "NM": JurisdictionRule("NM", "New Mexico", "percent", 1.00),
    "NY": JurisdictionRule("NY", "New York", "percent", 0.75),
    "NC": JurisdictionRule("NC", "North Carolina", "percent", 0.75),
    "ND": JurisdictionRule("ND", "North Dakota", "percent", 0.75),
    "OH": JurisdictionRule("OH", "Ohio", "tlf", 1.0, notes="TLF"),
    "OK": JurisdictionRule("OK", "Oklahoma", "percent", 0.60),
    "OR": JurisdictionRule("OR", "Oregon", "percent", 0.80),
    "PA": JurisdictionRule("PA", "Pennsylvania", "percent", 0.75),
    "RI": JurisdictionRule("RI", "Rhode Island", "percent", 0.75),
    "SC": JurisdictionRule("SC", "South Carolina", "percent", 0.75),
    "SD": JurisdictionRule("SD", "South Dakota", "percent", 1.00),
    "TN": JurisdictionRule("TN", "Tennessee", "percent", 0.75),
    "TX": JurisdictionRule("TX", "Texas", "percent", 1.00, structural_guideline=0.75, notes="100% standard; 75% structural guideline"),
    "UT": JurisdictionRule("UT", "Utah", "percent", 1.00),
    "VT": JurisdictionRule("VT", "Vermont", "percent", 1.00),
    "VA": JurisdictionRule("VA", "Virginia", "percent", 0.75),
    "WA": JurisdictionRule("WA", "Washington", "percent", 1.00),
    "WV": JurisdictionRule("WV", "West Virginia", "percent", 0.75),
    "WI": JurisdictionRule("WI", "Wisconsin", "percent", 0.70),
    "WY": JurisdictionRule("WY", "Wyoming", "percent", 0.75),
}


@dataclass
class RTVDecision:
    rtv_forensic: float
    state_code: str
    state_threshold: float
    mode: str
    tier: str
    commercial_fork: str
    borderline: bool
    structural_guideline_applied: bool
    reason: str
    formula_version: str = C.VERSION


def get_jurisdiction(state_code: str) -> JurisdictionRule:
    code = (state_code or "").upper().strip()
    if code not in JURISDICTIONS:
        return JurisdictionRule(code or "XX", "Unknown", "percent", 0.75, notes="default_fallback")
    return JURISDICTIONS[code]


def compute_rtv(
    total_repair_cost: float,
    acv_adjusted: float,
    state_code: str,
    salvage_estimate: float = 0.0,
    r_struct: float = 0.0,
    layer2_fork: Optional[str] = None,
) -> RTVDecision:
    rule = get_jurisdiction(state_code)
    if acv_adjusted <= 0:
        rtv = 999.0
    elif rule.mode == "tlf":
        rtv = (total_repair_cost + salvage_estimate) / acv_adjusted
    else:
        rtv = total_repair_cost / acv_adjusted

    threshold = rule.threshold
    structural_applied = False
    if rule.structural_guideline is not None and r_struct >= 0.55:
        threshold = min(threshold, rule.structural_guideline)
        structural_applied = True

    borderline = abs(rtv - threshold) <= C.RTV_BORDERLINE_MARGIN

    if rtv >= C.RTV_TOTAL_LOSS or rtv >= threshold:
        tier = "total_loss"
        fork = "total_loss_dealer"
        reason = f"rtv_{rtv:.3f}_gte_threshold_{threshold:.2f}_{rule.mode}"
    elif rtv >= C.RTV_REVIEW_LOW:
        tier = "review"
        fork = layer2_fork if layer2_fork in ("total_loss_dealer", "repairable_shop") else "repairable_shop"
        reason = f"rtv_review_band_{C.RTV_REVIEW_LOW:.2f}_to_1.0"
    else:
        tier = "repairable"
        fork = "repairable_shop"
        reason = f"rtv_{rtv:.3f}_below_review_band"

    if borderline and tier != "total_loss":
        reason += "|borderline_margin"

    return RTVDecision(
        rtv_forensic=round(rtv, 4),
        state_code=rule.code,
        state_threshold=threshold,
        mode=rule.mode,
        tier=tier,
        commercial_fork=fork,
        borderline=borderline,
        structural_guideline_applied=structural_applied,
        reason=reason,
    )
