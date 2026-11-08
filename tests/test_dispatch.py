"""
Milestone 5 — redaction, anchor ledger, dossier, ACORD, dispatcher.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.anchor.ledger import AnchorLedger, merkle_root  # noqa: E402
from backend.app.dispatch.dispatcher import build_dispatch  # noqa: E402
from backend.app.dispatch.redaction import mask_vin, redact_payload, vin_last4  # noqa: E402
from backend.app.reports.acord_xml import build_acord_autoloss  # noqa: E402
from backend.app.reports.forensic_pdf import build_dossier  # noqa: E402
from config import forensic_constants as C  # noqa: E402


def _sample_adj():
    return {
        "session_id": "sess-dispatch-1",
        "final_fork": "total_loss_dealer",
        "final_tier": "total_loss",
        "hold_for_review": False,
        "plain_english": "High RTV total loss path.",
        "estimate": {
            "total_repair_cost": 14500.0,
            "parts_subtotal": 8000.0,
            "labor_subtotal": 4000.0,
            "paint_subtotal": 1500.0,
            "adas_subtotal": 500.0,
            "tax_usd": 500.0,
            "lines": [{"part_number": "OEM-HOOD-001", "name": "Hood", "line_total_usd": 1200}],
        },
        "acv": {
            "acv_baseline": 18000.0,
            "acv_adjusted": 16200.0,
            "p_s": 0.1,
            "r_struct": 0.35,
            "claim2car_price": 19440.0,
            "method": "tri_source_blend",
        },
        "rtv": {
            "rtv_forensic": 0.895,
            "state_code": "TX",
            "state_threshold": 1.0,
            "mode": "percent",
            "tier": "review",
            "reason": "rtv_review_band",
        },
        "integrity": {"s_i": 0.92, "tier": "pass", "c_gps": 1.0, "c_hash": 1.0, "c_meta": 1.0},
        "fraud": {"flags": [], "risk_score": 0.0},
        "physics": {"e_k_kj": 120.0, "r_y_max": 1.2, "p_tl_physics": 0.7},
        "detections": [{"class_name": "crush", "zone": "front", "confidence": 0.9}],
        "depths": [{"zone": "front", "mean_depth_cm": 20.0, "volume_cm3": 5000.0}],
        "formula_version": C.VERSION,
    }


def test_vin_masking():
    assert vin_last4("1HGCM82633A004352") == "4352"
    masked = mask_vin("1HGCM82633A004352")
    assert "4352" in masked
    assert "HCM" not in masked or masked.startswith("1HG")


def test_redaction_owner_no_full_vin():
    payload = _sample_adj()
    payload["vin"] = "1HGCM82633A004352"
    out = redact_payload("owner", payload)
    assert "vin" not in out or out.get("vin") is None
    assert out.get("vin_last4") == "4352"


def test_redaction_shop_masked_vin():
    payload = _sample_adj()
    payload["vin"] = "1HGCM82633A004352"
    out = redact_payload("shop", payload)
    assert out.get("vin_masked")
    assert "vin" not in out


def test_merkle_deterministic():
    a = merkle_root(["aa", "bb"])
    b = merkle_root(["aa", "bb"])
    assert a == b
    assert len(a) == 64


def test_anchor_ledger_verify():
    ledger = AnchorLedger()
    leaves = ["abc", "def"]
    root = merkle_root(leaves)
    master = merkle_root([root, "sess-1"])
    ledger.append("sess-1", root, master)
    ok = ledger.verify("sess-1", root, master)
    assert ok["valid"] is True
    bad = ledger.verify("sess-1", root, "0" * 64)
    assert bad["valid"] is False


def test_anchor_kill_switch():
    ledger = AnchorLedger()
    root = merkle_root(["x"])
    ledger.append("s", root, root)
    ledger.kill_switch = True
    r = ledger.verify("s", root, root)
    assert r["valid"] is False
    assert r["reason"] == "kill_switch_engaged"


def test_dossier_seven_pages():
    d = build_dossier(_sample_adj(), role="carrier")
    assert len(d.pages) == 7
    assert d.pages[0].number == 1
    assert d.pages[6].number == 7
    assert "Executive" in d.pages[0].title
    assert "Verification" in d.pages[6].title
    assert "Forensic Dossier" in d.html


def test_acord_xml_contains_extensions():
    payload = _sample_adj()
    payload["vin"] = "1HGCM82633A004352"
    xml = build_acord_autoloss(payload)
    assert "ACORD" in xml
    assert "1HGCM82633A004352" in xml
    assert "ForensicExtension" in xml or "gavel" in xml.lower() or "RTV" in xml


def test_build_dispatch_four_packages():
    result = build_dispatch(
        _sample_adj(),
        photo_hashes=["a" * 64, "b" * 64],
        vin="1HGCM82633A004352",
        vehicle={"year": 2019, "make": "Honda", "model": "Civic"},
    )
    assert len(result.packages) == 4
    roles = {p.role for p in result.packages}
    assert roles == {"owner", "dealer", "shop", "carrier"}
    carrier = next(p for p in result.packages if p.role == "carrier")
    assert carrier.acord_xml is not None
    assert result.anchor.get("merkle_root")
    owner = next(p for p in result.packages if p.role == "owner")
    assert "vin" not in owner.payload or owner.payload.get("vin") is None


def test_no_owner_payout():
    assert C.OPERATOR_PAYOUT_USD == 110.0
    assert not hasattr(C, "OWNER_PAYOUT_USD")
