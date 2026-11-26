# Current governing calibration — 26 November 2026

> **Authority notice:** This is the current project calibration. Older dated checkpoints and “next task” statements below this notice are retained as history only. They are not active instructions where they conflict with this notice, the Foundational Vision & Technical White Paper, the current M1 acceptance registry, or a newer exact-head verified checkpoint.

- **Canonical product repository:** `C2C-Connect/claim2car-connect`; `main` is the only active product line. Historical/prototype repositories and branches are reference material, not alternate sources of truth.
- **Product:** a controlled evidence acquisition and substantiation platform for the accident-response ecosystem. Its differentiator is traceability from original observation through measurement and inference to an authorized decision.
- **Governing evidence architecture:** **Acquisition → Measurement → Inference → Decision**. Preserve original bytes; make derivatives traceable; attach methods, versions, units, calibration and uncertainty; abstain when inputs are insufficient; human-authorize consequential decisions.
- **Architecture direction:** React/Capacitor capture client; FastAPI modular monolith; PostgreSQL/PostGIS transactional authority; durable object storage; background workers/outbox. Do not introduce a parallel ledger or polyglot database without a demonstrated need.
- **M1 boundary:** authorized intake, consent and actor attribution; versioned 16-point capture accounting with safety exceptions/retakes and legacy interpretation; original-byte preservation; offline synchronization; server-side verification; authorized reviewer retrieval and attributable human decision.
- **M1 exclusions:** LiDAR volumetric crush measurement, autonomous structural/yield adjudication, CRASH3 outcome verdicts, collision causation, roadworthiness, repair authorization, total-loss decisions, payments, dispatch and marketplace. These remain separate research or release-gated workstreams.
- **Live repository checkpoint (26 Nov):** PR #185 is recorded merged to main as `590724597a65395ece225128b40ec48fa6ece34b`; its candidate head had 13/13 workflow types and DB-01–DB-14 14/14 technical PASS (408/408 counted DB tests). Post-merge exact-main verification is still required. PR #195 is open/draft with Evidence Measurement and Substantiation Contract v1.0.0; its recorded exact head `934f7cca7ff9d145d2a187f444c9bbcc4422c0f8` had 13/13 workflow types, 1,082 full-suite passes, 7 skips, 218 subtests, and DB authority 415/415 with 14/14 technical gates. This is contract validation, not sensor/metrology/model validation. PR #196 contains a consent-deletion retry fix; exact corrected-head verification remains pending. PR #186 report work is stale/stacked and must be rebased before use. PR #187 narrows M1 acceptance. PR #194 is a source-level audit checkpoint. PR #188 is an OCI proposal only.
- **Release truth:** M1 is not accepted; no physical-device field qualification, persistent integrated staging deployment, real participant evidence, live payment, or dispatch activation is established. Do not claim otherwise.
- **Device decision:** exact iPad baseline and whether LiDAR is an M1 requirement remain unresolved pending device-specific qualification. Standardized managed fleet is the intended operating model; hardware capability is not assumed from marketing specifications.
- **Commercial planning:** dealer fee $375 on qualified close; shop fee $275 on recorded acceptance per current planning documents; operator amount $110 carried forward but payout trigger/eligibility/ledger remain unresolved; owner cash incentive is excluded. No live payment or payout logic until its release and contract gates pass.
- **Claims discipline:** no “legally conclusive,” “tamper-proof,” automatic admissibility, universal sub-centimeter accuracy, validated physics/AI verdict, guaranteed financial outcome, or zero-liability claims. Integrity, provenance, authenticity, reliability and sufficiency remain distinct.
- **Execution rule:** implement working product slices; tests verify functionality. Report exact commit, tests, pass/fail, incomplete items, deployment and operational status. Never equate a green CI run with field qualification, acceptance or deployment.

**Authoritative references**
1. [Foundational Vision & Technical White Paper](CLAIM2CAR_FOUNDATIONAL_VISION_AND_TECHNICAL_WHITE_PAPER.md)
2. [System-Wide Engineering Audit — 2026-11-26](audits/SYSTEM_WIDE_ENGINEERING_AUDIT_2026-11-26.md)
3. [M1 Acceptance & Release Gate Matrix](acceptance/ACCEPTANCE_MATRIX.md)
4. [Evidence Measurement and Substantiation Contract v1.0](forensics/EVIDENCE_SUBSTANTIATION_CONTRACT_V1.md) — PR #195 until merged; not device or measurement validation.

