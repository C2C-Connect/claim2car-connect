## Verified checkpoint — PR #184 merged (2026-11-24)

PR #184 merged to main as `55f69790df123a4602196c3c474e143808c4b87e`; exact tested PR head `95692eaf30f76ca9ab8b7c0cf71c4bcf9fac5d68`. All 13 PR workflows passed. Full suite: **1,064 passed, 7 skipped, 31 warnings, 218 subtests**. Post-cutover authority suite: **407/407 counted tests passed**, DB-01–DB-14 **14/14 PASS**, **340 tenant-isolation assertions**. This establishes database authority acceptance for manifest chain-tip/context binding; it is not field validation or forensic accuracy qualification.

**Active increment — PR #185:** branch `cto/m1-runtime-manifest-registration`, current head `18b617facf9a3772a4d6d568acac315b0327be6f`. Migration 0030 adds a narrow application path to register the verified root in the same tenant transaction as live capture sealing. Review queue/details/artifact retrieval/review decisions verify the root before use. Exact 12-v1, 16-v1 and 16-v2 slot sets are enforced by the registration function. Initial CI exposed an ownership-transfer privilege issue and stale 29-migration test fixtures; the migration now grants schema CREATE only during the function-owner transfer and revokes it immediately, and the fixtures/gate counts are updated. Re-run of the corrected head is pending. Do not merge until all 13 workflows and the authority acceptance pass.

**M1 status:** database chain/context binding is merged; runtime seal registration is the remaining M1 integration task in PR #185. After it passes, proceed to M2 original-artifact provenance and then the observation/measurement/report vertical slice. No deployment, external notarization, trusted timestamp, participant evidence, field qualification, payment or dispatch is claimed.


# Current mission focus — forensic substantiation (2026-11-23)

## Latest verified checkpoint — PR #182 merged (2026-11-23)

PR #182 merged to main as `f0c6fbfc7d0278e77964a45004e0e42ede7a8146`; exact tested head `668785ea465b807932e63fdb6a555ed419099b6b`, **13/13 workflows passed**. Full suite: **1,054 passed, 31 warnings, 219 subtests**. Isolated synthetic PostgreSQL acceptance: **390/390 counted tests**, DB-01–DB-14 **14/14 PASS**, diagnostics successful and database overall ACCEPTED. This is not forensic M1 acceptance or field qualification.

Migration 0028 persists SHA-256 event hashes and transactionally backfills. PR #182 adds server-owned persisted-chain readback from PostgreSQL; invalid authority-schema history fails closed in `load_journal` and locked consumers; legacy schemas report `LEGACY_UNHASHED`; partial hash schema fails closed. Tamper, tenant, legacy and locked-consumer tests passed.

**M1 remains incomplete:** manifest-root chain-tip/sequence/hash-version/context binding, registered original/artifact binding, independent verifier agreement, restart/restore/concurrency/fork and external checkpoint. No deployment, field qualification, participant evidence, payment or dispatch.

**Next code target:** migration 0029 for seal/root chain-tip and context binding; recompute/validate the persisted chain at registration; make root/readback/completion/receipt consumers verify the binding. Then artifact provenance and independent/recovery/adversarial tests.

## Historical checkpoint before PR #180 (superseded)

This checkpoint described the initial PR #176 Python-only slice before merged PR #180. It is historical and superseded by the latest checkpoint above. PR #176 is closed; continue from main.

**Chronology warning:** the dated checkpoints below are retained as historical records. Their old “next task/next milestone” text is not actionable if it conflicts with the current forensic M1 checkpoint above. The active next task is M1 server-owned readback and chain-tip/context binding from current main; see docs/THREAD_HANDOFF_2026-11-23.md. OCI staging and other roadmap work are deferred unless a concrete blocker requires them.


**Founder directive:** put undivided engineering focus on substantiating what Claim2Car claims to know. Evidence integrity is the foundation, but forensic quality requires provenance, identity, capture geometry, calibrated measurements, damage observations, source-backed parts/repair analysis, uncertainty, reproducible reasoning, and defensible reports. No product breadth drift while this vertical slice is incomplete.

