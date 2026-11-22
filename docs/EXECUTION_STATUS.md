# Claim2Car execution status snapshot / new-thread handoff

## Verified product checkpoint — PR #154 and #156 merged (2026-11-22)

- **PR #154** `Persist original capture evidence offline and resume uploads` merged: `c77b81d38947621a9f612f0c3402d585e9630ade`. Tested head: `6a4390750faf7d87213f2eaa9b4876aae22eaded`.
- Integrated capture now queues original bytes in IndexedDB before upload, AES-GCM encrypts at rest with HKDF key material derived from the operator token, scopes records by tenant/actor/session, uses stable request/artifact IDs, FIFO fail-stop retry, online auto-retry, and clears ciphertext only after server acceptance. The UI discloses this is not WORM or device-qualified storage.
- Real Chromium/IndexedDB tests cover page-reload recovery, wrong-key fail-closed behavior, FIFO failure/retry, stable IDs, and scoped purge. The CodeQL DOM-XSS alert was resolved by rendering capture previews on canvas instead of assigning user-selected blob URLs directly to image DOM.
- **PR #156** `Show accepted and pending evidence progress in capture` merged: `607a257ac36cc95a224c3f101d46a5884646c40a`. Tested head: `60ae5e627399909502bb3e66e4d8bc358aaadeef`.
- The 16-view progress meter counts only server-accepted originals and separately reports pending local uploads/queue-unverified status; sealing remains blocked until server readiness and local queue scope are verified.
- Exact tested heads for both increments: **17 checks successful, 3 evidence-publication jobs skipped, 0 failures**. Full suite: **987 passed, 31 warnings, 208 subtests passed**. Integrated container smoke and OCI ARM64 build passed; Browser IndexedDB, guided capture, CodeQL, database authority/legacy, FastAPI, VIN, restricted-container, controlled-demo, and intake checks passed.
- Main after PR #156: `607a257ac36cc95a224c3f101d46a5884646c40a`.
- **No deployment/field acceptance:** there is no user-accessible staging URL, live OCI compute, verified PostgreSQL/PostGIS host, durable evidence volume, backup/restore rehearsal, or physical-device qualification. Guarded OCI plan/apply and image-publish workflows exist, but protected environment secrets cannot be inspected or dispatched from this session. Live payments/dispatch remain disabled.

## Next executable task

Run the guarded OCI infrastructure plan from GitHub Actions, review state and cost, then apply only through the protected environment after verifying credentials and approvals. Provision/verify Postgres/PostGIS and durable evidence storage, publish the immutable ARM64 integrated image, deploy privately, and test authenticated case capture, evidence retrieval/integrity, tenant isolation, restart persistence, and backup/restore. If a required protected secret/access path is absent, identify the exact prerequisite; continue product implementation meanwhile.

## Verified checkpoint — PR #153 merged (2026-11-22)

- PR #153, **Make the Claim2Car secure workspace entry actionable**, merged. Merge commit: `76d5c6795de283be8967978239f2f5b5e59f700f`; tested head: `d550f213766f0512bd46e13ca4782c5b9481f494`.
- Root landing UI directs to authenticated workspace, explains Connect → Capture → Review, and notes credential provisioning/no self-service signup. The primary CTA no longer sends users to the controlled prototype.
- Exact-head CI: **13/13 workflows successful**. Full suite and integrated runtime smoke passed, including non-root container, route/security boundary checks, and ARM64 image build; database authority, IndexedDB, guided capture, VIN, synthetic demo, and container checks passed.
- The integrated root workbench code includes persistent case creation/resume, owner consent, VIN, 16-slot evidence capture, browser IndexedDB original queue, quality attestation, manifest seal, and reviewer workflow. This is code/CI verification only.
- **No staging deployment or user-accessible URL exists yet.** The OCI protected environments, credentials/state bucket, private host, PostgreSQL/PostGIS, durable evidence volume, and secure access path still need provisioning/verification.
- Main after merge: `76d5c6795de283be8967978239f2f5b5e59f700f`.

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