---

## Current execution checkpoint — 2026-11-24

PR #184 merged the M1 database manifest-root chain-tip/context binding. Exact tested head `95692eaf30f76ca9ab8b7c0cf71c4bcf9fac5d68`: 13/13 workflows green; full suite 1,064 passed (7 skipped); authority suite 407/407 counted tests; DB-01–DB-14 14/14 PASS; 340 tenant-isolation assertions.

PR #185 is the active M1 runtime integration increment. It adds migration 0030 and connects the live capture seal transaction to root registration, then verifies the root before reviewer queue/details/artifact retrieval/review. It validates the exact protocol slot set for 12-v1, 16-v1 and 16-v2. The first runs exposed migration ownership, stale inventory fixtures, reviewer/seal-actor binding, and event-chain backfill fixture ordering. Those defects are corrected in the active branch; a fresh full CI and authority run is pending. Do not merge until all checks pass. No merge until all checks pass.

**Next code task:** finish and merge PR #185 only after exact-head verification. Then implement M2 original-artifact provenance and source/capture metadata within the existing FAOS journal/storage boundary. Do not create a parallel ledger. The old in-memory four-tier dossier/PDF service is not a production report pipeline; the report milestone must consume server-verified evidence, persist report revision/hash, and explicitly distinguish evidence inventory from assessed findings.


# Claim2Car Forensic Substantiation Program
## Latest verified implementation checkpoint — PR #182 merged (2026-11-23)

PR #182 merged as `f0c6fbfc7d0278e77964a45004e0e42ede7a8146`; exact tested head `668785ea465b807932e63fdb6a555ed419099b6b`, **13/13 workflows green**. Full suite: 1,054 passed, 31 warnings, 219 subtests. Isolated synthetic PostgreSQL acceptance: 390 counted tests, DB-01–DB-14 14/14 PASS and database overall ACCEPTED. This is not forensic M1 acceptance or field qualification.

Migration 0028 persists SHA-256 event hashes and fail-closed backfill. PR #182 adds server-owned persisted-chain readback from PostgreSQL; invalid chains fail closed before replay/locked consumers; legacy unhashed status is explicit; partial schema fails closed. Tamper, tenant, legacy and locked-consumer tests passed.

**M1 incomplete:** sealed manifest roots do not bind verified chain tip, sequence, hash version and context; registered original/artifact binding, independent verifier agreement, recovery/concurrency/fork tests and external checkpoint remain. No staging, field qualification, participant evidence, payment or dispatch.

**Next code task:** migration 0029 for manifest-root chain-tip/context binding and verified registration/consumers; then artifact provenance and independent/recovery/adversarial tests. No planning loop.

## Mission

Build the ability for Claim2Car to substantiate every meaningful claim made about a collision, vehicle, damage condition, measurement, technical assessment, and report. Every conclusion must be traceable to preserved evidence, explicit observations, documented methods, supported measurements, uncertainty, and a reproducible derivation.

**The product's differentiator is defensibility—not a volume of photographs, a hash badge, a VIN lookup, a polished PDF, or an AI label.**

## Non-negotiable epistemic rules

1. Preserve original evidence bytes; derived images, crops, masks, OCR, annotations, and model outputs are separate artifacts linked to originals.
2. A hash proves byte equality relative to the hash operation. It does not prove when/where/how an image was captured, that it depicts the asserted vehicle, or that the interpretation is correct.
3. A hash chain detects changes relative to a trusted anchor/checkpoint; an unanchored chain controlled by the same compromised system is not independent proof.
4. Capture authenticity, custody, identity, completeness, integrity, observation, measurement, inference, causation, and repair advice are separate claims.
5. Every forensic claim has evidence references, method/version, inputs, parameters, results, uncertainty/limitations, and review state.
6. No fabricated precision. If the image, calibration, geometry, scale, or method cannot support a measurement, report it as unavailable/qualitative or inconclusive.
7. Do not infer collision causation or absence of hidden damage solely from imagery.
8. Model/algorithm output is not truth. Confidence must be calibrated to validation evidence; otherwise label it uncalibrated.
9. Consequential workflow actions (dispatch, payment, partner release) must be authorized independently of forensic scoring or integrity status.
10. Never mutate originals to improve quality, align, crop, annotate, or normalize. All processing is reproducible on derivatives.

