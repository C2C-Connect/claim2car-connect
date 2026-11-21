"""Sandbox-only Square checkout-link client and webhook verifier.

No payment can be created outside Square Sandbox: the API host is fixed, the
environment must be explicitly set to "sandbox", and the client accepts only
verified shop-acceptance obligation records at the fixed $275 amount. This
module does not post, settle, refund, or mutate the financial ledger.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import urlparse

from backend.app.anchor.ledger import LedgerJournalEntry, LedgerPostingLine

SQUARE_SANDBOX_API = "https://connect.squareupsandbox.com"
SQUARE_API_VERSION = "2026-11-18"
SHOP_FEE_CENTS = 27_500
SHOP_FEE_TYPE = "REPAIR_SHOP_ACCEPTANCE_FEE"
OBLIGATION_KIND = "OBLIGATION_BOOKED"
ALLOWED_CHECKOUT_HOSTS = frozenset({"sandbox.square.link", "square.link", "checkout.square.site"})


class SquareSandboxError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class SquareSandboxConfig:
    access_token: str
    location_id: str
    webhook_signature_key: str
    webhook_notification_url: str
    environment: str = "sandbox"

    @classmethod
    def from_environment(cls) -> "SquareSandboxConfig":
        """Load sandbox-only settings from environment variables."""
        return cls(
            access_token=os.environ.get("SQUARE_SANDBOX_ACCESS_TOKEN", ""),
            location_id=os.environ.get("SQUARE_SANDBOX_LOCATION_ID", ""),
            webhook_signature_key=os.environ.get("SQUARE_SANDBOX_WEBHOOK_SIGNATURE_KEY", ""),
            webhook_notification_url=os.environ.get("SQUARE_SANDBOX_WEBHOOK_URL", ""),
            environment=os.environ.get("SQUARE_ENVIRONMENT", ""),
        )

    def validate(self) -> None:
        if self.environment != "sandbox":
            raise SquareSandboxError("SQUARE_SANDBOX_ENVIRONMENT_REQUIRED")
        if not isinstance(self.access_token, str) or not self.access_token.strip():
            raise SquareSandboxError("SQUARE_SANDBOX_ACCESS_TOKEN_REQUIRED")
        if not isinstance(self.location_id, str) or not self.location_id.strip():
            raise SquareSandboxError("SQUARE_SANDBOX_LOCATION_ID_REQUIRED")
        if not isinstance(self.webhook_signature_key, str) or not self.webhook_signature_key:
            raise SquareSandboxError("SQUARE_SANDBOX_WEBHOOK_KEY_REQUIRED")
        url = self.webhook_notification_url
        parsed = urlparse(url) if isinstance(url, str) else None
        if (not parsed or parsed.scheme != "https" or not parsed.hostname
                or parsed.username or parsed.password or parsed.fragment):
            raise SquareSandboxError("SQUARE_SANDBOX_WEBHOOK_URL_MUST_BE_HTTPS")


@dataclass(frozen=True)
class SquareSandboxCheckout:
    provider_link_id: str
    provider_order_id: str
    checkout_url: str
    idempotency_key: str
    obligation_entry_id: str
    amount_cents: int
    currency: str = "USD"


@dataclass(frozen=True)
class SquareSandboxPaymentEvent:
    event_id: str
    event_type: str
    payment_id: str
    order_id: str
    status: str
    amount_cents: int
    currency: str


Transport = Callable[[str, dict[str, str], bytes, int], tuple[int, bytes]]


def _http_post(url: str, headers: dict[str, str], body: bytes, timeout: int) -> tuple[int, bytes]:
    request = Request(url, data=body, headers=headers, method="POST")
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.status, response.read()
    except HTTPError as exc:
        # Do not propagate provider response bodies: they can contain sensitive details.
        return exc.code, b""
    except (URLError, TimeoutError, OSError):
        raise SquareSandboxError("SQUARE_SANDBOX_TRANSPORT_FAILED") from None


def create_shop_acceptance_checkout(
    obligation: object,
    config: SquareSandboxConfig,
    *,
    transport: Transport = _http_post,
    timeout_seconds: int = 15,
) -> SquareSandboxCheckout:
    """Create a Sandbox Quick Pay link for a verified shop-fee obligation only."""
    config.validate()
    if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, int) or not 1 <= timeout_seconds <= 30:
        raise SquareSandboxError("SQUARE_SANDBOX_TIMEOUT_INVALID")
    if not isinstance(obligation, LedgerJournalEntry) or obligation.entry_kind != OBLIGATION_KIND:
        raise SquareSandboxError("SHOP_FEE_OBLIGATION_REQUIRED")
    if obligation.fee_type != SHOP_FEE_TYPE:
        raise SquareSandboxError("SHOP_FEE_TYPE_REQUIRED")
    if obligation.amount_cents != SHOP_FEE_CENTS:
        raise SquareSandboxError("SHOP_FEE_AMOUNT_MISMATCH")
    if obligation.currency != "USD_CENTS":
        raise SquareSandboxError("SHOP_FEE_CURRENCY_INVALID")
    entry_id = obligation.entry_id
    acceptance_id = obligation.acceptance_id
    partner_id = obligation.partner_org_id
    tenant_id = obligation.tenant_id
    if not all(isinstance(value, str) and value.strip() for value in (entry_id, acceptance_id, partner_id, tenant_id)):
        raise SquareSandboxError("SHOP_FEE_OBLIGATION_IDENTITY_REQUIRED")
    lines = obligation.lines
    if (not isinstance(lines, tuple) or len(lines) != 2
            or not all(isinstance(line, LedgerPostingLine) for line in lines)):
        raise SquareSandboxError("SHOP_FEE_POSTINGS_INVALID")
    expected_postings = {
        (f"AR:SHOP:{partner_id}", "DEBIT", SHOP_FEE_CENTS),
        ("REV:REPAIR_SHOP_ACCEPTANCE", "CREDIT", SHOP_FEE_CENTS),
    }
    actual_postings = {(line.account_code, line.direction, line.amount_cents) for line in lines}
    if actual_postings != expected_postings:
        raise SquareSandboxError("SHOP_FEE_POSTINGS_INVALID")
    # Entry IDs may repeat across tenants; namespace the provider key by tenant.
    key = "c2c-shop-fee-" + hashlib.sha256(f"{tenant_id}|{entry_id}".encode("utf-8")).hexdigest()
    payload = {
        "idempotency_key": key,
        "quick_pay": {
            "name": "Claim2Car repair-shop acceptance fee",
            "price_money": {"amount": SHOP_FEE_CENTS, "currency": "USD"},
            "location_id": config.location_id,
        },
        "payment_note": "Claim2Car Sandbox shop acceptance fee",
    }
    headers = {
        "Authorization": f"Bearer {config.access_token}",
        "Square-Version": SQUARE_API_VERSION,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    status, response_body = transport(
        SQUARE_SANDBOX_API + "/v2/online-checkout/payment-links",
        headers,
        json.dumps(payload, separators=(",", ":")).encode("utf-8"),
        timeout_seconds,
    )
    if status < 200 or status >= 300:
        raise SquareSandboxError("SQUARE_SANDBOX_CHECKOUT_REQUEST_REJECTED")
    try:
        response = json.loads(response_body)
        link = response["payment_link"]
        link_id = link["id"]
        order_id = link["order_id"]
        checkout_url = link["url"]
    except (ValueError, TypeError, KeyError):
        raise SquareSandboxError("SQUARE_SANDBOX_CHECKOUT_RESPONSE_INVALID") from None
    if not isinstance(checkout_url, str) or not checkout_url:
        raise SquareSandboxError("SQUARE_SANDBOX_CHECKOUT_URL_INVALID")
    parsed_url = urlparse(checkout_url)
    try:
        explicit_port = parsed_url.port
    except ValueError:
        raise SquareSandboxError("SQUARE_SANDBOX_CHECKOUT_URL_INVALID") from None
    if (parsed_url.scheme != "https" or parsed_url.hostname not in ALLOWED_CHECKOUT_HOSTS
            or parsed_url.username or parsed_url.password or parsed_url.fragment or explicit_port is not None):
        raise SquareSandboxError("SQUARE_SANDBOX_CHECKOUT_URL_INVALID")
    if not all(isinstance(value, str) and value for value in (link_id, order_id)):
        raise SquareSandboxError("SQUARE_SANDBOX_CHECKOUT_RESPONSE_INVALID")
    return SquareSandboxCheckout(
        provider_link_id=link_id,
        provider_order_id=order_id,
        checkout_url=checkout_url,
        idempotency_key=key,
        obligation_entry_id=entry_id,
        amount_cents=SHOP_FEE_CENTS,
    )


def verify_square_webhook_signature(
    raw_body: bytes,
    signature: str,
    *,
    signature_key: str,
    notification_url: str,
) -> bool:
    """Verify Square's HMAC-SHA256 over exact configured URL + raw body."""
    if (not isinstance(raw_body, bytes) or not isinstance(signature, str) or not signature
            or not isinstance(signature_key, str) or not signature_key
            or not isinstance(notification_url, str) or not notification_url):
        return False
    expected = base64.b64encode(
        hmac.new(
            signature_key.encode("utf-8"),
            notification_url.encode("utf-8") + raw_body,
            hashlib.sha256,
        ).digest()
    ).decode("ascii")
    return hmac.compare_digest(expected, signature)


