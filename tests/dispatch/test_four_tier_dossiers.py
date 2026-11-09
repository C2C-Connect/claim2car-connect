from __future__ import annotations

import unittest
from uuid import UUID

from backend.app.anchor.ledger import IntegerFinancialLedger, PartnerAcceptanceRecord
from backend.app.reports.forensic_pdf import (
    ConsentSnapshot,
    DossierGenerationError,
    FourTierDossierService,
    SourceEvidenceBinding,
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
            damaged_zones=[], generated_by="dossier", now_iso=self.consent.recorded_at,
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
