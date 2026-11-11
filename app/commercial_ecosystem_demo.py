"""Slice 5G Full-System Commercial Ecosystem Demonstration (S5-5G-01 & S5-5G-02).

Executes the complete Claim2Car Connect lifecycle end-to-end across Slices 1 through 5.
"""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
from uuid import uuid4

from app.controlled_demo import run_demo
from app.damage_localization import DamageAnnotation, DamageRegion
from backend.app.anchor.ledger import IntegerFinancialLedger, PartnerAcceptanceRecord
from backend.app.reports.forensic_pdf import (
    ConsentSnapshot,
    FourTierDossierService,
    SourceEvidenceBinding,
)
from backend.app.vision.adapters import GatedVisionPhysicsPipeline, LocalYoloTwoStageDetector


def run_full_commercial_ecosystem(output_dir: Path, fixed_now: str = "2026-11-08T22:00:00+00:00") -> dict:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Phase A: Run canonical Gate A M1 core pipeline (Steps 1..12)
    base_record = run_demo(output_dir / "m1-core", fixed_now=fixed_now)
    session_id = base_record["session_id"]
    tenant_uuid = uuid4()

    # Phase B: Sovereign In-House Vision + DARCI Physics Gate (Slice 4B / 5F)
    grid = [[90] * 36 for _ in range(36)]
    for y in range(12, 20):
        for x in range(15, 22):
            grid[y][x] = 230

    with tempfile.TemporaryDirectory() as tmp:
        pt_part = Path(tmp) / "2_best.pt"
        pt_damage = Path(tmp) / "4_best.pt"
        pt_part.write_bytes(b"inhouse-2_best-weights")
        pt_damage.write_bytes(b"inhouse-4_best-weights")

        candidate_yolo = LocalYoloTwoStageDetector(
            part_weights_path=pt_part,
            damage_weights_path=pt_damage,
            inference_runner=lambda _slot, _img: [
                {"x1": 0.32, "y1": 0.32, "x2": 0.52, "y2": 0.52, "label": "major_dent", "confidence": 0.95}
            ],
        )
        annotation = DamageAnnotation(
            session_id=session_id,
            slot="front_left",
            region=DamageRegion("front_left", 0.32, 0.32, 0.52, 0.52, "structural_deformation", 1.0),
            annotated_by="synthetic-reviewer-01",
        )
        vision_pipeline = GatedVisionPhysicsPipeline(candidate_detector=candidate_yolo)
        advisory_vision = vision_pipeline.evaluate_and_extract_physics(
            session_id=session_id,
            slot="front_left",
            grid_fixture=grid,
            ground_truth_annotations=[annotation],
        )

    # Phase C: Marketplace Partner Acceptance & Double-Entry Integer-Cents Ledger (Slice 5B & 5D)
    ledger = IntegerFinancialLedger(operator_payout_policy_approved=False)
    dealer_acc = PartnerAcceptanceRecord(
        acceptance_id="acc-dealer-san-antonio-01",
        tenant_id=tenant_uuid,
        session_id=session_id,
        party_type="dealer",
        partner_org_id="dealer-sa-ford-01",
        accepted_by_actor="dealer-buyer-01",
        accepted_at=fixed_now,
    )
    shop_acc = PartnerAcceptanceRecord(
        acceptance_id="acc-shop-san-antonio-01",
        tenant_id=tenant_uuid,
        session_id=session_id,
        party_type="shop",
        partner_org_id="shop-sa-collision-01",
        accepted_by_actor="shop-estimator-01",
        accepted_at=fixed_now,
    )

    dealer_entry = ledger.record_partner_acceptance_obligation(
        dealer_acc, idempotency_key=f"idem-dealer-{session_id}", actor_id="marketplace-engine", now_iso=fixed_now
    )
    shop_entry = ledger.record_partner_acceptance_obligation(
        shop_acc, idempotency_key=f"idem-shop-{session_id}", actor_id="marketplace-engine", now_iso=fixed_now
    )

    # Phase D: 4-Tier Deterministic Document & Dossier Generation (Slice 5A)
    dossier_service = FourTierDossierService()
    consent = ConsentSnapshot(
        owner_actor_id="synthetic-driver",
        accepted=True,
        disclosure_version="disclosure-v1",
        scope="m1-capture-review-and-partner-distribution",
        recorded_at=fixed_now,
    )
    binding = SourceEvidenceBinding(
        session_id=session_id,
        tenant_id=tenant_uuid,
        manifest_digest=base_record["manifest_digest"],
        shot_list_version=base_record["shot_list_version"],
        verified_artifact_ids=tuple(base_record["integrity"]["verified_artifact_ids"]),
        reviewer_actor_id=base_record["reviewer_decision"]["actor"],
        reviewer_disposition=base_record["reviewer_decision"]["disposition"],
        reviewer_reason_code="GATE_A_AND_SLICE_5_VERIFIED",
        reviewed_at=fixed_now,
        vin_sha256="a" * 64,
        advisory_darci_summary={
            "vision": {
                "model_version": advisory_vision.model_version,
                "promoted_over_baseline": advisory_vision.promoted_over_baseline,
                "weight_digests": list(advisory_vision.weight_digests),
            },
            "physics": list(advisory_vision.darci_physics_inputs),
        },
    )

    owner_pdf = dossier_service.generate_vehicle_owner_pdf(
        consent=consent, binding=binding, generated_by="dossier-engine", now_iso=fixed_now
    )
    dealer_dossier = dossier_service.generate_dealer_dossier(
        consent=consent, binding=binding, ledger_entry=dealer_entry,
        estimated_acv_cents=2_150_000, generated_by="dossier-engine", now_iso=fixed_now
    )
    shop_packet = dossier_service.generate_repair_shop_packet(
        consent=consent, binding=binding, ledger_entry=shop_entry,
        damaged_zones=list(advisory_vision.darci_physics_inputs),
        generated_by="dossier-engine", now_iso=fixed_now
    )
    carrier_report = dossier_service.generate_carrier_seven_page_report(
        consent=consent, binding=binding, generated_by="dossier-engine", now_iso=fixed_now
    )

    summary = {
        "session_id": session_id,
        "m1_final_state": base_record["final_state"],
        "manifest_digest": base_record["manifest_digest"],
        "inhouse_vision": {
            "model_version": advisory_vision.model_version,
            "promoted_over_baseline": advisory_vision.promoted_over_baseline,
            "advisory_only": advisory_vision.advisory_only,
            "darci_physics_inputs": list(advisory_vision.darci_physics_inputs),
        },
        "financial_ledger": ledger.export_audit_ledger(tenant_id=tenant_uuid),
        "generated_dossiers": {
            "vehicle_owner_pdf": {"id": owner_pdf.document_id, "sha256": owner_pdf.pdf_sha256, "pages": owner_pdf.page_count},
            "dealer_dossier": {"id": dealer_dossier.document_id, "sha256": dealer_dossier.pdf_sha256, "fee_cents": dealer_entry.amount_cents},
            "repair_shop_packet": {"id": shop_packet.document_id, "sha256": shop_packet.pdf_sha256, "fee_cents": shop_entry.amount_cents},
            "carrier_seven_page_report": {"id": carrier_report.document_id, "sha256": carrier_report.pdf_sha256, "pages": carrier_report.page_count},
        },
    }

    out_file = output_dir / f"full-commercial-ecosystem-{session_id}.json"
    out_file.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


if __name__ == "__main__":
    res = run_full_commercial_ecosystem(Path("output/commercial-ecosystem"))
    print(json.dumps({
        "session_id": res["session_id"],
        "m1_final_state": res["m1_final_state"],
        "ledger_balanced": res["financial_ledger"]["balanced"],
        "total_booked_cents": res["financial_ledger"]["total_debits_cents"],
        "dossiers_generated": list(res["generated_dossiers"].keys()),
    }, indent=2))
