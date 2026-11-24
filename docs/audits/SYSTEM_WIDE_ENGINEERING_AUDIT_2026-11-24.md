# Claim2Car Connect — System-Wide Engineering Audit
**Audit date:** 2026-11-24  
**Repository:** `C2C-Connect/claim2car-connect`  
**Audit branch:** `audit/system-wide-engineering-2026-11-24`  
**Status:** IN PROGRESS — source-level findings confirmed; adversarial and integration reproduction still required.  
**Purpose:** Determine whether the code actually served and its API/database/evidence/authorization paths support the product claims. This is not a security certification, forensic validation, legal opinion, or field acceptance.

## Audit method and evidence standard

Trace the real entry point through UI → API → service → database/storage → authorization → downstream consumer. For each issue distinguish:
- **Confirmed:** directly visible in current source or a reproduced test.
- **Risk requiring reproduction:** plausible consequence requiring adversarial/integration testing.
- **Not established:** evidence is not currently available; do not infer success or failure.

Do not treat README statements, synthetic tests, a green workflow, or a PR description as proof of production behavior. Do not treat hash integrity as capture authenticity, identity, damage interpretation, or independent notarization.

## Executive assessment

The repository has substantial working infrastructure: tenant-scoped PostgreSQL authority, append-only event history, original-byte storage with digest checks, consent-gated capture, a browser queue with encryption on the canonical root workbench, and a live capture seal/review integration increment under PR #185. These are meaningful foundations.

The system is **not ready for real participant evidence or staging release**. The highest-priority remaining trust gaps are:
1. Integrity/adjudication inputs are caller assertions rather than server-derived verified evidence facts.
2. Consent withdrawal and physical deletion are not one durable, retryable lifecycle.
3. Two independently served workbenches contain materially different offline queue cryptography and behavior.
4. Identity remains static out-of-band credential provisioning.
5. Valuation and jurisdiction outputs lack adequate source/effective-date substantiation.
6. The legacy in-memory anchor/public verification path remains in the repository and must not be confused with the newer PostgreSQL provenance authority.
7. Field, device, backup/restore, operational monitoring, and deployment acceptance are not established.

## Findings by audit layer

### 1. Evidence integrity & forensic trust

#### AUD-2026-01 — Adjudication trusts caller-supplied integrity facts (P1; confirmed source gap)
**Source:** `backend/app/api/triage.py` (`AdjudicateRequest`, `adjudicate`); `backend/app/triage/adjudicate.py`; `backend/app/integrity/s_i.py`.

The internal adjudication request accepts `master_hash_valid`, `hash_tamper_suspected`, `chain_coverage`, `chain_uniqueness`, `meta_completeness`, `gps_accuracy_m`, and `gps_spoof_suspected` from the request body. These values are passed directly into `compute_s_i`. The resulting integrity tier influences `hold_for_review` and `final_tier`. The route requires the shared internal-service bearer credential and is mounted under the internal route prefix; this audit has not established an unauthenticated public exploit. The defect is the trust boundary: the service does not derive these values by independently reading and verifying the session's registered artifacts, manifest, and persisted chain at this decision point.

**Required correction:** adjudication must consume a server-generated verification result bound to the session and exact sealed manifest. Caller-supplied integrity booleans/fractions must be rejected or treated as non-authoritative diagnostics. A chain failure must fail closed. Integrity status alone must never authorize payment or dispatch.

#### AUD-2026-20 — Dispatch builder trusts caller-assembled integrity objects and photo hashes (P1; confirmed source, HTTP route contained)
**Sources:** `backend/app/dispatch/dispatcher.py`; `backend/app/api/dispatch.py`; `tests/test_dispatch.py`.

The HTTP `POST /api/v1/dispatch/build` route is correctly hard-disabled with HTTP 503 and does not call the builder. However, the directly callable `build_dispatch(adjudication, photo_hashes=...)` function remains enabled. Its authorization gate trusts a caller-provided dictionary containing `final_tier`, `final_fork`, and an `integrity` object with `s_i`, `tier`, `c_chain`, `c_hash`, and `all_or_nothing_collapse`. It also accepts caller-supplied 64-character photo hashes without retrieving originals or verifying them against a registered manifest. A fabricated dictionary can therefore satisfy the Python builder's integrity gate and generate role-specific packages plus a process-memory anchor if an internal caller invokes it. I found no production callsite for `build_dispatch` in the repository; current HTTP containment prevents the public route from reaching it.

