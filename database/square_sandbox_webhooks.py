"""Database boundary for verified Square Sandbox webhook receipts."""
from __future__ import annotations

from hashlib import sha256
from datetime import datetime


class SquareWebhookReceiptError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def reconcile_verified_event(conn, event, *, event_created_at: datetime, raw_body: bytes) -> str:
    """Persist and reconcile a signature-verified event; never post ledger entries."""
    if not isinstance(raw_body, bytes) or not raw_body:
        raise SquareWebhookReceiptError("SQUARE_WEBHOOK_BODY_REQUIRED")
    if not isinstance(event_created_at, datetime):
        raise SquareWebhookReceiptError("SQUARE_WEBHOOK_TIMESTAMP_INVALID")
    if event_created_at.tzinfo is None or event_created_at.utcoffset() is None:
        raise SquareWebhookReceiptError("SQUARE_WEBHOOK_TIMESTAMP_INVALID")
    digest = sha256(raw_body).hexdigest()
    try:
        result = conn.execute(
            "SELECT faos.reconcile_square_sandbox_webhook("
            "%s::text,%s::text,%s::text,%s::text,%s::text,%s::bigint,%s::text,%s::timestamptz,%s::text)",
            (event.event_id,event.event_type,event.payment_id,event.order_id,event.status,
             event.amount_cents,event.currency,event_created_at.isoformat(),digest),
        ).fetchone()
    except Exception as exc:
        # Return only a stable error code, never SQL details or connection data.
        primary = getattr(getattr(exc, "diag", None), "message_primary", None)
        if primary == "SQUARE_WEBHOOK_EVENT_ID_CONFLICT":
            raise SquareWebhookReceiptError(primary) from None
        raise SquareWebhookReceiptError("SQUARE_WEBHOOK_RECONCILIATION_FAILED") from None
    if not result or result[0] not in {"RECONCILED","DUPLICATE","UNMATCHED_ORDER","AMOUNT_MISMATCH","PAYMENT_ID_CONFLICT","STALE_EVENT"}:
        raise SquareWebhookReceiptError("SQUARE_WEBHOOK_RECONCILIATION_FAILED")
    return result[0]
