# Claim2Car Standing Execution Mandate & Thread Handoff

## Verified checkpoint — PR #138 merged (2026-11-21)

- PR #138, **Verify staging deployment rollback health and exact revision**, merged to main. Merge commit: `05ddb8349785c6d91ea2fb26457f3d7488b7b72c`; tested head: `66b5ca0d60777127a02f697432ac011ea6daf5f4`.
- Runtime deploy helper now extracts revision from the pinned OCI image ref and compares it to the exact JSON `revision` value from `/health/build`. It handles container launch failures and readiness failures through the rollback branch; a prior image is considered restored only if its readiness and exact revision both pass. Failed rollback cleans up the failed container. The last-image ref is recorded only after the new app passes readiness and restart-service enablement.
- Deployment script tests now assert shell syntax, exact revision matching, rollback startup/readiness checks, failure cleanup, and that healthy image recording happens only after checks.
- Exact tested head: **16 checks successful, 0 failures; 2 evidence-publication checks skipped**. Full suite: **979 passed, 31 warnings, 208 subtests passed**. Authority cutover, browser IndexedDB, controlled demo, intake DB, restricted container, FastAPI, VIN, smoke and code analysis all passed.
- Deployment rollback does not automatically reverse database migrations; failure output now states that limitation. This is staging deployment hardening, not a live staging deployment.

**Main after merge:** `05ddb8349785c6d91ea2fb26457f3d7488b7b72c`.

**Next milestone remains OCI deployment:** protected environment setup, remote-state bootstrap, reviewed Terraform plan, guarded apply, actual private runtime deployment, and live acceptance. None of these are yet verified as deployed.


## Verified checkpoint — PR #136 merged (2026-11-21)

- PR #136, **Fail early when OCI protected apply environment is incomplete**, merged to main. Merge commit: `063d1ec61f36b11e2abeecb9791185ebf1a53f9d`; tested head: `49c1f5d5908c4f132d748b5fbe78a69b45bbabad`.
- OCI guarded apply now validates required OCI credentials, compartment/VCN/private subnet/image OCIDs, and remote state bucket/namespace before CLI configuration and Terraform initialization. Missing inputs are named without exposing values.
- The staging runbook now explicitly documents that GitHub environment secrets/variables do not transfer from `oci-staging` to `oci-staging-apply`; configure each environment separately.
- Exact tested head CI: **13/13 workflows successful; 0 failures**, including OCI infrastructure validation and Full test suite.
- This is workflow hardening, not an applied OCI deployment.

**Main after merge:** `063d1ec61f36b11e2abeecb9791185ebf1a53f9d`.

**Next execution milestone:** execute the protected OCI state bootstrap, inspect the plan, and provision private staging. The OCI environment and credentials remain external configuration; deployment has not been verified. Avoid posting any secrets in chat.


## Verified checkpoint — PR #134 merged (2026-11-21)

- PR #134, **Require source revision integrity for staging acceptance**, merged to main. Merge commit: `8a07d922ef9c091696bd1fc664e9eb377001cbbd`; tested head: `70d88f3ab2276ac1a388fc1be7799df267b03aa5`.
- The OCI synthetic capture acceptance harness now requires a full lowercase 40-character deployed revision, exact match to the local checkout HEAD, and a clean checkout (tracked and untracked files) before creating synthetic acceptance records. Tests cover malformed revision, mismatch, and dirty checkout.
- Exact tested head CI: **12/12 workflows successful; 0 failures** (Full test suite, Browser IndexedDB queue, Legacy database, DB authority cutover, FastAPI, frontend VIN/decoder/transport, offline guided capture, offline VIN controller, controlled demo, controlled PostgreSQL intake, restricted intake container, restricted container verification).
- This protects acceptance evidence against source/image revision misattribution; it does **not** constitute a staging deployment or field acceptance.

**Main after merge:** `8a07d922ef9c091696bd1fc664e9eb377001cbbd`.

**Next execution priority remains real OCI staging:** credentials/protected environment/state-bucket access must be available to execute the guarded state bootstrap, plan, and apply. No OCI integrated deployment has been verified. Do not claim staging readiness; continue independent implementation/tooling while this access gap remains.


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

## Thread-resume instructions

When a new thread begins, read this file and `docs/CTO_MASTER_EXECUTION_PLAN.md`, then inspect GitHub's current main/PR/workflow state. Start at the next concrete execution task above. **Do not ask “what should we do next?” and do not recreate this plan.** Continue implementing, running, fixing, merging, deploying, and verifying.

## Reporting format

Keep it compact and factual:

- **Completed:** concrete code/merge/deploy outcome.
- **Evidence:** exact SHA, PR, workflow/check results, deployed URL/environment, test journey evidence.
- **Next:** one next executable dependency.
- **Blocker / action needed:** only if access/credentials/approval is truly needed; specify exactly.

No victory claims without evidence. No status-only tasks.
