"""
7-page Forensic PDF Audit Dossier — structured report builder.

Generates a full text/HTML dossier (PDF bytes when reportlab available;
always returns structured pages + HTML for portal rendering).
"""

from __future__ import annotations

import html
import json
import textwrap
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Dict, List, Optional, Sequence
from uuid import UUID

from backend.app.anchor.ledger import (
    DEALER_ACQUISITION_FEE_CENTS,
    REPAIR_SHOP_ACCEPTANCE_FEE_CENTS,
    LedgerJournalEntry,
)


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


# Four-tier document artifact from the approved production engineering spec.
DOCUMENT_TYPES = frozenset({
    "VEHICLE_OWNER_PDF",
    "DEALER_DOSSIER",
    "REPAIR_SHOP_PACKET",
    "CARRIER_SEVEN_PAGE_REPORT",
})

AUTHORIZED_RECIPIENT_ROLES: dict[str, frozenset[str]] = {
    "VEHICLE_OWNER_PDF": frozenset({"owner", "reviewer", "supervisor"}),
    "DEALER_DOSSIER": frozenset({"dealer", "reviewer", "supervisor"}),
    "REPAIR_SHOP_PACKET": frozenset({"shop", "reviewer", "supervisor"}),
    "CARRIER_SEVEN_PAGE_REPORT": frozenset({"carrier", "reviewer", "supervisor"}),
}

PROHIBITED_OUTPUT_SUBSTRINGS = (
    "owner_payout",
    "owner_incentive",
    "owner_cash_incentive",
    "vehicle_owner_incentive",
    "operator_payout",
    "tow_operator_payout",
)


