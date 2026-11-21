# Claim2Car execution status snapshot / new-thread handoff

**Updated:** 2026-11-21  
**Canonical repository:** `C2C-Connect/claim2car-connect`  
**Observed main:** `e198b40337e7e3fe310e518d76cd898bd151b89c` (verify live at session start)

## Non-negotiable execution rules

1. **Production over planning:** concept finalized. Do not substitute repeated plans, mock data, placeholders, disconnected scaffolds, or documentation-only work for functional implementation.
2. **Sequential execution:** select the next concrete dependency, implement real code and integrations, test, inspect/fix failures, rerun against exact candidate, verify, merge only after required checks, deploy, and exercise a real end-to-end flow.
3. **Proactive autonomy:** founder authorization covers ordinary architecture/implementation choices, refactors, files, dependencies, branches, commits, PRs, CI diagnosis, verified merges, and authorized OCI staging work. Do not pause for boilerplate approvals.
4. **Safety and access boundaries:** protect secrets and personal data; no unapproved costs; sandbox payments; no live dispatch, external distribution, real participant data, or consequential automated authority without required controls and authorization. Ask only for the specific unavailable credential, access, cost authorization, or genuine policy decision; continue other work.
5. **Evidence honesty:** implementation, integration, automated test, accuracy validation, field validation, deployment, and operational acceptance are distinct. Never claim a stage without evidence.

## Latest checkpoint observed

- **PR #121 merged** at `e198b40337e7e3fe310e518d76cd898bd151b89c`: structured Vehicle Intelligence Lab assessment JSON, SHA-256 integrity digest, rule-based disposition, escalation, missing-evidence handling, and browser download verification.
- **PR #127 active:** Square Sandbox webhook receipt/payment-state reconciliation on clean mainline; exact candidate head `dede7bdd4f803d7ea9fcb71991a47b98d8cf26ab`. Includes migration 0026, API receiver, mapping/reconciliation, diagnostic wiring and integration/unit tests. Migration 0025 is already on main and is not duplicated.
- A prior DB-authority run completed **362 database tests with 0 failures/errors/skips**, but the diagnostics matrix failed because payment fixtures for the second tenant were seeded after the first tenant's matrix had begun. The fixture order was corrected in PR #127. Fresh CI is pending; don't merge without green exact-head required checks and diff review.
- PRs #122 and #125 are closed unmerged as superseded. #127 is the sole active candidate.
- **OCI integrated staging is not deployed.** Terraform, guarded provisioning, image publishing, host preflight, identity-checked volume mounting, runtime bootstrap and deploy scripts exist, but no provisioned compute, app PostgreSQL/PostGIS, persistent evidence storage, backup/restore rehearsal, or integrated deployed journey is evidenced. Required OCI credentials/GitHub environment configuration, private state bucket, reviewed plan, protected apply, host access and deployment remain blockers. The Oracle MySQL DB System is not the app authority.

## Next executable task (do not ask the founder to choose)

1. Finish CI on PR #127 exact head; inspect DB-authority diagnostics and integration results. Fix failures and rerun.
2. Merge only when required checks are green on the exact candidate SHA.
3. Immediately progress OCI guarded staging provisioning and deployment: validate configuration and costs/access; create/verify remote state; plan/apply using protected workflow; provision Postgres/PostGIS and durable evidence storage; publish/deploy immutable image; verify health, restart persistence, evidence retrieval/integrity, tenant isolation, backup/restore, and integrated workflow.
4. If cloud credentials/configuration block deployment, identify the one concrete action required and continue unblockable implementation.

## Start-of-thread checklist

Read this file, `docs/EXECUTION_HANDOFF.md`, `docs/CTO_MASTER_EXECUTION_PLAN.md`, and README. Then inspect live GitHub main, PR #127, and workflow status. Resume implementation directly; do not recreate or narrate the plan.
