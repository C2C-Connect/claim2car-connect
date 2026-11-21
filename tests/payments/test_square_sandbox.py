from __future__ import annotations

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass

import pytest

from app.payments.square_sandbox import (
    SHOP_FEE_CENTS,
    SHOP_FEE_TYPE,
    SquareSandboxConfig,
    SquareSandboxError,
    create_shop_acceptance_checkout,
    verify_square_webhook_signature,
    verify_and_parse_square_payment_event,
)


@dataclass
class Obligation:
    entry_id: str = "ledger-shop-0001"
    entry_kind: str = "OBLIGATION_BOOKED"
    fee_type: str = SHOP_FEE_TYPE
    amount_cents: int = SHOP_FEE_CENTS
    currency: str = "USD_CENTS"
    acceptance_id: str = "acceptance-0001"
    partner_org_id: str = "shop-tenant-001"
    tenant_id: str = "tenant-001"


def config(**changes):
    values = dict(
        access_token="sandbox-token-test-only",
        location_id="sandbox-location",
        webhook_signature_key="webhook-test-key",
        webhook_notification_url="https://sandbox.example.test/webhook/square",
        environment="sandbox",
    )
    values.update(changes)
    return SquareSandboxConfig(**values)


def fake_transport(response=None, status=200):
    captured = {}
    if response is None:
        response = {"payment_link": {"id": "link-test", "order_id": "order-test", "url": "https://square.link/u/test"}}
    def post(url, headers, body, timeout):
        captured.update(url=url, headers=headers, body=json.loads(body), timeout=timeout)
        return status, json.dumps(response).encode()
    return captured, post


def test_checkout_link_is_sandbox_only_fixed_fee_and_idempotent():
    captured, transport = fake_transport()
    checkout = create_shop_acceptance_checkout(Obligation(), config(), transport=transport)
    assert captured["url"] == "https://connect.squareupsandbox.com/v2/online-checkout/payment-links"
    assert captured["headers"]["Square-Version"] == "2026-11-18"
    assert captured["headers"]["Authorization"] == "Bearer sandbox-token-test-only"
    body = captured["body"]
    assert body["quick_pay"]["price_money"] == {"amount": 27500, "currency": "USD"}
    assert body["quick_pay"]["location_id"] == "sandbox-location"
    assert body["payment_note"].startswith("Claim2Car sandbox obligation")
    assert checkout.checkout_url == "https://square.link/u/test"
    assert checkout.provider_order_id == "order-test"
    assert create_shop_acceptance_checkout(Obligation(), config(), transport=transport).idempotency_key == checkout.idempotency_key
    other_tenant = Obligation(tenant_id="tenant-002")
    assert create_shop_acceptance_checkout(other_tenant, config(), transport=transport).idempotency_key != checkout.idempotency_key


@pytest.mark.parametrize("changes,code", [
    ({"environment": "production"}, "SQUARE_SANDBOX_ENVIRONMENT_REQUIRED"),
    ({"access_token": ""}, "SQUARE_SANDBOX_ACCESS_TOKEN_REQUIRED"),
    ({"location_id": ""}, "SQUARE_SANDBOX_LOCATION_ID_REQUIRED"),
    ({"webhook_signature_key": ""}, "SQUARE_SANDBOX_WEBHOOK_KEY_REQUIRED"),
    ({"webhook_notification_url": "http://bad.example"}, "SQUARE_SANDBOX_WEBHOOK_URL_MUST_BE_HTTPS"),
])
def test_config_fail_closed(changes, code):
    with pytest.raises(SquareSandboxError, match=code):
        create_shop_acceptance_checkout(Obligation(), config(**changes), transport=fake_transport()[1])


@pytest.mark.parametrize("changes,code", [
    ({"entry_kind": "REVERSAL_BOOKED"}, "SHOP_FEE_OBLIGATION_REQUIRED"),
    ({"fee_type": "DEALER_ACQUISITION_FEE"}, "SHOP_FEE_TYPE_REQUIRED"),
    ({"amount_cents": 37500}, "SHOP_FEE_AMOUNT_MISMATCH"),
    ({"currency": "USD"}, "SHOP_FEE_CURRENCY_INVALID"),
    ({"entry_id": ""}, "SHOP_FEE_OBLIGATION_IDENTITY_REQUIRED"),
])
def test_checkout_requires_exact_shop_acceptance_obligation(changes, code):
    obligation = Obligation(**changes)
    with pytest.raises(SquareSandboxError, match=code):
        create_shop_acceptance_checkout(obligation, config(), transport=fake_transport()[1])