class DossierGenerationError(ValueError):
    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(code if not detail else f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class ConsentSnapshot:
    owner_actor_id: str
    accepted: bool
    disclosure_version: str
    scope: str
    recorded_at: str
    withdrawn_at: str | None = None


@dataclass(frozen=True)
class SourceEvidenceBinding:
    session_id: str
    tenant_id: UUID
    manifest_digest: str
    shot_list_version: str
    verified_artifact_ids: tuple[str, ...]
    reviewer_actor_id: str
    reviewer_disposition: str
    reviewer_reason_code: str
    reviewed_at: str
    vin_sha256: str | None
    advisory_darci_summary: dict = field(default_factory=dict)


@dataclass(frozen=True)
class GeneratedDocumentVersion:
    document_id: str
    session_id: str
    tenant_id: str
    document_type: str
    schema_version: str
    version_number: int
    supersedes_document_id: str | None
    manifest_digest: str
    ledger_entry_id: str | None
    ledger_entry_hash: str | None
    page_count: int
    pages: tuple[dict, ...]
    pdf_bytes: bytes
    pdf_sha256: str
    generated_by: str
    generated_at: str
    revoked: bool = False


def _assert_zero_prohibited_payout_fields(serialized_json: str) -> None:
    lowered = serialized_json.lower()
    for forbidden in PROHIBITED_OUTPUT_SUBSTRINGS:
        if forbidden in lowered:
            raise DossierGenerationError(
                "PROHIBITED_COMPENSATION_FIELD_DETECTED",
                f"Output contains banned compensation identifier: {forbidden!r}",
            )


def _render_deterministic_pdf_bytes(doc_header: str, pages: Sequence[dict]) -> bytes:
    canonical_body = json.dumps(pages, sort_keys=True, separators=(",", ":"))
    _assert_zero_prohibited_payout_fields(canonical_body)
    page_count = len(pages)
    if page_count == 0:
        raise DossierGenerationError("DOCUMENT_REQUIRES_AT_LEAST_ONE_PAGE")

    def pdf_escape(value: str) -> str:
        return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    objects: list[bytes] = []
    page_object_ids = [4 + index * 2 for index in range(page_count)]
    kids = " ".join(f"{object_id} 0 R" for object_id in page_object_ids)
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {page_count} >>".encode("ascii"))
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    for index, page in enumerate(pages):
        page_id = page_object_ids[index]
        content_id = page_id + 1
        page_text = json.dumps(page, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
        wrapped_lines = textwrap.wrap(page_text, width=92, break_long_words=True, break_on_hyphens=False)
        content_commands = ["BT", "/F1 9 Tf", "42 750 Td", "11 TL"]
        for line_number, line in enumerate(wrapped_lines[:62]):
            if line_number:
                content_commands.append("T*")
            content_commands.append(f"({pdf_escape(line)}) Tj")
        content_commands.append("ET")
        stream = "\n".join(content_commands).encode("ascii")
        page_object = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {content_id} 0 R >>"
        ).encode("ascii")
        content_object = f"<< /Length {len(stream)} >>\nstream\n".encode("ascii") + stream + b"\nendstream"
        while len(objects) <= content_id - 1:
            objects.append(b"")
        objects[page_id - 1] = page_object
        objects[content_id - 1] = content_object

    output = bytearray(b"%PDF-1.4\n% Claim2Car Connect deterministic document\n")
    offsets = [0]
    for object_id, body in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{object_id} 0 obj\n".encode("ascii"))
        output.extend(body)
        output.extend(b"\nendobj\n")
    xref_offset = len(output)
    output.extend(f"xref\n0 {len(offsets)}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.extend(
        f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode("ascii")
    )
    return bytes(output)


class FourTierDossierService:
    schema_version = "c2c-dossier-v1"

    def __init__(self) -> None:
        self._versions: dict[tuple[str, str], list[GeneratedDocumentVersion]] = {}
        self._delivery_tracking: dict[str, dict] = {}
        self._download_audit_log: list[dict] = []

    def _verify_consent_and_review(
        self, consent: ConsentSnapshot, binding: SourceEvidenceBinding, document_type: str
    ) -> None:
        if not isinstance(consent, ConsentSnapshot) or not consent.accepted or consent.withdrawn_at is not None:
            raise DossierGenerationError(
                "CONSENT_WITHDRAWN_OR_NOT_ACCEPTED",
                "Cannot generate or distribute documents without active vehicle-owner consent",
            )
        if not binding.manifest_digest or not binding.reviewer_actor_id or not binding.verified_artifact_ids:
            raise DossierGenerationError(
                "UNSEALED_OR_UNREVIEWED_EVIDENCE",
                "Documents require a sealed manifest and an attributed human reviewer decision",
            )
        if document_type in ("DEALER_DOSSIER", "REPAIR_SHOP_PACKET", "CARRIER_SEVEN_PAGE_REPORT"):
            if "withdrawn" in consent.scope.lower() or "none" in consent.scope.lower():
                raise DossierGenerationError("INSUFFICIENT_CONSENT_SCOPE", consent.scope)

    def generate_vehicle_owner_pdf(
        self, *, consent: ConsentSnapshot, binding: SourceEvidenceBinding,
        generated_by: str, now_iso: str | None = None,
    ) -> GeneratedDocumentVersion:
        self._verify_consent_and_review(consent, binding, "VEHICLE_OWNER_PDF")
        pages = (
            {
                "page": 1,
                "title": "Vehicle-Owner Evidence & Consent Summary",
                "session_id": binding.session_id,
                "consent_disclosure_version": consent.disclosure_version,
                "consent_recorded_at": consent.recorded_at,
                "vin_sha256": binding.vin_sha256,
            },
            {
                "page": 2,
                "title": "Cryptographic Evidence Manifest & Review Status",
                "manifest_digest": binding.manifest_digest,
                "shot_list_version": binding.shot_list_version,
                "verified_artifact_count": len(binding.verified_artifact_ids),
                "reviewer_disposition": binding.reviewer_disposition,
                "reviewed_at": binding.reviewed_at,
                "provenance_notice": "SHA-256 digest verifies byte integrity from capture to review.",
            },
        )
        return self._store_version(
            binding=binding, document_type="VEHICLE_OWNER_PDF", pages=pages,
            ledger_entry=None, generated_by=generated_by, now_iso=now_iso,
        )

    def generate_dealer_dossier(
        self, *, consent: ConsentSnapshot, binding: SourceEvidenceBinding,
        ledger_entry: LedgerJournalEntry, estimated_acv_cents: int,
        generated_by: str, now_iso: str | None = None,
    ) -> GeneratedDocumentVersion:
        self._verify_consent_and_review(consent, binding, "DEALER_DOSSIER")
        if (ledger_entry is None
                or ledger_entry.fee_type != "DEALER_ACQUISITION_FEE"
                or ledger_entry.amount_cents != DEALER_ACQUISITION_FEE_CENTS):
            raise DossierGenerationError(
                "VALID_DEALER_LEDGER_ENTRY_REQUIRED",
                f"Dealer dossier requires a verified {DEALER_ACQUISITION_FEE_CENTS}-cent ledger entry",
            )
        if isinstance(estimated_acv_cents, bool) or not isinstance(estimated_acv_cents, int) or estimated_acv_cents <= 0:
            raise DossierGenerationError("ACV_MUST_BE_POSITIVE_INTEGER_CENTS")

        pages = (
            {
                "page": 1,
                "title": "Dealer Acquisition Dossier — Vehicle & Provenance",
                "session_id": binding.session_id,
                "manifest_digest": binding.manifest_digest,
                "vin_sha256": binding.vin_sha256,
                "reviewer_disposition": binding.reviewer_disposition,
                "verified_artifact_ids": list(binding.verified_artifact_ids),
            },
            {
                "page": 2,
                "title": "Advisory Valuation & Commercial Fee Binding",
                "estimated_acv_cents": estimated_acv_cents,
                "dealer_acquisition_fee_cents": DEALER_ACQUISITION_FEE_CENTS,
                "ledger_entry_id": ledger_entry.entry_id,
                "ledger_entry_hash": ledger_entry.entry_hash,
                "partner_org_id": ledger_entry.partner_org_id,
                "advisory_darci_summary": binding.advisory_darci_summary,
                "advisory_notice": "Analytical valuation and DARCI outputs are strictly advisory.",
            },
        )
        return self._store_version(
            binding=binding, document_type="DEALER_DOSSIER", pages=pages,
            ledger_entry=ledger_entry, generated_by=generated_by, now_iso=now_iso,
        )

    def generate_repair_shop_packet(
        self, *, consent: ConsentSnapshot, binding: SourceEvidenceBinding,
        ledger_entry: LedgerJournalEntry, damaged_zones: Sequence[dict],
        generated_by: str, now_iso: str | None = None,
    ) -> GeneratedDocumentVersion:
        self._verify_consent_and_review(consent, binding, "REPAIR_SHOP_PACKET")
        if (ledger_entry is None
                or ledger_entry.fee_type != "REPAIR_SHOP_ACCEPTANCE_FEE"
                or ledger_entry.amount_cents != REPAIR_SHOP_ACCEPTANCE_FEE_CENTS):
            raise DossierGenerationError(
                "VALID_SHOP_ACCEPTANCE_LEDGER_ENTRY_REQUIRED",
                f"Repair-shop packet requires a verified {REPAIR_SHOP_ACCEPTANCE_FEE_CENTS}-cent ledger entry",
            )

        pages = (
            {
                "page": 1,
                "title": "Repair-Shop Intake Packet & Acceptance Binding",
                "session_id": binding.session_id,
                "manifest_digest": binding.manifest_digest,
                "shop_partner_org_id": ledger_entry.partner_org_id,
                "acceptance_id": ledger_entry.acceptance_id,
                "repair_shop_acceptance_fee_cents": REPAIR_SHOP_ACCEPTANCE_FEE_CENTS,
                "ledger_entry_id": ledger_entry.entry_id,
                "ledger_entry_hash": ledger_entry.entry_hash,
            },
            {
                "page": 2,
                "title": "Localized Damage Regions & Human Reviewer Notes",
                "reviewer_disposition": binding.reviewer_disposition,
                "reviewer_reason_code": binding.reviewer_reason_code,
                "damaged_zones": list(damaged_zones),
                "advisory_only": True,
            },
        )
        return self._store_version(
            binding=binding, document_type="REPAIR_SHOP_PACKET", pages=pages,
            ledger_entry=ledger_entry, generated_by=generated_by, now_iso=now_iso,
        )

    def generate_carrier_seven_page_report(
        self, *, consent: ConsentSnapshot, binding: SourceEvidenceBinding,
        generated_by: str, now_iso: str | None = None,
    ) -> GeneratedDocumentVersion:
        self._verify_consent_and_review(consent, binding, "CARRIER_SEVEN_PAGE_REPORT")
        pages = (
            {
                "page": 1,
                "section": "Executive Summary & Case Attribution",
                "session_id": binding.session_id,
                "tenant_id": str(binding.tenant_id),
                "machine_contract_version": "m1-v1",
            },
            {
                "page": 2,
                "section": "Attributable Disclosure & Vehicle-Owner Consent Record",
                "disclosure_version": consent.disclosure_version,
                "consent_scope": consent.scope,
                "recorded_at": consent.recorded_at,
            },
            {
                "page": 3,
                "section": "Vehicle Identification & Canonical 12-Slot Inventory",
                "vin_sha256": binding.vin_sha256,
                "shot_list_version": binding.shot_list_version,
                "verified_artifact_ids": list(binding.verified_artifact_ids),
            },
            {
                "page": 4,
                "section": "Cryptographic SHA-256 Evidence Manifest & Byte Integrity",
                "manifest_digest": binding.manifest_digest,
                "integrity_note": "Server-side SHA-256 recomputed against original bytes; proves byte integrity.",
            },
            {
                "page": 5,
                "section": "Advisory Computer Vision Damage Localization",
                "advisory_only": True,
                "vision_summary": binding.advisory_darci_summary.get("vision", {}),
            },
            {
                "page": 6,
                "section": "Advisory DARCI Physics & Structural Deformation Profile",
                "advisory_only": True,
                "weighting_disclosure": "Analytical 55/45 weighting is advisory and not claimed as proven field accuracy.",
                "physics_summary": binding.advisory_darci_summary.get("physics", {}),
            },
            {
                "page": 7,
                "section": "Human Reviewer Adjudication & Final Disposition",
                "reviewer_actor_id": binding.reviewer_actor_id,
                "disposition": binding.reviewer_disposition,
                "reason_code": binding.reviewer_reason_code,
                "reviewed_at": binding.reviewed_at,
            },
        )
        assert len(pages) == 7, "Carrier report must contain exactly 7 pages"
        return self._store_version(
            binding=binding, document_type="CARRIER_SEVEN_PAGE_REPORT", pages=pages,
            ledger_entry=None, generated_by=generated_by, now_iso=now_iso,
        )

    def retrieve_and_audit_download(
        self, *, session_id: str, document_type: str, recipient_actor_id: str,
        recipient_role: str, recipient_tenant_id: UUID, now_iso: str | None = None,
    ) -> GeneratedDocumentVersion:
        versions = self._versions.get((session_id, document_type))
        if not versions:
            raise DossierGenerationError("DOCUMENT_NOT_FOUND", f"{session_id}:{document_type}")

        latest = versions[-1]
        if latest.tenant_id != str(recipient_tenant_id):
            raise DossierGenerationError("CROSS_TENANT_DOCUMENT_ACCESS_DENIED")
        if latest.revoked:
            raise DossierGenerationError("DOCUMENT_REVOKED_ON_CONSENT_WITHDRAWAL", latest.document_id)

        role_norm = recipient_role.strip().lower()
        allowed_roles = AUTHORIZED_RECIPIENT_ROLES.get(document_type, frozenset())
        if role_norm not in allowed_roles:
            raise DossierGenerationError("RECIPIENT_ROLE_UNAUTHORIZED", f"{role_norm} cannot access {document_type}")

        occurred_at = now_iso or datetime.now(timezone.utc).isoformat()
        audit_entry = {
            "sequence": len(self._download_audit_log) + 1,
            "document_id": latest.document_id,
            "session_id": session_id,
            "document_type": document_type,
            "version_number": latest.version_number,
            "pdf_sha256": latest.pdf_sha256,
            "recipient_actor_id": recipient_actor_id,
            "recipient_role": role_norm,
            "downloaded_at": occurred_at,
        }
        self._download_audit_log.append(audit_entry)
        self._delivery_tracking[f"{latest.document_id}:{recipient_actor_id}"] = {
            "status": "DELIVERED",
            "delivered_at": occurred_at,
            "pdf_sha256": latest.pdf_sha256,
        }
        return latest

    def revoke_all_for_session_on_consent_withdrawal(self, session_id: str, *, revoked_by: str) -> int:
        revoked_count = 0
        for (sess_id, _doc_type), ver_list in self._versions.items():
            if sess_id == session_id:
                for idx, doc in enumerate(ver_list):
                    if not doc.revoked:
                        ver_list[idx] = GeneratedDocumentVersion(
                            **{**asdict(doc), "revoked": True, "pdf_bytes": b""}
                        )
                        revoked_count += 1
        return revoked_count

    def download_audit_log(self) -> tuple[dict, ...]:
        return tuple(self._download_audit_log)

    def _store_version(
        self, *, binding: SourceEvidenceBinding, document_type: str, pages: tuple[dict, ...],
        ledger_entry: LedgerJournalEntry | None, generated_by: str, now_iso: str | None,
    ) -> GeneratedDocumentVersion:
        key = (binding.session_id, document_type)
        existing_versions = self._versions.setdefault(key, [])
        version_number = len(existing_versions) + 1
        supersedes_id = existing_versions[-1].document_id if existing_versions else None
        occurred_at = now_iso or datetime.now(timezone.utc).isoformat()

        doc_header = f"{binding.session_id}:{document_type}:v{version_number}:{binding.manifest_digest}"
        pdf_bytes = _render_deterministic_pdf_bytes(doc_header, pages)
        pdf_sha256 = sha256(pdf_bytes).hexdigest()
        document_id = f"doc-{document_type.lower()}-v{version_number}-{pdf_sha256[:10]}"

        version_record = GeneratedDocumentVersion(
            document_id=document_id,
            session_id=binding.session_id,
            tenant_id=str(binding.tenant_id),
            document_type=document_type,
            schema_version=self.schema_version,
            version_number=version_number,
            supersedes_document_id=supersedes_id,
            manifest_digest=binding.manifest_digest,
            ledger_entry_id=ledger_entry.entry_id if ledger_entry else None,
            ledger_entry_hash=ledger_entry.entry_hash if ledger_entry else None,
            page_count=len(pages),
            pages=pages,
            pdf_bytes=pdf_bytes,
            pdf_sha256=pdf_sha256,
            generated_by=generated_by,
            generated_at=occurred_at,
            revoked=False,
        )
        existing_versions.append(version_record)
        return version_record
