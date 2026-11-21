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

## Next acceptance increment

1. Implement deduplicated webhook receipt persistence and reconciliation.
2. Add refund/void sandbox workflow and ledger reversal integration.
3. Exercise the real Square Sandbox using authorized test credentials; retain redacted request/response and event evidence.
4. Keep live Square credentials, payment collection, and settlement disabled pending separate release authorization.