**Required correction:** keep the builder disabled at the function boundary until it accepts a server-owned, tenant-bound, manifest-verified evidence context that it cannot be forged from JSON/dict fields. The authorization object must be constructed only by the trusted evidence verifier; it must bind exact original artifact hashes, chain tip, manifest root, consent, review disposition, and recipient authorization. Tests must prove caller-created dictionaries and hash lists cannot create packages or ledger entries.

#### AUD-2026-21 — Parts resolver uses a hardcoded seed catalog, not verified OEM/CAPA data (P1 for product claims; confirmed source)
**Source:** `backend/app/catalog/parts_catalog.py`.

The module states directly that it has no external OEM/CAPA APIs and uses admin-managed/CSV-seeded data. Its default catalog is a hardcoded `SEED_PARTS` list containing placeholder identifiers such as `OEM-HOOD-001`, fixed prices, fixed labor hours, and generic applicability by zone/damage class. This is useful for controlled algorithm tests but is not a verified vehicle-specific OEM parts catalog, source-backed supersession table, or current regional estimate. The resolver must not present these entries as verified OEM part numbers, current prices, or vehicle-specific repair procedures.

**Required correction:** label seed records as synthetic/demo data in every output; require a versioned source record and vehicle applicability for verified parts/pricing; keep unsupported components unresolved instead of inventing a part match.

#### AUD-2026-02 — Legacy in-memory anchor remains a misleading parallel verifier (P1/P2; confirmed source)
**Source:** `backend/app/anchor/ledger.py`; `backend/app/api/dispatch.py`.

The legacy `AnchorLedger` is process memory, not the PostgreSQL event authority. Its public verify request accepts `session_id`, `merkle_root`, and `master_hash` from the caller and compares them with the in-process record. The ledger cannot provide durable restart verification or an independent external checkpoint. Dispatch package construction is explicitly disabled pending trusted provenance, which is a useful containment. The legacy verification routes and module must be clearly isolated/retired or explicitly labeled as a non-authoritative compatibility diagnostic so consumers cannot mistake it for current forensic verification.

##### AUD-2026-19 — Capture service read paths bypass persisted-chain recomputation (P1; confirmed source)
**Sources:** `database/readback.py`; `database/capture_evidence.py` (`_history`); `database/incident_intake.py`; `migrations/0003_completion_lock.sql`; `authority_migrations/0028_persistent_event_hash_chain.sql`.

Migration 0028 adds database-enforced hash fields, append-time full-chain verification, insert guards, and mutation blocking. PR #182 also added `database/readback.py`, which recomputes the full persisted chain from PostgreSQL rows and fails closed before journal replay. However, the live capture and incident-intake services do not call `load_journal`, `locked_journal`, or `verify_persisted_event_chain` in their history read path. `CaptureEvidenceService._history` and the incident-intake history reader call `faos.lock_session_for_completion` and then select sequence/kind/actor/payload/event ID directly. Migration 0003 shows that function only locks the session row; it does not verify the hash chain. The append function verifies the chain before writes, but that does not prove that every read/decision consumer has recomputed it. I inspected PR #185's exact head as well: it adds a database manifest-root registration/verification path that validates chain prefix/tail and is invoked by seal/review consumers on that branch. That is a meaningful mitigation for sealed manifest/review. It does not change the direct sequence-only `_history` reader itself, and the same pattern remains in incident-intake reads; the PR is also still unmerged.

**Impact:** the repository contains a correct persisted-chain readback primitive and tests, but the principal capture service path still uses a sequence-only history read. On current main, do not infer that all capture, consent, seal, review, and incident-intake consumers are protected merely because the chain columns and readback tests exist. PR #185 appears to close the sealed-manifest/review portion when integrated, but does not by itself establish verified readback for every state/consent/incident-intake read.

**Required correction:** route all security-sensitive history consumers through one tenant-scoped, locked, server-owned verified readback in the same transaction/lock as the state evaluation. Ensure the manifest registration/review path uses the verified chain tip and exact artifact set. Add integration tamper tests that mutate stored hashes through a privileged test fixture and prove capture readiness, consent, seal, incident intake, review queue/detail, and report generation all fail closed. PR #185 describes a seal/review integration correction but remains unmerged; verify its exact branch implementation and CI before relying on it.

### AUD-2026-03 — Canonical root queue encryption is implemented; second workbench remains divergent (P1; confirmed source)
**Sources:** `app/main.py`; `app/web/index.html`; `app/web/assets/app.js`; `app/web/assets/offline_evidence_queue.mjs`; `frontend/app/index.html`; `frontend/app/app.mjs`; `frontend/app/offline_evidence_queue.mjs`.

