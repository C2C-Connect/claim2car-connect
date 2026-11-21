# Claim2Car execution status snapshot / new-thread handoff

## Verified checkpoint — PR #134 merged (2026-11-21)

- PR #134, **Require source revision integrity for staging acceptance**, merged to main. Merge commit: `8a07d922ef9c091696bd1fc664e9eb377001cbbd`; tested head: `70d88f3ab2276ac1a388fc1be7799df267b03aa5`.
- The OCI synthetic capture acceptance harness now requires a full lowercase 40-character deployed revision, exact match to the local checkout HEAD, and a clean checkout (tracked and untracked files) before creating synthetic acceptance records. Tests cover malformed revision, mismatch, and dirty checkout.
- Exact tested head CI: **12/12 workflows successful; 0 failures** (Full test suite, Browser IndexedDB queue, Legacy database, DB authority cutover, FastAPI, frontend VIN/decoder/transport, offline guided capture, offline VIN controller, controlled demo, controlled PostgreSQL intake, restricted intake container, restricted container verification).
- This protects acceptance evidence against source/image revision misattribution; it does **not** constitute a staging deployment or field acceptance.

**Main after merge:** `8a07d922ef9c091696bd1fc664e9eb377001cbbd`.

**Next execution priority remains real OCI staging:** credentials/protected environment/state-bucket access must be available to execute the guarded state bootstrap, plan, and apply. No OCI integrated deployment has been verified. Do not claim staging readiness; continue independent implementation/tooling while this access gap remains.


**Updated:** 2026-11-21
**Canonical repo:** `C2C-Connect/claim2car-connect`

## Previous verified checkpoint (post-PR #132 merge; superseded by PR #134 checkpoint above)

- **Main:** `bf0649b6c65ec6d1bdb0d6dbcde8843abdad4122` — PR #132 merged: optional Square Sandbox runtime configuration now passes through OCI bootstrap/runtime deploy. Bootstrap writes five optional Square settings as empty by default; deployment injects them into the integrated container. Tests cover defaults, secret-file permissions, and pass-through. No credentials were committed.
- **PR #127:** Square Sandbox webhook receipt/payment-state reconciliation (migration 0026) merged. HMAC validation, deduplication, tenant-bound order mapping, mismatch/conflict/stale/unmatched outcomes, and synthetic PostgreSQL tests are implemented.
- **PR #121:** structured Vehicle Intelligence Lab assessment JSON, digest, rule-based disposition, escalation, missing-evidence handling and report download verification merged.
- **PR #132 verification:** exact head `ccade1681ce122750160c8a5169fe2b86d821190`; **12/12 distinct workflows successful**. Full suite, DB authority cutover, legacy DB, FastAPI and frontend VIN/decoder/transport checks are green on that candidate. Merge commit is above.
- **PR #127 verification (separate earlier increment):** 13/13 workflows green; 1,185 tests, 0 failures/errors/skips; DB-01–DB-14 14/14; 26 migrations; 17 tenant-scoped tables and 34 tenant-matrix entries. Synthetic CI acceptance, not field validation or production certification.
- **OCI staging remains NOT deployed.** Terraform state bucket, plan/apply, infrastructure, host, Postgres/PostGIS, persistent evidence storage, backup/restore and integrated journey have not been executed/verified. Cloud credentials and protected GitHub environments are not inspectable or dispatchable from this session. The private staging host cannot receive Square webhooks from Square directly; no relay has been reviewed or deployed. Live payments remain disabled.

## Next executable task (no founder choice required)

1. Inspect live OCI infrastructure state and GitHub environment configuration for authorized credentials/state/access; do not print or expose secrets.
2. Run the guarded Terraform plan, resolve drift/configuration, and execute apply only through the protected staging workflow after confirming costs and permissions are within authorization.
3. Provision/verify Postgres/PostGIS and durable evidence storage, bootstrap tenant authority, deploy the immutable image, and test health, restart persistence, capture/evidence retrieval/integrity, tenant isolation, backup/restore and the integrated journey.
4. If credentials or access are missing, ask only for the exact prerequisite and keep implementing/testable deployment tooling.

## Start-of-thread checklist

Read this file, `docs/EXECUTION_HANDOFF.md`, `docs/CTO_MASTER_EXECUTION_PLAN.md`, and README; then inspect live main, OCI credentials/configuration, and current deployment workflow. Resume the staging implementation directly—do not re-plan.
