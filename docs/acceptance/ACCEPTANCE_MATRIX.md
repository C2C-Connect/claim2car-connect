## Verified checkpoint — 2026-11-23 (PR #171 merged)

## Active forensic substantiation gate — M1 (2026-11-23)

**Status: IN PROGRESS / NOT ACCEPTED.** PR #176 (feat/persistent-forensic-provenance-m1, head 36fdd083ebbbe1268e6e2f51d40dfe60b9523404) has an initial Python deterministic hash contract, full-chain verifier and known-answer/unit tests. Exact-head CI 13/13 successful, but automated workflow success does not satisfy the M1 gate. SQL migration/backfill/parity, persistence, server verifier, chain-tip-bound immutable seal, artifact binding, tenant/RLS, append-only and adversarial tests, restart/concurrency/idempotency, and independent verifier agreement are not yet complete. Keep draft/unmerged. See docs/THREAD_HANDOFF_2026-11-23.md for source reconnaissance, vectors and acceptance details. No external notarization, field qualification, forensic certification, or dispatch/payment authorization is implied.

- **Main branch:** `main` (verify the live head on resume). **Last verified code merge:** PR #171 at `beb72950081201e891a7a3e66f42addd13c9f528`; audit/handoff docs PRs #172 and #173 are merged.
- **PR #171 — canonical offline queue encryption and metadata authentication:** merged. Exact tested head `086cf77d71da42342c3ec1c3dd348085014e15f3`.
- **Exact-head CI:** 13/13 workflows passed. Full suite **1,035 passed, 31 warnings, 208 subtests**; offline queue unit tests **11/11**; Chromium/IndexedDB verification passed; integrated runtime/OCI ARM64 build passed.
- Canonical root queue uses HKDF/AES-GCM, authenticated metadata, legacy plaintext and prior ciphertext migration, wrong-token/tamper fail-closed behavior, stable retry identifiers, and purge tests.
- **Acceptance scope:** implementation and automated tests verified; not field-qualified, not WORM, not secure-device storage. Real participant evidence remains prohibited until staging and release gates.
- **System audit:** 24 findings; AUD-001/AUD-016 and AUD-003 remediated. The remaining priority is persistent event-chain and full manifest provenance (AUD-006/017/018), consent/deletion and server encryption (AUD-008/019), source-backed triage/valuation and capture protocol privacy (AUD-013/009/021), then identity, financial, collision/outbox, and staging infrastructure. Audit ledger is linked in the handoff.

## Latest verified checkpoint — 2026-11-22 (PR #165 merged)