## Evidence-to-conclusion architecture

### Layer 1 — Original evidence
Immutable logical originals: photos, video, VIN image, documents, capture/session/actor metadata. Store artifact ID, byte length, SHA-256, media type, source, acquisition time (and distinction between device time and server time), capture protocol/slot, tenant/session, actor, and authorization. Original integrity is verified before any derivative.

### Layer 2 — Provenance, custody, and persistence
Persistent tenant-scoped PostgreSQL provenance/event records; canonical event encoding; schema/version; stable event IDs; idempotency; server-authored event timestamps; actor/authorization; previous hash; current hash; event payload commitment; sealed manifest; artifact hashes; append-only database controls; audit reconstruction; restart durability; concurrency and tenant isolation. Independently recompute the complete chain from genesis or a clearly defined authenticated checkpoint, verify each event, manifest, artifacts, ordering, completeness, and session binding. Detect missing, duplicate, reordered, altered, forked, or unanchored records. Do not overstate an internal database anchor as external/independent notarization.

### Layer 3 — Observations
Separate objective observation from interpretation. Examples: a visible crease, cracked lamp, displaced trim, panel gap, broken attachment, OCR characters, image blur, occlusion. Store structured observation, source image/artifact, coordinates/mask/bbox, capture slot, annotator/model, method/version, timestamps, and review. Permit disagreement and null/unknown.

### Layer 4 — Geometry and measurements
Formal versioned vehicle coordinate frame (origin, axes, handedness, units); camera intrinsics and distortion; camera pose/extrinsics or explicit unknown; capture-slot pose guidance; vehicle landmarks; reference/scale provenance; transforms; projected geometry; segmentation/silhouette; residuals; dimensional measurement; uncertainty and sensitivity. Store calculation inputs and outputs. Never turn uncalibrated pixels into metric dimensions.

### Layer 5 — Vehicle and component identity
VIN capture and preservation; OCR as a derivative; syntax/check digit validation where applicable; decoder/source/version/date; decoded fields and raw response; cross-check against physical identifiers and observations; discrepancy/ambiguity. Vehicle configuration, trim, options, market, production range, and applicability must be source-backed. Parts hierarchy and identification include OEM part number, supersession/alternate, applicability, side/location, assembly, source/revision/effective date. No unsupported generated part number or compatibility assertion.

### Layer 6 — Damage detection and classification
Use a versioned pipeline for image quality, vehicle/component localization, segmentation, landmarks, cross-view correspondence, damage detection/classification, geometry/surface/panel-gap analysis, and occlusion. Establish the baseline and supported conditions for each algorithm. Treat visual signals as hypotheses/observations. Explicitly consider camera pose, lighting, reflections, perspective, model mismatch, manufacturing variation, pre-existing damage, steering, loading, shadow, and occlusion. Support unknown, inconclusive, conflicting, and human-corrected results. Do not imply hidden components have been inspected.

### Layer 7 — Reasoning and conclusions
Represent the inference graph: evidence → observations → measurements → findings → assessment → conclusion. Each edge has rationale/method/version and supports/contradicts/qualifies semantics. Distinguish observed, measured, classified, collision-associated, causation, safety/repair recommendation. Record alternative explanations, prior damage, missing evidence, assumptions, and limitations. Require human review for consequential or unsupported outputs. Conclusions can be inconclusive.

### Layer 8 — Technical repair assessment
Source-backed OEM repair procedures, component applicability, repair/replace criteria, safety-critical adjacent systems, diagnostic/scan/disassembly requirements, parts, labor and dependencies. Record source, revision, date, applicability and limitations. Photo assessment must not assert hidden damage or required procedures without support.

### Layer 9 — Report
Deterministic, versioned rendering from the structured record: case and vehicle identity; scope; evidence inventory and provenance; capture coverage/quality; observations; measurements with method/units/reference frame/uncertainty; findings and supporting evidence; technical assessment with sources; conclusions and alternatives; limitations and required further inspection; review; integrity/reproducibility and report hash. Every annotation links to the original. Reports are revisioned; no silent overwrite. If inputs or findings change, produce a new report version and preserve prior issued versions.

