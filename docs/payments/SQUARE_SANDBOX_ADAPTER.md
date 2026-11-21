# Square Sandbox adapter — first increment

This adapter is deliberately **Sandbox-only**. It hardcodes Square's Sandbox API host and requires the environment setting to equal `sandbox`; it has no production host selection.

## Implemented

- Creates a Square-hosted Quick Pay link for an existing **shop acceptance obligation** only.
- Requires the exact current shop fee: 27,500 cents (USD), `REPAIR_SHOP_ACCEPTANCE_FEE`, and `OBLIGATION_BOOKED`.
- Dealer acquisition checkout remains unavailable until the qualified-acquisition-close source event is integrated.
- Uses a deterministic idempotency key per tenant + internal ledger entry, preventing cross-tenant collisions.
- Validates returned checkout-link URL hosts and never returns/logs raw provider response bodies.
- Verifies webhook HMAC-SHA256 against the exact configured notification URL + raw request bytes, using constant-time comparison.
- Parses payment events into a minimal record after signature verification. It does not reconcile webhook events, post a ledger entry, refund, void, or settle anything. The next increment persists the checkout intent, not payment settlement.

## Configuration (Sandbox only)

Supply through a secret manager/environment; do not commit credentials:

- `SQUARE_ENVIRONMENT=sandbox`
- `SQUARE_SANDBOX_ACCESS_TOKEN`
- `SQUARE_SANDBOX_LOCATION_ID`
- `SQUARE_SANDBOX_WEBHOOK_SIGNATURE_KEY`
- `SQUARE_SANDBOX_WEBHOOK_URL` (exact HTTPS notification URL configured at Square)

The API host is fixed to `https://connect.squareupsandbox.com`. Sandbox test credentials/resources cannot be used against production. No provider calls are made during unit tests; transport is injected.

## Webhook reconciliation increment (implemented, awaiting CI and real Sandbox verification)\n\n- Exposes `POST /webhooks/square` only in integrated runtime.\n- Verifies HMAC-SHA256 against exact notification URL and raw body before connecting to the database.\n- Stores event identity, minimal payment fields, event time and raw-body SHA-256; raw webhook payload is not stored.\n- Reconciles by provider order against a protected tenant mapping; deduplicates event IDs and payment IDs; checks exact $275 USD.\n- Tenant-readable payment state is separate from the financial ledger. No settlement or ledger posting is implied.\n- Unmatched orders, amount mismatch, payment ID conflict, stale events are recorded and return stable outcomes.\n- **Still not verified:** CI, live Sandbox delivery, deployment, webhook replay from Square dashboard, or ledger settlement/refunds.\n\n## Next acceptance increment

1. Complete CI verification for webhook persistence/reconciliation and the updated 26-migration acceptance inventory.
2. Exercise the real Square Sandbox using authorized test credentials; verify signature delivery, duplicate replay, amount mismatch, payment status transitions, and tenant isolation with redacted evidence.
3. Implement refund/void Sandbox workflows and ledger reversal integration as a separate reviewed financial increment.
4. Keep live Square credentials, payment collection, and settlement disabled pending separate release authorization.

