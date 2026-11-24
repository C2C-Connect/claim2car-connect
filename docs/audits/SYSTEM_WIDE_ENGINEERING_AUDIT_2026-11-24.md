# Claim2Car Connect — System-Wide Engineering Audit
**Audit date:** 2026-11-24  
**Repository:** `C2C-Connect/claim2car-connect`  
**Audit branch:** `audit/system-wide-engineering-2026-11-24-final`  
**Status:** IN PROGRESS — source-level findings confirmed; three high-risk remediations merged; remaining report, identity, deletion, storage, market/legal, and field-readiness gaps remain.  
**Purpose:** Determine whether the code actually served and its API/database/evidence/authorization paths support the product claims. This is not a security certification, forensic validation, legal opinion, or field acceptance.

## Audit method and evidence standard

Trace the real entry point through UI → API → service → database/storage → authorization → downstream consumer. For each issue distinguish:
- **Confirmed:** directly visible in current source or a reproduced test.
- **Risk requiring reproduction:** plausible consequence requiring adversarial/integration testing.
- **Not established:** evidence is not currently available; do not infer success or failure.

Do not treat README statements, synthetic tests, a green workflow, or a PR description as proof of production behavior. Do not treat hash integrity as capture authenticity, identity, damage interpretation, or independent notarization.

## Executive assessment

The repository has substantial working infrastructure: tenant-scoped PostgreSQL authority, append-only event history, original-byte storage with digest checks, consent-gated capture, a browser queue with encryption on the canonical root workbench, and an unmerged capture seal/review integration increment under PR #185. These are meaningful foundations.

The system is **not ready for real participant evidence or staging release**. PR #190 (prototype queue metadata authentication), PR #192 (verified event-chain reads in capture/intake history paths), and PR #193 (unverified triage/direct dispatch containment) are now merged to main. The highest-priority remaining trust gaps are:
1. Consent withdrawal and physical deletion are not one durable, per-artifact retryable lifecycle.
2. Two separately served workbenches remain; queue cryptography is now aligned, but UI, workflow, and protocol divergence persists.
3. Identity remains static out-of-band credential provisioning without owner proofing/recovery/revocation UX.
4. Valuation and jurisdiction outputs lack adequate source/effective-date substantiation; the default parts catalog is synthetic seed data.
5. Current-main report generation still has caller-asserted bindings and process-memory versions; the durable evidence-linked report path remains unmerged on PR #186.
6. The legacy in-memory anchor/public verification module remains in the repository and must not be confused with the PostgreSQL provenance authority.
7. Server-side storage encryption, backup/restore, retention, field/device usability, operational monitoring, and deployment acceptance are not established.

## Findings by audit layer

### 1. Evidence integrity & forensic trust

#### AUD-2026-01 — Adjudication trusted caller-supplied integrity facts (P1; remediated by PR #193; server integration remains incomplete)
**Source:** `backend/app/api/triage.py` (`AdjudicateRequest`, `adjudicate`); `backend/app/triage/adjudicate.py`; `backend/app/integrity/s_i.py`.

Before PR #193, the internal adjudication request accepted `master_hash_valid`, `hash_tamper_suspected`, `chain_coverage`, `chain_uniqueness`, `meta_completeness`, `gps_accuracy_m`, `gps_spoof_suspected`, and internal ACV values from the request body. Those values flowed into `compute_s_i` and influenced `hold_for_review`/`final_tier`. The route required the shared internal-service bearer credential and was not an unauthenticated public endpoint. PR #193 removed the request-body contract and now returns HTTP 503 `SERVER_VERIFIED_EVIDENCE_REQUIRED`; triage health reports adjudication disabled. The pure calculation modules remain available for controlled tests only. No caller-provided integrity values can now obtain an adjudication response through this API.

**Remediation status:** the unsafe API composition is contained by PR #193. To re-enable it, build a tenant-bound service that derives verification from original bytes, registered artifact records, sealed manifest, persisted chain tip, consent, vehicle identity, source-backed market data, and effective-dated jurisdiction rules. A chain failure must fail closed. Integrity status alone must never authorize payment or dispatch.

#### AUD-2026-20 — Dispatch builder trusted caller-assembled integrity objects and photo hashes (P1; remediated by PR #193)
**Sources:** `backend/app/dispatch/dispatcher.py`; `backend/app/api/dispatch.py`; `tests/test_dispatch.py`.