## Program milestones and acceptance gates

### M0 — Forensic claim schema + method registry
Implement canonical models/API/schema for evidence references, observation, measurement, finding, inference link, method, uncertainty, validation state, reviewer and report revision. Versioned units/coordinate conventions; typed status taxonomy; required fields and referential validation. Test invalid/unsupported claims fail closed.

**Acceptance:** A claim cannot be created without a traceable source and method or explicit manual-review rationale; unknown/inconclusive is first-class; all schema versions and references validate.

### M1 — Persistent provenance and independent verification (FIRST CODE TARGET)
Replace or supersede process-memory anchor ledger. Persist PostgreSQL events and sealed manifests. Establish canonicalization, stable event IDs, idempotency, tenant boundaries, serialization/version, hash-link formula, append-only policy, transaction/concurrency semantics, recovery, checkpoint/anchor semantics and verification result model. Recompute the complete chain and artifact/manifests on verify. Separate trusted checkpoint/anchor from mere internal chain.

**Tests:** restart recovery; complete chain recomputation; entry payload/hash tamper; artifact alteration/missing artifact; manifest tamper; missing/duplicate/reordered event; chain fork; bad checkpoint; idempotent duplicate request; concurrent writers; tenant cross-read/write; unsealed/incomplete evidence; DB transaction rollback; append-only policy; fail-closed verifier. Verify an independent verifier agrees with server result.

**Acceptance:** Verification returns a structured result with chain, checkpoint, manifest, artifact, session/tenant binding, completeness, and limitations individually represented. Any critical provenance failure blocks “verified/sealed” status and all downstream claims that depend on it. Integrity verification alone does not grant dispatch/payment authorization.

### M2 — Evidence inventory and artifact authenticity boundaries
Validate server-registered original artifact IDs, bytes, digest, size, type, metadata, capture/consent context, manifest membership, and duplicate handling. Derivatives retain parent links and transformation details. Define what server can/cannot attest about device capture and location. Test altered, substituted, orphaned, wrong-tenant, duplicate, missing and unregistered artifacts.

**Acceptance:** Findings/report only cite registered artifacts with verified digest; capture authenticity limitations are explicit.

### M3 — VIN and vehicle configuration substantiation
VIN OCR/capture, validation, source-backed decode, version/raw response, cross-check, discrepancy resolution, configuration/applicability. Test check-digit/invalid VIN, source unavailable, contradictory decode, OCR ambiguity, multiple identifiers and unsupported market/trim.

**Acceptance:** Identity is “validated/corroborated/ambiguous/unverified” according to evidence; no silently inferred configuration.

### M4 — Capture protocol and camera geometry
Formal 16-view protocol (and legacy protocol compatibility); camera alignment guidance and deviation metrics; calibration metadata; vehicle landmarks; frame and transform contracts; reference scale; capture-quality acceptance rules based on validation; silhouette/projection feasibility and uncertainty. Treat phone-camera calibration and pose as device/session-specific and potentially unknown. Capture originals remain unchanged.

**Acceptance:** A controlled capture can produce pose/calibration/landmark records; geometric operations reject insufficient calibration or produce explicitly qualitative results. Each slot's exact definition and protocol version remain immutable.

### M5 — Damage localization and one calibrated measurement
Start with one bounded component/region and one supported measurement. Implement reproducible segmentation/landmark/geometry, validated reference scale or calibrated multi-view geometry, residual and uncertainty, image annotations as derivatives, and findings tied to exact evidence.

**Acceptance:** Synthetic known geometry has predetermined error tolerance; held-out real measurements are compared with independent reference measurements; algorithm output includes uncertainty/limitations; no metric claim without valid scale/pose.

### M6 — Parts and technical assessment
Source-backed vehicle/component/part applicability and repair procedures; source/revision/date; dependency and safety checks; unknown/inspection-required status.

**Acceptance:** Each part/repair assertion traces to a supported source/applicability record or is marked provisional and requires review. No unsupported OEM assertions.

### M7 — Forensic report generator
Generate structured report from schema, evidence graph and method outputs. Report all provenance, observations, methods, units, uncertainty, sources, alternatives, limitations, review, revision and verification status. Stable reproducible rendering; PDF and machine-readable export. Preserve revisions.

