"""Tenant-authorized persistence for Square Sandbox checkout-link intents."""
from dataclasses import dataclass
from uuid import uuid4

from backend.app.anchor.ledger import LedgerJournalEntry
from app.payments.square_sandbox import SquareSandboxCheckout, SquareSandboxError


class SquareSandboxPaymentStoreError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class SquareSandboxPaymentIntent:
    payment_intent_id: str
    tenant_id: str
    obligation_entry_id: str
    acceptance_id: str
    partner_org_id: str
    provider_link_id: str
    provider_order_id: str
    checkout_url: str
    idempotency_key: str
    amount_cents: int
    currency: str
    status: str
    created_by: str
    created_at: str
    updated_at: str


class SquareSandboxPaymentIntentStore:
    """Register a provider checkout link only against a tenant's real ledger obligation."""

    def __init__(self, sessions):
        self._sessions = sessions

    def register_checkout_link(self, authorization, obligation, checkout, *, actor_id):
        if not isinstance(obligation, LedgerJournalEntry):
            raise SquareSandboxPaymentStoreError("SHOP_FEE_OBLIGATION_REQUIRED")
        if not isinstance(checkout, SquareSandboxCheckout):
            raise SquareSandboxPaymentStoreError("SQUARE_SANDBOX_CHECKOUT_REQUIRED")
        if (checkout.obligation_entry_id != obligation.entry_id
                or checkout.amount_cents != 27_500 or checkout.currency != "USD"):
            raise SquareSandboxPaymentStoreError("CHECKOUT_OBLIGATION_MISMATCH")
        if not isinstance(actor_id, str) or not actor_id.strip():
            raise SquareSandboxPaymentStoreError("LEDGER_ACTOR_REQUIRED")
        tenant_id = str(obligation.tenant_id)
        payment_intent_id = str(uuid4())
        with self._sessions._authorized(authorization) as (conn, actor):
            if actor.actor_role not in ("operator", "supervisor") or actor.actor_id != actor_id:
                raise SquareSandboxPaymentStoreError("LEDGER_ACTOR_NOT_AUTHORIZED")
            if str(actor.tenant_id) != tenant_id:
                raise SquareSandboxPaymentStoreError("TENANT_CONTEXT_MISMATCH")
            conn.execute(
                "SELECT faos.register_square_sandbox_payment_intent("
                "%s::uuid,%s::uuid,%s::text,%s::text,%s::text,%s::text,%s::text,%s::text)",
                (tenant_id,payment_intent_id,obligation.entry_id,checkout.provider_link_id,
                 checkout.provider_order_id,checkout.checkout_url,checkout.idempotency_key,actor_id),
            )
            row = conn.execute(
                "SELECT payment_intent_id::text,tenant_id::text,obligation_entry_id,acceptance_id,"
                "partner_org_id,provider_link_id,provider_order_id,checkout_url,idempotency_key,"
                "amount_cents,currency,status,created_by,created_at::text,updated_at::text "
                "FROM faos.square_sandbox_payment_intents WHERE tenant_id=%s AND idempotency_key=%s",
                (tenant_id,checkout.idempotency_key),
            ).fetchone()
            if row is None:
                raise SquareSandboxPaymentStoreError("SQUARE_PAYMENT_INTENT_READBACK_FAILED")
        return SquareSandboxPaymentIntent(*row)
