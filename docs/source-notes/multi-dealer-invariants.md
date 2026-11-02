# Multi-dealer invariants

Source: Ramsey Ibrahim's 2026-10-11 correction, recorded in `claim2car-faos-v1` `docs/phase-c-multi-dealer-invariants.md` at `b1ea4e3fe7007721971f2e00bf6f7612883348cb`. Post-M1. This note does not authorize routing, a dealer seed, or a live offer.

San Antonio is a multi-brand, multi-dealer target. No rule may hardcode Ancira or any other group as the only destination. Naming a dealer group is not a partnership, a location list, or routing authority.

## Rules

- Organizations, users, memberships, dealer groups, and dealer locations are separate. A `tenant_id` column by itself is not isolation.
- Brands and each location's brand portfolio live in data, not in code.
- Enabled state, service area, capacity, and fee rules are versioned configuration.
- A candidate is eligible only when it is enabled, the brand matches, data-sharing is authorized, the location is in range, and capacity remains. Missing identity or location is unavailable or review. It is never a guessed assignment.
- Capacity is reserved in a transaction. The route stores its inputs, exclusions, policy version, chosen location, and who decided.
- Money is integer minor units plus a currency code. The fee rule and the amount are snapshotted on the obligation. A later price change does not rewrite history.
- Idempotency keys are scoped by tenant and operation, bound to the request digest, return the original result for the same retry, and reject a conflicting reuse.
- Rejected and expired leads keep an attributed closure. They do not re-enter routing by themselves.
- Feature and model provenance can be reserved. That is not a claim that a model is trained or deployed.
- One shot contract drives ingestion, validation, and manifests. That contract is `contracts/shot-list.json`.

Commercial amounts in older drafts are fixtures. The pilot amounts that are actually in force are the ones in the product contract ($175 dealer invoice and $110 operator payout, acceptance only; pass is $0 and is not recycled). This note does not change them.

## Acceptance gates still pending

1. Cross-tenant reads and writes fail under the application database role.
2. More than one dealer group and location can be configured without a code change.
3. A brand mismatch is excluded before ranking.
4. Missing identity or location is an explicit unavailable or review result.
5. Concurrent assignments cannot exceed configured capacity.
6. A fee change preserves historical amounts and rule references.
7. An identical retry returns the original result. A conflicting payload fails.
8. A rejected or expired lead keeps its closure event and cannot automatically re-enter.
9. One shot contract drives ingestion, validation, and manifests.
10. Migration, access, concurrency, and retry behavior are executed against PostgreSQL, with PostGIS only once spatial eligibility is actually in the schema. Mocks do not count.

None of these gates are awarded.
