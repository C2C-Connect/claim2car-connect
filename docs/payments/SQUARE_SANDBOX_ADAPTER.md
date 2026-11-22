# Square Sandbox adapter — first increment

This adapter is deliberately **Sandbox-only**. It hardcodes Square's Sandbox API host and requires the environment setting to equal `sandbox`; it has no production host selection.

## Implemented

- Creates a Square-hosted Quick Pay link for an existing **shop acceptance obligation** only.
- Requires the exact current shop fee: 27,500 cents (USD), `REPAIR_SHOP_ACCEPTANCE_FEE`, and `OBLIGATION_BOOKED`.
- Dealer acquisition checkout remains unavailable until the qualified-acquisition-close source event is integrated.
- Uses a deterministic idempotency key per tenant + internal ledger entry, preventing cross-tenant collisions.
- Validates returned checkout-link URL hosts and never returns/logs raw provider response bodies.
- Verifies webhook HMAC-SHA256 against the exact configured notification URL + raw request bytes, using constant-time comparison.
- Webhook receipts and payment-state reconciliation are integrated with PostgreSQL; settlement/ledger posting, refunds, and voids remain separate and disabled.

## Configuration (Sandbox only)

Supply through a secret manager/environment; do not commit credentials:

- `SQUARE_ENVIRONMENT=sandbox`
- `SQUARE_SANDBOX_ACCESS_TOKEN`
- `SQUARE_SANDBOX_LOCATION_ID`
- `SQUARE_SANDBOX_WEBHOOK_SIGNATURE_KEY`
- `SQUARE_SANDBOX_WEBHOOK_URL` (exact HTTPS notification URL configured at Square)

The API host is fixed to `https://connect.squareupsandbox.com`. Sandbox test credentials/resources cannot be used against production. No provider calls are made during unit tests; transport is injected.

## Webhook reconciliation increment (implemented; CI verified; live Sandbox delivery not verified)

- Exposes `POST /webhooks/square` only in integrated runtime.
- Verifies HMAC-SHA256 against exact notification URL and raw body before connecting to the database.
- Stores event identity, minimal payment fields, event time and raw-body SHA-256; raw webhook payload is not stored.
- Reconciles by provider order against a protected tenant mapping; deduplicates event IDs and payment IDs; checks exact $275 USD.
- Tenant-readable payment state is separate from the financial ledger. No settlement or ledger posting is implied.
- The reconciliation path is a restricted `SECURITY DEFINER` function owned by `faos_writer`; the order mapping and reconciliation tables enforce RLS and do not expose provider lookup keys to ordinary application queries.
- Unmatched orders, amount mismatch, payment ID conflict, stale events are recorded and return stable outcomes.
- **Verified:** mainline CI includes synthetic webhook signature, persistence, replay/conflict, payment-state transition and tenant isolation tests.
- **Not verified:** live Square Sandbox delivery, webhook replay from Square dashboard, refunds/voids, or ledger settlement.
- The private staging runtime has no public ingress; Square cannot directly deliver a webhook to it. Live provider delivery requires a separately reviewed HTTPS relay/tunnel and secure exposure design.
## Next acceptance increment

1. Verify live Sandbox webhook delivery only after an approved relay/tunnel path exists; keep direct public ingress disabled.
2. Exercise the real Square Sandbox using authorized test credentials; verify signature delivery, duplicate replay, amount mismatch, payment status transitions, and tenant isolation with redacted evidence.
3. Implement refund/void Sandbox workflows and ledger reversal integration as a separate reviewed financial increment.
4. Keep live Square credentials, payment collection, and settlement disabled pending separate release authorization.

