# Claim2Car — authoritative thread handoff / current engineering state
**Snapshot date:** 2026-11-23 (America/Chicago)
**Canonical product repository:** C2C-Connect/claim2car-connect
**Canonical product branch:** main
**Active forensic implementation branch:** feat/persistent-forensic-provenance-m1
**Active PR:** [#176 — M1 persistent forensic provenance and event-chain verification](https://github.com/C2C-Connect/claim2car-connect/pull/176)
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

## 5. Current M1 branch/PR checkpoint (verify live)

- PR #175 documentation program merged to main: merge commit cf985ee92ed6624467bc8dbeaea9e25ff9e207fa.
- PR #176 is **draft/open/not merged**, based on main at cf985ee92ed6624467bc8dbeaea9e25ff9e207fa; branch feat/persistent-forensic-provenance-m1; head last verified 36fdd083ebbbe1268e6e2f51d40dfe60b9523404.
- PR #176 currently has the Python versioned deterministic SHA-256 event/genesis commitment contract, full-chain verifier and known-answer/unit tests (3 files, 232 additions at checkpoint). This is an initial slice only, **not persistent SQL implementation**.
- Hash contract: domain-separated FAOS_EVENT_CHAIN_GENESIS_V1 and FAOS_EVENT_HASH_V1; version event-hash-v1. Bound fields include tenant, session, event ID, sequence, kind, actor, event time, reason, exact payload text, schema version, previous hash. Free text is UTF-8 hex within an unambiguous fixed-field encoding; SHA-256.
- Known-answer vector: tenant 12345678-1234-5678-1234-567812345678, session sess-α; genesis 3caf4b5b5be75332e7483650e6450531bf17a203e7bb917483f93c3ef9236cff; event 1 6be67e7eca3721355e15440ef7a7ae9477bc0acd8ca62879355ce58f8bef9dbd.
- Unit tests cover known vector, valid single event, payload tamper, prev-link tamper, sequence gap/reorder, session binding, empty chain, invalid tenant, unsupported version.
- Exact PR head CI at checkpoint: **13/13 workflows completed successfully**, including Full test suite, Database authority cutover, Legacy database, FastAPI, browser IndexedDB, VIN, guided capture, controlled demo, intake PostgreSQL, restricted containers and runtime smoke. Publication-only jobs skipped where expected. Full test job passed but detailed test count was not captured; do not invent it.
- No SQL migration/backfill, SQL/Python parity, DB persistence integration, server verifier replacement, manifest tip binding, restart/concurrency/adversarial DB tests, external checkpoint, deployment, or field/forensic qualification is complete.
- PR must remain draft and must **not merge** until full M1 acceptance gate passes on its exact head.

## 6. M1 implementation constraints and next concrete work

1. Review Python contract for edge cases; add tests for canonical UUID/tenant handling, exact event field serialization, timestamps, payload bytes, unsupported/malformed fields and hash version.
2. Inspect migration runner, PostgreSQL versions/extensions/privileges, roles and existing SQL append function. Determine safe migration/backfill and rollback plan.
3. Implement versioned SQL hash/genesis functions with exact Python parity and published vectors. Check whether PostgreSQL SHA-256 support is native/available in target; do not assume extension availability.
4. Add columns/versioned commitments to existing event rows; backfill deterministically per tenant/session in sequence without rewriting event payload text. Define explicit behavior for legacy rows and migration failure.
5. Replace/extend faos.append_event: existing session lock, tenant context, stable event IDs, idempotency, next sequence, full existing-chain verification, new previous hash and entry hash calculated server-side, append transactionally. Restrict direct writes; preserve RLS/FORCE RLS and ownership/privileges.
6. Full-chain server verifier independent of stored head: recompute genesis and every event; reject gaps, duplicates, missing/deleted, reorder, payload/field tamper, hash mismatch, fork, session/tenant mismatch, unsupported version. Compare expected head and event count.
7. Bind manifest/seal to chain head and sequence, manifest digest, protocol, server seal time, actor, consent state/reference, quality outcomes, exceptions, registered originals and hashes. Immutable seal versions; corrections append, not overwrite.
8. Replace caller-supplied-root verification with server-derived records and registered bytes. Privacy-safe verification ID/token; no guessable ID data leakage. Keep dispatch/payment disabled.
9. DB integration/security tests: cross-language vector; migration/backfill; rollback; append-only; direct SQL/role adversarial; RLS; tenant cross-read/write; duplicate idempotency/conflict; concurrent writers; restart; restore/replay; tamper; missing/deleted/reordered/forked; manifest/artifact binding; independent verifier agreement.
10. Update consumers, gate matrix and documentation; exact-head CI; inspect failed logs; merge only after acceptance. External signer/checkpoint is separate gate and trust model.

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
2. Query GitHub live: main SHA; PR #176 head/state; workflows on exact head; relevant commits/files; check whether this documentation PR merged.
3. Continue M1 implementation at items 1–3 in section 6. Do not re-plan, broaden scope, or ask what next.
4. If CI failure, inspect logs and fix; if green but acceptance incomplete, continue implementation. Keep #176 draft until M1 acceptance is complete.
5. Update this handoff, README, execution handoff/status, audit, acceptance matrix, architecture manual and product premise after each verified milestone. Use exact commit/test evidence and explicit limitations.
6. Next focus after M1 acceptance: M2, then M3–M8 in order. Only advance when gate evidence exists.

**This snapshot supersedes stale “next task = OCI staging” or broader roadmap statements wherever they conflict. OCI deployment remains a real blocker, but it is not the current forensic implementation priority.**

## Complete owner-provided requirements

Read [complete forensic substantiation specification](docs/forensics/COMPLETE_FORENSIC_SUBSTANTIATION_SPEC.md) for the expanded requirements in full: truth architecture; observation/measurement/finding distinctions; exact finding schema; M1 persistence and trust model; VIN and parts lineage; camera calibration, alignment, coordinate frame and projection; damage detection/localization/quantification and uncertainty equations; causation boundaries; OEM/hidden-damage limits; deterministic report; validation dataset and blind evaluation; first vertical slice; gates. This is requirements, not a claim that every capability is implemented.
