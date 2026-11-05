"""
Role-gated redaction matrix for multi-recipient document packages.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Set

# Fields allowed per role (allow-list). Anything not listed is stripped or masked.
ROLE_ALLOW: Dict[str, Set[str]] = {
    "owner": {
        "session_id", "verdict", "plain_english", "final_fork", "final_tier",
        "rtv_forensic", "state_code", "total_repair_cost", "acv_adjusted",
        "vin_last4", "vehicle_year", "vehicle_make", "vehicle_model",
        "s_i_tier", "hold_for_review",
    },
    "dealer": {
        "session_id", "verdict", "plain_english", "final_fork", "final_tier",
        "rtv_forensic", "state_code", "state_threshold", "total_repair_cost",
        "acv_baseline", "acv_adjusted", "p_s", "r_struct", "claim2car_price",
        "vin", "vehicle_year", "vehicle_make", "vehicle_model", "vehicle_trim",
        "estimate_lines", "s_i", "s_i_tier", "fraud_flags", "layer2_fork",
        "physics_summary", "hold_for_review", "gold_lead",
    },
    "shop": {
        "session_id", "verdict", "final_fork", "final_tier",
        "total_repair_cost", "estimate_lines", "physics_summary",
        "vin_masked", "vehicle_year", "vehicle_make", "vehicle_model",
        "depths", "detections", "hold_for_review", "digital_twin",
    },
    "carrier": {
        "session_id", "verdict", "plain_english", "final_fork", "final_tier",
        "rtv_forensic", "state_code", "state_threshold", "mode",
        "total_repair_cost", "acv_baseline", "acv_adjusted", "p_s",
        "vin", "vehicle_year", "vehicle_make", "vehicle_model", "vehicle_trim",
        "estimate_lines", "s_i", "s_i_tier", "fraud_flags", "fraud_risk_score",
        "physics_summary", "integrity", "hold_for_review", "acord_ready",
    },
    "qc": set(),  # full access — special-cased
    "admin": set(),
}


def mask_vin(vin: str) -> str:
    v = (vin or "").upper()
    if len(v) < 8:
        return "********"
    return v[:3] + "*" * (len(v) - 7) + v[-4:]


def vin_last4(vin: str) -> str:
    v = (vin or "").upper()
    return v[-4:] if len(v) >= 4 else "****"


def redact_payload(role: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply role-gated redaction. qc/admin receive a deep copy unredacted.
    """
    role = (role or "owner").lower()
    data = deepcopy(payload)

    if role in ("qc", "admin"):
        return data

    # Derive convenience fields
    vin = str(data.get("vin") or "")
    data["vin_last4"] = vin_last4(vin)
    data["vin_masked"] = mask_vin(vin)

    allow = ROLE_ALLOW.get(role, ROLE_ALLOW["owner"])
    out: Dict[str, Any] = {"role": role, "redacted": True}
    for key in allow:
        if key in data:
            out[key] = data[key]
        elif key == "verdict":
            out["verdict"] = data.get("final_tier") or data.get("final_fork")
        elif key == "estimate_lines" and "estimate" in data:
            out["estimate_lines"] = data["estimate"].get("lines")
        elif key == "physics_summary" and "physics" in data:
            out["physics_summary"] = data["physics"]
        elif key == "integrity" and "integrity" in data:
            out["integrity"] = data["integrity"]
        elif key == "digital_twin":
            out["digital_twin"] = {
                "detections": data.get("detections"),
                "depths": data.get("depths"),
                "estimate_lines": (data.get("estimate") or {}).get("lines"),
            }
        elif key == "acord_ready":
            out["acord_ready"] = True

    # Owner: never expose full VIN
    if role == "owner":
        out.pop("vin", None)

    # Shop: never expose full VIN or owner PII
    if role == "shop":
        out.pop("vin", None)
        out.pop("fraud_flags", None)

    # Always surface a public-safe verification block (needed for dossier page 6/7
    # and independent public verify). No PII is included.
    anchor = data.get("anchor") or {}
    out["public_verify"] = {
        "session_id": data.get("session_id"),
        "merkle_root": anchor.get("merkle_root") or data.get("merkle_root"),
        "master_hash": anchor.get("master_hash") or data.get("master_hash"),
        "entry_hash": anchor.get("entry_hash"),
        "anchored_at": anchor.get("anchored_at"),
        "endpoint": "/api/v1/verify/",
    }
    # Also keep a compact anchor reference for dossier builders
    if out["public_verify"].get("merkle_root"):
        out["anchor"] = {
            "merkle_root": out["public_verify"]["merkle_root"],
            "master_hash": out["public_verify"]["master_hash"],
            "entry_hash": out["public_verify"].get("entry_hash"),
            "anchored_at": out["public_verify"].get("anchored_at"),
        }

    return out