The root integrated shell is served from `app/web/index.html` at `/`. It imports the root queue module, passes the transient operator token as key material, and the current root queue uses HKDF/AES-GCM with authenticated additional metadata and a migration path for legacy plaintext records. The separate `frontend/app` workbench is also mounted at `/prototype`; it has its own queue implementation. That implementation uses AES-GCM but does not bind the record metadata as authenticated additional data. The root shell links users to prototype pages. The two independently served paths therefore do not share one queue contract or equivalent metadata integrity protections.

**Required correction:** converge on one queue implementation and one canonical UI entry. Until the migration is complete, the prototype must not be treated as equivalent to the root workbench; tests must explicitly cover each served route and its queue behavior. The encrypted browser queue remains defense in depth, not a secure enclave or WORM store. Token loss, expiry, rotation, browser eviction, device loss, and legacy plaintext migration need explicit recovery behavior.

### 2. Capture mechanics & roadside usability

#### AUD-2026-04 — 16-v1 collects sensitive documents by default; 16-v2 is not the default (P1; confirmed contract)
**Sources:** `contracts/shot-list-16-v1.json`; `app/web/index.html`; `docs/release/CAPTURE_PROTOCOL_VERSIONING.md`; capture protocol registry.

The approved default `claims2car-16-v1` includes driver's-license and insurance-document slots. The additive `claims2car-16-v2` contract replaces those two slots with safer structural-corner and cabin/telemetry/identity views and treats documents as supplemental, separately necessary and consented. The versioning document states v1 remains the default until disclosure, rollout, and field qualification are reviewed. The root workbench's hardcoded selector exposes 16-v1 and legacy 12-v1, while its explanatory text discusses v2. The actual registry-driven prototype has a separate UI path. This is both a data-minimization issue and a cross-UI protocol drift risk.

**Required correction:** decide and implement one consistent protocol-selection/disclosure policy; do not collect license/insurance imagery unless the separate purpose and consent justify it. Preserve historical protocol identity and never relabel sessions. Validate safe standing positions, exception/resume, device/browser behavior, and real roadside usability before field use.

#### AUD-2026-05 — Quality is advisory and client-reported at the persistence boundary (P2; confirmed source)
**Sources:** `app/capture_api.py`; `database/capture_evidence.py` (`record_quality`); `app/quality_gate.py`; `app/web/assets/app.js`.

The API accepts a map of slot → boolean and persists it with `advisory_only: true`. The separate quality-gate module can calculate blur/exposure/occlusion/flatness metrics from supplied pixels, but the persisted evidence service accepts booleans, not independently recomputed metrics tied to the exact original bytes. The UI correctly describes these results as advisory and not certification. Therefore the persisted event is an operator/client assertion of advisory checks, not a server-verifiable quality assessment.

**Required correction:** preserve advisory status in all consumers and reports. If a quality result is to gate a consequential workflow, bind its metrics, algorithm version, and exact artifact digest to server-verified originals or independently reproduce the check. Do not silently promote a boolean to a verified quality fact.

### 3. Identity, consent & security

#### AUD-2026-06 — Identity remains an out-of-band static credential model (P1; confirmed source)
**Source:** `app/identity.py`.

Credential resolution checks a configured SHA-256 token digest, enabled flag, and expiry. Revocation requires configuration reload. There is no owner self-enrollment, identity proofing, invitation/recovery, self-service credential rotation, or live revocation workflow. Server-side role/tenant binding and database authorization remain important controls, but this is controlled-test identity, not a field-ready owner identity lifecycle.

**Required correction:** design and implement revocation/rotation, recovery, owner identity proofing, operational credential issuance, and audit trails before participant use. Do not expose test credentials or place raw tokens in logs/storage.

#### AUD-2026-07 — Consent withdrawal can commit before original-file deletion completes (P1; confirmed source)
**Source:** `database/capture_evidence.py` (`record_consent`).

The withdrawal event and related database revocations occur inside the authorized PostgreSQL transaction. Original artifacts are deleted from the POSIX store after that transaction exits. If deletion fails partway through, the database records withdrawn consent while one or more originals can remain. The API response reports a deletion count; there is no durable per-artifact deletion receipt/outbox or background retry worker in this method. There is one useful recovery behavior: replaying the same idempotent withdrawal request re-reads the append-only artifact registrations and attempts deletion again, so a caller retry can recover a transient failure. That is not durable autonomous recovery and provides no per-artifact status. The root UI purges the local queue only after receiving a successful server response. An offline device cannot receive immediate withdrawal and may retain local ciphertext until it reconnects and the owner/operator can complete cleanup.

