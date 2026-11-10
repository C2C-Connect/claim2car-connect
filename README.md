# Claim2Car Connect / FAOS - San Antonio pilot

Current implementation and release evidence are tracked in the [Acceptance & Release Gate Matrix](docs/acceptance/ACCEPTANCE_MATRIX.md). It distinguishes tested code from field validation and deployment authorization.

## Canonical product line

C2C-Connect/claim2car-connect is the single canonical product repository.
The owner-designated architecture is a FastAPI service, PostgreSQL core, and
React/Capacitor capture shell. References to a separate "Grok-built app" describe
deprecated external prototypes, not another canonical product or deployment.

This release candidate provides the database/event/evidence foundation and its
tests. It does not establish that the FastAPI service or React/Capacitor shell
has been fully implemented, integrated or deployed. PR #1 tracks those coverage
boundaries and the foundation release acceptance criteria.

San Antonio pilot direction includes a multi-dealer network with brand-appropriate
routing (Ford to Ford, Toyota to Toyota). Tenant authority is a security boundary;
it does not implement dealer matching or prove brand-routing correctness.

## Product constraints retained from the original pilot brief

- Operator payout: $110 amount carried forward; eligibility, trigger, and ledger
  treatment remain an open decision (plan v1.3, D-04). Shop acceptance of the vehicle
  authorizes tow dispatch/routing to that shop — the tow driver is then routed to
  take and drop off the vehicle there.
- Dealer acquisition fee: flat $375, due upon close of the qualified acquisition
  (plan v1.3, D-01; supersedes the prior $375–$425 range and the earlier $175 figure).
  Repair-shop fee: flat $275, due upon the shop's recorded acceptance of the vehicle.
- Pass: $0, not recycled. Owner cash: none (permanently excluded per legal counsel).
  Shop pitch: forbidden by product policy.
- DARCI: explainable triage; never invent speed or sell the lead.
- Integrity direction: SHA-256 chain, not blockchain. This candidate's manifest
  hashing is not proof that every intended integrity feature is implemented.
- Ancira Auto Group is the historical pilot buyer reference, not a separate codebase.
- Excluded: salvage auctions, Polygon, owner cash incentive, pay-on-close,
  Grok vision jury, carrier XML.
- On workflow completion the system distributes the dealer dossier, shop repair
  packet, owner PDF, and carrier 7-page document to the relevant parties; on
  acceptance by the receiving party, the system provides step-by-step guided
  navigation (Google Maps-class) to the destination, and the tow driver is
  routed to the accepting shop for vehicle delivery. See
  docs/acceptance/product-contract.md §7. Live sends remain disabled pending
  attorney review (docs/LEGAL_REVIEW.md).
- Slice 7 lands candidate mechanics for the §7 flow: acceptance-gated tow dispatch
  routing (in-memory reference engine + pgRouting parity on a synthetic network
  only), navigation handoff deep links (provider-selectable), and a CIECA-aligned
  carrier message model (`carrier-message-v1`, docs/carrier-integration.md). The
  "carrier XML" exclusion refers to the legacy enterprise-XML approach; the new
  model is CIECA-aligned in category structure, not a compliance claim.

## Full authority migration command

Supply MIGRATION_DATABASE_URL securely for the explicitly approved target, then run:

```sh
python -m database.migrate
python -m database.migrate  # identical rerun must have no pending migrations
```

The default plan includes both migrations/ and authority_migrations/, ordered and
validated together, currently through 0011_claim_case_idempotency_conflicts.sql. The 0010/0011 increments add the tenant-scoped claim-case register and controlled idempotency conflicts. Existing
ledger checksums, migration locking and transactional application remain in force.
python -m database.authority_migrate is a compatibility alias for the same plan.
No synthetic connection URL is used as a fallback by the normal migration command.

The comparison suite deliberately initializes the older schema with
FAOS_LEGACY_BASELINE_ALLOWED=1 and --legacy-baseline. This is disposable test
setup only, never the staging or production migration route. The guarded component
harness is a legacy comparison suite; the authority workflow subsequently runs
full-plan migration regressions and upgrades the primary database before its
post-cutover checks. Component counts are not a complete post-cutover regression
claim. No full 14-gate certification follows from green CI alone.

## Automated verification

Both verification workflows cover all PR base branches, including draft PRs,
main, acceptance, acceptance/**, database-acceptance-run/**, release/**,
release-candidate/** and rc/** branch pushes, rc-* and v*-rc* tag pushes,
merge-group events and manual dispatch. PRs have no path filters.
PR verification uses contents:read and does not persist checkout credentials.
Write-enabled structured evidence publication runs in a separate job only for
branch pushes/manual dispatch, never PR or merge-group events. Release-candidate
tag verification retains artifact evidence without publishing an evidence branch.
Required-check/ruleset enforcement and event-specific execution still need review;
workflow trigger configuration alone does not prevent all unverified merges.

## Railway restricted staging rehearsal

Railway project `463d410b-09a3-4117-a3b5-05e6646e7807` is the supplied hosting
target. [The staging deployment guide](docs/railway-staging.md) describes a
dedicated restricted runtime, exact-revision HTTP checks, and the repository
settings needed to enable deployment. Deployment is disabled by default until
the environment, service, and token are verified. The runtime exposes only
scoped health checks and disabled dispatch construction, not the integrated
claims application. The existing intake Dockerfile is unchanged.

## San Antonio database staging target - not provisioned

Proposed logical environment: san-antonio-pilot-staging. This is a planning name,
not a provisioned database, hosting project or verified GitHub Environment.
The database provider, region, existing/new database target and owner must be
resolved before database deployment. Use persistent storage, managed secrets,
restricted bound identities and the full default migration route. The tmpfs test
Compose stack and claim2car_test bootstrap are not a persistent staging recipe.
The migration engine is not production-certified; environment-specific provisioning,
restore/recreation rehearsal and an approved deployment operation remain required.
Only synthetic data is in scope for the first staging rehearsal; live financial
and dispatch integrations are not enabled by this release candidate.

Retired prototypes (do not use as canonical): C2C-Connect/C2C and
claim2car-network/claim2car-faos-core. PR #1 remains Draft pending release review.