**Program/acceptance gates:** `docs/forensics/FORENSIC_SUBSTANTIATION_PROGRAM.md` is the current mission and method contract. Read it first on resume. The initial vertical slice is one controlled vehicle/component/damage region/validated measurement/evidence-linked finding/reproducible report.

**Next code target (M1):** implement manifest-root chain-tip/context binding in migration 0029, verify root binding in registration and readback/completion/receipt consumers, then registered-original/artifact binding and independent/recovery/adversarial verification. Inspect existing migrations, PostgreSQL authority, event/seal/manifest, integrity API, verifier, and callers; reuse existing components rather than create a competing ledger. Fail closed on incomplete/altered/orphaned/reordered/forked provenance. Tenant isolation, restart recovery, idempotency, concurrency and tamper tests. Keep forensic integrity separate from dispatch/payment authorization. Establish contract and tests, then implement a narrow verified PR.

**Focus sequence:** M0 claim/observation/measurement/finding contracts as needed → M1 persistent provenance → M2 artifact provenance → M3 VIN/configuration source substantiation → M4 camera calibration/alignment/coordinate frame → M5 damage localization and one calibrated measurement → M6 source-backed parts/OEM technical assessment → M7 report generator → M8 blind validation/qualification. Synthetic data first; controlled non-participant vehicle validation later. No unsupported precision or causation assertions.

**Release boundary:** no real participant evidence, live payment, dispatch, forensic certification, field accuracy claim, or public/accepted staging until specific gates are implemented and validated. CI passing is not field validation.

---

## Verified checkpoint — 2026-11-23 (PR #171 merged)

- **Main branch:** `main` (verify the live head on resume). **Last verified code merge:** PR #171 at `beb72950081201e891a7a3e66f42addd13c9f528`; audit/handoff docs PRs #172 and #173 are merged.
- **PR #171 — Canonical offline evidence queue encryption:** merged by squash. Tested PR head `086cf77d71da42342c3ec1c3dd348085014e15f3`.
- **Exact-head CI:** **13/13 workflow types green**. Full suite: **1,035 passed, 31 warnings, 208 subtests passed**. Offline queue unit tests **11/11** and actual Chromium/IndexedDB verification passed. Database authority, legacy DB, FastAPI, restricted runtime, integrated runtime including OCI ARM64 build, capture, VIN, intake, and controlled-demo checks passed.
- The canonical root workbench now encrypts originals before IndexedDB storage using HKDF-derived AES-GCM keys and authenticated metadata (AAD). Plaintext and prior-format queue records are integrity-checked and migrated before upload; wrong token, digest mismatch, and metadata tampering fail closed. Stable IDs, FIFO retry, and purge behavior are preserved. The sign-in field clears after successful authentication.
- **Limitations remain:** token-derived local recovery requires the same credential; browser eviction/quota, Safari/iPad and physical-device recovery are not field-qualified; no WORM or secure-device guarantee. Do not use real participant evidence.
- **System audit:** 24 initial findings documented. AUD-001/AUD-016 remediation and README claim correction are verified by PR #171. Remaining high priorities are persistent event hash-chain + full sealed provenance (AUD-006/017/018), consent/deletion receipts and server storage encryption (AUD-008/019), synthetic triage defaults and source provenance (AUD-013/009), identity, financial lifecycle, collision/outbox, protocol privacy, and OCI ingress/DB configuration. See the audit report.
- **Release boundary:** no OCI integrated staging deployment, user-accessible URL, field acceptance, real participant data, live payments, or dispatch.
- **Next executable work:** continue the audit-led corrective sequence, starting with the persistent evidence/event provenance contract and fail-closed integrity authorization. Owner-controlled OCI protected environments, state bucket, ingress restrictions, PostgreSQL/PostGIS and credentials remain external staging blockers; do not request secrets in chat.

## Latest verified checkpoint — 2026-11-22 (PR #165 merged)

