from __future__ import annotations

import base64
import hashlib
import hmac
import json
from dataclasses import replace
from uuid import UUID

import pytest

from backend.app.anchor.ledger import IntegerFinancialLedger, PartnerAcceptanceRecord
from app.payments.square_sandbox import (
    SHOP_FEE_CENTS,
    SHOP_FEE_TYPE,
    SquareSandboxConfig,
    SquareSandboxError,
    create_shop_acceptance_checkout,
    verify_square_webhook_signature,
    verify_and_parse_square_payment_event,
)


def make_obligation(tenant_id="10000000-0000-4000-8000-000000000001", idempotency_key="ledger-idem-shop"):
    ledger = IntegerFinancialLedger()
    acceptance = PartnerAcceptanceRecord(
        acceptance_id="acceptance-0001",
        tenant_id=UUID(tenant_id),
        session_id="session-0001",
        party_type="shop",
        partner_org_id="shop-tenant-001",
        accepted_by_actor="operator-001",
        accepted_at="2026-11-21T00:00:00Z",
    )
    return ledger.record_partner_acceptance_obligation(
        acceptance, idempotency_key=idempotency_key, actor_id="operator-001",
        now_iso="2026-11-21T00:00:00Z",
    )


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
        response = {"payment_link": {"id": "link-test", "order_id": "order-test", "url": "https://sandbox.square.link/u/test"}}
    def post(url, headers, body, timeout):
        captured.update(url=url, headers=headers, body=json.loads(body), timeout=timeout)
        return status, json.dumps(response).encode()
    return captured, post


def test_checkout_link_is_sandbox_only_fixed_fee_and_idempotent():
    captured, transport = fake_transport()
    checkout = create_shop_acceptance_checkout(make_obligation(), config(), transport=transport)
    assert captured["url"] == "https://connect.squareupsandbox.com/v2/online-checkout/payment-links"
    assert captured["headers"]["Square-Version"] == "2026-11-18"
    assert captured["headers"]["Authorization"] == "Bearer sandbox-token-test-only"
    body = captured["body"]
    assert body["quick_pay"]["price_money"] == {"amount": 27500, "currency": "USD"}
    assert body["quick_pay"]["location_id"] == "sandbox-location"
    assert body["payment_note"] == "Claim2Car Sandbox shop acceptance fee"
    assert "ledger-shop-0001" not in body["payment_note"]
    assert "acceptance-0001" not in body["payment_note"]
    assert checkout.checkout_url == "https://sandbox.square.link/u/test"
    assert checkout.provider_order_id == "order-test"
    assert create_shop_acceptance_checkout(make_obligation(), config(), transport=transport).idempotency_key == checkout.idempotency_key
    other_tenant = make_obligation(tenant_id="10000000-0000-4000-8000-000000000002", idempotency_key="ledger-idem-shop")
    assert other_tenant.entry_id == make_obligation().entry_id
    assert create_shop_acceptance_checkout(other_tenant, config(), transport=transport).idempotency_key != checkout.idempotency_key


def test_config_loads_from_environment(monkeypatch):
    monkeypatch.setenv("SQUARE_ENVIRONMENT", "sandbox")
    monkeypatch.setenv("SQUARE_SANDBOX_ACCESS_TOKEN", "test-token")
    monkeypatch.setenv("SQUARE_SANDBOX_LOCATION_ID", "test-location")
    monkeypatch.setenv("SQUARE_SANDBOX_WEBHOOK_SIGNATURE_KEY", "test-signature-key")
    monkeypatch.setenv("SQUARE_SANDBOX_WEBHOOK_URL", "https://sandbox.example.test/hooks/square")
    loaded = SquareSandboxConfig.from_environment()
    loaded.validate()
    assert loaded.environment == "sandbox"
    assert loaded.location_id == "test-location"

@pytest.mark.parametrize("changes,code", [
    ({"environment": "production"}, "SQUARE_SANDBOX_ENVIRONMENT_REQUIRED"),
    ({"access_token": ""}, "SQUARE_SANDBOX_ACCESS_TOKEN_REQUIRED"),
    ({"location_id": ""}, "SQUARE_SANDBOX_LOCATION_ID_REQUIRED"),
    ({"webhook_signature_key": ""}, "SQUARE_SANDBOX_WEBHOOK_KEY_REQUIRED"),
    ({"webhook_notification_url": "http://bad.example"}, "SQUARE_SANDBOX_WEBHOOK_URL_MUST_BE_HTTPS"),
])
def test_config_fail_closed(changes, code):
    with pytest.raises(SquareSandboxError, match=code):
        create_shop_acceptance_checkout(make_obligation(), config(**changes), transport=fake_transport()[1])


