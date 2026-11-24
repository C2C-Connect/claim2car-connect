from __future__ import annotations

import unittest
from hashlib import sha256
from io import BytesIO
from uuid import UUID

from PIL import Image

from backend.app.anchor.ledger import (
    IntegerFinancialLedger, LedgerJournalEntry, LedgerPostingLine, PartnerAcceptanceRecord,
)
from backend.app.reports.forensic_pdf import (
    ConsentSnapshot,
    DossierGenerationError,
    FourTierDossierService,
    SourceEvidenceBinding,
)
from backend.app.reports.damage_assessment import (
    CameraAngle, DamageAssessment, DamageEvidenceImage, DamageFinding,
)


class FourTierDossierTests(unittest.TestCase):
    def setUp(self):
        self.tenant = UUID("12345678-1234-5678-1234-567812345678")
        self.service = FourTierDossierService()
        self.consent = ConsentSnapshot(
            owner_actor_id="owner-1", accepted=True, disclosure_version="v1",
            scope="m1-capture-review-and-partner-distribution",
            recorded_at="2026-11-08T18:00:00+00:00",
        )
        self.binding = SourceEvidenceBinding(
            session_id="session-1", tenant_id=self.tenant, manifest_digest="a" * 64,
            shot_list_version="m1-v1", verified_artifact_ids=("artifact-1",),
            reviewer_actor_id="reviewer-1", reviewer_disposition="NOTE_ONLY",
            reviewer_reason_code="reviewed", reviewed_at="2026-11-08T18:01:00+00:00",
            vin_sha256="b" * 64,
        )

    def ledger_entry(self, party):
        if party == "dealer":
            # Dossier rendering consumes a verified close-ledger record. This
            # fixture tests document formatting only; it does not book a fee
            # from dealer acceptance or bypass the production close-event gate.
            amount = 37_500
            return LedgerJournalEntry(
                sequence=1, entry_id="fixture-dealer-close", idempotency_key="fixture-close",
                tenant_id=str(self.tenant), session_id="session-1",
                entry_kind="OBLIGATION_BOOKED", fee_type="DEALER_ACQUISITION_FEE",
                partner_org_id="dealer-org", acceptance_id="qualified-close-1",
                amount_cents=amount,
                currency="USD_CENTS",
                lines=(
                    LedgerPostingLine("AR:DEALER:dealer-org", "DEBIT", amount),
                    LedgerPostingLine("REV:DEALER_ACQUISITION", "CREDIT", amount),
                ),
                actor_id="marketplace", occurred_at="2026-11-08T18:00:00+00:00",
                reason="Verified qualified acquisition close (qualified-close-1)",
                reverses_entry_id=None, previous_hash="0" * 64, entry_hash="1" * 64,
            )
        ledger = IntegerFinancialLedger()
        acceptance = PartnerAcceptanceRecord(
            acceptance_id=f"accept-{party}", tenant_id=self.tenant, session_id="session-1",
            party_type=party, partner_org_id=f"{party}-org", accepted_by_actor="partner-user",
            accepted_at="2026-11-08T18:00:00+00:00",
        )
        return ledger.record_partner_acceptance_obligation(
            acceptance, idempotency_key=f"idem-{party}", actor_id="marketplace"
        )

    def test_four_document_tiers_create_pdf_and_restrict_downloads(self):
        owner = self.service.generate_vehicle_owner_pdf(
            consent=self.consent, binding=self.binding, generated_by="dossier", now_iso=self.consent.recorded_at
        )
        dealer = self.service.generate_dealer_dossier(
            consent=self.consent, binding=self.binding, ledger_entry=self.ledger_entry("dealer"),
            estimated_acv_cents=2_150_000, generated_by="dossier", now_iso=self.consent.recorded_at,
        )
        shop = self.service.generate_repair_shop_packet(
            consent=self.consent, binding=self.binding, ledger_entry=self.ledger_entry("shop"),
            localization_observations=[], generated_by="dossier", now_iso=self.consent.recorded_at,
        )
        carrier = self.service.generate_carrier_seven_page_report(
            consent=self.consent, binding=self.binding, generated_by="dossier", now_iso=self.consent.recorded_at
        )
        self.assertEqual(owner.page_count, 2)
        self.assertEqual(dealer.page_count, 2)
        self.assertEqual(shop.page_count, 2)
        self.assertEqual(carrier.page_count, 7)
        for doc in (owner, dealer, shop, carrier):
            self.assertTrue(doc.pdf_bytes.startswith(b"%PDF-1.4"))
            self.assertIn(b"xref\n", doc.pdf_bytes)
            self.assertEqual(len(doc.pdf_sha256), 64)
            self.assertNotIn(b"owner_payout", doc.pdf_bytes)
        fetched = self.service.retrieve_and_audit_download(
            session_id="session-1", document_type="DEALER_DOSSIER", recipient_actor_id="buyer",
            recipient_role="dealer", recipient_tenant_id=self.tenant,
        )
        self.assertEqual(fetched.document_id, dealer.document_id)
        self.assertEqual(len(self.service.download_audit_log()), 1)
        with self.assertRaises(DossierGenerationError):
            self.service.retrieve_and_audit_download(
                session_id="session-1", document_type="DEALER_DOSSIER", recipient_actor_id="wrong",
                recipient_role="shop", recipient_tenant_id=self.tenant,
            )

    def test_damage_assessment_report_requires_manifest_bound_images_and_review(self):
        image_buffer = BytesIO()
        Image.new("RGB", (320, 240), "silver").save(image_buffer, format="JPEG")
        original = image_buffer.getvalue()
        evidence = DamageEvidenceImage(
            artifact_id="artifact-1", capture_slot="front_right_oblique",
            original_bytes=original, expected_sha256=sha256(original).hexdigest(),
            registered_at="2026-11-08T18:00:00+00:00",
            camera_angle=CameraAngle(yaw_degrees=30, pitch_degrees=0, roll_degrees=0, source="CAPTURE_METADATA"),
        )
        finding = DamageFinding(
            finding_id="D-001", component="Front fender",
            vehicle_location="Passenger-side front quarter",
            damage_type="surface deformation candidate",
            observation="Localized visible contour change",
            evidence_artifact_id="artifact-1",
            bbox_normalized=(.2,.2,.6,.7),
            status="CONFIRMED_BY_REVIEWER",
            reviewer_actor_id="reviewer-1", reviewed_at="2026-11-08T18:01:00+00:00",
        )
        assessment = DamageAssessment(
            session_id="session-1", vehicle_description="2022 Example Sedan",
            report_revision=1, findings=(finding,), evidence_images=(evidence,),
        )
        report_binding = SourceEvidenceBinding(
            **{**self.binding.__dict__, "artifact_sha256_by_id": {"artifact-1": sha256(original).hexdigest()}}
        )
        report = self.service.generate_damage_assessment_report(
            consent=self.consent, binding=report_binding, assessment=assessment,
            generated_by="forensic-report", now_iso=self.consent.recorded_at,
        )
        self.assertEqual(report.document_type, "DAMAGE_ASSESSMENT_REPORT")
        self.assertTrue(report.pdf_bytes.startswith(b"%PDF-"))
        self.assertIn(b"/Subtype /Image", report.pdf_bytes)
        self.assertEqual(report.pages[0]["findings"][0]["evidence_artifact_id"], "artifact-1")
        self.assertEqual(report.pages[0]["findings"][0]["bbox_normalized"], [.2,.2,.6,.7])
        wrong_digest_binding = SourceEvidenceBinding(
            **{**self.binding.__dict__, "artifact_sha256_by_id": {"artifact-1": "f" * 64}}
        )
        with self.assertRaisesRegex(DossierGenerationError, "DAMAGE_REPORT_IMAGE_DIGEST_NOT_IN_MANIFEST"):
            self.service.generate_damage_assessment_report(
                consent=self.consent, binding=wrong_digest_binding, assessment=assessment,
                generated_by="forensic-report",
            )
        with self.assertRaisesRegex(DossierGenerationError, "DAMAGE_REPORT_IMAGE_NOT_IN_VERIFIED_MANIFEST"):
            unbound = DamageAssessment(
                session_id="session-1", vehicle_description="2022 Example Sedan",
                report_revision=2, findings=(),
                evidence_images=(DamageEvidenceImage(
                    artifact_id="not-in-manifest", capture_slot="front",
                    original_bytes=original, expected_sha256=sha256(original).hexdigest(),
                    registered_at="2026-11-08T18:00:00+00:00",
                ),),
            )
            self.service.generate_damage_assessment_report(
                consent=self.consent, binding=self.binding, assessment=unbound,
                generated_by="forensic-report",
            )

    def test_confirmed_damage_finding_must_match_bound_reviewer_identity(self):
        image_buffer = BytesIO()
        Image.new("RGB", (320, 240), "silver").save(image_buffer, format="JPEG")
        original = image_buffer.getvalue()
        evidence = DamageEvidenceImage(
            artifact_id="artifact-1", capture_slot="front_right_oblique",
            original_bytes=original, expected_sha256=sha256(original).hexdigest(),
            registered_at="2026-11-08T18:00:00+00:00",
        )
        finding = DamageFinding(
            finding_id="D-002", component="Front fender", vehicle_location="Passenger front",
            damage_type="dent", observation="Visible deformation",
            evidence_artifact_id="artifact-1", bbox_normalized=(.2,.2,.5,.5),
            status="CONFIRMED_BY_REVIEWER", reviewer_actor_id="spoofed-reviewer",
            reviewed_at="2026-11-08T18:01:00+00:00",
        )
        assessment = DamageAssessment(
            session_id="session-1", vehicle_description="2022 Example Sedan",
            report_revision=1, findings=(finding,), evidence_images=(evidence,),
        )
        report_binding = SourceEvidenceBinding(
            **{**self.binding.__dict__, "artifact_sha256_by_id": {"artifact-1": sha256(original).hexdigest()}}
        )
        with self.assertRaisesRegex(DossierGenerationError, "DAMAGE_REPORT_REVIEWER_IDENTITY_MISMATCH"):
            self.service.generate_damage_assessment_report(
                consent=self.consent, binding=report_binding, assessment=assessment,
                generated_by="forensic-report",
            )

    def test_consent_withdrawal_blocks_generation_and_revokes_versions(self):
        doc = self.service.generate_vehicle_owner_pdf(
            consent=self.consent, binding=self.binding, generated_by="dossier"
        )
        self.assertEqual(self.service.revoke_all_for_session_on_consent_withdrawal(
            "session-1", revoked_by="owner-1"
        ), 1)
        self.assertTrue(self.service._versions[("session-1", doc.document_type)][0].revoked)
        revoked_consent = ConsentSnapshot(
            owner_actor_id="owner-1", accepted=False, disclosure_version="v1",
            scope=self.consent.scope, recorded_at=self.consent.recorded_at,
            withdrawn_at="2026-11-08T18:02:00+00:00",
        )
        with self.assertRaises(DossierGenerationError):
            self.service.generate_vehicle_owner_pdf(
                consent=revoked_consent, binding=self.binding, generated_by="dossier"
            )

    def test_prohibited_compensation_key_in_advisory_input_is_rejected(self):
        binding = SourceEvidenceBinding(
            **{**self.binding.__dict__, "advisory_darci_summary": {"operator_payout": 110}}
        )
        ledger_entry = self.ledger_entry("dealer")
        with self.assertRaises(DossierGenerationError):
            self.service.generate_dealer_dossier(
                consent=self.consent, binding=binding, ledger_entry=ledger_entry,
                estimated_acv_cents=2_150_000, generated_by="dossier",
            )


if __name__ == "__main__":
    unittest.main()
