# Claim2Car Connect / FAOS - San Antonio pilot

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

- Operator payout: $110 on dealer acceptance only; dealer invoice: $175 on acceptance.
- Pass: $0, not recycled. Owner cash: none. Shop pitch: forbidden by product policy.
- DARCI: explainable triage; never invent speed or sell the lead.
- Integrity direction: SHA-256 chain, not blockchain. This candidate's manifest
  hashing is not proof that every intended integrity feature is implemented.
- Ancira Auto Group is the historical pilot buyer reference, not a separate codebase.
- Excluded: salvage auctions, Polygon, $80 owner incentive, pay-on-close,
  Grok vision jury, carrier XML.

## Full authority migration command

Supply MIGRATION_DATABASE_URL securely for the explicitly approved target, then run:

```sh
python -m database.migrate
python -m database.migrate  # identical rerun must have no pending migrations
```

The default plan includes both migrations/ and authority_migrations/, ordered and
validated together, currently through 0008_tenant_login_authority.sql. Existing
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

## San Antonio staging target - not provisioned

Proposed logical environment: san-antonio-pilot-staging. This is a planning name,
not a provisioned database, hosting project or verified GitHub Environment.
Hosting provider, account/project, region, existing/new database target and owner
must be resolved before deployment. Use persistent storage, managed secrets,
restricted bound identities and the full default migration route. The tmpfs test
Compose stack and claim2car_test bootstrap are not a persistent staging recipe.
The migration engine is not production-certified; environment-specific provisioning,
restore/recreation rehearsal and an approved deployment operation remain required.
Only synthetic data is in scope for the first staging rehearsal; live financial
and dispatch integrations are not enabled by this release candidate.

Retired prototypes (do not use as canonical): C2C-Connect/C2C and
claim2car-network/claim2car-faos-core. PR #1 remains Draft pending release review.