**Required correction:** implement a durable deletion/revocation workflow with per-artifact state, idempotent retries, reconciliation, explicit retention exceptions, and a truthful receipt distinguishing confirmed server deletion from pending remote-device cleanup and backup expiry. Never claim global deletion based on one successful HTTP response.

### 4. Data architecture & persistence

#### AUD-2026-08 — POSIX artifact storage verifies bytes but does not itself encrypt them (P1; confirmed source)
**Source:** `app/artifact_storage.py`.

The byte store validates SHA-256 on write/read, uses tenant/session/artifact UUID path scoping, no-follow file operations, restrictive file modes, atomic linking, and fsync. The module contains no application-level encryption. Encryption at the underlying volume/provider layer is not established by this source inspection and must be separately verified. The database journal and file store also have a cross-system transaction boundary: database event and filesystem write/delete cannot be assumed atomic without explicit recovery/reconciliation.

**Required correction:** establish and test encrypted persistent volume/object-store configuration, key management, rotation, restore, orphan reconciliation, and atomicity/recovery behavior. Do not infer encryption from filesystem permissions or a successful hash check.

#### AUD-2026-09 — Withdrawal deletion and storage reconciliation need durable state (P1; confirmed source)
The file store is a POSIX byte store while metadata and authorization live in PostgreSQL. A filesystem write/delete and a PostgreSQL transaction are not a single atomic transaction. The current withdrawal method's post-commit deletion makes this concrete. The same boundary requires tests for upload-write success followed by journal failure, journal retry, missing/orphaned files, and crash/restart between operations.

### 5. AI, physics & decision mechanics

#### AUD-2026-10 — ACV values are not source-backed market observations (P1; confirmed source)
**Sources:** `backend/app/api/triage.py`; `backend/app/valuation/acv.py`.

The adjudication API accepts three internal ACV numbers from the request (with fixed defaults); if absent, `compute_acv` uses `max(4000, 32000 × 0.86^age)`. The result records a generic source label such as `internal_a` or `fallback_curve`, but not a source record, comparable vehicle identity, geography, mileage/condition, retrieval timestamp, or freshness. This is a deterministic calculation, not verified current market valuation.

**Required correction:** use source records with provenance, effective/retrieved timestamps, comparable attributes, normalization, and uncertainty. Label the age curve as a coarse illustrative fallback and prevent it from supporting a market-verified or consequential total-loss conclusion.

#### AUD-2026-11 — Jurisdiction rules lack per-rule authority and effective dates (P1; confirmed source)
**Source:** `backend/app/jurisdiction/thresholds.py`.

The 50-state/DC table is hardcoded with numeric thresholds and short notes; there are no per-rule authority citations, effective dates, review dates, jurisdiction-specific source versions, or change history in the rule objects. Unknown jurisdiction silently receives a generic 75% fallback. A legal/statutory determination must not rely on an undocumented generic fallback.

**Required correction:** version each rule with authoritative source, citation, effective interval, jurisdiction, method, review owner/date, and explicit unknown/out-of-scope handling. Return `undetermined / legal review required` rather than silently applying a generic rule where no supported rule exists.

#### AUD-2026-12 — Legacy analysis endpoint is explicitly synthetic, not real vehicle-image inference (P1 for product claims; confirmed source)
**Sources:** `backend/app/api/analysis.py`; `backend/app/api/triage.py`.

The analysis route constructs synthetic placeholder bytes from the session ID; it does not ingest vehicle photographs. Its health response identifies stub models and `vehicle_images_supported: false`; its response marks the decision simulated and not an appraisal. This is appropriately disclosed in the route, but these outputs must not be surfaced as actual damage detection, measurements, or appraisals. The triage route accepts caller-provided detections/depths and therefore is not an evidence-to-finding pipeline.

### 6. Workflow & state machines

#### AUD-2026-13 — Quality and seal are separate events; quality payload is advisory
The capture service verifies registered originals and session protocol before recording quality and sealing, but the quality event contains client-supplied boolean results marked advisory. Tests must explicitly prove that false advisory results cannot be misrepresented as verified quality or as a reason to infer absence/presence of damage. State-machine acceptance must cover consent withdrawal races, duplicate requests, retries, post-seal changes, pause/exception resolution, and review actor separation.

