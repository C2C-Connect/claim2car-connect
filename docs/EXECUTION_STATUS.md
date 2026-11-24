## Verified checkpoint — PR #184 merged (2026-11-24)

- **Merge commit:** `55f69790df123a4602196c3c474e143808c4b87e`; tested head `95692eaf30f76ca9ab8b7c0cf71c4bcf9fac5d68`; **13/13 workflows passed**.
- **Full suite:** 1,064 passed, 7 skipped, 31 warnings, 218 subtests.
- **Authority acceptance:** 407/407 counted tests passed; DB-01–DB-14 14/14 PASS; 340 tenant-isolation assertions.
- **Active PR #185:** `cto/m1-runtime-manifest-registration`, current head `18b617facf9a3772a4d6d568acac315b0327be6f`. It wires root registration into the live seal/review path through migration 0030, in the same tenant transaction, with exact protocol slot-set validation and root checks before review access. Corrected migration-owner privileges and 30-migration inventory fixtures are awaiting a fresh full CI/authority run.
- **Merge gate:** all 13 workflows green plus DB-01–DB-14 accepted on the exact current head. PR #185 is not merged.

**M1:** chain-tip/context binding is in main; live runtime registration is the remaining integration step. **Next after M1:** M2 original-artifact provenance, followed by persisted observations, calibrated measurements, source-backed findings, and deterministic report generation. Do not use the legacy in-memory dossier service as a production report path.


# Active focus — forensic substantiation (2026-11-23)

## Latest verified checkpoint — PR #182 merged (2026-11-23)

PR #182 merged to main as `f0c6fbfc7d0278e77964a45004e0e42ede7a8146`; exact tested PR head `668785ea465b807932e63fdb6a555ed419099b6b`, **13/13 workflows passed**. Full suite: **1,054 passed, 31 warnings, 219 subtests**. Isolated synthetic PostgreSQL acceptance: **390/390 counted tests**, DB-01–DB-14 **14/14 PASS**, 14 gate passes awarded, diagnostics successful and overall database acceptance ACCEPTED. This is not forensic M1 acceptance or field qualification.

Migration 0028 persists SHA-256 event hashes and backfills transactionally. PR #182 adds server-owned persisted readback that recomputes the chain from PostgreSQL rows; `load_journal` and locked consumers fail closed on invalid chain; legacy unhashed schemas are explicitly `LEGACY_UNHASHED`; partial hash schemas fail closed. Tamper, tenant, legacy and locked-consumer tests passed.

**M1 still incomplete:** sealed manifest roots do not yet bind chain tip/sequence/hash version/context; registered original/artifact binding; independent verifier; restart/restore/concurrency/fork and external checkpoint. No deployment, field qualification, participant evidence, payment or dispatch.

**Next code target:** migration 0029 for seal/root chain-tip and context binding; server recomputes and validates chain at registration; root/readback/completion/receipt consumers verify binding. Then artifact provenance, independent/recovery/adversarial tests.

## Historical checkpoint before PR #180 (superseded)

- PR #175 documentation program merged to main: cf985ee92ed6624467bc8dbeaea9e25ff9e207fa.
- PR #176's initial Python hash/verifier slice was superseded and closed by merged PR #180; its branch is stale and should not be resumed.
- This historical checkpoint described Python-only hashes before SQL migration 0028. Current merged code includes persistence, parity, backfill, append verification and immutable event guards; remaining M1 work is stated in the latest checkpoint above.
- Next task is the remaining M1 readback, manifest-root and artifact-binding code gates from the current handoff.
- This active focus supersedes previous “next task OCI staging” status. OCI staging remains unverified/undeployed, no accessible URL, Postgres/PostGIS/evidence volume/backup-restore/secure access still blockers.

**Chronology warning:** the dated checkpoints below are retained as historical records. Their old “next task/next milestone” text is not actionable if it conflicts with the current forensic M1 checkpoint above. The active task is M1 server-owned readback and chain-tip/context binding from current main; see docs/THREAD_HANDOFF_2026-11-23.md. OCI staging and other roadmap work are deferred unless a concrete blocker requires them.


The owner has explicitly directed undivided focus on the ability to substantiate every meaningful forensic claim. The ordered implementation methodology and acceptance gates are in **`docs/forensics/FORENSIC_SUBSTANTIATION_PROGRAM.md`**. This is now the primary engineering focus; avoid adjacent feature expansion.

