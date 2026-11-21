# Claim2Car Standing Execution Mandate & Thread Handoff

**Last updated:** 2026-11-21  
**Canonical repository:** `C2C-Connect/claim2car-connect`  
**Purpose:** preserve the founder's direction, exact operating expectations, and execution checkpoint across new chat threads.

## The goal—non-negotiable

Build and deliver a **working, deployable Claim2Car platform**. The concept and business direction are settled enough to execute. The founder does not want repeated plans, audit loops, mock information, placeholders, scaffolding celebrated as product, or work that never materializes into an integrated system.

The required result is an operational application with real persistence, workflows, evidence handling, integrations in their supported test modes, a deployed environment, and end-to-end validation. Staging success is not production/field acceptance; clearly distinguish those.

## Standing authorization

The founder expressly grants high-autonomy execution. Proceed without routine approval for:

- Technical sequencing and architecture decisions consistent with the product.
- Implementation, refactoring, file creation/deletion, code/API/schema/UX changes.
- Branches, commits, PRs, CI execution, diagnosing and fixing failures.
- Merge of increments **after verification**.
- Provisioning/deploying the approved OCI staging platform using guarded infrastructure and available access.
- Post-deploy testing, integration, and evidence capture.
- Continuing through dependencies in sequence; do not ask the founder to repeat authorization or approve routine choices.

This supersedes prior documentation that required approval for routine engineering, verified merges, or staging deployment.

**Boundaries are operational requirements, not excuses to stall:** protect secrets and user data; don't bypass legal/privacy/security controls; don't spend beyond the authorized budget or incur costs without clear authorization; keep payments sandboxed until live payment controls and required authorization are in place; don't dispatch, share location, distribute real data externally, or grant consequential automated authority until the respective controls are implemented and verified. If a required credential/permission is unavailable, ask for only that concrete missing action and continue independent work.

## Execution standard

For each increment:

1. Inspect the actual current main/branch/PR and state; do not rely on stale handoffs.
2. Pick the next dependency-respecting product slice.
3. Implement actual code/integration, not documentation-only work.
4. Run the relevant tests and workflows.
5. Inspect failures; fix root causes; rerun on the exact candidate commit.
6. Verify changed files, diff, commit, and workflow evidence.
7. Merge only a verified increment; confirm merge SHA and main state.
8. Deploy to the real staging environment when possible.
9. Exercise the real end-to-end journey in deployed environment (including persistence, restart/retrieval, tenant boundaries, evidence integrity, and failure handling where relevant).
10. Record observed evidence, limitations, and the next executable task.

**Definition of real progress:** code integrated and tested, or an actual deploy/test result with traceable evidence. Plans, checklists, mocked flows, synthetic demo runs, image-build smoke tests, and scripts are useful only as supporting work; they are never to be reported as product completion.

## Product intent / architecture

- Claim2Car is the end-to-end post-accident intelligence and resolution platform: authenticated intake, original evidence preservation, vehicle/damage intelligence, explainable supported findings, authorized reporting, next steps, and auditable resolution.
- Canonical repo is this repository. Owner-aligned architecture: FastAPI service, PostgreSQL/PostGIS core, React/Capacitor capture shell. Modular monolith with workers; do not rewrite to MySQL.
- Evidence provenance, accuracy, uncertainty, consent, tenant boundaries, auditability, and accountability are core.
- Capture protocol: new 16-v1 contract while maintaining explicit legacy 12-v1 interpretability; version fixed per session. Implement and validate exact views/order, conditional exceptions, retry/quality, actor/session/VIN/timestamp, resume, package, and reviewer path.
- Separate capture/evidence, consent, QA, partner/dealer engagement, and financial lifecycle state machines with tenant/actor/version/reason/timestamp/idempotency/audit.
- Payment progression: sandbox only until authorized live activation. Current shop fee $275, dealer acquisition fee $375, operator amount $110 (eligibility/trigger ledger rules require the current canonical product/legal record); no owner cash incentive. Avoid contradicting canonical policy.
- DARCI/AI provides explainable, bounded triage, not unsupported facts or consequential decisions.
- Do not claim hashing/signatures/Merkle/blockchain or admissibility beyond exact implementation and evidence.

## Execution priorities (order; update as dependencies close)

