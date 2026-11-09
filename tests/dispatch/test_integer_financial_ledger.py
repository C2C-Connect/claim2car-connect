from __future__ import annotations

import unittest
from uuid import UUID

from backend.app.anchor.ledger import (
    DEALER_ACQUISITION_FEE_CENTS,
    REPAIR_SHOP_ACCEPTANCE_FEE_CENTS,
    IntegerFinancialLedger,
    LedgerError,
    PartnerAcceptanceRecord,
)


class IntegerFinancialLedgerTests(unittest.TestCase):
    def setUp(self):
        self.ledger = IntegerFinancialLedger()
        self.tenant = UUID("12345678-1234-5678-1234-567812345678")

    def acceptance(self, party="dealer", key="accept-1"):
        return PartnerAcceptanceRecord(
            acceptance_id=key,
            tenant_id=self.tenant,
            session_id="session-1",
            party_type=party,
            partner_org_id=f"{party}-org",
            accepted_by_actor="partner-user",
            accepted_at="2026-11-08T18:00:00+00:00",
        )

    def test_fixed_partner_fees_and_balanced_double_entry(self):
        dealer = self.ledger.record_partner_acceptance_obligation(
            self.acceptance(), idempotency_key="dealer-1", actor_id="marketplace"
        )
        shop = self.ledger.record_partner_acceptance_obligation(
            self.acceptance("shop", "accept-2"), idempotency_key="shop-1", actor_id="marketplace"
        )
        self.assertEqual(dealer.amount_cents, DEALER_ACQUISITION_FEE_CENTS)
        self.assertEqual(shop.amount_cents, REPAIR_SHOP_ACCEPTANCE_FEE_CENTS)
        export = self.ledger.export_audit_ledger(tenant_id=self.tenant)
        self.assertTrue(export["balanced"])
        self.assertEqual(export["total_debits_cents"], 65_000)

    def test_float_overrides_and_noncanonical_fees_rejected(self):
        with self.assertRaises(LedgerError):
            self.ledger.record_partner_acceptance_obligation(
                self.acceptance(), idempotency_key="float", actor_id="marketplace",
                amount_override_cents=37500.0,
            )
        with self.assertRaises(LedgerError):
            self.ledger.record_partner_acceptance_obligation(
                self.acceptance(), idempotency_key="wrong", actor_id="marketplace",
                amount_override_cents=37000,
            )

    def test_idempotency_and_reversal_are_append_only(self):
        entry = self.ledger.record_partner_acceptance_obligation(
            self.acceptance(), idempotency_key="same", actor_id="marketplace"
        )
        self.assertIs(entry, self.ledger.record_partner_acceptance_obligation(
            self.acceptance(), idempotency_key="same", actor_id="marketplace"
        ))
        reversal = self.ledger.record_reversal_or_dispute_refund(
            entry.entry_id, idempotency_key="reverse-1", actor_id="finance", reason="disputed"
        )
        self.assertEqual(reversal.reverses_entry_id, entry.entry_id)
        self.assertEqual(len(self.ledger.export_audit_ledger()["entries"]), 2)
        self.assertTrue(self.ledger.export_audit_ledger()["balanced"])
        with self.assertRaises(LedgerError):
            self.ledger.record_reversal_or_dispute_refund(
                entry.entry_id, idempotency_key="reverse-2", actor_id="finance", reason="again"
            )

    def test_owner_incentive_and_unapproved_operator_payout_blocked(self):
        for label, amount in (("owner incentive", 8_000), ("operator payout", 11_000)):
            with self.assertRaises(LedgerError):
                self.ledger.guard_prohibited_compensation(label, amount)

    def test_idempotency_cannot_cross_tenant_or_acceptance(self):
        self.ledger.record_partner_acceptance_obligation(
            self.acceptance(), idempotency_key="shared-key", actor_id="marketplace"
        )
        different_tenant = PartnerAcceptanceRecord(
            acceptance_id="accept-1", tenant_id=UUID("87654321-4321-8765-4321-876543218765"),
            session_id="session-1", party_type="dealer", partner_org_id="dealer-org",
            accepted_by_actor="partner-user", accepted_at="2026-11-08T18:00:00+00:00",
        )
        different_acceptance = self.acceptance(key="accept-other")
        for acceptance in (different_tenant, different_acceptance):
            with self.assertRaisesRegex(LedgerError, "IDEMPOTENCY_KEY_CONFLICT"):
                self.ledger.record_partner_acceptance_obligation(
                    acceptance, idempotency_key="shared-key", actor_id="marketplace"
                )

    def test_operator_policy_gate_requires_boolean_configuration(self):
        with self.assertRaisesRegex(LedgerError, "POLICY_FLAG_MUST_BE_BOOLEAN"):
            IntegerFinancialLedger(operator_payout_policy_approved="false")


if __name__ == "__main__":
    unittest.main()