- **Main HEAD:** `1f18668b2d9f1cc4e19b49e16c1e66c1313fc116` (PR #165 squash merge).
- **PR #165 — FAOS 16-v2 capture contract:** merged. Tested PR head: `766c0bc99e319e830c626c1fa8d7cacdf1822e9d`. All required workflows passed; full suite: **1026 passed, 31 warnings, 208 subtests passed**. This increment adds migration `0027_capture_protocol_16_v2.sql`, a versioned contract/registry, server API support, browser selection/resume, manifest binding, damage-localization exclusion for non-exterior slots, and compatibility tests.
- **Protocol status:** `claims2car-16-v2` is selectable for controlled testing. `claims2car-16-v1` remains the default; legacy `claims2car-12-v1` remains supported. V2's current 16 positions are eight exterior views, four accessible structural corners, two cabin/restraint views, instrument-cluster telemetry, and physical VIN identity. The manual's second telemetry frame remains an explicit alignment gap; do not silently relabel or alter this immutable version. Field qualification is not complete.
- Browser image quality remains advisory only; it never rejects or changes original evidence. Thresholds are not field calibrated.
- **Current implementation target:** M1 server-owned readback verification and manifest chain-tip/context binding from current main, per the handoff. The previous integrity-score/dispatch hardening target is historical; dispatch remains disabled and will be revisited only under the separate authorization gate.

- **Deployment:** OCI staging is still NOT deployed/accepted. Owner-controlled protected-environment/OCI configuration and workflow dispatch remain external blockers; do not request secrets in chat. Continue all code/test work.
- **Thread continuity:** read README, this handoff, status, FAOS manual, and acceptance matrix; inspect live main/PR/check/deployment state; resume the next executable task above without replanning.
## Latest verified state — 2026-11-22 (PR #158, #155, #152 merged)

- **PR #158** hardened the one-time synthetic staging runtime credential bootstrap. Merge commit: `f96732ec9ecea957aa2bb286a8d824db4b8a220c`; tested head: `ce924d5f338cda40e0358ae44a75834c1b1a649f`. Atomic mode-0600 temporary writes, flush/fsync, replace + directory fsync, output-directory symlink rejection, and an exclusive bootstrap lock prevent unsafe concurrent/partial secret generation. Tests bind raw tokens to role/hash/expiry, check no stdout/runtime-config leak, enforce file modes, and reject lock/symlink/re-run cases.
- PR #158 exact-head CI: **16 successful checks, 3 expected evidence-publication skips, 0 failures**. Full suite: **1010 passed, 31 warnings, 208 subtests**. Restricted containment suite: **224 passed, 20 warnings, 87 subtests**. Manual local bootstrap verification also passed.
- **PR #155** operator case progress dashboard merged: `91753175251bb3a13d00dafe7a2692fbb7b88af6`. Dashboard reflects server-derived owner consent, vehicle reference, accepted original evidence count, advisory quality and seal state; refreshes after upload/consent withdrawal.
- PR #155 exact tested head: `3e9cf110a78c684c3b577f2d5c49193702ec7d95`. **17 checks passed, 3 evidence publication checks skipped, 0 failures**; pytest **987 passed, 31 warnings, 208 subtests**; integrated runtime/OCI ARM64 build passed.
- **PR #152** private OCI staging deployment through Instance Agent Run Command merged: `f63788095986b889a8fb83efd4492aa9c437c03f`. It adds exact-instance dynamic group, least-privilege policies, protected manual deployment workflow, Vault-fed OCIR credentials on-host, restricted sudo wrapper, immutable digest verification, source-pinned deployment helper checksum, and command polling. Run Command contains no registry password/token.
- PR #152 exact tested head: `7f179b6f76484c9031be60762d110334fc1f3110`. **18 checks passed, 3 evidence publication checks skipped, 0 failures**; pytest **1009 passed, 31 warnings, 208 subtests**; Terraform validation, restricted runtime, integrated container, and OCI ARM64 build passed.
- **Still not deployed:** no user-accessible URL or verified staging host/database/evidence volume. OCI protected-environment secrets/variables, state bucket bootstrap, reviewed Terraform plan/apply, host storage identity/mount setup, PostgreSQL/PostGIS, OCIR image publish, private deploy, and authenticated persistence/restore validation remain outstanding. Manual workflow dispatch and environment-secret inspection are not available through the current connector; never claim deployment or request secrets in chat.
- Field/device acceptance, real participant data, live payments, and dispatch remain disabled/unverified.

## Standing execution mandate

The concept is finalized. Stop producing high-level plans, placeholders, mock product data, or status-only work. Work directly on functional product increments. Use synthetic fixtures only inside tests/controlled demos and never present them as live cases. Continue with autonomous code changes, branches, commits, PRs, CI diagnosis/fixes, verified merges, and deployment where tools/credentials permit. Batch intermediate commits to avoid workflow spam. Do not bypass gates or claim a deployment/test passed without evidence.

**Deferred staging task (historical; not the current engineering priority):** the OCI setup/apply/deploy sequence remains documented below as a future operational task. No staging is deployed or accepted. Do not divert from M1–M8 forensic substantiation to perform this sequence unless a required dependency or owner-approved priority change makes it necessary.

## Verified checkpoint — PR #153 merged (2026-11-22)

- PR #153, **Make the Claim2Car secure workspace entry actionable**, merged. Merge commit: `76d5c6795de283be8967978239f2f5b5e59f700f`; tested head: `d550f213766f0512bd46e13ca4782c5b9481f494`.
- The root landing page now directs users to the authenticated workspace (not the separate controlled prototype), explains Connect → Capture → Review, and clearly states that access credentials are provisioned out-of-band and self-service signup is not available.
- Exact-head CI: **13/13 workflows passed**, including full test suite, integrated runtime container smoke (non-root + route/security checks + OCI ARM64 image build), database authority, IndexedDB queue, guided capture, VIN, controlled synthetic demo, and intake/container verification.
- This is a product-entry UX increment in the canonical integrated frontend. **It is still not deployed.** No public URL, live OCI staging, owner/operator credentials, field acceptance, or real participant-data use is established by this merge.
- Main after merge: `76d5c6795de283be8967978239f2f5b5e59f700f`.

**Deferred product/deployment blocker:** OCI protected environments, state bucket, private host, PostgreSQL/PostGIS, evidence storage, immutable image publication, secure access and live journey acceptance remain unresolved. These are recorded for the staging phase, but are not the active task while forensic M1–M8 are being executed.

## Verified checkpoint — PR #150 merged (2026-11-21)

- PR #150, **Restrict OCI staging plan workflow to main**, merged. Merge commit: `35f9f3f737b44d2d0d93c40649887782798b1518`; tested head: `82f93313a86a5a93bf80debc4202716ee402dacf`.
- Security fix: the manual Terraform plan workflow now only runs on `main`, has a redundant shell-level branch guard, checks out the immutable triggering SHA, and disables persisted checkout credentials. It remains plan-only; no apply capability added.
- Exact-head CI: **17 successful checks, 3 evidence-publication jobs skipped, 0 failures**. Terraform validation passed. Full pytest: **987 passed, 31 warnings, 208 subtests passed**. Database authority, smoke, restricted container, browser IndexedDB, API health, VIN, guided capture, controlled demo, intake DB, container smoke, lookup, and all analysis checks passed.
- The earlier rollback harness PR #147 remains merged and tested: 986 passed, 31 warnings, 208 subtests; 24 successful checks and 6 publication checks skipped. PR #146 was closed as duplicate.
- Main after merge: `35f9f3f737b44d2d0d93c40649887782798b1518`.

**Actual OCI staging deployment remains unperformed.** The protected environment and OCI credentials are not accessible through the available GitHub connector; workflow dispatch cannot be initiated here. Continue implementation, but do not claim Terraform apply, integrated deployment, or live acceptance.


## Verified checkpoint — PR #147 merged (2026-11-21)

- PR #147, **Exercise OCI staging deployment rollback with a mocked runtime**, merged. Merge commit: `f97367a8d5bd5f6fdb1a6b1fc459b958d2ea7f88`; tested head: `6021ec328d1b42be7a35c0a6e71d7ab6d4e289cf`.
- OCI deployment helper now compares the exact JSON build revision, and rollback reports success only after the previous digest-pinned image passes readiness and revision checks. Container launch failure is also caught and routed through rollback. Database migrations are not automatically reversed; this limitation is stated in failure output.
- Added a command-mocked integration harness that executes the actual deployment shell script across 4 scenarios: successful deployment; health/readiness failure with verified rollback; container launch failure with verified rollback; and unhealthy rollback that fails closed. Root-owned marker reading and test cleanup are exercised with sudo.
- Exact head CI: **24 checks successful, 6 publication checks skipped, 0 failures**. Restricted-container verification passed. Full pytest suite: **986 passed, 31 warnings, 208 subtests passed**.
- Redundant harness PRs were closed; PR #147 is the merged source of truth.

**Main after merge:** `f97367a8d5bd5f6fdb1a6b1fc459b958d2ea7f88`.

**Actual OCI deployment remains unperformed.** Next milestone is protected-environment configuration, state bucket bootstrap, reviewed non-destructive plan, guarded apply, private host/volume setup, integrated image publish/deploy, and live acceptance. No production or field acceptance is claimed.


## Verified checkpoint — PR #138 merged (2026-11-21)

- PR #138, **Verify staging deployment rollback health and exact revision**, merged to main. Merge commit: `05ddb8349785c6d91ea2fb26457f3d7488b7b72c`; tested head: `66b5ca0d60777127a02f697432ac011ea6daf5f4`.
- Runtime deploy helper now extracts revision from the pinned OCI image ref and compares it to the exact JSON `revision` value from `/health/build`. It handles container launch failures and readiness failures through the rollback branch; a prior image is considered restored only if its readiness and exact revision both pass. Failed rollback cleans up the failed container. The last-image ref is recorded only after the new app passes readiness and restart-service enablement.
- Deployment script tests now assert shell syntax, exact revision matching, rollback startup/readiness checks, failure cleanup, and that healthy image recording happens only after checks.
- Exact tested head: **16 checks successful, 0 failures; 2 evidence-publication checks skipped**. Full suite: **979 passed, 31 warnings, 208 subtests passed**. Authority cutover, browser IndexedDB, controlled demo, intake DB, restricted container, FastAPI, VIN, smoke and code analysis all passed.
- Deployment rollback does not automatically reverse database migrations; failure output now states that limitation. This is staging deployment hardening, not a live staging deployment.

**Main after merge:** `05ddb8349785c6d91ea2fb26457f3d7488b7b72c`.

**Historical/deferred milestone — OCI deployment:** the infrastructure setup and private deployment checklist remains valid for later staging work; not the current focus. No deployment is verified.

## Verified checkpoint — PR #136 merged (2026-11-21)

- PR #136, **Fail early when OCI protected apply environment is incomplete**, merged to main. Merge commit: `063d1ec61f36b11e2abeecb9791185ebf1a53f9d`; tested head: `49c1f5d5908c4f132d748b5fbe78a69b45bbabad`.
- OCI guarded apply now validates required OCI credentials, compartment/VCN/private subnet/image OCIDs, and remote state bucket/namespace before CLI configuration and Terraform initialization. Missing inputs are named without exposing values.
- The staging runbook now explicitly documents that GitHub environment secrets/variables do not transfer from `oci-staging` to `oci-staging-apply`; configure each environment separately.
- Exact tested head CI: **13/13 workflows successful; 0 failures**, including OCI infrastructure validation and Full test suite.
- This is workflow hardening, not an applied OCI deployment.

**Main after merge:** `063d1ec61f36b11e2abeecb9791185ebf1a53f9d`.

**Deferred staging milestone:** guarded OCI state bootstrap, reviewed plan/apply, PostgreSQL/PostGIS, durable evidence volume, immutable deployment and operational acceptance remain future work, subject to access and authorization.

## Verified checkpoint — PR #134 merged (2026-11-21)

- PR #134, **Require source revision integrity for staging acceptance**, merged to main. Merge commit: `8a07d922ef9c091696bd1fc664e9eb377001cbbd`; tested head: `70d88f3ab2276ac1a388fc1be7799df267b03aa5`.
- The OCI synthetic capture acceptance harness now requires a full lowercase 40-character deployed revision, exact match to the local checkout HEAD, and a clean checkout (tracked and untracked files) before creating synthetic acceptance records. Tests cover malformed revision, mismatch, and dirty checkout.
- Exact tested head CI: **12/12 workflows successful; 0 failures** (Full test suite, Browser IndexedDB queue, Legacy database, DB authority cutover, FastAPI, frontend VIN/decoder/transport, offline guided capture, offline VIN controller, controlled demo, controlled PostgreSQL intake, restricted intake container, restricted container verification).
- This protects acceptance evidence against source/image revision misattribution; it does **not** constitute a staging deployment or field acceptance.

**Main after merge:** `8a07d922ef9c091696bd1fc664e9eb377001cbbd`.

**Deferred staging priority:** OCI staging remains undeployed; continue the forensic M1–M8 program first.

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

## Current next task — M1 readback and seal binding (after PR #180)

Continue from current main. Implement server-owned readback verification; bind manifest seal/root to verified chain tip, sequence/version and capture context; bind registered original/artifacts; then independent verifier, restart/restore, concurrency and adversarial tests. Keep dispatch/payment disabled. M1 remains incomplete; do not claim acceptance.



## Thread-resume instructions

When a new thread begins, read this file and `docs/CTO_MASTER_EXECUTION_PLAN.md`, then inspect GitHub's current main/PR/workflow state. Start at the next concrete execution task above. **Do not ask “what should we do next?” and do not recreate this plan.** Continue implementing, running, fixing, merging, deploying, and verifying.

## Reporting format

Keep it compact and factual:

- **Completed:** concrete code/merge/deploy outcome.
- **Evidence:** exact SHA, PR, workflow/check results, deployed URL/environment, test journey evidence.
- **Next:** one next executable dependency.
- **Blocker / action needed:** only if access/credentials/approval is truly needed; specify exactly.

No victory claims without evidence. No status-only tasks.


## Governing FAOS core-engine premise (owner directive, 2026-11-22)

The owner supplied and adopted the **FAOS Core Engine Implementation Guide & Subsystem Engineering Manual** as persistent product direction. Read [the manual](architecture/FAOS_CORE_ENGINE_IMPLEMENTATION_GUIDE.md) before architecture or implementation decisions. It covers the sensor edge and managed-device target, VIN/check digit and source-attributed decode, 16-point AR walkaround, quality gates, session-isolated FIFO/offline evidence, first-mile SHA-256/chain/Merkle provenance, durable gateway/persistence, DARCI mechanics, multimodal AI, proposed 55/45 consensus and overrides, integrity scoring, jurisdictional triage, BFPI/dealer and repair-auction economics, ACORD/report dispatch, and sandbox settlement.

**Important acceptance boundary:** owner-provided numerical thresholds, performance claims, model names, legal references, example identifiers, blockchain anchors, and financial formulas are targets/hypotheses unless the acceptance matrix records implementation and validation evidence. Physics/AI cannot autonomously make legally or financially consequential determinations in the unvalidated state. Preserve originals and uncertainty; critical integrity defects stop dispatch. Do not introduce vendor/database complexity without a verified need; PostgreSQL/PostGIS remains the target persistence architecture and existing architecture decisions prevail unless deliberately changed.

**Thread continuation:** when this conversation ends, use README + this handoff + docs/EXECUTION_STATUS.md + FAOS manual + acceptance matrix; inspect live main/PR/check/deployment state; then continue the last unfinished executable increment without another planning cycle or asking the founder to repeat these directives.
\n\n## Canonical full technical specification\n\nThe complete forensic substantiation contract and technical roadmap is in [complete forensic substantiation specification](docs/forensics/COMPLETE_FORENSIC_SUBSTANTIATION_SPEC.md). This supersedes compact summaries for requirement detail.\n