Before PR #193, the HTTP `POST /api/v1/dispatch/build` route was hard-disabled, but the directly callable `build_dispatch(adjudication, photo_hashes=...)` function remained enabled and trusted caller-supplied `final_tier`, `final_fork`, integrity fields, and 64-character photo hashes. PR #193 replaced the builder with a fail-closed function that always raises `SERVER_VERIFIED_EVIDENCE_CONTEXT_REQUIRED`; a fabricated passing dictionary or arbitrary hash list can no longer create packages or a process-memory anchor. No production callsite was found, but the direct function boundary is now contained as well.

**Remediation status:** PR #193 enforces the function-level block and adds regression tests for forged passing integrity dictionaries and arbitrary hashes. Re-enable only after a server-issued, tenant-bound verified context binds exact originals, chain tip, manifest root, consent, review disposition, and recipient authorization.

#### AUD-2026-21 — Parts resolver uses a hardcoded seed catalog, not verified OEM/CAPA data (P1 for product claims; confirmed source)
**Source:** `backend/app/catalog/parts_catalog.py`.

The module states directly that it has no external OEM/CAPA APIs and uses admin-managed/CSV-seeded data. Its default catalog is a hardcoded `SEED_PARTS` list containing placeholder identifiers such as `OEM-HOOD-001`, fixed prices, fixed labor hours, and generic applicability by zone/damage class. This is useful for controlled algorithm tests but is not a verified vehicle-specific OEM parts catalog, source-backed supersession table, or current regional estimate. The resolver must not present these entries as verified OEM part numbers, current prices, or vehicle-specific repair procedures.

**Required correction:** label seed records as synthetic/demo data in every output; require a versioned source record and vehicle applicability for verified parts/pricing; keep unsupported components unresolved instead of inventing a part match.

#### AUD-2026-02 — Legacy in-memory anchor remains a misleading parallel verifier (P1/P2; confirmed source)
**Source:** `backend/app/anchor/ledger.py`; `backend/app/api/dispatch.py`.

The legacy `AnchorLedger` is process memory, not the PostgreSQL event authority. Its public verify request accepts `session_id`, `merkle_root`, and `master_hash` from the caller and compares them with the in-process record. The ledger cannot provide durable restart verification or an independent external checkpoint. Dispatch package construction is explicitly disabled pending trusted provenance, which is a useful containment. The legacy verification routes and module must be clearly isolated/retired or explicitly labeled as a non-authoritative compatibility diagnostic so consumers cannot mistake it for current forensic verification.

##### AUD-2026-19 — Persisted-chain readback was bypassed by capture/intake history readers (P1; remediated for identified history paths by PR #192; other metadata-only readers remain to audit)
**Sources:** `database/readback.py`; `database/capture_evidence.py` (`_history`); `database/incident_intake.py`; `migrations/0003_completion_lock.sql`; `authority_migrations/0028_persistent_event_hash_chain.sql`.

Migration 0028 adds database-enforced hash fields, append-time full-chain verification, insert guards, and mutation blocking. PR #182 also added `database/readback.py`, which recomputes the full persisted chain from PostgreSQL rows and fails closed before journal replay. However, the live capture and incident-intake services do not call `load_journal`, `locked_journal`, or `verify_persisted_event_chain` in their history read path. `CaptureEvidenceService._history` and the incident-intake history reader call `faos.lock_session_for_completion` and then select sequence/kind/actor/payload/event ID directly. Migration 0003 shows that function only locks the session row; it does not verify the hash chain. The append function verifies the chain before writes, but that does not prove that every read/decision consumer has recomputed it. I inspected PR #185's exact head as well: it adds a database manifest-root registration/verification path that validates chain prefix/tail and is invoked by seal/review consumers on that branch. That is a meaningful mitigation for sealed manifest/review. It does not change the direct sequence-only `_history` reader itself, and the same pattern remains in incident-intake reads; the PR is also still unmerged.

**Impact:** the repository contains a correct persisted-chain readback primitive and tests, but the principal capture service path still uses a sequence-only history read. On current main, do not infer that all capture, consent, seal, review, and incident-intake consumers are protected merely because the chain columns and readback tests exist. PR #185 appears to close the sealed-manifest/review portion when integrated, but does not by itself establish verified readback for every state/consent/incident-intake read.

