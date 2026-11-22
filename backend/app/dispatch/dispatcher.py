"""Multi-recipient dispatcher with fail-closed integrity authorization."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List

from backend.app.anchor.ledger import LEDGER, merkle_root
from backend.app.dispatch.redaction import redact_payload
from backend.app.reports.acord_xml import build_acord_autoloss
from backend.app.reports.forensic_pdf import ForensicDossier, build_dossier
from config import forensic_constants as C


ROLES = ("owner", "dealer", "shop", "carrier")
LABELS = {
    "owner": "Digital Compass",
    "dealer": "Forensic Deal Jacket",
    "shop": "Digital Twin",
    "carrier": "Trojan Horse FNOL Packet",
}


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


class DispatchBlocked(RuntimeError):
    """Dispatch blocked because adjudication or evidence integrity is not authorized."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _require_dispatch_authorized(adjudication: Dict[str, Any], photo_hashes: List[str] | None) -> List[str]:
    session_id = str(adjudication.get("session_id") or "").strip()
    if not session_id or session_id.lower() == "unknown":
        raise DispatchBlocked("DISPATCH_SESSION_ID_REQUIRED")
    if adjudication.get("hold_for_review") is True or adjudication.get("final_tier") in {"review", "reject", "reject_fraud"}:
        raise DispatchBlocked("DISPATCH_REVIEW_HOLD")
    if adjudication.get("final_fork") not in {"total_loss_dealer", "repairable_shop"}:
        raise DispatchBlocked("DISPATCH_FINAL_FORK_INVALID")

    integrity = adjudication.get("integrity")
    if not isinstance(integrity, dict):
        raise DispatchBlocked("DISPATCH_INTEGRITY_REQUIRED")
    score = integrity.get("s_i")
    if (
        integrity.get("tier") != "pass"
        or integrity.get("all_or_nothing_collapse") is True
        or integrity.get("c_chain") != 1.0
        or integrity.get("c_hash") != 1.0
        or not isinstance(score, (int, float))
        or isinstance(score, bool)
        or score < C.S_I_PASS
    ):
        raise DispatchBlocked("DISPATCH_INTEGRITY_NOT_PASSED")

    if not isinstance(photo_hashes, list) or not photo_hashes:
        raise DispatchBlocked("DISPATCH_EVIDENCE_HASHES_REQUIRED")
    normalized_hashes = []
    for photo_hash in photo_hashes:
        if not isinstance(photo_hash, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", photo_hash):
            raise DispatchBlocked("DISPATCH_INVALID_EVIDENCE_HASH")
        normalized_hashes.append(photo_hash.lower())
    if len(set(normalized_hashes)) != len(normalized_hashes):
        raise DispatchBlocked("DISPATCH_DUPLICATE_EVIDENCE_HASH")
    return normalized_hashes


def build_dispatch(
    adjudication: Dict[str, Any],
    *,
    photo_hashes: List[str] | None = None,
    vin: str = "",
    vehicle: Dict[str, Any] | None = None,
) -> DispatchResult:
    normalized_hashes = _require_dispatch_authorized(adjudication, photo_hashes)
    session_id = str(adjudication["session_id"]).strip()
    vehicle = vehicle or {}

    base = dict(adjudication)
    base["vin"] = vin or base.get("vin") or ""
    base["vehicle_year"] = vehicle.get("year") or base.get("vehicle_year")
    base["vehicle_make"] = vehicle.get("make") or base.get("vehicle_make")
    base["vehicle_model"] = vehicle.get("model") or base.get("vehicle_model")
    base["vehicle_trim"] = vehicle.get("trim") or base.get("vehicle_trim")

    photo_root = merkle_root(normalized_hashes)
    master_root = merkle_root([photo_root, session_id, base["vin"] or "NA"])
    record = LEDGER.append(
        session_id,
        photo_root,
        master_root,
        meta={"source": "dispatch", "photo_hash_count": len(normalized_hashes)},
    )
    base["anchor"] = {
        "merkle_root": record.merkle_root,
        "master_hash": record.master_hash,
        "entry_hash": record.entry_hash,
        "anchored_at": record.timestamp_unix,
    }
    base["merkle_root"] = record.merkle_root
    base["master_hash"] = record.master_hash

    packages = []
    for role in ROLES:
        redacted = redact_payload(role, base)
        dossier = build_dossier(redacted if role != "carrier" else base, role=role)
        acord = build_acord_autoloss(base) if role == "carrier" else None
        packages.append(DispatchPackage(role=role, label=LABELS[role], payload=redacted, dossier=dossier, acord_xml=acord))

    return DispatchResult(session_id=session_id, packages=packages, anchor=base["anchor"])