#### AUD-2026-14 — Cross-store crash/retry behavior is not yet proven end-to-end
PostgreSQL transactions and POSIX artifact operations are separate resources. Exact retry, crash recovery, orphan reconciliation, and partial deletion behavior need fault-injection coverage. A green DB-only suite does not prove file-store atomicity/recovery.

### 7. Commercial & operational mechanics

#### AUD-2026-15 — Dispatch package construction is disabled (confirmed containment)
**Source:** `backend/app/api/dispatch.py`.

The HTTP dispatch builder returns a disabled response and explicitly states trusted provenance is not integrated. Keep dispatch, partner routing, and consequential financial actions disabled until evidence-derived authorization, recipient scoping, consent, idempotency, ledger reconciliation, dispute/cancellation, and durable outbox recovery are verified. The presence of commercial ledger classes or a synthetic demonstration is not operational activation.

#### AUD-2026-16 — Payment and partner lifecycle release acceptance is not established
No current source-level evidence in this audit establishes a live, end-to-end, authorized Square transaction lifecycle, dealer/shop acceptance, settlement reconciliation, or production dispute recovery. Keep sandbox/live credentials and actions gated. The release acceptance registry and exact operational evidence must be reviewed before enabling any such behavior.

### 8. Product usability & performance

#### AUD-2026-17 — Two separately served workbenches are visible to operators (P1; confirmed source)
The root workbench links directly to `/prototype/vehicle-lab.html`, and `app.main` mounts the `frontend/app` directory at `/prototype`. The prototype has its own capture UI, protocol loading, and queue. This creates a real route-switch and behavior-drift surface, not merely unused source code.

**Required correction:** one canonical entry point and shared components/contracts. Retire or clearly isolate the prototype after migrating any unique lab functionality. Add route tests proving users cannot accidentally enter a stale workflow.

#### AUD-2026-18 — Field usability, accessibility, latency, and device qualification are not established
Synthetic browser/IndexedDB workflows prove only the tested browser behavior. They do not establish roadside usability under glare, rain, gloves, poor connectivity, low battery, storage pressure, camera permission denial, device loss, or accessibility needs. No real-device field study or performance acceptance is evidenced here. Do not describe the capture workflow as field-qualified.

## Current implementation / release state observed

- Main README describes PR #182 as merged and identifies PostgreSQL hash persistence in migration 0028.
- PR #185 is an open implementation increment for chain/context-bound manifest registration in the live seal/review path. Its description reports exact-head CI of 13/13 workflows, full suite 1,283 tests with zero skips, DB authority 408/408 and DB-01–DB-14 14/14. This is a PR-reported verification result, not an independent audit reproduction or release approval.
- PR #186 is an evidence-linked PDF report increment stacked on PR #185; it is not independently mergeable until its base is integrated and exact-head checks rerun.
- PR #187 records technical DB gates separately from release gates; release acceptance remains NOT ACCEPTED.
- PR #188 proposes OCI staging architecture only; no infrastructure was provisioned by that proposal.
- The integrated application is not yet deployed and operationally accessible to the founder. No real participant evidence, live payment, or dispatch activity is authorized by these code checks.

## Remediation order

1. Replace caller-asserted integrity inputs at adjudication with a server-derived, manifest-bound verification result.
2. Make consent withdrawal and artifact deletion a durable, idempotent, reconciled workflow; prove partial-failure recovery.
3. Unify the two served workbenches and queue cryptographic contract; authenticate all queue metadata; define token loss/rotation recovery.
4. Complete owner identity and credential lifecycle before participant evidence.
5. Make ACV and jurisdiction decisions source-backed, time-versioned, and explicit about unsupported cases.
6. Verify server-side storage encryption, backups, restore, retention, orphan cleanup, and cross-store crash recovery.
7. Keep synthetic analysis, heuristic quality, and dispatch clearly bounded; implement one evidence-linked calibrated measurement slice before broader AI claims.
8. Run field/device/accessibility/performance validation and only then consider staging/field release gates.

## Explicit limitations of this audit checkpoint

This is a source-level audit checkpoint, not a complete audit. The following still require execution/reproduction: adversarial HTTP tests for integrity input spoofing; database/file-store fault injection; multi-tenant authorization and credential revocation tests; browser tests for both served queue implementations, token expiry/rotation and metadata tampering; capture UX/device tests; authoritative legal-rule review; market-data source integration/validation; backup/restore and deletion-retention drills; payment/outbox failure testing; and independent forensic measurement validation.

No merge, deployment, public release, real participant evidence, payment activation, or dispatch activation is authorized by this document.