**Acceptance:** Independent report verifier resolves every claim/evidence reference and checks all commitments; altered inputs invalidate/revoke the verification status; a report does not display unsupported claim as verified.

### M8 — Validation/qualification
Build curated and synthetic datasets, truth/ground-truth methods, separate development/calibration/held-out sets, blind evaluation, failure analysis, reviewer agreement, calibrated confidence, test-device and environmental matrix, external validation where possible. Define thresholds before held-out evaluation. Track versioned results and regressions.

**Acceptance:** No field/accuracy claim until a relevant dataset, method, metric, threshold, scope, result, and limitation are documented and independently reviewed.

## Technical implementation methodology

For each milestone:
1. Inspect current code, schema, migrations, API, UI and tests; trace the actual runtime and find existing implementation to reuse.
2. Define the claim/contract and measurable acceptance criteria before code.
3. Create one narrow branch and dependency-sized PR.
4. Implement real integrated mechanics, not placeholder scaffolding.
5. Add deterministic unit, integration, API, database, security, and failure tests as appropriate.
6. Add synthetic known-answer tests; test negative/contradictory/incomplete cases.
7. Run exact PR-head CI; inspect test coverage and logs, fix regressions.
8. Merge only verified increments, then update this plan, audit ledger, handoff, README and execution status.
9. Deployment/field qualification are separate gates. No real participant evidence, live payment, dispatch, or public staging until their release criteria are independently accepted.

## Initial vertical slice (use as a north-star, not a disconnected demo)

**One controlled vehicle + one exterior component + one bounded damage region + one calibrated measurement + one evidence-linked finding + one reproducible report.**

Synthetic fixtures first, then controlled non-participant test vehicle/reference measurements, then independent blind validation. All stages share the production-intended data/provenance/report contracts. Avoid implementing unrelated breadth until this slice passes.

## Focus order — do not drift

1. M0 claim/observation/measurement/finding/report contracts, only as required to support M1.
2. **M1 persistent provenance and independent full-chain verification.**
3. M2 evidence binding and authenticity boundary.
4. M3 VIN/configuration source substantiation.
5. M4 capture alignment/calibration/coordinate frame.
6. M5 damage localization + one validated measurement.
7. M6 part/OEM source-backed assessment.
8. M7 report.
9. M8 validation/qualification.
   
Do not spend focus on payments, dispatch, marketplace expansion, polished UI, broad AI features, speculative blockchain/external anchors, or general deployment work while this forensic vertical slice is incomplete, except necessary security/operational blockers.

## Immediate next action

Inspect `backend/app/anchor/ledger.py`, migrations, existing PostgreSQL event/provenance models, manifest/seal code, integrity APIs, verifier and test suite. Write a contract mapping old behavior to the new durable schema. Implement M1 as the first code PR, reusing PostgreSQL authority already established and avoiding a parallel persistence subsystem. Trace every verification/dispatch/payment caller and keep authorization separate. Establish test coverage before schema migration. Continue without asking routine approvals.

## Explicit readiness boundary

The current application and capture protocols are controlled-test implementations. The M1 implementation is not yet complete or accepted. Do not claim forensic certification, independently notarized evidence, calibrated measurement, validated damage quantification, causation, hidden-damage assessment, or field accuracy until the specific mechanism has been implemented, tested, validated, and scoped. No real participant evidence or live consequential action.

## New-chat handoff

Read this document first, then `README.md`, `docs/EXECUTION_HANDOFF.md`, `docs/EXECUTION_STATUS.md`, `docs/audits/FOUNDATIONAL_SYSTEM_AUDIT_2026-11-23.md`, and `docs/architecture/PRODUCT_PREMISE_FORENSIC_INTELLIGENCE.md`. Verify current main/PR/check status. Resume **M1 persistent provenance and independent full-chain verification**—do not re-plan or pivot away from forensic substantiation.
\n\n## Complete engineering contract\n\nThis ordered program is accompanied by the complete owner-directed specification: [complete forensic substantiation specification](docs/forensics/COMPLETE_FORENSIC_SUBSTANTIATION_SPEC.md). The spec contains the full truth-layer definitions, finding schema, formulas, geometry and calibration requirements, causation boundaries, report outline, validation methodology, V1 slice, gates and current implementation checkpoint. Use it as the detailed acceptance reference.\n