1. **Reconcile main and release evidence.** Inspect current branch, main SHA, acceptance matrix, PR/workflows, and deployed state.
2. **Square sandbox payments:** finish the intent persistence and webhook receipt/reconciliation path, correct migrations/tenant isolation/idempotency/event ordering, verify CI on exact commit, integrate only green verified increments. Never treat provider simulation as real payment.
3. **Persistent private staging deployment (OCI, us-chicago-1):** provision through existing Terraform/guarded pipeline, private networking, PostgreSQL/PostGIS, evidence volume/object storage as designed, secrets, image publication with exact digest, host/runtime setup, health check, deploy. Verify cost/Free Tier assumptions before applying.
4. **Deployed product journey:** operator intake → consent → 16-view capture (resume/quality/retry) → upload/persist original evidence → vehicle decode/intelligence → review and supported findings → report/export → partner/shop workflow → sandbox financial state → audit/tenant controls. Verify restart and retrieval, no cross-tenant leakage, offline queue behavior, failure/recovery.
5. **Operationalize:** backup/restore, monitoring/logging without sensitive leakage, deployment/rollback runbook, support/incident/stop conditions, device qualification, pilot rehearsal.
6. **Field/pilot readiness:** only after software and deployment are demonstrated; close legal/partner, consent, data retention, safety, and field-validation requirements.
7. **Broader marketplace/dispatch/payment/analytics:** implement incrementally behind explicit lifecycle and security controls.

## Current verified checkpoint (2026-11-21; freshly reconciled)

- **Main baseline observed:** `1c1a010143ce8c9407fc3299e0eeaa5f623e4c08` — commit titled “Record standing autonomous execution mandate and thread handoff (#124)”. Verify live main before acting; this snapshot is not a substitute for live inspection.
- **PR #119 — tenant-bound Square Sandbox checkout intents:** merged to main at `c7befe0aa8366b109818310ae488809cc695e58c`. This increment adds persisted sandbox checkout-intent registration with eligibility and tenant checks. Do not infer actual Square payments or settlement.
- **PR #125 — Square Sandbox webhook receipt/payment-state reconciliation, fresh CI validation:** open as last observed. It carries migrations 0025/0026, webhook receipt/reconciliation, and related fixes. Its PR description says corrected head has no workflow runs attached yet; exact head/check status must be fetched before merge. PR #120 was closed unmerged as superseded; PR #122 must not be treated as integrated unless live evidence proves it. PR #125 is the active validation candidate to inspect first.
- **Latest merged app workflow increments:** #116 hardened non-root runtime, #117 Sandbox-only Square checkout/webhook verification, #118 direct capture-workbench/Vehicle-Lab entry points, and #119 persisted checkout intents; inspect current main and CI evidence before relying on these summaries.
- **OCI integrated staging:** not deployed. The guarded apply workflow and remote Terraform backend are merged, but no state bucket, apply, compute, PostgreSQL/PostGIS authority DB, persistent evidence storage, or integrated staging deployment is evidenced. Required OCI/GitHub configuration and access remain the practical blockers. Existing Oracle MySQL Always Free DB is not the app authority.
- **Next execution step:** inspect live main, PR #125 exact head and all checks; run or enable CI for that exact head if possible; fix failures; merge only when all required checks pass. Then proceed immediately to OCI state bucket/configuration and guarded plan/apply/deployment, verifying costs and access first. Keep independent implementation moving if credentials/configuration block cloud work.
- **Status discipline:** this snapshot is dated, and facts may age. Always verify live repository, PR, workflow, and cloud state before claiming current status.

## Thread-resume instructions

When a new thread begins, read this file and `docs/CTO_MASTER_EXECUTION_PLAN.md`, then inspect GitHub's current main/PR/workflow state. Start at the next concrete execution task above. **Do not ask “what should we do next?” and do not recreate this plan.** Continue implementing, running, fixing, merging, deploying, and verifying.

## Reporting format

Keep it compact and factual:

- **Completed:** concrete code/merge/deploy outcome.
- **Evidence:** exact SHA, PR, workflow/check results, deployed URL/environment, test journey evidence.
- **Next:** one next executable dependency.
- **Blocker / action needed:** only if access/credentials/approval is truly needed; specify exactly.

No victory claims without evidence. No status-only tasks.
