# Claim2Car Connect / FAOS - San Antonio pilot

## Governing product premise

Claim2Car is an end-to-end post-accident intelligence and resolution platform. It establishes, documents, explains, and coordinates the truth that can responsibly be established about a collision—from authenticated intake and preserved evidence through vehicle and damage assessment, explainable findings, authorized reporting, driver next steps, and auditable event resolution. The broader objective is to responsibly coordinate the post-accident economy around a trustworthy incident record. Accuracy, provenance, uncertainty disclosure, consent, and accountability are foundational product requirements—not optional enhancements.

The canonical owner-aligned product vision, Post-Accident Truth Standard, end-to-end journey, foundational system responsibilities, accuracy-validation requirements, first vertical slice, and future-agent handoff instructions are in **[Claim2Car Product Premise: Forensic Intelligence, Truth, and Resolution](docs/architecture/PRODUCT_PREMISE_FORENSIC_INTELLIGENCE.md)**. Read it before making product or architecture decisions. It defines the intended product; the acceptance matrix below remains authoritative for what has actually been implemented and verified.


Current implementation and release evidence are tracked in the [Acceptance & Release Gate Matrix](docs/acceptance/ACCEPTANCE_MATRIX.md). It distinguishes tested code from field validation and deployment authorization.

## Current user-facing application (verified 2026-11-22)

- The canonical integrated application shell is `app/web/index.html` and its JavaScript/CSS assets under `app/web/assets/`; it is served at `/` only in integrated runtime mode. The root CTA directs to authenticated workspace sign-in; the controlled prototype is not the product entry point.
- The integrated operator workbench code supports persistent case creation/reopen, consent-gated owner flow, VIN reference, 16-slot capture, browser IndexedDB queue-before-upload/FIFO retry, advisory quality checks, evidence sealing, and a server-derived progress dashboard for consent, vehicle reference, registered originals, quality, and seal. Dashboard progress refreshes after upload and consent withdrawal. Reviewer functionality is also implemented in the same integrated shell.
- Runtime credentials are provisioned out-of-band; no self-service signup exists. Do not create or expose test tokens in repository, chat, or public logs.
- **The application is not deployed or reachable by the founder yet.** The private OCI Run Command deployment mechanism is merged, but protected OCI environments/secrets/variables, secured state bucket, reviewed Terraform apply, private host, PostgreSQL/PostGIS, verified persistent volumes, image publish/deploy, and secure access remain blockers. Code/CI verification does not substitute for deployment.

