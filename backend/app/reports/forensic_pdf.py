"""
7-page Forensic PDF Audit Dossier — structured report builder.

Generates a full text/HTML dossier (PDF bytes when reportlab available;
always returns structured pages + HTML for portal rendering).
"""

from __future__ import annotations

import html
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


PAGE_TITLES = [
    "1. Executive Summary & Safety Verdict",
    "2. Identity & Telemetry",
    "3. Physics Audit Log",
    "4. Vision & Volumetric Analytics",
    "5. Valuation & RTV",
    "6. Chain of Custody & Anchors",
    "7. Attestation & Public Verification",
]


@dataclass
class DossierPage:
    number: int
    title: str
    sections: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class ForensicDossier:
    session_id: str
    pages: List[DossierPage]
    html: str
    plain_text: str
    role: str = "carrier"


def _kv(sections: List[Dict[str, Any]], title: str, rows: Dict[str, Any]) -> None:
    sections.append({"heading": title, "rows": {k: v for k, v in rows.items() if v is not None}})


def build_dossier(payload: Dict[str, Any], role: str = "carrier") -> ForensicDossier:
    session_id = str(payload.get("session_id") or "unknown")
    pages: List[DossierPage] = []

    # Page 1 — Executive
    p1: List[Dict[str, Any]] = []
    _kv(p1, "Verdict", {
        "final_fork": payload.get("final_fork"),
        "final_tier": payload.get("final_tier"),
        "hold_for_review": payload.get("hold_for_review"),
        "plain_english": payload.get("plain_english"),
    })
    pages.append(DossierPage(1, PAGE_TITLES[0], p1))

    # Page 2 — Identity
    p2: List[Dict[str, Any]] = []
    _kv(p2, "Vehicle", {
        "vin": payload.get("vin") if role != "owner" else payload.get("vin_last4"),
        "year": payload.get("vehicle_year"),
        "make": payload.get("vehicle_make"),
        "model": payload.get("vehicle_model"),
        "trim": payload.get("vehicle_trim"),
    })
    _kv(p2, "Integrity", {
        "s_i": (payload.get("integrity") or {}).get("s_i"),
        "tier": (payload.get("integrity") or {}).get("tier"),
        "c_gps": (payload.get("integrity") or {}).get("c_gps"),
        "c_hash": (payload.get("integrity") or {}).get("c_hash"),
        "c_meta": (payload.get("integrity") or {}).get("c_meta"),
    })
    pages.append(DossierPage(2, PAGE_TITLES[1], p2))

    # Page 3 — Physics
    phys = payload.get("physics") or payload.get("physics_summary") or {}
    p3: List[Dict[str, Any]] = []
    _kv(p3, "DARCI Outputs", {
        "e_k_kj": phys.get("e_k_kj"),
        "peak_g": phys.get("peak_g"),
        "r_y_max": phys.get("r_y_max"),
        "p_brittle": phys.get("p_brittle"),
        "shannon_h": phys.get("shannon_h"),
        "p_struct": phys.get("p_struct"),
        "r_struct": phys.get("r_struct"),
        "p_tl_physics": phys.get("p_tl_physics") or payload.get("p_tl_physics"),
    })
    pages.append(DossierPage(3, PAGE_TITLES[2], p3))

    # Page 4 — Vision
    p4: List[Dict[str, Any]] = []
    _kv(p4, "Detections", {"count": len(payload.get("detections") or [])})
    p4.append({"heading": "Detection List", "rows": {"items": payload.get("detections") or []}})
    p4.append({"heading": "Depth / Volume", "rows": {"items": payload.get("depths") or []}})
    pages.append(DossierPage(4, PAGE_TITLES[3], p4))

    # Page 5 — Valuation & RTV
    acv = payload.get("acv") or {}
    rtv = payload.get("rtv") or {}
    est = payload.get("estimate") or {}
    p5: List[Dict[str, Any]] = []
    _kv(p5, "Costs", {
        "total_repair_cost": est.get("total_repair_cost") or payload.get("total_repair_cost"),
        "parts": est.get("parts_subtotal"),
        "labor": est.get("labor_subtotal"),
        "paint": est.get("paint_subtotal"),
        "adas": est.get("adas_subtotal"),
        "tax": est.get("tax_usd"),
    })
    _kv(p5, "Valuation", {
        "acv_baseline": acv.get("acv_baseline"),
        "p_s": acv.get("p_s"),
        "acv_adjusted": acv.get("acv_adjusted"),
        "claim2car_price": acv.get("claim2car_price"),
        "method": acv.get("method"),
    })
    _kv(p5, "RTV", {
        "rtv_forensic": rtv.get("rtv_forensic"),
        "state": rtv.get("state_code"),
        "threshold": rtv.get("state_threshold"),
        "mode": rtv.get("mode"),
        "tier": rtv.get("tier"),
        "reason": rtv.get("reason"),
    })
    pages.append(DossierPage(5, PAGE_TITLES[4], p5))

    # Page 6 — Chain of custody
    anchor = payload.get("anchor") or {}
    p6: List[Dict[str, Any]] = []
    _kv(p6, "Anchors", {
        "merkle_root": anchor.get("merkle_root") or payload.get("merkle_root"),
        "master_hash": anchor.get("master_hash") or payload.get("master_hash"),
        "entry_hash": anchor.get("entry_hash"),
        "anchored_at": anchor.get("anchored_at"),
    })
    pages.append(DossierPage(6, PAGE_TITLES[5], p6))

    # Page 7 — Attestation
    p7: List[Dict[str, Any]] = []
    _kv(p7, "Public Verification", {
        "endpoint": "/api/v1/verify/",
        "session_id": session_id,
        "instruction": "Submit session_id with recomputed merkle/master hashes for independent verification.",
    })
    _kv(p7, "Attestation", {
        "formula_version": payload.get("formula_version"),
        "operator_payout_usd": payload.get("operator_payout_usd"),
        "owner_payout": None,
        "disclaimer": "Pending attorney review before publication. See LEGAL_REVIEW.md.",
    })
    pages.append(DossierPage(7, PAGE_TITLES[6], p7))

    # Render HTML + plain text
    html_parts = [f"<html><head><title>Forensic Dossier {html.escape(session_id)}</title></head><body>"]
    text_parts: List[str] = []
    for page in pages:
        html_parts.append(f"<h1>{html.escape(page.title)}</h1>")
        text_parts.append(page.title)
        text_parts.append("=" * len(page.title))
        for sec in page.sections:
            heading = sec.get("heading") or ""
            html_parts.append(f"<h2>{html.escape(str(heading))}</h2><ul>")
            text_parts.append(f"\n{heading}")
            rows = sec.get("rows") or {}
            for k, v in rows.items():
                html_parts.append(f"<li><b>{html.escape(str(k))}</b>: {html.escape(str(v))}</li>")
                text_parts.append(f"  {k}: {v}")
            html_parts.append("</ul>")
        text_parts.append("")
    html_parts.append("</body></html>")

    return ForensicDossier(
        session_id=session_id,
        pages=pages,
        html="\n".join(html_parts),
        plain_text="\n".join(text_parts),
        role=role,
    )
