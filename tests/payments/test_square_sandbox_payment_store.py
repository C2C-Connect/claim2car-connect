from contextlib import contextmanager
from types import SimpleNamespace
from uuid import UUID

import pytest

from backend.app.anchor.ledger import IntegerFinancialLedger, PartnerAcceptanceRecord
from app.payments.square_sandbox import SquareSandboxCheckout
from database.square_sandbox_payments import (
    SquareSandboxPaymentIntentStore,
    SquareSandboxPaymentStoreError,
)


def ledger_entry(tenant="10000000-0000-4000-8000-000000000001"):
    ledger = IntegerFinancialLedger()
    acceptance = PartnerAcceptanceRecord(
        acceptance_id="acceptance-1",tenant_id=UUID(tenant),session_id="session-1",
        party_type="shop",partner_org_id="shop-1",accepted_by_actor="operator-1",
        accepted_at="2026-11-21T00:00:00Z",
    )
    return ledger.record_partner_acceptance_obligation(acceptance,idempotency_key="idem-1",actor_id="operator-1")


def checkout(entry):
    return SquareSandboxCheckout(
        provider_link_id="link-1",provider_order_id="order-1",checkout_url="https://sandbox.square.link/u/test",
        idempotency_key="c2c-shop-fee-test",obligation_entry_id=entry.entry_id,amount_cents=27500,currency="USD",
    )


class FakeConn:
    def __init__(self,row=None,register_status="CREATED"):
        self.row=row
        self.register_status=register_status
        self.calls=[]
    def execute(self,query,params):
        self.calls.append((query,params))
        if "register_square_sandbox_payment_intent" in query:
            return SimpleNamespace(fetchone=lambda:(self.register_status,))
        return SimpleNamespace(fetchone=lambda:self.row)


class FakeSessions:
    def __init__(self,conn,actor):
        self.conn=conn
        self.actor=actor
    @contextmanager
    def _authorized(self,authorization):
        yield self.conn,self.actor


def fake_row(entry):
    return (
        "payment-intent-1",str(entry.tenant_id),entry.entry_id,entry.acceptance_id,entry.partner_org_id,
        "link-1","order-1","https://sandbox.square.link/u/test","c2c-shop-fee-test",
        27500,"USD","LINK_CREATED","operator-1","2026-11-21T00:00:00+00:00","2026-11-21T00:00:00+00:00",
    )


def test_store_registers_and_reads_back_tenant_bound_intent():
    entry=ledger_entry()
    conn=FakeConn(fake_row(entry))
    actor=SimpleNamespace(actor_role="operator",actor_id="operator-1",tenant_id=entry.tenant_id)
    store=SquareSandboxPaymentIntentStore(FakeSessions(conn,actor))
    result=store.register_checkout_link("operator-token",entry,checkout(entry),actor_id="operator-1")
    assert result.status=="LINK_CREATED"
    assert result.obligation_entry_id==entry.entry_id
    assert len(conn.calls)==2
    assert "register_square_sandbox_payment_intent" in conn.calls[0][0]


@pytest.mark.parametrize("actor,actor_id,code",[
    (SimpleNamespace(actor_role="partner",actor_id="operator-1",tenant_id="10000000-0000-4000-8000-000000000001"),"operator-1","LEDGER_ACTOR_NOT_AUTHORIZED"),
    (SimpleNamespace(actor_role="operator",actor_id="operator-2",tenant_id="10000000-0000-4000-8000-000000000001"),"operator-1","LEDGER_ACTOR_NOT_AUTHORIZED"),
    (SimpleNamespace(actor_role="operator",actor_id="operator-1",tenant_id="10000000-0000-4000-8000-000000000002"),"operator-1","TENANT_CONTEXT_MISMATCH"),
])
def test_store_requires_operator_identity_and_tenant_binding(actor,actor_id,code):
    entry=ledger_entry()
    store=SquareSandboxPaymentIntentStore(FakeSessions(FakeConn(fake_row(entry)),actor))
    with pytest.raises(SquareSandboxPaymentStoreError,match=code):
        store.register_checkout_link("token",entry,checkout(entry),actor_id=actor_id)


def test_store_rejects_mismatched_checkout_and_non_ledger_entry():
    entry=ledger_entry()
    store=SquareSandboxPaymentIntentStore(FakeSessions(FakeConn(fake_row(entry)),SimpleNamespace(actor_role="operator",actor_id="operator-1",tenant_id=entry.tenant_id)))
    bad=SquareSandboxCheckout("link-1","order-1","https://sandbox.square.link/u/test","idem","other-entry",27500,"USD")
    with pytest.raises(SquareSandboxPaymentStoreError,match="CHECKOUT_OBLIGATION_MISMATCH"):
        store.register_checkout_link("token",entry,bad,actor_id="operator-1")
    with pytest.raises(SquareSandboxPaymentStoreError,match="SHOP_FEE_OBLIGATION_REQUIRED"):
        store.register_checkout_link("token",object(),checkout(entry),actor_id="operator-1")