@pytest.mark.parametrize("changes,code", [
    ({"entry_kind": "REVERSAL_BOOKED"}, "SHOP_FEE_OBLIGATION_REQUIRED"),
    ({"fee_type": "DEALER_ACQUISITION_FEE"}, "SHOP_FEE_TYPE_REQUIRED"),
    ({"amount_cents": 37500}, "SHOP_FEE_AMOUNT_MISMATCH"),
    ({"currency": "USD"}, "SHOP_FEE_CURRENCY_INVALID"),
    ({"entry_id": ""}, "SHOP_FEE_OBLIGATION_IDENTITY_REQUIRED"),
    ({"partner_org_id": ""}, "SHOP_FEE_OBLIGATION_IDENTITY_REQUIRED"),
])
def test_checkout_requires_exact_shop_acceptance_obligation(changes, code):
    obligation = replace(make_obligation(), **changes)
    with pytest.raises(SquareSandboxError, match=code):
        create_shop_acceptance_checkout(obligation, config(), transport=fake_transport()[1])


@pytest.mark.parametrize("timeout", [0, -1, 31, True, "15"])
def test_checkout_timeout_is_bounded(timeout):
    with pytest.raises(SquareSandboxError, match="TIMEOUT_INVALID"):
        create_shop_acceptance_checkout(make_obligation(), config(), transport=fake_transport()[1], timeout_seconds=timeout)


def test_checkout_rejects_fake_obligation_object():
    with pytest.raises(SquareSandboxError, match="SHOP_FEE_OBLIGATION_REQUIRED"):
        create_shop_acceptance_checkout(object(), config(), transport=fake_transport()[1])


def test_checkout_rejects_corrupt_postings():
    entry = make_obligation()
    corrupt = replace(entry, lines=(entry.lines[0], replace(entry.lines[1], amount_cents=1)))
    with pytest.raises(SquareSandboxError, match="SHOP_FEE_POSTINGS_INVALID"):
        create_shop_acceptance_checkout(corrupt, config(), transport=fake_transport()[1])


def test_provider_failure_and_bad_checkout_url_are_redacted_and_rejected():
    _, rejected = fake_transport(status=403)
    with pytest.raises(SquareSandboxError, match="CHECKOUT_REQUEST_REJECTED"):
        create_shop_acceptance_checkout(make_obligation(), config(), transport=rejected)
    _, bad_url = fake_transport({"payment_link": {"id": "l", "order_id": "o", "url": "https://evil.example/payment"}})
    with pytest.raises(SquareSandboxError, match="CHECKOUT_URL_INVALID"):
        create_shop_acceptance_checkout(make_obligation(), config(), transport=bad_url)


@pytest.mark.parametrize("url", [
    "https://sandbox.square.link/u/test",
    "https://square.link/u/test",
    "https://checkout.square.site/checkout/test",
])
def test_checkout_accepts_known_square_hosts(url):
    _, transport = fake_transport({"payment_link": {"id": "l", "order_id": "o", "url": url}})
    assert create_shop_acceptance_checkout(make_obligation(), config(), transport=transport).checkout_url == url


@pytest.mark.parametrize("url", [
    "http://sandbox.square.link/u/test",
    "https://sandbox.square.link.evil.test/u/test",
    "https://user@sandbox.square.link/u/test",
    "https://sandbox.square.link:443/u/test",
    "https://sandbox.square.link/u/test#fragment",
])
def test_checkout_rejects_malformed_or_untrusted_url(url):
    _, transport = fake_transport({"payment_link": {"id": "l", "order_id": "o", "url": url}})
    with pytest.raises(SquareSandboxError, match="CHECKOUT_URL_INVALID"):
        create_shop_acceptance_checkout(make_obligation(), config(), transport=transport)


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
    ("COMPLETED", 27000, "USD", "PAYMENT_AMOUNT_MISMATCH"),
    ("PENDING", 27500, "USD", "PAYMENT_STATUS_UNSUPPORTED"),
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