**Current implementation milestone:** M1 persistent hashes and server-owned readback are merged; implement chain-tip/context binding in sealed manifest roots. The current `backend/app/anchor/ledger.py` is process-memory based and is not the durable forensic ledger required by FAOS. Trace existing PostgreSQL migrations/authority, sealed manifests, registered original evidence, event/audit systems, verifier, integrity scoring, and dispatch/payment callers. Implement a persistent, tenant-scoped, append-only event/anchor model with canonical serialization, stable IDs, idempotency, server times, chain recomputation, checkpoint semantics, manifest/artifact/session binding, restart/concurrency recovery, and fail-closed verification. Do not create parallel persistence systems. Integrity status is not dispatch/payment authorization.

**Program:** M0 schemas/contracts → M1 provenance → M2 registered original/artifact binding → M3 VIN/configuration source verification → M4 camera calibration/alignment/coordinate frame → M5 damage localization + one calibrated measurement → M6 source-backed parts/OEM assessment → M7 deterministic versioned report → M8 held-out/blind validation and qualification. Start with synthetic known-answer data. Target first vertical slice: one controlled vehicle, one component, one bounded damage region, one validated measurement, one evidence-linked finding, one reproducible report.

No unsupported metric precision, causation, hidden damage, forensic certification, or field accuracy claims. No real participant evidence, live payments, dispatch, or public/accepted staging without their independent gates.

---

## Verified checkpoint — 2026-11-23 (PR #171 merged)

- **Main branch:** `main` (verify the live head on resume). **Last verified code merge:** PR #171 at `beb72950081201e891a7a3e66f42addd13c9f528`; audit/handoff docs PRs #172 and #173 are merged.
- **PR #171** canonical offline evidence queue encryption merged; tested head `086cf77d71da42342c3ec1c3dd348085014e15f3`.
- **Exact-head CI:** **13/13 workflows passed**; full suite **1,035 passed, 31 warnings, 208 subtests**; offline queue unit tests **11/11**; Chromium IndexedDB verification passed.
- Canonical root queue now uses HKDF/AES-GCM with authenticated metadata, migrates legacy plaintext and previous ciphertext formats before upload, and fails closed on wrong-token, digest, or metadata-tamper errors. Credential input is cleared after successful sign-in. This remains controlled-test only; no real participant data.
- **System audit:** 24 findings. AUD-001/AUD-016 and AUD-003 are remediated. Audit findings/priority ledger in `docs/audits/FOUNDATIONAL_SYSTEM_AUDIT_2026-11-23.md`; audit/handoff documentation PR #172 is merged. Next code priority: persistent event hash-chain + sealed provenance and server-derived integrity authorization.
- **Not deployed:** no OCI integrated staging URL, field/device acceptance, real participants, live payments, or dispatch. Protected OCI configuration, state bucket, ingress tightening, correct PostgreSQL/PostGIS authority, host/evidence volume and credentials remain blockers.

## Latest verified checkpoint — 2026-11-22 (PR #165 merged)