Current UI entry change: [PR #153](https://github.com/C2C-Connect/claim2car-connect/pull/153) merged at `76d5c6795de283be8967978239f2f5b5e59f700f` (13/13 workflows passed).

## Standing execution mandate — product over planning

- **Production over planning:** the product concept is settled. Do not produce another high-level plan, placeholder, mock, or disconnected scaffold as a substitute for working software. Every increment must materially improve a functional, integrated, deployable product.
- **Sequential execution:** choose the next dependency-respecting implementation task and carry it through real logic, integrations, tests, failure fixes, exact-commit verification, merge when verified, deployment, and real end-to-end checks.
- **Proactive autonomy:** execute within the founder's standing authorization. Make reasonable architecture and implementation decisions, resolve ordinary dependencies, edit files, run CI, and proceed without asking for routine intermediate approvals. Pause only for concrete missing credentials/access, costs not authorized, or genuine legal/privacy/security/safety decisions.
- **No false completion:** distinguish implemented, integrated, automated-tested, accuracy/field-validated, deployed, and operationally accepted. Do not report placeholders, synthetic demonstrations, green CI, or a container smoke test as a deployed product.
- **Resume without re-planning:** new sessions must read the handoff and status snapshot, inspect live GitHub state, and continue the next executable step; do not ask the founder what to do next or repeat the plan.

- **Production over planning:** the product concept is settled. Do not produce another high-level plan, placeholder, mock, or disconnected scaffold as a substitute for working software. Every increment must materially improve a functional, integrated, deployable product.
- **Sequential execution:** choose the next dependency-respecting implementation task and carry it through real logic, integrations, tests, failure fixes, exact-commit verification, merge when verified, deployment, and real end-to-end checks.
- **Proactive autonomy:** execute within the founder's standing authorization. Make reasonable architecture and implementation decisions, resolve ordinary dependencies, edit files, run CI, and proceed without asking for routine intermediate approvals. Pause only for concrete missing credentials/access, costs not authorized, or genuine legal/privacy/security/safety decisions.
- **No false completion:** distinguish implemented, integrated, automated-tested, accuracy/field-validated, deployed, and operationally accepted. Do not report placeholders, synthetic demonstrations, green CI, or a container smoke test as a deployed product.
- **Resume without re-planning:** new sessions must read the handoff and status snapshot, inspect live GitHub state, and continue the next executable step; do not ask the founder what to do next or repeat the plan.

The founder has expressly authorized high-autonomy, end-to-end execution: sequentially implement, integrate, test, commit, merge verified increments, provision/deploy the platform where access permits, and validate the deployed product. The goal is an operational Claim2Car product—not an endless plan, placeholder, mock, scaffold, or demo presented as production.

The durable handoff, current checkpoint, and exact next action are in **[Standing Execution Mandate & Thread Handoff](docs/EXECUTION_HANDOFF.md)** and the dated **[Execution Status Snapshot](docs/EXECUTION_STATUS.md)**. These are the first documents to read when resuming work in a new chat/thread. The status snapshot records verified facts and blockers—not aspirations. This authorization supersedes prior routine approval requirements for engineering sequencing, code changes, CI, verified merges, staging provisioning/deployment, and post-deployment testing. Never treat a deployment as complete without evidence.

## Canonical product line

C2C-Connect/claim2car-connect is the single canonical product repository.
The owner-designated architecture is a FastAPI service, PostgreSQL core, and
React/Capacitor capture shell. References to a separate "Grok-built app" describe
deprecated external prototypes, not another canonical product or deployment.

This release candidate provides the database/event/evidence foundation and its
tests. The integrated FastAPI runtime, capture/reviewer workflows, and React/Capacitor
capture shell are present in the repository. Persistent OCI staging deployment,
physical-device qualification, and field acceptance remain unverified. The
acceptance matrix records the current evidence and release boundaries.

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
validated together, currently through authority migration 0024_audited_capture_exceptions_pause_resume.sql. Migration 0020 introduces the independent Collision Lifecycle Record (CLR), tenant-scoped vehicle and participant relationships, claim links, an append-only lifecycle event stream, and a transactional database outbox. Migration 0021 adds the authorized, idempotent collision-to-claim association path, with event/outbox emission and capture-session discoverability. Migration 0022 adds consent-bound vehicle identity association from an already linked capture session, stores only a keyed VIN digest in the registry, records source lineage, and revokes the registry's active identity source when the owner withdraws capture consent. Migration 0023 adds separately consented NHTSA vPIC profile snapshots with normalized per-attribute provenance and a digest of the VIN-redacted provider response, no raw VIN or raw provider-response retention, and profile revocation on either decoding-consent or capture-consent withdrawal. Migration 0024 adds append-only per-view capture-exception and resolution events plus operator pause/resume events; unresolved exceptions block quality review, paused sessions block capture writes, and exceptions never substitute for required original artifacts. The 0010–0013 increments add the tenant-scoped claim-case register, least-privilege idempotent creation, and owner-bound capture-session association; 0014 adds separately deletable, owner-consented structured incident details under RLS. Existing
ledger checksums, migration locking and transactional application remain in force.
python -m database.authority_migrate is a compatibility alias for the same plan.
The consented vehicle-profile API is part of the integrated evidence service: owners can retrieve and accept the separate `vehicle-decode-disclosure-v1`, operators can request a bounded NHTSA vPIC decode, and collision views expose the latest active profile with per-attribute source metadata. The current browser workbench does not yet expose this optional owner-consent flow; API integration and PostgreSQL persistence are covered by the feature branch's acceptance tests. This profile is descriptive vehicle data only—not a damage assessment, physics input, ownership determination, or roadworthiness finding.
No synthetic connection URL is used as a fallback by the normal migration command.

The comparison suite deliberately initializes the older schema with
FAOS_LEGACY_BASELINE_ALLOWED=1 and --legacy-baseline. This is disposable test
setup only, never the staging or production migration route. The guarded component
harness is a legacy comparison suite; the authority workflow subsequently runs
full-plan migration regressions and upgrades the primary database before its
post-cutover checks. Component counts are not a complete post-cutover regression
claim. Formal DB-01–DB-14 acceptance is recorded separately in the acceptance evidence package; green CI alone never awards gates.

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

## Restricted container verification

The CI-only restricted runtime is provider-neutral. `Dockerfile.restricted-staging`
builds a health-only containment image; `.github/workflows/restricted-container-verification.yml`
verifies the exact revision, disabled business capabilities, non-root execution,
and HTTP safety boundaries. It does not deploy to a cloud provider and is not
the integrated claims application.

## Current product state — integrated frontend, not yet deployed

The canonical integrated application is in `frontend/app/`. Main now includes:

- Authenticated operator/reviewer workspace and persistent case creation/resume.
- 16-view capture contract, server-accepted evidence readiness and sealing.
- AES-GCM encrypted browser IndexedDB recovery queue; FIFO retry and network-return sync.
- Visible accepted-versus-pending capture progress. A view counts as accepted only after server registration.
- Owner consent, VIN, human QA and reviewer routes.

The UI does not fabricate case counts or demo activity. Synthetic fixtures remain test-only.

**There is still no user-accessible deployed application URL.** The runtime has been verified in CI, including ARM64 image build and 1,010 passing full-suite tests. The one-time synthetic staging credential bootstrap now uses atomic restrictive writes, refuses symlinked output, and locks concurrent runs. OCI staging has not yet been provisioned/deployed or field-tested.

## OCI integrated staging — deployment pending

OCI is the selected target in `us-chicago-1`. Existing network foundations are owner-created. Guarded manual Terraform plan/apply and immutable integrated-image publish workflows exist on `main`; they are not evidence that infrastructure was applied or that the app is deployed. The protected environment credentials/state, compute host, PostgreSQL/PostGIS authority DB, durable evidence volume, backup/restore, and private access path remain unverified. The existing OCI MySQL DB System is not compatible with the app authority database.

See [the OCI integrated-staging runbook](docs/deployment/oci-integrated-staging.md) and [release go/no-go](docs/release/PERSISTENT_STAGING_GO_NO_GO.md). This session's GitHub connector cannot dispatch the protected manual workflows or inspect environment secrets. Do not put OCIDs, keys, tokens, or secrets in source.

Only synthetic data is in scope for staging. Live financial and dispatch integrations remain disabled.

Retired prototypes (do not use as canonical): C2C-Connect/C2C and
claim2car-network/claim2car-faos-core. PR #1 remains Draft pending release review.

