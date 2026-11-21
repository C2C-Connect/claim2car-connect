# Claim2Car execution status snapshot / new-thread handoff

**Updated:** 2026-11-21
**Canonical repo:** `C2C-Connect/claim2car-connect`

## Current verified checkpoint (2026-11-21; post-merge)

- **Main:** `ee7e7c4680f7c3cfbf9fa1eb86bec463e8384fc0` — PR #127 merged after all 13 required workflows passed on exact candidate `dede7bdd4f803d7ea9fcb71991a47b98d8cf26ab`.
- **PR #121:** merged structured Vehicle Intelligence Lab assessment JSON, SHA-256 digest, rule-based disposition, escalation, missing-evidence handling and download verification.
- **PR #127:** merged Square Sandbox webhook receipt/payment-state reconciliation (migration 0026). It includes HMAC validation, event dedupe, tenant-bound provider order mapping, payment-state reconciliation, amount mismatch/conflict/stale/unmatched outcomes, webhook receiver, diagnostics and PostgreSQL integration tests. Migration 0025 was already main.
- **Verification:** 13/13 workflows green. Full suite: **1,185 tests, 0 failures, 0 errors, 0 skips**. DB-01 through DB-14: **14/14 pass/awarded**, 26 migrations verified, synthetic diagnostics accepted, 17 tenant-scoped tables and 34 matrix entries pass. This is synthetic CI acceptance, not field validation or production certification.
- **Earlier defects fixed during this increment:** payment fixtures seeded for both tenants before isolation matrix; DB-14 migration inventory count updated from stale 24 to 26. Both fixes are covered by successful exact-head CI.
- PRs #122 and #125 are closed unmerged as superseded.
- **OCI integrated staging remains NOT deployed.** Terraform/guarded apply, image publishing, volume identity/mount, bootstrap and runtime deploy code exist, but no provisioned staging compute, app Postgres/PostGIS, durable evidence volume, backup/restore rehearsal, or integrated deployed journey is evidenced. Remaining practical prerequisites: OCI access/credentials, remote-state bucket, reviewed Terraform plan, protected apply, private host access, deployment and real acceptance. Oracle MySQL is not the app authority. Square Sandbox provider delivery itself has not been verified; live payments remain disabled.

## Next executable task (no founder choice required)

1. Inspect live OCI infrastructure state and GitHub environment configuration for authorized credentials/state/access; do not print or expose secrets.
2. Run the guarded Terraform plan, resolve drift/configuration, and execute apply only through the protected staging workflow after confirming costs and permissions are within authorization.
3. Provision/verify Postgres/PostGIS and durable evidence storage, bootstrap tenant authority, deploy the immutable image, and test health, restart persistence, capture/evidence retrieval/integrity, tenant isolation, backup/restore and the integrated journey.
4. If credentials or access are missing, ask only for the exact prerequisite and keep implementing/testable deployment tooling.

## Start-of-thread checklist

Read this file, `docs/EXECUTION_HANDOFF.md`, `docs/CTO_MASTER_EXECUTION_PLAN.md`, and README; then inspect live main, OCI credentials/configuration, and current deployment workflow. Resume the staging implementation directly—do not re-plan.
