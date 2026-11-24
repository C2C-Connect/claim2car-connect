# Claim2Car — authoritative thread handoff / current engineering state

## 0. Current checkpoint — 2026-11-24

- **PR #184 merged:** `55f69790df123a4602196c3c474e143808c4b87e`; exact tested head `95692eaf30f76ca9ab8b7c0cf71c4bcf9fac5d68`; 13/13 workflows passed. Full suite 1,064 passed, 7 skipped, 31 warnings, 218 subtests. Authority suite 407/407 counted tests; DB-01–DB-14 14/14 PASS; 340 tenant-isolation assertions.
- **M1 database chain/context binding is merged.** Do not repeat migration 0029 or describe M1 as wholly complete: the live capture service still needed to register the root at seal time.
- **Active PR #185:** [runtime manifest registration](https://github.com/C2C-Connect/claim2car-connect/pull/185), branch `cto/m1-runtime-manifest-registration`, current branch head (verify live PR #185 before acting). Migration 0030 adds a narrow SECURITY DEFINER app path; the live seal transaction registers and verifies the root; review consumers fail closed without a valid root; exact 12-v1/16-v1/16-v2 slot sets are checked. The first CI run found an owner-transfer schema privilege error and stale 29-migration test fixtures. The migration now grants schema CREATE only for ownership transfer and immediately revokes it; fixtures and gate inventory were updated. A subsequent run exposed reviewer requests passing the reviewer actor rather than the original seal actor; this is corrected. The migration backfill-gap fixture now seeds before migration 0028's append guard, and checksum/order tests target migration 0030. Corrected-head CI is pending.
- **Merge gate:** all 13 workflows green and DB-01–DB-14 accepted on the exact latest head. PR #185 is not merged.
- **Next after PR #185:** M2 original-artifact provenance and metadata; then observation/finding persistence, calibrated geometry/measurement, source-backed technical assessment, and deterministic report generation. The legacy in-memory four-tier PDF service is not an acceptable production report pipeline.
- **Release boundary:** no deployment, external notarization, trusted timestamp, field accuracy qualification, participant evidence, live payment or dispatch is claimed.

**Active branch:** `cto/m1-runtime-manifest-registration`
**Active PR:** #185
**Canonical base:** `main`

---

## 0. Latest verified checkpoint — persisted readback verification merged (2026-11-23)

- **Main merge:** PR #182 squash-merged as `f0c6fbfc7d0278e77964a45004e0e42ede7a8146`. PR #180 is the previous merged increment; PR #176 was superseded and closed.
- **Exact tested PR #182 head:** `668785ea465b807932e63fdb6a555ed419099b6b`; **13/13 GitHub workflows passed**.
- **Full repository suite:** **1,054 passed, 31 warnings, 219 subtests passed**.
- **PostgreSQL authority acceptance:** **390/390 counted DB tests passed**; DB-01 through DB-14 **14/14 PASS / 14 gate passes awarded**, diagnostics successful and overall database acceptance ACCEPTED on isolated synthetic PostgreSQL. This is database-authority acceptance, not forensic M1 acceptance or field qualification.
- **Merged implementation:** migration 0028 persists SHA-256 previous/entry hashes and hash version, transactionally backfills, fails on sequence gaps, and append verifies the chain. PR #182 adds server-owned `database/readback.py` recomputation from PostgreSQL rows; `load_journal` and `locked_journal` fail closed on invalid authority-schema chains; explicit `LEGACY_UNHASHED` compatibility; partial hash schema fails closed. Tamper, tenant, locked-consumer, legacy and partial-schema tests passed.
- **M1 remains incomplete:** sealed manifest/root does not yet bind verified chain tip, sequence, hash version and context; registered original/artifact binding and independent verifier agreement remain; restart/restore/concurrency/fork and independent checkpoint acceptance remain.
- **Release state:** no staging deployment, field/participant evidence, live payment or dispatch. Those gates remain closed.

### Next executable work

Continue from main with **manifest-root chain-tip/context binding**: migration 0029 should persist seal-event chain hash/sequence/hash version and a deterministic context commitment; registration must recompute/validate the persisted chain and seal record before idempotent registration; readback/completion/receipt consumers must verify root binding. Then bind original artifact records to the registered manifest, implement independent verifier/recovery/adversarial tests and execute the M1 gate. External checkpoint/signature/trusted timestamp is separate and must not be represented as provided by the database chain.

