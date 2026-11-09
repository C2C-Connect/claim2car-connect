"""Regression coverage for Claim2Car commercial prohibitions and fee rules."""
from __future__ import annotations

import inspect
import unittest

from config import forensic_constants as C


class CommercialProhibitionTests(unittest.TestCase):
    def test_owner_cash_incentive_and_operator_payout_are_not_active_outputs(self):
        """The owner incentive is prohibited; operator compensation is not approved."""
        from backend.app.reports import forensic_pdf
        from backend.app.triage import adjudicate

        for module in (adjudicate, forensic_pdf):
            source = inspect.getsource(module)
            for field in ('"owner_payout"', "'owner_payout'", '"owner_incentive"',
                          '"operator_payout_usd"', '"operator_payout"'):
                self.assertNotIn(field, source)

    def test_flat_partner_fees_are_preserved(self):
        self.assertEqual(C.DEALER_ACQUISITION_FEE_USD, 375)
        self.assertEqual(C.SHOP_FEE_USD, 275)

    def test_shop_acceptance_is_required_before_tow_routing(self):
        from app.dispatch_routing import (
            AcceptanceRecord,
            DispatchRoutingService,
            InMemoryRoutingEngine,
            RoutingError,
            load_road_network,
        )

        service = DispatchRoutingService(InMemoryRoutingEngine())
        network = load_road_network()
        with self.assertRaises((RoutingError, ValueError, TypeError)):
            service.plan(network, None, "operator-depot", "incident-scene", "google")

        acceptance = AcceptanceRecord(
            party_type="shop",
            party_id="verified-shop-001",
            accepted_at="2026-11-08T18:00:00+00:00",
            location_label="shop-a",
        )
        plan = service.plan(network, acceptance, "operator-depot", "incident-scene", "google")
        self.assertEqual(plan.acceptance.party_type, "shop")