**Remediation status:** PR #192 added `locked_verified_journal_in_transaction`, wired it into capture evidence, incident-intake, and controlled VIN draft history, and added a privileged tamper integration test proving capture readiness fails closed. Exact-head CI passed 13/13 workflows; full suite 1,073 passed; DB authority 415/415 and DB-01–DB-14 14/14. **Remaining:** audit metadata-only `CaptureSessionStore._read` and session-list/detail paths, and verify all report/review consumers. PR #185's manifest registration path remains unmerged and must be rebased/reverified.

### AUD-2026-03 — Canonical root queue encryption is implemented; second workbench remains divergent (P1; confirmed source)
**Sources:** `app/main.py`; `app/web/index.html`; `app/web/assets/app.js`; `app/web/assets/offline_evidence_queue.mjs`; `frontend/app/index.html`; `frontend/app/app.mjs`; `frontend/app/offline_evidence_queue.mjs`.

The root integrated shell is served from `app/web/index.html` at `/`. It imports the root queue module, passes the transient operator token as key material, and the current root queue uses HKDF/AES-GCM with authenticated additional metadata and a migration path for legacy plaintext records. The separate `frontend/app` workbench is also mounted at `/prototype`; it remains a distinct UI/runtime. Its queue initially used AES-GCM without authenticated additional metadata. PR #190 is now merged and replaces that prototype queue with the same HKDF/AES-GCM v2 metadata-authentication contract as the root queue, preserving the prototype IndexedDB database and migrating prior ciphertext only after digest/length verification. The cryptographic drift is therefore remediated on main, but the two independently served workbenches and their workflow/protocol divergence remain.

**Remediation status:** PR #190 unified the queue cryptographic contract and added Node/Chromium tamper and migration tests. **Remaining:** converge on one canonical UI entry; retire or migrate unique prototype functionality; test token loss, expiry/rotation, browser eviction, device loss, and remote cleanup. The encrypted browser queue remains defense in depth, not a secure enclave or WORM store.

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

#### AUD-2026-22 — Report generation trusts caller-asserted bindings and keeps versions in process memory (P1; confirmed source)
**Source:** `backend/app/reports/forensic_pdf.py` (`build_dossier`, `FourTierDossierService`, `_verify_consent_and_review`, `_store_version`).

The legacy seven-page `build_dossier(payload)` renders caller-provided `final_fork`, `final_tier`, integrity, valuation, physics, and detection fields without validating evidence references or a verified finding graph. The newer `FourTierDossierService` is more structured, but its `SourceEvidenceBinding` is a caller-constructed dataclass. `_verify_consent_and_review` checks that manifest digest, reviewer actor, and artifact-ID list are nonempty; it does not retrieve/verify those values from PostgreSQL or the evidence store. `_store_version` persists generated versions in the service instance's `self._versions` dictionary, so versions do not survive process restart and are not a durable, tenant-enforced report registry. The existing pages summarize artifact counts/IDs and selected values; they do not yet provide the required per-finding image annotations, bounding boxes/masks, view/angle, calibrated measurement method, uncertainty, and traceable observation-to-conclusion graph.

**Required correction:** generate reports only from a server-issued verified evidence/review context; persist immutable document versions and revision lineage in PostgreSQL/object storage; bind each annotation to an original artifact and coordinates; bind every measurement to method/calibration/uncertainty; bind each conclusion to findings and alternatives; verify report bytes and source manifest on retrieval. Until then, treat generated dossiers as controlled-test templates, not defensible forensic reports.

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
- PR #185 remains open at head `a7174d45a02cc6b8312a00b1ca31671019726728`; compared with current main it is 56 commits ahead and 3 behind (main advanced through PR #190, #192, and #193). Its previously reported exact-head CI is stale; rebase and rerun before merge.
- PR #186 remains open at head `0a4b6087049d2483d8cf4ecc68fa0faaaa3126de`, stacked on an earlier PR #185 head `0431dbaf6e1a3bb3348f6d94c094e893543e513c`. Its current branch describes a durable PDF/JSON report registry with image annotations, normalized bounding boxes, capture-angle provenance, reviewer linkage, and fresh-process retrieval tests; it still needs rebase onto the updated PR #185/main stack and exact-head CI. It is not current-main capability.
- PR #187 records technical DB gates separately from release gates; release acceptance remains NOT ACCEPTED.
- PR #193 merged as `26edf9da1bb293dd48f46723b5014ee5d2c44066`: triage adjudication and direct dispatch package building now fail closed until a server-verified evidence context exists. Exact-head CI passed 13/13 workflows; full suite 1,070 passed; DB authority 415/415 and DB-01–DB-14 14/14.
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