**Snapshot date:** 2026-11-23 (America/Chicago)
**Canonical product repository:** C2C-Connect/claim2car-connect
**Canonical product branch:** main
**Active forensic implementation branch:** main
**Latest implementation increment:** [PR #182 — persisted-chain readback verification](https://github.com/C2C-Connect/claim2car-connect/pull/182) — merged
**Owner mandate:** execute real product work autonomously; no planning loops, placeholder/mock work, or claims without evidence. This file is the detailed handoff; check GitHub live because commit/check status can change.

## 1. Mission and product truth

Claim2Car / FAOS is to substantiate meaningful claims about an incident, vehicle, evidence, observation, measurement, damage assessment, technical repair assessment, and report. The differentiator is defensible, traceable forensic intelligence—not photo volume, a VIN decoder, a hash badge, or an AI label. Focus remains forensic substantiation until a narrow end-to-end vertical slice is implemented and validated.

Target first slice: **one controlled vehicle + one component + one bounded damage region + one calibrated measurement + one evidence-linked finding + one reproducible report**. Synthetic known-answer fixtures first; then controlled, non-participant test-vehicle measurements; then blind/held-out validation.

## 2. Non-negotiable evidence and epistemic rules

- Preserve original bytes. Crops, masks, OCR, normalized/aligned imagery, annotations, model outputs, and reports are separate derivatives with parent/source links and reproducible transformations.
- SHA-256 establishes byte equality for the bytes hashed; it does not prove capture time/place/device, vehicle identity, authenticity, interpretation, causation, or completeness.
- A chain detects edits relative to a trusted anchor/checkpoint. An unanchored chain under the same compromised database authority is not independent notarization. Hashes, Merkle roots, digital signatures, trusted timestamps, and blockchain anchoring are distinct mechanisms and must not be conflated.
- Distinguish source evidence, objective observation, measurement, classification, inference, collision association, causation, hidden damage, repair advice, and final conclusion.
- Every claim must link to source(s), method/model and version, inputs, parameters, result, units, uncertainty, limitations, alternatives, validation scope, and review state. Unknown/inconclusive/conflicting is first-class; no fabricated precision.
- Pixels do not become metric dimensions without valid calibration, pose, scale, geometry and uncertainty. Never imply hidden parts were inspected from imagery alone.
- VIN/vehicle configuration, parts/OEM applicability and repair procedures must be source-backed with lineage, revision/effective date, market/configuration applicability and discrepancies.
- Models are advisory until scoped validation and calibration are demonstrated; no forensic certification, field accuracy, causation or roadworthiness claim absent relevant evidence.
- Dispatch, payment, dealer/shop release, and other consequential actions require independent authorization; forensic/integrity status alone cannot authorize them.

## 3. Ordered program (M0–M8)

1. **M0 contracts:** canonical versioned evidence reference, observation, measurement, finding, inference, method, uncertainty, review and report models. Units and coordinate conventions. Validate references; unknown/inconclusive supported.
2. **M1 persistent provenance/full verification — FIRST ACTIVE CODE TARGET:** persistent tenant/session event chain; manifest/seal and registered-original binding; full recomputation; independent verifier agreement; explicit checkpoint/trust semantics.
3. **M2 evidence/artifact binding:** server-registered original bytes, IDs, digest, size, MIME/type, capture/consent metadata, manifest membership, derivative parent links and authenticity boundary.
4. **M3 VIN/configuration:** capture and preservation, OCR derivative, VIN syntax/check digit where applicable, decode provider/source/version/date/raw response handling, cross-checks and ambiguity; no inferred trim/options.
5. **M4 camera geometry/capture:** immutable versioned 16-view protocol and legacy compatibility; camera intrinsics/distortion, pose/extrinsics, landmarks, coordinate frame, scale, alignment deviations, calibration, silhouette/projection and uncertainty.
6. **M5 damage localization + one validated measurement:** one component/region; segmentation/landmarks/cross-view correspondence; calibrated metric geometry; residuals and uncertainty; known-answer synthetic tolerance and independent reference comparison.
7. **M6 technical assessment:** supported OEM repair/replace procedures, parts applicability/supersession, safety/diagnostic/disassembly needs and source revisions; provisional/inspection-required state.
8. **M7 deterministic report:** structured, versioned/reproducible PDF + machine-readable report; all provenance, coverage, observations, measurements/method/units/uncertainty, finding rationale, source references, alternatives, limitations, reviewer, revision and integrity status. Preserve issued versions.
9. **M8 qualification:** curated/synthetic ground truth, separate development/calibration/held-out sets, blind evaluation, failure analysis, reviewer agreement, calibrated confidence and test-device/environment matrix; thresholds specified before held-out test. No accuracy claim until scoped validation.

Do not drift into payments, dispatch, marketplace, broad AI, polish, speculative anchoring, or deployment tasks while the forensic slice is incomplete, except necessary security/operational blockers. Deployment/field qualification is a separate gate.

## 4. M1 source reconnaissance — actual existing mechanisms and gaps

Reuse the current PostgreSQL authority and event/manifest systems; do **not** create a parallel database or ledger.

- migrations/0002_event_journal.sql: tenant/session scoped faos.events, unique event IDs and sequence, session FK, RLS/FORCE RLS, faos.append_event session locking, idempotent duplicate handling and next-sequence validation. Persistent rows do **not** currently carry previous/event cryptographic hashes.
- database/journal.py: calls SQL append under tenant transaction.
- database/readback.py: sequence replay/readback; no independent cryptographic recomputation.
- app/domain_events.py: Python canonical JSON dialect. migrations/0007_event_payload_compactness.sql compacts whitespace outside strings only; key ordering, Unicode escaping and numeric spelling parity are unresolved. Do not claim Python/SQL parity until tested.
- migrations/0004_manifest_roots.sql and 0019_manifest_root_protocol_binding.sql: manifest digest, capture protocol, seal event, registration time, tenant/protocol/session controls. Does not yet bind a verified chain tip, full context, consent/quality/exceptions or external checkpoint.
- app/evidence_manifest.py: synthetic byte-integrity checks; manifest commits session/protocol/entries (artifact IDs, slots, original SHA-256) and schema version, but not capture authenticity or durable trusted sealing.
- app/review_pipeline.py: recomputes originals’ hashes in controlled seal/review; documented boundary is local durable storage/synthetic events, no notary/trusted durable seal.
- backend/app/anchor/ledger.py: process-memory singleton; verification compares caller-supplied Merkle/master hashes with a session record instead of recomputing complete stored chain; restart loses ledger.
- backend/app/api/dispatch.py: public verification reads in-memory ledger and accepts caller-supplied roots; HTTP dispatch build is disabled. **Keep dispatch disabled.**

## 5. Historical checkpoint — PR #176 (superseded by merged PR #180)

- PR #176 contained the initial Python deterministic hash/genesis contract, full-chain verifier and known-answer tests. It was superseded and closed; do not resume its branch.
- Its vector remains valid: tenant 12345678-1234-5678-1234-567812345678, session sess-α; genesis `3caf4b5b5be75332e7483650e6450531bf17a203e7bb917483f93c3ef9236cff`; event 1 `6be67e7eca3721355e15440ef7a7ae9477bc0acd8ca62879355ce58f8bef9dbd`.
- PR #180 carries that contract into PostgreSQL migration 0028, SQL parity, backfill, append enforcement and trigger controls. See section 0 for exact-head verification and merged SHA.

## 6. M1 implementation constraints and next concrete work (updated after PR #182)

1. **Implemented/verified:** Python hash/genesis contract; SQL parity; migration 0028 persistent hashes; deterministic transactional backfill; append full-chain recomputation; direct-insert validation and update/delete guard; server-owned readback recomputation from PostgreSQL; `load_journal` and locked consumers fail closed on invalid authority-schema chains; explicit legacy-unhashed status; partial schema fails closed. Exact CI/test evidence is in section 0.
2. **Next:** migration 0029 to bind manifest roots/seals to verified chain tip, sequence, hash version and deterministic capture-context commitment. Registration must recompute/validate persisted chain and seal event before idempotent root registration. Readback/completion/receipt consumers must verify stored root binding.
3. Bind registered original artifacts/bytes to tenant/session/manifest/chain; verify ID, bytes/hash, provenance and relationship.
4. Independent verifier must derive DB event records and registered originals, not accept client-supplied roots/hashes. Return privacy-safe results with explicit limitations.
5. Add tests for independent agreement, restart/restore, concurrent writers, missing/deleted/reordered/forked rows, privileged paths, seal/context mismatch, artifact mismatch and chain checkpoint behavior. Keep external signer/checkpoint/trusted timestamp separate.
6. Execute full M1 acceptance gate on exact head after criteria complete. Keep dispatch/payment and participant evidence disabled.

## 7. Acceptance and trust semantics

Verification output must separately represent event-chain validity, trusted checkpoint/anchor, manifest, originals/artifacts, tenant/session binding, protocol, completeness, consent/authorization, quality/exceptions and limitations. Any critical provenance failure blocks verified/sealed status and dependent claims. Internal DB chain alone does not defend against rewriting the entire chain by privileged database compromise; define threat model and external trust anchor separately.

## 8. Product and release boundaries

- Capture: 16-view v2 contract is current; preserve old 12-view compatibility as versioned protocol, not silent reinterpretation. Offline queue encryption exists in canonical root application, tested in CI, but is not WORM or field/device qualified.
- Existing VIN vPIC profile is consented, descriptive, provenance-tracked; not damage analysis or physics evidence. Source/configuration cross-check is still M3.
- Frontend/API capture/reviewer mechanics exist in controlled-test code; no user-accessible staging application.
- OCI integrated staging: NOT deployed/accepted. Owner-controlled protected GitHub environments/secrets/variables, state bucket, reviewed Terraform apply, private compute, PostgreSQL/PostGIS, durable evidence storage, backup/restore and private access remain unverified. OCI MySQL Free HeatWave is not a substitute for PostgreSQL/PostGIS.
- No real participant evidence, live payment, dispatch, external recipients, public accepted staging, forensic certification, validated damage/measurement accuracy or causation claims.
- User authorizes high-autonomy engineering execution and verified merge/deploy, but pause only for concrete unavailable access, unauthorized cost, or legal/privacy/security/safety decision. Do not request secrets in chat.

## 9. New-thread resume procedure (do this, don’t ask owner to repeat)

1. Read this file, README.md, docs/EXECUTION_HANDOFF.md, docs/EXECUTION_STATUS.md, docs/forensics/FORENSIC_SUBSTANTIATION_PROGRAM.md, docs/audits/FOUNDATIONAL_SYSTEM_AUDIT_2026-11-23.md, docs/architecture/PRODUCT_PREMISE_FORENSIC_INTELLIGENCE.md, docs/architecture/FAOS_CORE_ENGINE_IMPLEMENTATION_GUIDE.md, and docs/acceptance/ACCEPTANCE_MATRIX.md.
2. Query GitHub live: main SHA; latest implementation PR/state; exact-head workflows; relevant commits/files.
3. Continue M1 implementation at the next executable items in section 6. Do not re-plan, broaden scope, or ask what next.
4. If CI failure, inspect logs and fix; if green but acceptance incomplete, continue implementation. Merge only verified increments.
5. Update this handoff, README, execution handoff/status, audit, acceptance matrix, architecture manual and product premise after each verified milestone. Use exact commit/test evidence and explicit limitations.
6. After M1 acceptance, proceed M2 then M3–M8 in order; do not skip evidence gates.

**This snapshot supersedes stale “next task = OCI staging” or broader roadmap statements wherever they conflict. OCI deployment remains a real blocker, but it is not the current forensic implementation priority.**

## Complete owner-provided requirements

Read [complete forensic substantiation specification](docs/forensics/COMPLETE_FORENSIC_SUBSTANTIATION_SPEC.md) for the expanded requirements in full: truth architecture; observation/measurement/finding distinctions; exact finding schema; M1 persistence and trust model; VIN and parts lineage; camera calibration, alignment, coordinate frame and projection; damage detection/localization/quantification and uncertainty equations; causation boundaries; OEM/hidden-damage limits; deterministic report; validation dataset and blind evaluation; first vertical slice; gates. This is requirements, not a claim that every capability is implemented.