def test_provider_failure_and_bad_checkout_url_are_redacted_and_rejected():
    _, rejected = fake_transport(status=403)
    with pytest.raises(SquareSandboxError, match="CHECKOUT_REQUEST_REJECTED"):
        create_shop_acceptance_checkout(Obligation(), config(), transport=rejected)
    _, bad_url = fake_transport({"payment_link": {"id": "l", "order_id": "o", "url": "https://evil.example/payment"}})
    with pytest.raises(SquareSandboxError, match="CHECKOUT_URL_INVALID"):
        create_shop_acceptance_checkout(Obligation(), config(), transport=bad_url)


def sign(body, cfg):
    return base64.b64encode(hmac.new(cfg.webhook_signature_key.encode(), cfg.webhook_notification_url.encode()+body, hashlib.sha256).digest()).decode()


def payment_event(status="COMPLETED", amount=27500, currency="USD"):
    return json.dumps({
        "event_id": "event-001",
        "type": "payment.updated",
        "data": {"object": {"payment": {
            "id": "payment-001", "order_id": "order-test", "status": status,
            "amount_money": {"amount": amount, "currency": currency}
        }}}
    }, separators=(",", ":")).encode()


def test_webhook_signature_exact_url_body_and_key():
    cfg = config()
    raw = payment_event()
    signature = sign(raw, cfg)
    assert verify_square_webhook_signature(raw, signature, signature_key=cfg.webhook_signature_key, notification_url=cfg.webhook_notification_url)
    assert not verify_square_webhook_signature(raw+b" ", signature, signature_key=cfg.webhook_signature_key, notification_url=cfg.webhook_notification_url)
    assert not verify_square_webhook_signature(raw, signature, signature_key="wrong-key", notification_url=cfg.webhook_notification_url)
    assert not verify_square_webhook_signature(raw, signature, signature_key=cfg.webhook_signature_key, notification_url="https://other.example/webhook")


def test_payment_event_is_authenticated_and_parsed_minimally():
    cfg = config()
    raw = payment_event()
    parsed = verify_and_parse_square_payment_event(raw, sign(raw, cfg), cfg, square_environment="Sandbox")
    assert (parsed.event_id, parsed.payment_id, parsed.order_id) == ("event-001", "payment-001", "order-test")
    assert (parsed.status, parsed.amount_cents, parsed.currency) == ("COMPLETED", 27500, "USD")
    assert not hasattr(parsed, "raw_payload")
    with pytest.raises(SquareSandboxError, match="SIGNATURE_INVALID"):
        verify_and_parse_square_payment_event(raw, "invalid", cfg, square_environment="Sandbox")


@pytest.mark.parametrize("status,amount,currency,code", [
    ("COMPLETED", 27500, "CAD", "PAYMENT_CURRENCY_UNSUPPORTED"),
    ("COMPLETED", -1, "USD", "PAYMENT_EVENT_INVALID"),
    ("COMPLETED", True, "USD", "PAYMENT_EVENT_INVALID"),
])
def test_webhook_rejects_invalid_amount_currency(status, amount, currency, code):
    cfg = config()
    raw = payment_event(status, amount, currency)
    with pytest.raises(SquareSandboxError, match=code):
        verify_and_parse_square_payment_event(raw, sign(raw, cfg), cfg, square_environment="Sandbox")


def test_webhook_rejects_non_sandbox_environment_header():
    cfg = config()
    raw = payment_event()
    with pytest.raises(SquareSandboxError, match="WEBHOOK_ENVIRONMENT_INVALID"):
        verify_and_parse_square_payment_event(raw, sign(raw, cfg), cfg, square_environment="Production")


def test_webhook_rejects_unsupported_event_type():
    cfg = config()
    raw = json.dumps({"event_id":"event-2","type":"refund.created","data":{"object":{"payment":{}}}}).encode()
    with pytest.raises(SquareSandboxError, match="EVENT_UNSUPPORTED"):
        verify_and_parse_square_payment_event(raw, sign(raw, cfg), cfg, square_environment="Sandbox")