- **Main HEAD:** `1f18668b2d9f1cc4e19b49e16c1e66c1313fc116` (PR #165 squash merge).
- **PR #165 — FAOS 16-v2 capture contract:** merged. Tested PR head: `766c0bc99e319e830c626c1fa8d7cacdf1822e9d`. All required workflows passed; full suite: **1026 passed, 31 warnings, 208 subtests passed**. This increment adds migration `0027_capture_protocol_16_v2.sql`, a versioned contract/registry, server API support, browser selection/resume, manifest binding, damage-localization exclusion for non-exterior slots, and compatibility tests.
- **Protocol status:** `claims2car-16-v2` is selectable for controlled testing. `claims2car-16-v1` remains the default; legacy `claims2car-12-v1` remains supported. V2's current 16 positions are eight exterior views, four accessible structural corners, two cabin/restraint views, instrument-cluster telemetry, and physical VIN identity. The manual's second telemetry frame remains an explicit alignment gap; do not silently relabel or alter this immutable version. Field qualification is not complete.
- Browser image quality remains advisory only; it never rejects or changes original evidence. Thresholds are not field calibrated.
- **Next implementation target:** enforce the FAOS forensic integrity contract. Audit found that current `C_hash` can remain nonzero with incomplete/duplicate chains, the backend score uses a weighted geometric mean rather than the manual's weighted sum, and internal dispatch has no strict integrity authorization and falls back to a session ID when photo hashes are absent. Implement fail-closed chain collapse, formula alignment, and dispatch authorization tests before enabling dispatch.
- **Deployment:** OCI staging is still NOT deployed/accepted. Owner-controlled protected-environment/OCI configuration and workflow dispatch remain external blockers; do not request secrets in chat. Continue all code/test work.
- **Thread continuity:** read README, this handoff, status, FAOS manual, and acceptance matrix; inspect live main/PR/check/deployment state; resume the next executable task above without replanning.
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


## Previous verified checkpoint (post-PR #132 merge; superseded by PR #134 checkpoint above)

- **Main:** `bf0649b6c65ec6d1bdb0d6dbcde8843abdad4122` — PR #132 merged: optional Square Sandbox runtime configuration now passes through OCI bootstrap/runtime deploy. Bootstrap writes five optional Square settings as empty by default; deployment injects them into the integrated container. Tests cover defaults, secret-file permissions, and pass-through. No credentials were committed.
- **PR #127:** Square Sandbox webhook receipt/payment-state reconciliation (migration 0026) merged. HMAC validation, deduplication, tenant-bound order mapping, mismatch/conflict/stale/unmatched outcomes, and synthetic PostgreSQL tests are implemented.
- **PR #121:** structured Vehicle Intelligence Lab assessment JSON, digest, rule-based disposition, escalation, missing-evidence handling and report download verification merged.
- **PR #132 verification:** exact head `ccade1681ce122750160c8a5169fe2b86d821190`; **12/12 distinct workflows successful**. Full suite, DB authority cutover, legacy DB, FastAPI and frontend VIN/decoder/transport checks are green on that candidate. Merge commit is above.
- **PR #127 verification (separate earlier increment):** 13/13 workflows green; 1,185 tests, 0 failures/errors/skips; DB-01–DB-14 14/14; 26 migrations; 17 tenant-scoped tables and 34 tenant-matrix entries. Synthetic CI acceptance, not field validation or production certification.
- **OCI staging remains NOT deployed.** Terraform state bucket, plan/apply, infrastructure, host, Postgres/PostGIS, persistent evidence storage, backup/restore and integrated journey have not been executed/verified. Cloud credentials and protected GitHub environments are not inspectable or dispatchable from this session. The private staging host cannot receive Square webhooks from Square directly; no relay has been reviewed or deployed. Live payments remain disabled.

## Next executable task (no founder choice required)

1. Continue the audit-led corrective sequence: establish a persistent cryptographic capture-event chain and a versioned sealed manifest that binds the chain tip, actor/time, consent, quality, exceptions, and original hashes. Trace integrity inputs to server-derived evidence and keep dispatch disabled.
2. Implement precise consent-withdrawal/deletion receipts with durable retry/pending state; verify originals encryption at rest, snapshots, and backups.
3. Remove synthetic triage defaults or isolate them behind explicit controlled-demo mode; attach provenance and uncertainty to ACV/jurisdiction outputs. Resolve the privacy-sensitive default capture protocol.
4. Continue identity, durable financial lifecycle, collision state/outbox relay work.
5. In parallel, revalidate OCI public ingress, retire/confirm unused MySQL resource, configure protected staging environments and private PostgreSQL/PostGIS, then deploy and qualify only through approved gates.

See [Execution Handoff](../EXECUTION_HANDOFF.md), [Execution Status Snapshot](../EXECUTION_STATUS.md), and the [system audit](../audits/FOUNDATIONAL_SYSTEM_AUDIT_2026-11-23.md).

---

# Fresh handoff checkpoint — 2026-11-21

This repository is to be executed, not continually replanned. The founder's standing authorization is to implement, test, fix, verify, merge verified increments, deploy to authorized staging, and exercise real end-to-end workflows with proactive autonomy. See [Execution Handoff](../EXECUTION_HANDOFF.md) and [Execution Status Snapshot](../EXECUTION_STATUS.md). This snapshot is deliberately brief; historical milestone sections below are historical evidence and must not be mistaken for the latest branch or release state.

**Observed main:** `1c1a010143ce8c9407fc3299e0eeaa5f623e4c08` (verify live before use).  
**Latest open validation candidate observed:** PR #125 (Square sandbox webhook reconciliation); PR description reports no workflow runs for its corrected head. Exact head/checks must be revalidated. Do not merge without exact-head required checks green.  
**Staging:** OCI integrated staging is not deployed; cloud prerequisites remain.

---

## Current OCI apply-workflow milestone — PR #86 (2026-11-20)

**Status:** merged to `main`; all 14 workflow checks passed.

- PR: [#86 — Add guarded OCI staging infrastructure apply](https://github.com/C2C-Connect/claim2car-connect/pull/86)
- Merge commit: `bbee7003adb14d53c83e3eb60295ee379209bb7b`.
- Manual-only, main-only, explicit confirmation, remote-state plan, delete/replace guard, one-day saved-plan artifact, and separate reviewer-gated apply environment are implemented.
- OCI infrastructure validation, Terraform validation, full suite, DB authority, browser, and integrated ARM64 container checks passed.
- **No apply has been run and no OCI resources have been created.** The state bucket, environment secrets/variables, and required reviewer configuration are still prerequisites.

## Current Terraform remote-state milestone — PR #85 (2026-11-20)

**Status:** merged to `main`; 14/14 workflow runs successful.

- PR: [#85 — Move OCI staging Terraform plans to persistent remote state](https://github.com/C2C-Connect/claim2car-connect/pull/85)
- Merge commit: `a527bbe4eeb93ebcbace42f0beb312ac7f97df94`.
- Terraform now requires 1.12+ and declares the native OCI Object Storage backend.
- The manual plan workflow requires a pre-created state bucket/namespace, initializes remote state and locking, and remains plan-only with destructive-action rejection.
- OCI infrastructure validation, Terraform formatting, and backend-free validation passed; full project CI passed on the PR.
- **No state bucket or OCI infrastructure was created.** The state bucket must be created/versioned and GitHub environment variables configured before the plan/apply workflows can access OCI.

## Current infrastructure automation milestone — PR #84 (2026-11-20)

**Status:** merged to `main`; CI green on exact PR head.

- PR: [#84 — Add protected manual integrated-image publication to OCIR](https://github.com/C2C-Connect/claim2car-connect/pull/84)
- Merge commit: `9e462a83e18432d8a2831bb60c75e8a666f478cf`.
- **19/19 workflow runs successful**; no failures.
- Full suite: **859 passed, 208 subtests passed, 31 warnings** — run [44783729668](https://github.com/C2C-Connect/claim2car-connect/actions/runs/44783729668).
- PostgreSQL authority: **357/357 counted tests passed**, **14/14 DB gates awarded**, overall `ACCEPTED` — run [44783729938](https://github.com/C2C-Connect/claim2car-connect/actions/runs/44783729938).
- OCI workflow lint/validation passed — run [44783708964](https://github.com/C2C-Connect/claim2car-connect/actions/runs/44783708964).
- Integrated runtime native container smoke passed and the OCI ARM64 cross-build/export completed successfully — run [44783708409](https://github.com/C2C-Connect/claim2car-connect/actions/runs/44783708409).
- Added a manual, environment-scoped OCIR publishing workflow: explicit confirmation, `main` only, immutable source-SHA image, provenance/SBOM. No image was pushed and no deployment was executed because OCI registry variables/credentials are not configured from this session.
- **Still no staging deployment:** compute, PostgreSQL/PostGIS, persistent volumes, secrets, private host rollout, backups/restore and end-to-end persistence remain unverified.

## Current verified implementation milestone — PR #83 (2026-11-20)

**Status:** merged into `main`; synthetic CI passed on the exact candidate head before merge.

- PR: [#83 — Connect Vehicle Lab to persistent claim-case creation](https://github.com/C2C-Connect/claim2car-connect/pull/83)
- Candidate head: `ca97cdd4d10c6a6d39b03ee14183fb46ae0da1e2`; merge commit: `853cbe36fa30211a925d8bc24b1cdb705835c70c`.
- Full repository pytest: **859 passed, 208 subtests passed, 31 warnings** — [run 44782624984](https://github.com/C2C-Connect/claim2car-connect/actions/runs/44782624984).
- PostgreSQL authority acceptance: **357/357 counted tests executed and passed**, zero failures/errors/skips/expected failures/unexpected successes; **DB-01–DB-14 14/14 PASS with 14 formal awards**, contract adopted, `overall_acceptance: ACCEPTED` — [run 44782624939](https://github.com/C2C-Connect/claim2car-connect/actions/runs/44782624939).
- Browser IndexedDB and Vehicle Lab Chromium journey: [run 44782624967](https://github.com/C2C-Connect/claim2car-connect/actions/runs/44782624967). The browser journey verified persistent claim-case creation, owner capture consent, VIN reference and separate decode consent, capture pause/resume, and server-readiness refreshes. The fixture echoes the client-generated claim ID to verify idempotent binding.
- All **13/13 PR workflow runs** passed on the exact PR head before merge.
- Vehicle Lab now creates a persistent claim case through `/api/v1/claim-cases`, binds the server-returned capture session, validates the response scope/IDs, preserves claim/request UUIDs across retry, and displays both identifiers. The controlled-test-only session creation route is no longer used by this UI.
- **Deployment status:** no OCI staging deployment. PostgreSQL/PostGIS, dedicated persistent database/evidence volumes, secrets, host deployment, restart-persistence, restore rehearsal, private access and field qualification remain unverified/release-blocking.

# Claim2Car Connect — Acceptance & Release Gate Matrix

> **Product north star:** [Claim2Car Product Premise: Forensic Intelligence, Truth, and Resolution](../architecture/PRODUCT_PREMISE_FORENSIC_INTELLIGENCE.md) defines the owner-aligned product objective and Post-Accident Truth Standard. This document records implementation, verification, and release evidence; the vision document must not be read as proof that target capabilities are already implemented.


**Canonical repository:** `C2C-Connect/claim2car-connect`
**Current main baseline before PR #64 integration:** `1898259e64548f38020877c2c6e80237b81eeac5`
**Capture protocol:** `claims2car-16-v1` is the new-session default; explicit historical `claims2car-12-v1` compatibility is preserved.
**Database contract:** `C2C-DB-AC-001 v1.0` owner-adopted; independent review waived (not performed); post-adoption DB-01–DB-14 acceptance completed with 14/14 formal awards and overall `ACCEPTED` on synthetic PostgreSQL evidence.

## Latest candidate verification — PR #64 (2026-11-18)

**Status:** Verified candidate; PR remains draft/open until final review and merge.

- PR: [#64 — Add separately consented, provenance-aware vehicle profiles](https://github.com/C2C-Connect/claim2car-connect/pull/64)
- Candidate head: `5c97be791e3612f97170b8110434f8a4167222fa`
- Base `main`: `1898259e64548f38020877c2c6e80237b81eeac5`; this candidate is not yet merged.
- Full repository pytest: **803 passed, 196 subtests passed, 28 warnings** — full-suite run [44301345481](https://github.com/C2C-Connect/claim2car-connect/actions/runs/44301345481).
- PR workflow runs: **13/13 successful** on this candidate. The browser IndexedDB job succeeded on its second attempt after a runner package-install failure; the successful attempt is recorded under [run 44301345353](https://github.com/C2C-Connect/claim2car-connect/actions/runs/44301345353).
- PostgreSQL authority run: **329/329 counted database tests passed**, zero failures/errors/skips; **DB-01 through DB-14: 14/14 PASS and 14 formal awards**; `overall_acceptance: ACCEPTED` — [run 44301345760](https://github.com/C2C-Connect/claim2car-connect/actions/runs/44301345760).
- The authority evidence is checksum-bound to **24 migrations**, on isolated synthetic PostgreSQL 16.4, with **280/280 tenant-isolation assertions** across 14 tenant-scoped tables.
- Migration 0023 adds separately consented NHTSA vPIC vehicle-profile snapshots. Migration 0024 adds append-only capture exception/resolution and pause/resume events; exceptions do not count as evidence, unresolved exceptions block quality review, and sealing still requires all original 16-view artifacts. The integration journey verifies that lookup is blocked before separate owner consent, disclosure versions are enforced, normalized attributes and field provenance persist across runtime restart, retries are idempotent, raw VIN/provider response are not persisted, and consent withdrawal clears active profile attributes.
- vPIC output remains descriptive manufacturer/provider data only. It is not proof of ownership, physical condition, damage, curb weight, structural status, or roadworthiness; raw detector or provider values are not promoted into physics inputs.
- **Limitations remain:** the optional consent flow is API-integrated but not yet surfaced in the browser workbench; vPIC unit/integration tests use controlled provider fixtures and do not establish live provider availability or field accuracy. No real-participant pilot, production deployment, legal acceptance, or field validation is claimed.

The historical sections below record earlier milestones and must not be treated as the current branch or deployment status.

## Historical verification snapshot — 2026-11-17

### PR #41 — capture protocol 16-v1

PR #41 is merged into `main`.

- PR: [#41](https://github.com/C2C-Connect/claim2car-connect/pull/41)
- Merge commit: `4c52f169239c79e45ef979f91b2e66b8e51b6336`
- Full pytest on that merged source: **758 passed, 200 subtests passed**.
- The 13 PR workflows passed before merge.

### Historical pre-adoption DB-01 through DB-14 implementation snapshot

PR #43 implemented and merged the 14 gate verifier functions, per-gate test selectors, direct PostgreSQL evidence requirements, and the fail-closed counted-test runner. PR #44 corrected the structured evidence JSON publisher.

- PR #43: [Executable DB-01 through DB-14 verifiers](https://github.com/C2C-Connect/claim2car-connect/pull/43)
- PR #44: [Acceptance evidence JSON serialization fix](https://github.com/C2C-Connect/claim2car-connect/pull/44)
- Current main SHA: `32ed4174d10ab7ac2d895741e413b0624e53ecaa`
- Full pytest: **768 passed, 201 subtests passed**, zero skipped.
- Counted PostgreSQL suite: **307/307 passed**, zero failures, errors, skips, expected failures, or unexpected successes.
- PostgreSQL: **16.4**, isolated synthetic database `claim2car_test`; explicit `postgres`, `faos_app`, and `faos_migrator` identities recorded.
- Migration inventory: all 18 migrations recorded with SHA-256 digests.
- Direct SQL parity probes passed for timestamp validity, compact JSON, key ordering, numeric exponent spelling, escaped Unicode, and positive canonical round trips.
- Historical payload preservation and rollback tests passed; no migration rewrites or normalizes existing event history.
- Tenant isolation: 14 tables × 2 tenants × 10 adversarial assertions = **280/280 passed**.
- All 14 gate criteria evaluated `PASS` in the post-cutover authority report.
- The structured evidence artifact was successfully published after PR #44.

**At this historical snapshot, formal gate award remained 0/14.** The source contract was then `PROPOSED_PENDING_OWNER_ADOPTION`; each gate was reported as `NOT AWARDED` with `criteria_result: PASS`. This state was superseded by the post-adoption PR #47 evidence below.

### Issue disposition

- Issues #33–#38 are closed with PostgreSQL, migration, immutability, replay, and CI evidence.
- Issue #39 remains open pending independent review and formal owner adoption of C2C-DB-AC-001.
- No additional SQL parity migration was needed: existing `0017_event_contract_parity.sql` already enforces the Python-equivalent boundary; new adversarial tests validate it.

### PR #47 — manifest-root protocol binding migration 0019 (merged and accepted)

- PR: [#47](https://github.com/C2C-Connect/claim2car-connect/pull/47)
- Merge commit on `main`: `f3ba5b28eede44eff5fef70a6b5fda8b4358757f`.
- PR candidate head: `4b753441374130c21e39b16780d0b85472cdd202`.
- Tested synthetic merge checkout: `64488e5d5ab4d94347cd55bbe709bc59ab69c174`; the actual merge commit and tested checkout have no file differences (GitHub commit comparison returned zero changed files).
- Main first parent / pre-merge baseline: `8217bbf3723b0087c8cab340da6fe19ebf356e4f`.
- Current-head GitHub Actions: **18/18 run records succeeded across 13/13 distinct workflow types**, with no failures or cancellations.
- Full repository pytest: **780 passed, 201 subtests passed, 23 warnings** — [run 44183764131](https://github.com/C2C-Connect/claim2car-connect/actions/runs/44183764131); [full-suite artifact](https://github.com/C2C-Connect/claim2car-connect/actions/runs/44183764131/artifacts/14373761156).
- Counted PostgreSQL suite: **319/319 executed and passed**, zero failures, errors, skips, expected failures, or unexpected successes — [authority run 44183764027](https://github.com/C2C-Connect/claim2car-connect/actions/runs/44183764027); [acceptance evidence artifact](https://github.com/C2C-Connect/claim2car-connect/actions/runs/44183764027/artifacts/14372808585).
- Post-adoption authority diagnostics: contract `C2C-DB-AC-001 v1.0` is `ADOPTED`; **DB-01 through DB-14: 14/14 PASS and 14 formal gate awards**; `overall_acceptance: ACCEPTED`.
- The evidence records a complete checksum-bound 19-migration inventory, 14 tenant-scoped tables, and 280 adversarial tenant-isolation assertions on isolated synthetic PostgreSQL 16.4.
- The 16-v1 manifest-root regression passed: valid 16-v1 registration succeeds, mismatched registration fails, and a direct mismatched write is rejected by the database trigger under the writer role. The separate application-role denial tests also pass.
- The Product Owner explicitly waived independent review for v1.0 adoption. **Independent review was not performed and is not claimed**; it remains recommended as follow-on assurance.
- Issue #39 closure criteria are now met: review waiver recorded, owner adoption recorded, PR #47 merged, complete post-adoption DB-01–DB-14 run recorded, and formal results reported without inference.
- Persistent integrated staging, production migration, real-participant intake, payment settlement, dispatch, external distribution, and field/legal acceptance remain separate gates and are not claimed by this database milestone.

Migration 0019 is not a replacement for event-contract parity. It adds a separate evidence-manifest/session protocol binding boundary.

### Remaining acceptance and release boundaries

- Historical synthetic results were not formal acceptance until contract adoption; the later post-adoption result is recorded above and in the PR #47 section.
- Synthetic acceptance does not establish production readiness, real participant/field acceptance, legal admissibility, measurement accuracy, or complete commercial deployment.
- Live Square settlement, external carrier/partner delivery, and live dispatch remain disabled unless separately authorized and verified.

## Commercial and safety controls

| Requirement | Enforcement surface | Verification | Status |
|---|---|---|---|
| Dealer fee is fixed at $375 (37,500 cents) | `config/forensic_constants.py`; `backend/app/anchor/ledger.py`; persistent ledger migration and adapter | `tests/contracts/test_commercial_prohibitions.py`; `tests/dispatch/test_integer_financial_ledger.py`; full-suite CI | Dealer fee posting is fail-closed in both the Python ledger and SQL authority function until a verified qualified-acquisition-close event is integrated; shop acceptance posting remains a component, not a live partner workflow |
| Shop fee is fixed at $275 (27,500 cents) on recorded acceptance | `app/dispatch_routing.py`; persistent integer-cents ledger | Commercial and ledger suites | Implemented and regression-tested on the PR #29 candidate; live partner acceptance is not deployed |
| Owner cash incentives are prohibited | Commercial constants, ledger guard, dossier output guard | Commercial and dossier suites | Implemented and regression-protected on the PR #29 candidate |
| $110 operator payout remains disabled pending policy decision | Integer-cents ledger gate and active-output checks | Commercial and ledger suites | Disabled on the PR #29 candidate; no settlement is authorized |
| Roadside pause, unsafe-slot skip, and scene abort remain available | `frontend/src/modules/capture/slice2_workbench_controller.mjs` | `frontend/tests/slice2_workbench.test.mjs` | Implemented on the PR #29 candidate; 12 assertions pass in the local Node run and the GitHub full-suite workflow passes |
| Independent human reviewer inspects sealed evidence and records a supported review outcome | Integrated reviewer queue, verified-session detail API, original-byte retrieval API, and review-record API | Capture evidence service tests; integrated runtime route tests; full-suite CI | Initial connected reviewer workbench is implemented on PR #29: sealed manifest and original bytes are re-verified before artifact metadata is returned; originals are retrievable by an independent reviewer; NOTE_ONLY and HUMAN_QC_REQUIRED are recorded. Qualified-device/field validation, reviewer assignment/escalation, and final claim adjudication remain incomplete. |

## Security, evidence, and product gates

| Gate | Exit requirement | Evidence | Current status |
|---|---|---|---|
| GATE-01 Governance | Commercial rules reconciled across active outputs, ledger, and docs | Commercial and ledger suites; this matrix | Candidate implementation is present on PR #29; not independently reviewed or accepted on `main` |
| GATE-02 Security | Server-derived actor and tenant authority, PostgreSQL RLS, original-byte integrity, authenticated internal routes | Database/security suites; integrated route and capture evidence service tests | Candidate code and CI cover configured actor roles, owner consent events, keyed VIN references, original-byte registration, server-side manifest sealing, and independent reviewer authorization; persistent integrated deployment remains unverified |
| GATE-03 Product | Operator capture and reviewer workbench demonstrated end-to-end on qualified iPad hardware | Slice 2 controller tests; integrated web-shell/API tests; verified-original review tests | Not passed; a connected integrated shell now supports case creation/resume, separate owner consent, canonical-slot original uploads, advisory operator attestations, manifest sealing, verified reviewer retrieval, and limited human-review outcomes. Qualified iPad/browser/device demonstration and field validation have not been performed. |
| GATE-04 Data | Persistent database/object storage, backup restore, consent withdrawal deletion | RLS event journal and POSIX original-byte store; capture evidence service tests | Partial; withdrawal now deletes registered original objects and blocks subsequent use. Storage encryption and backup/restore remain unverified |
| GATE-05 Deployment | One integrated runtime deployed and verified in persistent staging | `app.main:create_app(runtime_mode="integrated")` composes intake and internal analytical routes; provider-neutral restricted-container CI verifies the separate health-only runtime; OCI integrated staging is not yet deployed | Not passed; integrated mode remains opt-in, Railway deployment workflows have been retired, and OCI compute/PostgreSQL/PostGIS/evidence storage are not yet provisioned. No persistent integrated staging deployment is evidenced |
| GATE-06 Operations | Pilot owner, onboarding, grading, and reconciliation procedures | No field evidence in this branch | Not passed |
| GATE-07 Legal & partner | Counsel review and signed partner/data agreements | `docs/LEGAL_REVIEW.md` | Not passed |
| GATE-08 Measurement | Scene-time, retakes, and model performance calibrated against shop ground truth | Synthetic benchmarks only | Not passed; no field validation claimed |
| GATE-09 Commercial | Integer-cents accounting, payment sandbox/live settlement, and authorized carrier delivery | Persistent tenant-scoped integer ledger, reversal, idempotency and audit-export integration tests; deterministic dossier tests | Partially implemented; payment settlement and external distribution are not enabled |

## Artifact and model gates

| Requirement | Evidence | Status |
|---|---|---|
| Local model weight digest provenance and benchmark-gated adoption | `backend/app/vision/adapters.py`; `tests/dispatch/test_inhouse_vision_adapter.py` | Adapter and synthetic gate tests implemented; production model weights are not present and accuracy is not validated |
| Recipient-scoped deterministic dossier generation and withdrawal revocation | `backend/app/reports/forensic_pdf.py`; `tests/dispatch/test_four_tier_dossiers.py` | Implemented locally; distribution remains disabled pending legal, partner, security, and consent review |
| Complete commercial lifecycle demonstration | `app/commercial_ecosystem_demo.py` | Added; execution depends on the POSIX storage runtime used by the Linux CI container |

## Release discipline

The former Railway configuration was a restricted synthetic containment service, not the integrated product, and has been retired. The provider-neutral restricted-container CI remains health-only. OCI is the selected integrated-staging target but is not yet deployed. Live dispatch, payments, partner/carrier delivery, production publication, and real participant data remain disabled until their legal, security, partner, operational, and deployment gates have actual evidence.

## Persistent claim-case register and owner-bound evidence journey — 2026-11-10

**Candidate revision:** `1c9a1b839f56396a758b1c0bc8837f8a5e5a2ea1`  
**Implementation status:** Implemented and automated-test verified on PR #29 using synthetic test identities and synthetic image bytes; not field-validated or deployed.

- Added authority migrations `0010_claim_case_registry.sql` through `0013_claim_case_capture_session.sql`.
- Added `faos.claim_cases` with tenant-scoped identifiers, immutable creator/time/state metadata, RLS, and a server-owned idempotent creation function. App identities read; creation occurs through a narrowly granted database function; app identities have no table update/delete grant.
- Each persistent claim record provisions a distinct capture session with a first journal event explicitly identifying it as a persistent claim session, not a controlled-test session.
- The first provisioned owner actor credential to record consent is bound to the case. A different owner actor in the same tenant cannot take over or consent to that case.
- Added authenticated create/list/reopen APIs, bounded listing, creator scoping, explicit session scope, and operator UI controls that open the linked capture session.
- Kept the standalone `POST /v1/capture-sessions` route explicitly controlled-test only.
- Added PostgreSQL end-to-end coverage for the persistent claim session: owner consent, keyed VIN HMAC (raw VIN not journaled), original bytes for every canonical capture slot, advisory quality, manifest sealing, reviewer queue/details, integrity-checked original retrieval, and a supported human-review outcome.

**Deliberate boundary:** the complete automated journey uses synthetic VIN and synthetic image bytes. The case currently stores identity, creator/time/state, and capture-session association; incident details/location/narrative, claimant personal information, and policy details are not yet stored. Owner binding relies on a server-provisioned owner actor credential; this is not end-user login, identity proofing, or claimant invitation. The end-to-end test is not field acceptance, live participant-data approval, automated adjudication, or proof of a deployed customer-facing environment.

**Founder-approved capture-protocol direction — 2026-11-10:** `claims2car-16-v1` is the default target; `claims2car-12-v1` remains a selectable, explicitly versioned alternative. Historical 12-v1 sessions and manifests must retain their original protocol identity and interpretation. This supersedes the earlier open question about which count is the target.

**Resolved by Owner Executive Approval — canonical 16-v1 contract:** The binding 16 ordered slot IDs and descriptions are in `contracts/shot-list-16-v1.json`. The implementation maps those exact IDs through the API, evidence manifest, capture service, root workbench, guided workflow, and reviewer controller. The prior conflicting architecture enumerations are superseded for new sessions by this owner-supplied contract; the original 12-v1 contract remains unchanged for historical sessions and explicit selection.

**Verification evidence at the candidate revision:**
- Full repository suite: **685 passed, 192 subtests passed, 21 warnings** — GitHub Actions run [42755651654](https://github.com/C2C-Connect/claim2car-connect/actions/runs/42755387422).
- Database authority cutover and post-cutover tenant-isolation diagnostics: passed — run [42755651694](https://github.com/C2C-Connect/claim2car-connect/actions/runs/42755387498).
- FastAPI foundation, restricted intake container, offline capture, frontend VIN/transport, controlled-test PostgreSQL, synthetic demonstration, historical Railway-hosted restricted smoke, and PR #29 checks: passed.
- Historical Railway restricted staging verification passed — run [42755641253](https://github.com/C2C-Connect/claim2car-connect/actions/runs/42755387517). The actual deploy job was skipped; this is not deployment of the integrated Claim2Car application.

**Next implementation slice:** reconcile the 12-versus-16 capture-slot contract; establish the incident intake data contract and consent/disclosure scope; replace static owner actor credentials with the approved owner authentication/invitation path; then deploy the integrated app to restricted staging and validate with approved test participants before any production release.


## Structured incident intake and supplemental owner consent — 2026-11-10

**Implementation:** PR #29 candidate branch, migrations `0014_claim_case_incident_intake.sql` and `0015_incident_event_kinds.sql`; synthetic PostgreSQL integration coverage added and verified.

**Verification at candidate `10b2f7b5ba26393a0d67cf4579fc890cf9bd416a`:** full repository suite passed; database authority migration/cutover and tenant-isolation diagnostics passed, including direct-table-read denial and actor-filtered read verification; API health, controlled intake PostgreSQL, integrated-container smoke, frontend, VIN, CodeQL, and historical Railway-hosted restricted smoke checks passed. The historical Railway deploy job remained skipped. These are CI/synthetic results, not field acceptance or a live deployment.

- Added a separate owner consent event with disclosure version `incident-intake-v1` and scope `incident_details`. It is distinct from the existing `disclosure-v1` capture/evidence consent.
- Added a tenant-scoped, RLS-forced `faos.claim_case_incident_intake` table. The first version collects only incident timestamp, category, city, two-letter state/territory code, and ZIP code.
- Explicitly excluded street address/GPS, free-text narrative, claimant contact information, date of birth, policy number, and payment information.
- Incident details are stored outside the append-only event journal so the structured row can be deleted on supplemental withdrawal or withdrawal of the underlying capture consent. The journal records consent and request references, not the incident fields.
- Owner identity must be the already-bound owner actor for the persistent claim case. Operator credentials cannot submit owner consent or incident details.
- API exposure is gated by `C2C_INCIDENT_INTAKE_ENABLED=true`; the default is disabled. The disclosure contract is marked `draft_pending_legal_review`. No real participant data use is authorized by this code increment.
- This is a first structured intake slice, not the complete incident/claimant/policy intake contract. Owner access still relies on a server-provisioned owner actor credential; end-user authentication, identity proofing, and claimant invitation remain outstanding.


## Actor-scoped incident detail read path — 2026-11-10

- Migration `0016_claim_case_incident_read_boundary.sql` revokes direct `SELECT` on incident details from the shared application database role.
- The application reads incident details through a restricted database function that filters by the server-resolved actor ID against the case creator or bound owner. The API additionally enforces the actor role and case-creator/owner rules before invoking it.
- Added owner and case-creating-operator read paths; other same-tenant operators and reviewers are denied. Reviewer access is not included in this supplemental disclosure scope.
- The owner-facing disclosure now states who can view these details and that they are not automatically sent to insurers, repair shops, or dealerships.
- The operator shell can load the details after the owner separately consents. Withdrawal removes the row, so the read path no longer returns it.
- The database authority diagnostic now verifies that the shared application role cannot directly select this table and must use the actor-filtered read function.

**Verification at candidate `10b2f7b5ba26393a0d67cf4579fc890cf9bd416a`:** the complete database authority/cutover workflow and full repository suite passed (**693 passed, 23 warnings, 192 subtests**), including the owner/creator readback and denial-to-other-operator integration test. API health, integrated-container smoke, controlled PostgreSQL intake, VIN, frontend, CodeQL, and historical Railway-hosted restricted verification also passed; the actual historical Railway deploy job remained skipped.

**Remaining boundary:** owner authentication is still based on a provisioned actor credential; this does not establish the real person's identity. The feature remains disabled by default and the disclosure remains pending legal review.


## Canonical offline queue hardening — PR #171 merged (2026-11-23)

- Canonical integrated root workbench stores original bytes encrypted before IndexedDB persistence using HKDF-derived AES-GCM keys with random salt/IV.
- AAD authenticates tenant, actor, session, capture slot, artifact/request IDs, digest, byte length, MIME type, queue timestamp, and encryption version.
- Legacy plaintext and prior AES-GCM-without-AAD queue records are digest-checked and migrated in place before upload; corrupted legacy items remain blocked.
- Wrong token or metadata tampering causes decryption failure and no upload. Stable IDs, FIFO fail-stop retry, uploaded-payload removal, and tenant/session purge are preserved.
- Sign-in token field is cleared after successful authentication. Key remains transient; local recovery requires re-entering the same credential.
- Exact-head CI: 13/13 workflows green; full suite 1,035 passed, 31 warnings, 208 subtests; unit queue tests 11/11; Chromium/IndexedDB browser verification passed.
- **Limit:** encryption is defense-in-depth, not WORM/secure-device storage; no physical-device, Safari/iPad, quota/eviction, or field qualification. No real evidence is authorized.

## Browser-persistent original evidence queue — 2026-11-10

**Candidate revision:** `0ebe7337b74c5fe82ba7b2e39cc1c08aedbf7737` (current code and verification revision; subsequent commits update documentation only).

**Implemented on PR #29:**
- The integrated operator shell stores selected original image bytes in IndexedDB before attempting upload. It does not transform or recompress the bytes.
- Queue records are scoped to the authenticated tenant, actor, and capture session. A separate tenant/session index supports local cleanup after consent withdrawal.
- Each queued original receives stable request and artifact UUIDs plus a browser-computed SHA-256 digest. Retries reuse those identifiers so the existing server idempotency behavior can recognize an accepted request whose response was lost.
- Upload is serial in queue order and stops at the first failure. The operator can retry manually, on the browser's `online` event, or when reopening a session.
- After server acceptance, the browser removes the local binary payload and retains only receipt metadata. Status refreshes do not load queued image bytes into the UI.
- A server-authoritative evidence-readiness route reports whether the case creator has active owner consent and a valid vehicle reference. The operator UI checks this before queueing while online and again before synchronization. During a connectivity interruption, the current page may rely on the last server-verified readiness result held in memory.
- The owner can withdraw capture consent. After server confirmation, the same browser purges all local queue entries for that tenant/session. If withdrawal occurs on another device, the operator device can purge its pending queue on its next synchronization attempt or case reopen while online and after checking server readiness.

**Verification at the implementation revision:**
- Offline guided-capture workflow, queue behavior assertions, and integrated browser-module syntax checks passed — [run 42781775036](https://github.com/C2C-Connect/claim2car-connect/actions/runs/42781775036).
- Full repository suite passed — [run 42781775011](https://github.com/C2C-Connect/claim2car-connect/actions/runs/42781775011).
- Database authority/cutover verification passed — [run 42781774737](https://github.com/C2C-Connect/claim2car-connect/actions/runs/42781774737).
- Restricted intake container verification passed — [run 42781774732](https://github.com/C2C-Connect/claim2car-connect/actions/runs/42781774732). This is not an integrated Claim2Car deployment.
- Restricted Railway smoke passed — [run 42781774969](https://github.com/C2C-Connect/claim2car-connect/actions/runs/42781774969); its deploy job was skipped. No integrated staging deployment is claimed.
- Actual Chromium/IndexedDB browser verification passed — [run 42781774794](https://github.com/C2C-Connect/claim2car-connect/actions/runs/42781774794). It exercised offline local writes, page-reload recovery, FIFO fail-stop, stable retry identifiers, local binary removal, tenant/actor isolation, and tenant/session purge using synthetic bytes and a mocked upload callback.

**Important limits — not field acceptance:**
- Pure queue-logic assertions also use an injected in-memory store. The separate Chromium run exercises the real IndexedDB adapter, but uses synthetic bytes and a mocked upload callback; it does not exercise the integrated app-to-API upload path.
- Safari/iPad storage behavior, browser eviction, physical-device restart recovery, quota exhaustion, and real-world roadside connectivity interruption have not been field-tested.
- The canonical root queue now encrypts originals using AES-GCM with authenticated metadata and token-derived keys; it is still not a secure-device vault, WORM store, or production durability guarantee. Browser eviction/quota, Safari/iPad, and physical-device recovery remain unqualified. This feature remains a controlled-test aid and is not authorized for real participant evidence.
- The last verified readiness result is held in page memory, not a signed offline consent permit. After a page restart while offline, new evidence cannot be queued until the server can revalidate readiness. If consent is withdrawn elsewhere while the operator device remains offline, already queued local bytes cannot be remotely erased until that device reconnects.
- No claim is made that this completes the offline-first field-capture requirement. Native/device-qualified storage, explicit local retention controls, integrated app-to-API browser tests, and iPad field validation remain open.


## Event-journal SQL/Python contract parity — 2026-11-10

**Validated historical candidate code revision:** `c6f36810affb72f61a4e4fb3e6d8345705cffb73`. PR #29, PR #31, and wrapper PR #40 have since been consolidated and merged into `main` at `3aa87f9d1523a68a1df09c6930ab57efbd182ba4`. The verification below is historical evidence for the candidate revision, not a claim that its historical run proves the current database acceptance gates.

- Added authority migration `0017_event_contract_parity.sql`. It requires RFC3339 timestamps with an explicit timezone, checks calendar validity, enforces compact canonical JSON with lexically ordered object keys and consistent UTF-8 string encoding, and aligns the SQL event-kind allowlist with Python.
- The shared Python serializer now emits deterministic compact JSON, preserves legitimate decimal quality metrics using fixed decimal notation, and is used by capture, manifest-sealing, and review event producers.
- Direct SQL writes that bypass Python validation are rejected by database constraints. The migration does not rewrite historical rows; incompatible existing rows block migration for explicit investigation.
- Replaced defect-characterization assertions with full-plan PostgreSQL integration coverage using a restricted, tenant-bound application login. Tests verify rejection/no-history-mutation for timezone-naive and malformed timestamps, whitespace, unordered keys, and exponent-form numbers; they also verify canonical UTF-8/decimal round-trip and the complete event-kind allowlist.
- The test fixture registers the authenticated database login-to-tenant binding required by the authority model; it does not rely on superuser execution for application writes.

**Verification at candidate revision `c6f3681...`:**
- Full repository pytest suite: **691 passed, 200 subtests passed, 23 warnings** — [GitHub Actions run 42789801371](https://github.com/C2C-Connect/claim2car-connect/actions/runs/42789801371).
- Database authority full-plan migration, restricted-login integration, post-cutover diagnostics, and tenant-isolation checks: **passed** — [run 42789801486](https://github.com/C2C-Connect/claim2car-connect/actions/runs/42789801486).
- Controlled synthetic demonstration: [passed](https://github.com/C2C-Connect/claim2car-connect/actions/runs/42789801288).
- Chromium/Playwright IndexedDB persistence and recovery: [passed](https://github.com/C2C-Connect/claim2car-connect/actions/runs/42789801223).
- FastAPI foundation and API health: [passed](https://github.com/C2C-Connect/claim2car-connect/actions/runs/42789801311).
- Offline guided capture: [passed](https://github.com/C2C-Connect/claim2car-connect/actions/runs/42789801497).
- Restricted intake container: [passed](https://github.com/C2C-Connect/claim2car-connect/actions/runs/42789801572).
- historical Railway-hosted restricted-container smoke: [passed](https://github.com/C2C-Connect/claim2car-connect/actions/runs/42789801199); the separate deployment job was **skipped**. This is not an integrated staging or production deployment.

**Boundary:** the successful database workflow uses isolated/disposable PostgreSQL test databases and synthetic records. It does not establish production database migration safety against unknown live historical rows, durable cloud storage, backup/restore, production deployment, Safari/iPad qualification, field validation, or legal admissibility. Hashes and canonical journal serialization establish consistency and replayability, not the truth of a claim or capture provenance.

**Next P0 slice:** exercise the complete authenticated HTTP path against the full authority schema and durable artifact store, including process restart, manifest seal/readback, independent reviewer retrieval, cross-tenant denial, consent withdrawal, and tampered-byte rejection. Keep deployment disabled until that integrated path and the persistent storage/recovery controls have evidence.


## Capture protocol version binding — 2026-11-11

**Implementation history:** PR #31 was consolidated through PR #29 and merged to `main` via PR #40 at `3aa87f9d1523a68a1df09c6930ab57efbd182ba4`. The exact owner-approved 16-v1 contract and end-to-end version binding are implemented in the current PR #41 candidate; merge and acceptance remain gated on its current CI.

- New sessions default to `claims2car-16-v1`; `claims2car-12-v1` is explicitly selectable.
- Authority migration 0018 backfills existing sessions as 12-v1, adds a constrained protocol-version column, sets the default for new sessions to 16-v1, and makes the version immutable with a database trigger.
- Claim-case creation, controlled-session creation, session readback, and claim-case readback carry the selected version. Idempotent retries cannot change it.
- The authenticated protocol-registry API and operator workbench expose the default and the selectable legacy alternative.
- Both 16-v1 and 12-v1 contracts are executable. Evidence registration, quality recording, sealing, and reviewer retrieval resolve the exact immutable protocol stored on the session; neither version falls through to the other.

**Implementation status:** the owner-authorized 16-v1 slot list is now committed in `contracts/shot-list-16-v1.json`. New-session defaults, legacy selection, protocol-specific manifests, capture validation, reviewer verification, browser workbench rendering, and exterior-only crush-physics mapping have dedicated coverage. This establishes software-contract implementation, not real-device/field acceptance or persistent staging acceptance.

See `docs/release/CAPTURE_PROTOCOL_VERSIONING.md` for the immutable-session rules and remaining work.


## Database contract owner adoption and formal acceptance — 2026-11-17

- The Claim2Car hub account owner expressly authorized adoption of `C2C-DB-AC-001 v1.0` and explicitly waived independent review as a prerequisite to this version's adoption.
- The waiver is not an independent review; no reviewer approval or attestation is claimed. A later independent review remains recommended.
- PR #47 merged to `main` at `f3ba5b28eede44eff5fef70a6b5fda8b4358757f`.
- The post-adoption authority run [44183764027](https://github.com/C2C-Connect/claim2car-connect/actions/runs/44183764027) evaluated DB-01–DB-14: **14/14 PASS, 14 formal gate awards, overall ACCEPTED**; the counted PostgreSQL suite executed 319/319 tests with zero skips.
- The tested synthetic merge checkout `64488e5d5ab4d94347cd55bbe709bc59ab69c174` and actual merge commit `f3ba5b28eede44eff5fef70a6b5fda8b4358757f` have no file differences.
- This database-only adoption does not authorize production deployment, real participant intake, live payments, dispatch, external distribution, or claims of legal admissibility or field acceptance.


## Standing execution mandate / continuity update — 2026-11-21

The founder has expressly authorized autonomous sequential implementation, test/fix, verified merges, staging deployment, and end-to-end validation to materialize the product. The handoff is recorded in `docs/EXECUTION_HANDOFF.md`; it is the continuity source for new chat threads. Planning, scaffolding, mock/demo output, and documentation do not count as product completion.

Checkpoint: PR #119 sandbox checkout-intent persistence merged at `c7befe0aa8366b109818310ae488809cc695e58c`; its exact tested head `dd21e35484a90dcced1990eccbf674e9cad5c342` had 18 successful workflow runs. PR #120 webhook reconciliation was closed unmerged/superseded; latest branch head `3b7ab26c7aca151ded5b2fd41c09573f618f4b68` had no reported workflow runs and is not accepted. OCI deployment remains unexecuted. See the handoff for next tasks and exact boundaries.
