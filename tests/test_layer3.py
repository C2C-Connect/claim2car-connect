"""
Milestone 4 / Layer 3 unit tests — ACV, P_s, RTV, S_i, catalog, adjudication.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.catalog.parts_catalog import PartsCatalogResolver  # noqa: E402
from backend.app.integrity.s_i import IntegrityInputs, compute_s_i  # noqa: E402
from backend.app.jurisdiction.thresholds import JURISDICTIONS, compute_rtv  # noqa: E402
from backend.app.triage.adjudicate import Adjudicator  # noqa: E402
from backend.app.valuation.acv import compute_acv, fallback_acv, structural_penalty  # noqa: E402
from config import forensic_constants as C  # noqa: E402


def test_fallback_acv_curve():
    assert fallback_acv(0) == C.ACV_FALLBACK_BASE
    assert fallback_acv(100) == C.ACV_FALLBACK_FLOOR
    v5 = fallback_acv(5)
    assert C.ACV_FALLBACK_FLOOR <= v5 < C.ACV_FALLBACK_BASE


def test_structural_penalty():
    assert structural_penalty(0.0) == 0.0
    assert structural_penalty(1.0) == C.P_S_CAP
    assert abs(structural_penalty(0.5) - min(0.45, 0.5 * 0.6)) < 1e-9


def test_acv_blend_and_adjust():
    r = compute_acv(0.5, age_years=6, internal_a=20000, internal_b=19000, internal_c=21000)
    assert r.acv_baseline > 0
    assert r.acv_adjusted < r.acv_baseline
    assert r.p_s == structural_penalty(0.5)
    assert r.method == "tri_source_blend"
    assert r.claim2car_price == round(r.acv_baseline * C.CLAIM2CAR_PRICE_MULTIPLIER, 2)


def test_acv_fallback_when_no_sources():
    r = compute_acv(0.2, age_years=4)
    assert r.method == "fallback_curve"
    assert abs(r.acv_baseline - round(fallback_acv(4), 2)) < 0.02


def test_51_jurisdictions():
    assert len(JURISDICTIONS) == 51
    assert "TX" in JURISDICTIONS
    assert "DC" in JURISDICTIONS
    assert JURISDICTIONS["CA"].threshold == 0.80
    assert JURISDICTIONS["IL"].threshold == 0.67


def test_rtv_total_loss():
    d = compute_rtv(total_repair_cost=20000, acv_adjusted=15000, state_code="FL")
    assert d.rtv_forensic > 1.0
    assert d.tier == "total_loss"
    assert d.commercial_fork == "total_loss_dealer"


def test_rtv_repairable():
    d = compute_rtv(total_repair_cost=3000, acv_adjusted=18000, state_code="TX")
    assert d.rtv_forensic < C.RTV_REVIEW_LOW
    assert d.tier == "repairable"
    assert d.commercial_fork == "repairable_shop"


def test_rtv_review_band():
    # 0.70 <= rtv < state threshold; CO threshold is 1.00 so 0.80 lands in review
    d = compute_rtv(total_repair_cost=8000, acv_adjusted=10000, state_code="CO")
    assert C.RTV_REVIEW_LOW <= d.rtv_forensic < 1.0
    assert d.tier == "review"


def test_s_i_pass():
    r = compute_s_i(IntegrityInputs(gps_accuracy_m=10, master_hash_valid=True, chain_coverage=1.0, chain_uniqueness=1.0, meta_completeness=1.0))
    assert r.s_i >= C.S_I_PASS
    assert r.tier == "pass"
    assert not r.all_or_nothing_collapse


def test_s_i_all_or_nothing():
    r = compute_s_i(IntegrityInputs(gps_accuracy_m=10, master_hash_valid=False, hash_tamper_suspected=True))
    assert r.s_i == 0.0
    assert r.all_or_nothing_collapse
    assert r.tier == "reject"


def test_s_i_weighted_geometric():
    r = compute_s_i(IntegrityInputs(gps_accuracy_m=5, master_hash_valid=True, chain_coverage=1, chain_uniqueness=1, meta_completeness=1))
    assert abs(r.s_i - 1.0) < 0.02


def test_catalog_resolver_lines():
    res = PartsCatalogResolver()
    est = res.resolve(
        detections=[
            {"class_name": "dent", "confidence": 0.8, "zone": "front"},
            {"class_name": "door_intrusion", "confidence": 0.9, "zone": "side"},
        ],
        depths=[
            {"mean_depth_cm": 12.0, "volume_cm3": 3000.0, "zone": "front"},
            {"mean_depth_cm": 20.0, "volume_cm3": 5000.0, "zone": "side"},
        ],
        region="TX",
    )
    assert len(est.lines) >= 1
    assert est.total_repair_cost > 0
    assert est.parts_subtotal >= 0
    for ln in est.lines:
        assert ln.repair_decision in ("pdr", "repair", "section", "replace")
        assert ln.oem_price_usd >= 0
        assert ln.capa_price_usd >= 0


def test_adjudicator_end_to_end():
    adj = Adjudicator()
    result = adj.adjudicate(
        "sess-m4-1",
        detections=[
            {"class_name": "crush", "confidence": 0.85, "zone": "front"},
            {"class_name": "dent", "confidence": 0.7, "zone": "side"},
        ],
        depths=[
            {"mean_depth_cm": 22.0, "volume_cm3": 8000.0, "zone": "front"},
            {"mean_depth_cm": 8.0, "volume_cm3": 1500.0, "zone": "side"},
        ],
        r_struct=0.4,
        age_years=7,
        state_code="TX",
        region="TX",
        layer2_fork="repairable_shop",
        internal_acv_a=16000,
        internal_acv_b=15500,
        internal_acv_c=16200,
    )
    assert result.estimate.total_repair_cost > 0
    assert result.acv.acv_adjusted > 0
    assert result.rtv.rtv_forensic >= 0
    assert result.integrity.s_i >= 0
    assert result.final_fork in ("total_loss_dealer", "repairable_shop")
    assert "total_repair_cost" in result.trace
    assert result.formula_version == C.VERSION


def test_no_owner_payout_constant():
    assert not hasattr(C, "OPERATOR_PAYOUT_USD")
    assert not hasattr(C, "OWNER_PAYOUT_USD")
