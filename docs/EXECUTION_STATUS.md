# Claim2Car execution status snapshot / new-thread handoff

**Updated:** 2026-11-21  
**Canonical repository:** `C2C-Connect/claim2car-connect`  
**Observed main commit:** `1c1a010143ce8c9407fc3299e0eeaa5f623e4c08` (verify live at session start)

## Non-negotiable execution rules

1. **Production over planning:** concept finalized. Do not substitute repeated plans, mock data, placeholders, disconnected scaffolds, or documentation-only work for functional implementation.
2. **Sequential execution:** select the next concrete dependency, implement real code and integrations, test, inspect/fix failures, rerun against exact candidate, verify, merge only after required checks, deploy, and exercise a real end-to-end flow.
3. **Proactive autonomy:** founder authorization covers ordinary architecture/implementation choices, refactors, files, dependencies, branches, commits, PRs, CI diagnosis, verified merges, and authorized OCI staging work. Do not pause for boilerplate approvals.
4. **Safety and access boundaries:** protect secrets and personal data; no unapproved costs; sandbox payments; no live dispatch, external distribution, real participant data, or consequential automated authority without required controls and authorization. Ask only for the specific unavailable credential, access, cost authorization, or genuine policy decision; continue other work.
5. **Evidence honesty:** implementation, integration, automated test, accuracy validation, field validation, deployment, and operational acceptance are distinct. Never claim a stage without evidence.

## Latest checkpoint observed

- Main was observed at `1c1a010143ce8c9407fc3299e0eeaa5f623e4c08`, titled “Record standing autonomous execution mandate and thread handoff (#124)”.
- **PR #119** persisted tenant-bound Square Sandbox checkout intents and is merged at `c7befe0aa8366b109818310ae488809cc695e58c`.
- **PR #125** is the current observed fresh-CI-validation candidate for Square Sandbox webhook receipt/payment-state reconciliation (migrations 0025/0026 plus webhook and database logic/tests). Its PR description reports no workflow runs attached to the corrected head. Fetch the live head and workflow checks; do not merge until required checks are green on that exact SHA. PR #120 is superseded/closed unmerged. Treat PR #122 as unverified/not integrated unless live evidence proves otherwise.
- Prior #116–#118 merged changes are listed in the handoff; verify before relying on them.
- OCI guarded apply, remote Terraform backend, and image-publishing workflows are code merged, but **there is no evidence of an actual integrated OCI deployment**. State bucket, configuration/secrets, apply, compute, PostgreSQL/PostGIS, persistent evidence storage, backups/restores, and real deployed journey remain outstanding. Do not use the OCI MySQL DB System as the application authority.

## Next executable task (do not ask the founder to choose)

1. Inspect live `main`, PR #125, exact head, and required workflows.
2. Ensure CI runs on the exact head; fix failures in code/tests and rerun until verified.
3. Merge only after exact-head required checks are green and diff is reviewed.
4. Immediately progress OCI staging prerequisites and guarded deployment: verify configuration, costs and access; create/configure remote state, execute plan/apply through protected workflow, deploy the immutable image, provision PostgreSQL/PostGIS and durable evidence storage, then test health, restart persistence, evidence retrieval/integrity, tenant isolation, backup/restore, and the integrated workflow.
5. If cloud credentials/configuration block deployment, identify the single concrete action needed and continue unblockable product work.

## Start-of-thread checklist

Read this file, `docs/EXECUTION_HANDOFF.md`, `docs/CTO_MASTER_EXECUTION_PLAN.md`, and README. Then inspect the live GitHub main/PR/workflow state. Resume implementation directly; do not recreate or narrate the plan.