- **Main HEAD:** `1f18668b2d9f1cc4e19b49e16c1e66c1313fc116` (PR #165 squash merge).
- **PR #165 — FAOS 16-v2 capture contract:** merged. Tested PR head: `766c0bc99e319e830c626c1fa8d7cacdf1822e9d`. All required workflows passed; full suite: **1026 passed, 31 warnings, 208 subtests passed**. This increment adds migration `0027_capture_protocol_16_v2.sql`, a versioned contract/registry, server API support, browser selection/resume, manifest binding, damage-localization exclusion for non-exterior slots, and compatibility tests.
- **Protocol status:** `claims2car-16-v2` is selectable for controlled testing. `claims2car-16-v1` remains the default; legacy `claims2car-12-v1` remains supported. V2's current 16 positions are eight exterior views, four accessible structural corners, two cabin/restraint views, instrument-cluster telemetry, and physical VIN identity. The manual's second telemetry frame remains an explicit alignment gap; do not silently relabel or alter this immutable version. Field qualification is not complete.
- Browser image quality remains advisory only; it never rejects or changes original evidence. Thresholds are not field calibrated.
- **Next implementation target:** enforce the FAOS forensic integrity contract. Audit found that current `C_hash` can remain nonzero with incomplete/duplicate chains, the backend score uses a weighted geometric mean rather than the manual's weighted sum, and internal dispatch has no strict integrity authorization and falls back to a session ID when photo hashes are absent. Implement fail-closed chain collapse, formula alignment, and dispatch authorization tests before enabling dispatch.
- **Deployment:** OCI staging is still NOT deployed/accepted. Owner-controlled protected-environment/OCI configuration and workflow dispatch remain external blockers; do not request secrets in chat. Continue all code/test work.
- **Thread continuity:** read README, this handoff, status, FAOS manual, and acceptance matrix; inspect live main/PR/check/deployment state; resume the next executable task above without replanning.
## Verified product checkpoint — PR #158, #155, #152 merged (2026-11-22)

- **PR #158** hardened the one-time synthetic runtime credential bootstrap; merged `f96732ec9ecea957aa2bb286a8d824db4b8a220c`, tested head `ce924d5f338cda40e0358ae44a75834c1b1a649f`. Atomic mode-0600 temp writes, fsync, replace, directory sync, symlink refusal, and exclusive lock are implemented.
- Exact PR #158 checks: **16 passed, 3 expected publication skips, 0 failed**. Full suite **1010 passed / 31 warnings / 208 subtests**; restricted containment **224 passed / 20 warnings / 87 subtests**.
- **PR #155** operator progress dashboard merged: `91753175251bb3a13d00dafe7a2692fbb7b88af6`. It reports backend-derived consent, vehicle reference, accepted original count, advisory quality and seal state.
- Exact PR #155 head: `3e9cf110a78c684c3b577f2d5c49193702ec7d95`. **17 successful, 3 skipped, 0 failed**; pytest **987 passed, 31 warnings, 208 subtests**.
- **PR #152** private OCI Run Command deploy mechanism merged: `f63788095986b889a8fb83efd4492aa9c437c03f`. Exact tested head `7f179b6f76484c9031be60762d110334fc1f3110`; **18 successful, 3 skipped, 0 failed**; pytest **1009 passed, 31 warnings, 208 subtests**.
- **Not deployed/operationally accepted:** no public/user-accessible staging URL, live OCI host, PostgreSQL/PostGIS, verified persistent evidence volume, backup/restore rehearsal, or field qualification. OCI environment secrets/variables and state bucket require owner configuration; protected manual workflows cannot be dispatched from this connector.
- Synthetic-only testing; no real participant data, live payments, or dispatch.

**Deferred staging task (historical; not the current engineering priority):** the OCI setup/apply/deploy sequence remains documented below as a future operational task. No staging is deployed or accepted. Do not divert from M1–M8 forensic substantiation to perform this sequence unless a required dependency or owner-approved priority change makes it necessary.

## Deferred staging checklist (retained for later)

Configure the protected OCI environments/state bucket, run reviewed plan/apply, provision private Postgres/PostGIS and evidence storage, deploy immutable image, and verify capture/review, tenant isolation, restart persistence and restore. Do not claim deployment. This is not the active task.



## Verified product checkpoint — PR #154 and #156 merged (2026-11-22)

- **PR #154** `Persist original capture evidence offline and resume uploads` merged: `c77b81d38947621a9f612f0c3402d585e9630ade`. Tested head: `6a4390750faf7d87213f2eaa9b4876aae22eaded`.
- Integrated capture now queues original bytes in IndexedDB before upload, AES-GCM encrypts at rest with HKDF key material derived from the operator token, scopes records by tenant/actor/session, uses stable request/artifact IDs, FIFO fail-stop retry, online auto-retry, and clears ciphertext only after server acceptance. The UI discloses this is not WORM or device-qualified storage.
- Real Chromium/IndexedDB tests cover page-reload recovery, wrong-key fail-closed behavior, FIFO failure/retry, stable IDs, and scoped purge. The CodeQL DOM-XSS alert was resolved by rendering capture previews on canvas instead of assigning user-selected blob URLs directly to image DOM.
- **PR #156** `Show accepted and pending evidence progress in capture` merged: `607a257ac36cc95a224c3f101d46a5884646c40a`. Tested head: `60ae5e627399909502bb3e66e4d8bc358aaadeef`.
- The 16-view progress meter counts only server-accepted originals and separately reports pending local uploads/queue-unverified status; sealing remains blocked until server readiness and local queue scope are verified.
- Exact tested heads for both increments: **17 checks successful, 3 evidence-publication jobs skipped, 0 failures**. Full suite: **987 passed, 31 warnings, 208 subtests passed**. Integrated container smoke and OCI ARM64 build passed; Browser IndexedDB, guided capture, CodeQL, database authority/legacy, FastAPI, VIN, restricted-container, controlled-demo, and intake checks passed.
- Main after PR #156: `607a257ac36cc95a224c3f101d46a5884646c40a`.
- **No deployment/field acceptance:** there is no user-accessible staging URL, live OCI compute, verified PostgreSQL/PostGIS host, durable evidence volume, backup/restore rehearsal, or physical-device qualification. Guarded OCI plan/apply and image-publish workflows exist, but protected environment secrets cannot be inspected or dispatched from this session. Live payments/dispatch remain disabled.

## Current next task — M1 manifest-root chain-tip binding (after PR #182)

From current main, implement migration 0029 to bind manifest roots/seals to verified chain tip, sequence/hash version and deterministic capture context; recompute/validate chain at registration; verify root binding in readback/completion/receipt consumers; then bind registered originals/artifacts and add independent verifier, restart/restore, concurrency, tamper, missing/reorder/fork tests. Keep dispatch/payment disabled. M1 remains incomplete. See authoritative thread handoff and complete forensic specification.

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

**Historical/deferred milestone — OCI deployment:** this remains a staging checklist only; no deployment is accepted and it is not the active priority.

## Verified checkpoint — PR #136 merged (2026-11-21)

- PR #136, **Fail early when OCI protected apply environment is incomplete**, merged to main. Merge commit: `063d1ec61f36b11e2abeecb9791185ebf1a53f9d`; tested head: `49c1f5d5908c4f132d748b5fbe78a69b45bbabad`.
- OCI guarded apply now validates required OCI credentials, compartment/VCN/private subnet/image OCIDs, and remote state bucket/namespace before CLI configuration and Terraform initialization. Missing inputs are named without exposing values.
- The staging runbook now explicitly documents that GitHub environment secrets/variables do not transfer from `oci-staging` to `oci-staging-apply`; configure each environment separately.
- Exact tested head CI: **13/13 workflows successful; 0 failures**, including OCI infrastructure validation and Full test suite.
- This is workflow hardening, not an applied OCI deployment.

**Main after merge:** `063d1ec61f36b11e2abeecb9791185ebf1a53f9d`.

**Deferred staging milestone:** guarded OCI bootstrap/plan/apply, Postgres/PostGIS, durable evidence storage, image publish/deploy and live operational acceptance remain future work after the forensic substantiation focus.

## Verified checkpoint — PR #134 merged (2026-11-21)

- PR #134, **Require source revision integrity for staging acceptance**, merged to main. Merge commit: `8a07d922ef9c091696bd1fc664e9eb377001cbbd`; tested head: `70d88f3ab2276ac1a388fc1be7799df267b03aa5`.
- The OCI synthetic capture acceptance harness now requires a full lowercase 40-character deployed revision, exact match to the local checkout HEAD, and a clean checkout (tracked and untracked files) before creating synthetic acceptance records. Tests cover malformed revision, mismatch, and dirty checkout.
- Exact tested head CI: **12/12 workflows successful; 0 failures** (Full test suite, Browser IndexedDB queue, Legacy database, DB authority cutover, FastAPI, frontend VIN/decoder/transport, offline guided capture, offline VIN controller, controlled demo, controlled PostgreSQL intake, restricted intake container, restricted container verification).
- This protects acceptance evidence against source/image revision misattribution; it does **not** constitute a staging deployment or field acceptance.

**Main after merge:** `8a07d922ef9c091696bd1fc664e9eb377001cbbd`.

**Deferred staging priority:** staging is still not deployed; resume its prerequisite work only after the current forensic program or if a concrete dependency makes it necessary.

## Previous verified checkpoint (post-PR #132 merge; superseded by PR #134 checkpoint above)

- **Main:** `bf0649b6c65ec6d1bdb0d6dbcde8843abdad4122` — PR #132 merged: optional Square Sandbox runtime configuration now passes through OCI bootstrap/runtime deploy. Bootstrap writes five optional Square settings as empty by default; deployment injects them into the integrated container. Tests cover defaults, secret-file permissions, and pass-through. No credentials were committed.
- **PR #127:** Square Sandbox webhook receipt/payment-state reconciliation (migration 0026) merged. HMAC validation, deduplication, tenant-bound order mapping, mismatch/conflict/stale/unmatched outcomes, and synthetic PostgreSQL tests are implemented.
- **PR #121:** structured Vehicle Intelligence Lab assessment JSON, digest, rule-based disposition, escalation, missing-evidence handling and report download verification merged.
- **PR #132 verification:** exact head `ccade1681ce122750160c8a5169fe2b86d821190`; **12/12 distinct workflows successful**. Full suite, DB authority cutover, legacy DB, FastAPI and frontend VIN/decoder/transport checks are green on that candidate. Merge commit is above.
- **PR #127 verification (separate earlier increment):** 13/13 workflows green; 1,185 tests, 0 failures/errors/skips; DB-01–DB-14 14/14; 26 migrations; 17 tenant-scoped tables and 34 tenant-matrix entries. Synthetic CI acceptance, not field validation or production certification.
- **OCI staging remains NOT deployed.** Terraform state bucket, plan/apply, infrastructure, host, Postgres/PostGIS, persistent evidence storage, backup/restore and integrated journey have not been executed/verified. Cloud credentials and protected GitHub environments are not inspectable or dispatchable from this session. The private staging host cannot receive Square webhooks from Square directly; no relay has been reviewed or deployed. Live payments remain disabled.

## Current next task — M1 readback and seal binding (after PR #180)

Continue from current main. Integrate server-owned persisted-chain readback verification; bind manifest roots to verified chain tip, sequence/hash version and capture context; bind registered original/artifacts; then add independent verifier, restart/restore, concurrency, tamper, missing/reorder/fork tests. Keep dispatch/payment disabled. M1 remains incomplete; see the authoritative thread handoff.



## Start-of-thread checklist

Read docs/THREAD_HANDOFF_2026-11-23.md and the forensic program first. Query GitHub live for main, active PRs, exact-head CI and deployment status; continue the remaining M1 code gates without re-planning. OCI is deferred.



## FAOS core-engine premise and thread-resume continuity (owner directive — 2026-11-22)

The full target architecture and subsystem requirements are now codified in [FAOS Core Engine Implementation Guide](architecture/FAOS_CORE_ENGINE_IMPLEMENTATION_GUIDE.md) and linked from README. Treat it as governing product direction: managed field sensor baseline; VIN validation/decode lineage; 16-point capture; quality/stability/audio targets; offline session FIFO; cryptographic artifact and chain verification; gateway and durable persistence; DARCI mechanics; multimodal vision/context; proposed 55/45 consensus and override; integrity scoring; jurisdiction-specific loss criteria; BFPI/dealer path; repair auction; ACORD/report/dispatch and sandbox payment. **Do not treat target values, models, sample XML/IDs, equations, blockchain examples, or commercial formulas as implemented/validated.** Actual maturity is evidenced by the gate matrix, code, exact commit and CI/deployment/field results. Consequential disposition remains human-authorized and unvalidated model output advisory only.

**Resume protocol for any new thread:** Read README, docs/EXECUTION_HANDOFF.md, this file, docs/architecture/FAOS_CORE_ENGINE_IMPLEMENTATION_GUIDE.md, and docs/acceptance/ACCEPTANCE_MATRIX.md. Then query GitHub for current main SHA, PRs, latest exact-head workflow results, and deployment status. Continue directly from the next unfinished verified implementation/deployment task; do not re-plan or ask the founder to restate the mandate. Last documented infrastructure blocker is owner-controlled GitHub protected-environment/OCI credentials and manual workflow dispatch; do not request secrets in chat. Continue all unblockable code/test work meanwhile.


## Canonical full requirements reference

See [complete forensic substantiation specification](docs/forensics/COMPLETE_FORENSIC_SUBSTANTIATION_SPEC.md) for the full owner-directed forensic requirements and scientific validation contract. This status page records the verified implementation state only; the specification does not imply implementation.
