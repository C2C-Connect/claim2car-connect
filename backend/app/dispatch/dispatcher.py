"""
Multi-Recipient Document Dispatcher — builds role-gated packages.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from backend.app.anchor.ledger import LEDGER, merkle_root
from backend.app.dispatch.redaction import redact_payload
from backend.app.reports.acord_xml import build_acord_autoloss
from backend.app.reports.forensic_pdf import ForensicDossier, build_dossier


ROLES = ("owner", "dealer", "shop", "carrier")


@dataclass
class DispatchPackage:
    role: str
    label: str
    payload: Dict[str, Any]
    dossier: ForensicDossier
    acord_xml: str | None = None


@dataclass
class DispatchResult:
    session_id: str
    packages: List[DispatchPackage] = field(default_factory=list)
    anchor: Dict[str, Any] = field(default_factory=dict)
    public_verify_path: str = "/api/v1/verify/"


LABELS = {
    "owner": "Digital Compass",
    "dealer": "Forensic Deal Jacket",
    "shop": "Digital Twin",
    "carrier": "Trojan Horse FNOL Packet",
}


def build_dispatch(
    adjudication: Dict[str, Any],
    *,
    photo_hashes: List[str] | None = None,
    vin: str = "",
    vehicle: Dict[str, Any] | None = None,
) -> DispatchResult:
    session_id = str(adjudication.get("session_id") or "unknown")
    vehicle = vehicle or {}

    # Enrich base payload
    base = dict(adjudication)
    base["vin"] = vin or base.get("vin") or ""
    base["vehicle_year"] = vehicle.get("year") or base.get("vehicle_year")
    base["vehicle_make"] = vehicle.get("make") or base.get("vehicle_make")
    base["vehicle_model"] = vehicle.get("model") or base.get("vehicle_model")
    base["vehicle_trim"] = vehicle.get("trim") or base.get("vehicle_trim")

    leaves = photo_hashes or [session_id]
    mroot = merkle_root(leaves)
    master = merkle_root([mroot, session_id, base["vin"] or "NA"])
    rec = LEDGER.append(session_id, mroot, master, meta={"source": "dispatch"})
    base["anchor"] = {
        "merkle_root": rec.merkle_root,
        "master_hash": rec.master_hash,
        "entry_hash": rec.entry_hash,
        "anchored_at": rec.timestamp_unix,
    }
    base["merkle_root"] = rec.merkle_root
    base["master_hash"] = rec.master_hash

    packages: List[DispatchPackage] = []
    for role in ROLES:
        redacted = redact_payload(role, base)
        dossier = build_dossier(redacted if role != "carrier" else base, role=role)
        acord = build_acord_autoloss(base) if role == "carrier" else None
        packages.append(
            DispatchPackage(
                role=role,
                label=LABELS[role],
                payload=redacted,
                dossier=dossier,
                acord_xml=acord,
            )
        )

    return DispatchResult(
        session_id=session_id,
        packages=packages,
        anchor=base["anchor"],
    )