def verify_and_parse_square_payment_event(
    raw_body: bytes,
    signature: str,
    config: SquareSandboxConfig,
    *,
    square_environment: str,
) -> SquareSandboxPaymentEvent:
    """Authenticate first; return a minimal payment event, not PII or raw payload."""
    config.validate()
    if square_environment != "Sandbox":
        raise SquareSandboxError("SQUARE_SANDBOX_WEBHOOK_ENVIRONMENT_INVALID")
    if not verify_square_webhook_signature(
        raw_body,
        signature,
        signature_key=config.webhook_signature_key,
        notification_url=config.webhook_notification_url,
    ):
        raise SquareSandboxError("SQUARE_SANDBOX_WEBHOOK_SIGNATURE_INVALID")
    try:
        envelope = json.loads(raw_body)
        event_id = envelope["event_id"]
        event_type = envelope["type"]
        payment = envelope["data"]["object"]["payment"]
        payment_id = payment["id"]
        order_id = payment["order_id"]
        status = payment["status"]
        money = payment["amount_money"]
        amount = money["amount"]
        currency = money["currency"]
    except (ValueError, TypeError, KeyError):
        raise SquareSandboxError("SQUARE_SANDBOX_PAYMENT_EVENT_INVALID") from None
    if event_type not in {"payment.created", "payment.updated"}:
        raise SquareSandboxError("SQUARE_SANDBOX_PAYMENT_EVENT_UNSUPPORTED")
    if not all(isinstance(value, str) and value for value in (event_id, payment_id, order_id, status, currency)):
        raise SquareSandboxError("SQUARE_SANDBOX_PAYMENT_EVENT_INVALID")
    if isinstance(amount, bool) or not isinstance(amount, int) or amount <= 0:
        raise SquareSandboxError("SQUARE_SANDBOX_PAYMENT_EVENT_INVALID")
    if amount != SHOP_FEE_CENTS:
        raise SquareSandboxError("SQUARE_SANDBOX_PAYMENT_AMOUNT_MISMATCH")
    if currency != "USD":
        raise SquareSandboxError("SQUARE_SANDBOX_PAYMENT_CURRENCY_UNSUPPORTED")
    if status not in {"APPROVED", "COMPLETED", "CANCELED", "FAILED"}:
        raise SquareSandboxError("SQUARE_SANDBOX_PAYMENT_STATUS_UNSUPPORTED")
    return SquareSandboxPaymentEvent(
        event_id=event_id,
        event_type=event_type,
        payment_id=payment_id,
        order_id=order_id,
        status=status,
        amount_cents=amount,
        currency=currency,
    )
