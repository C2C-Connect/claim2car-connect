"""
Layer 3 orchestrator: estimate + ACV + RTV + S_i + fraud flags → final adjudication.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from backend.app.catalog.parts_catalog import ItemizedEstimate, PartsCatalogResolver
from backend.app.integrity.s_i import IntegrityInputs, IntegrityResult, compute_s_i
from backend.app.jurisdiction.thresholds import RTVDecision, compute_rtv
from backend.app.valuation.acv import ACVResult, compute_acv
from config import forensic_constants as C


@dataclass
class FraudFlags:
    flags: List[str] = field(default_factory=list)
    risk_score: float = 0.0  # 0..1 heuristic


@dataclass
class AdjudicationResult:
    session_id: str
    estimate: ItemizedEstimate
    acv: ACVResult
    rtv: RTVDecision
    integrity: IntegrityResult
    fraud: FraudFlags
    final_fork: str
    final_tier: str
    hold_for_review: bool
    plain_english: str
    trace: Dict[str, Any]
    formula_version: str = C.VERSION


def score_fraud(
    integrity: IntegrityResult,
    layer2_notes: Sequence[str],
    physics_ai_disagree: bool,
    rtv: RTVDecision,
) -> FraudFlags:
    flags: List[str] = []
    score = 0.0
    if integrity.all_or_nothing_collapse or integrity.tier == "reject":
        flags.append("integrity_collapse_or_reject")
        score += 0.5
    if integrity.tier == "review":
        flags.append("integrity_review_band")
        score += 0.15
    if physics_ai_disagree:
        flags.append("physics_vision_disagreement")
        score += 0.2
    for n in layer2_notes:
        if "spoof" in n.lower() or "tamper" in n.lower():
            flags.append(f"layer2:{n}")
            score += 0.2
    if rtv.borderline:
        flags.append("rtv_borderline")
        score += 0.05
    return FraudFlags(flags=flags, risk_score=min(1.0, score))


def plain_english_summary(
    estimate: ItemizedEstimate,
    acv: ACVResult,
    rtv: RTVDecision,
    integrity: IntegrityResult,
    fork: str,
) -> str:
    n_lines = len(estimate.lines)
    decision = "total loss (dealer path)" if fork == "total_loss_dealer" else "repairable (shop path)"
    return (
        f"Detected {n_lines} affected component(s). "
        f"Estimated repair cost ${estimate.total_repair_cost:,.2f} against "
        f"physics-adjusted ACV ${acv.acv_adjusted:,.2f} "
        f"(baseline ${acv.acv_baseline:,.2f}, structural penalty P_s={acv.p_s:.2%}). "
        f"Forensic RTV={rtv.rtv_forensic:.2%} vs {rtv.state_code} threshold {rtv.state_threshold:.0%} ({rtv.mode}). "
        f"Integrity S_i={integrity.s_i:.2f} ({integrity.tier}). "
        f"Commercial path: {decision}."
    )


class Adjudicator:
    def __init__(self) -> None:
        self.resolver = PartsCatalogResolver()

    def adjudicate(
        self,
        session_id: str,
        *,
        detections: Sequence[dict],
        depths: Sequence[dict],
        r_struct: float,
        age_years: float,
        state_code: str,
        region: str = "default",
        layer2_fork: Optional[str] = None,
        layer2_notes: Optional[Sequence[str]] = None,
        physics_ai_disagree: bool = False,
        gps_accuracy_m: Optional[float] = 15.0,
        master_hash_valid: bool = True,
        chain_coverage: float = 1.0,
        chain_uniqueness: float = 1.0,
        meta_completeness: float = 1.0,
        internal_acv_a: Optional[float] = None,
        internal_acv_b: Optional[float] = None,
        internal_acv_c: Optional[float] = None,
        salvage_estimate: float = 0.0,
        prefer_capa: bool = True,
    ) -> AdjudicationResult:
        estimate = self.resolver.resolve(
            detections=detections,
            depths=depths,
            region=region,
            prefer_capa=prefer_capa,
        )
        acv = compute_acv(
            r_struct=r_struct,
            age_years=age_years,
            internal_a=internal_acv_a,
            internal_b=internal_acv_b,
            internal_c=internal_acv_c,
        )
        rtv = compute_rtv(
            total_repair_cost=estimate.total_repair_cost,
            acv_adjusted=acv.acv_adjusted,
            state_code=state_code,
            salvage_estimate=salvage_estimate,
            r_struct=r_struct,
            layer2_fork=layer2_fork,
        )
        integrity = compute_s_i(
            IntegrityInputs(
                gps_accuracy_m=gps_accuracy_m,
                master_hash_valid=master_hash_valid,
                chain_coverage=chain_coverage,
                chain_uniqueness=chain_uniqueness,
                meta_completeness=meta_completeness,
            )
        )
        fraud = score_fraud(integrity, layer2_notes or [], physics_ai_disagree, rtv)

        # Final fork: integrity reject blocks auto path; review holds
        hold = False
        final_fork = rtv.commercial_fork
        final_tier = rtv.tier
        if integrity.tier == "reject" or integrity.all_or_nothing_collapse:
            hold = True
            final_tier = "reject_fraud"
        elif integrity.tier == "review" or rtv.tier == "review" or rtv.borderline or fraud.risk_score >= 0.35:
            hold = True
            if final_tier == "repairable":
                final_tier = "review"

        # Prefer total loss if layer2 and rtv both say so
        if layer2_fork == "total_loss_dealer" and rtv.tier == "total_loss":
            final_fork = "total_loss_dealer"

        summary = plain_english_summary(estimate, acv, rtv, integrity, final_fork)

        trace = {
            "total_repair_cost": estimate.total_repair_cost,
            "acv_baseline": acv.acv_baseline,
            "p_s": acv.p_s,
            "acv_adjusted": acv.acv_adjusted,
            "rtv_forensic": rtv.rtv_forensic,
            "state_threshold": rtv.state_threshold,
            "s_i": integrity.s_i,
            "layer2_fork": layer2_fork,
            "formulas": {
                "p_s": "min(0.45, R_struct * 0.6)",
                "acv_adjusted": "ACV * (1 - P_s)",
                "rtv": "total_repair_cost / ACV_adjusted (or TLF)",
                "s_i": "C_gps^0.30 * C_hash^0.45 * C_meta^0.25",
            },
        }

        return AdjudicationResult(
            session_id=session_id,
            estimate=estimate,
            acv=acv,
            rtv=rtv,
            integrity=integrity,
            fraud=fraud,
            final_fork=final_fork,
            final_tier=final_tier,
            hold_for_review=hold,
            plain_english=summary,
            trace=trace,
        )
