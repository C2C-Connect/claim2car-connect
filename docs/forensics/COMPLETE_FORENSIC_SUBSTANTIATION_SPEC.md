# Claim2Car — complete forensic substantiation specification

**Owner-directed canonical specification. Snapshot: 2026-11-23.** This document captures the complete forensic substantiation mandate and detailed implementation roadmap in one persistent source. It is a requirements specification—not a statement that all mechanisms are implemented or validated.

## 1. Central objective

Claim2Car’s differentiator is the ability to defend the chain of reasoning from original evidence to every conclusion. Capturing pictures, storing files, producing a polished damage report, hashing an artifact, decoding a VIN, or labeling an image with AI is insufficient in isolation. A polished report with unsupported conclusions is worthless. A hash of a poor photograph proves only preservation of the bytes hashed. A VIN decoder does not establish that a vehicle was involved in a reported collision. A camera view does not establish measured deformation unless geometry, calibration, assumptions, and uncertainty support the measurement.

**Objective:** establish a defensible evidence-to-conclusion pipeline:

> Original evidence → Verified observations → Measured geometry → Supported findings → Defensible report

Every transition must be testable, reproducible, and disclose limitations. The system must answer: (1) What was actually captured? (2) What can objectively be observed? (3) What can be measured, and with what uncertainty? (4) What conclusions are supported by those measurements? (5) Can another qualified person reproduce or challenge the conclusion?

Do not collapse these questions into one AI-generated answer.

## 2. Forensic truth architecture

1. **Original evidence:** unmodified photographs/video, VIN imagery, documents, timestamps and capture metadata.
2. **Provenance & integrity:** hashes, manifests, signatures where actually used, custody, persistent anchors, identity/authorization and event history.
3. **Observations:** visible damage, landmarks, shadows, edges, components, identifiers, occlusions, objective descriptions.
4. **Measurements:** scale, geometry, dimensions, alignment, depth proxies, uncertainty, confidence/quality and coordinate frame.
5. **Analysis:** vehicle/configuration identification, component identification, damage classification and technical reasoning.
6. **Conclusions:** supported findings, alternatives, unknowns, limitations, competing explanations, review and disagreement.
7. **Report:** evidence citations, methods, results, uncertainty, reproducibility, revision/versioning and integrity verification.

Each layer preserves inputs/outputs and lineage. Analysis cannot overwrite originals. Conclusions cannot silently upgrade observations into facts.

## 3. Phase 0 — scientific and forensic contract

Before algorithms proliferate, establish canonical, versioned contracts for finding, evidence reference, observation, measurement, inference, method, uncertainty, review, report and reproducibility.

Each finding records, at minimum:

| Field | Required meaning |
|---|---|
| Finding ID | Stable unique identifier |
| Claim | Precisely worded conclusion/proposition |
| Evidence IDs | Exact original artifact(s) and relevant derivative(s) |
| Observation | Directly observable supporting features, separated from interpretation |
| Method | Algorithm, measurement or expert method |
| Parameters | Thresholds, calibration, model/method version, settings |
| Result | Classification/measurement, units and reference frame |
| Uncertainty | Numerical uncertainty or explicit qualitative limitation |
| Confidence | Calibrated confidence only where calibration evidence exists; otherwise no false probability |
| Alternatives | Other explanations not excluded and contradictory evidence |
| Status | Supported, provisional, inconclusive, contradicted, withdrawn, etc. |
| Reviewer | Review identity, disposition, disagreement and timestamp |
| Reproducibility | Versioned inputs and instructions needed to repeat |

A finding without source evidence references cannot enter the report as a forensic finding. Use typed claim levels and enforce transitions: observation → measurement → classification → event association → causation → repair recommendation. These are distinct propositions with distinct evidentiary requirements.

## 4. Phase 1 — persistent forensic provenance (first implementation milestone)

Process-memory anchor ledger is inadequate. Implement durable provenance in the existing PostgreSQL authority, not a parallel database/ledger.

Required mechanics:
- PostgreSQL persistence, tenant-scoped records and stable event IDs.
- Idempotency, server-generated timestamps and deterministic/versioned serialization.
- Hash-linked event sequence, append-only controls enforced by DB roles/functions/triggers, not just app convention.
- Full recomputation from genesis or an explicitly defined trusted checkpoint; never trust stored `entry_hash` without recomputation.
- Durable sealing of evidence manifest and registered originals.
- Restart recovery, tamper detection, explicit missing/duplicate/reordered/altered event handling.
- Concurrent writers and serialization/locking behavior.
- Independent verifier/tooling, with clear trust model and privacy-safe verification.
- Tests for migration/backfill, rollback, RLS/tenant isolation, privileged/direct SQL paths, idempotency, conflict, concurrency, restart, replay, missing/deleted records, reordering, payload/metadata tampering, fork, manifest/artifact mismatch and verifier agreement.

Core commitment (exact byte encoding and version must be specified; this symbolic form is not a canonicalization implementation):

\[
H_i = \operatorname{SHA256}(C(E_i) \parallel H_{i-1})
\]

Where \(E_i\) binds event identity, tenant, session, actor, event type, timestamp, payload commitment or exact payload representation, schema/hash version and other contract-defined fields; \(C\) is deterministic, unambiguous, versioned serialization; and \(H_{i-1}\) is the preceding verified hash. Genesis is domain-separated and tenant/session bound. Cross-runtime (Python/SQL) parity requires exact vectors, including Unicode, numeric spelling, timestamps, nulls and field ordering.

The event chain must be independently recomputed. The chain also binds a sealed evidence package: manifest, original artifact IDs and hashes, session/vehicle/capture protocol, chain tip and sequence, seal actor/time, consent state/reference, quality outcomes, exceptions, and registration context. Corrections append new events/seal versions; no silent rewrite of prior seals.

Distinguish explicitly: byte hash integrity; chain integrity; manifest completeness; artifact provenance/authenticity; capture authenticity; identity assurance; interpretation; independent trusted checkpoint. A hash chain stored only in one database is not independent notarization against an actor capable of rewriting that database. External signer, trusted timestamp, transparency/checkpoint or anchoring service is a separate threat-model/gate. Hashes, Merkle roots, signatures, timestamps and blockchain are not synonyms.

## 5. Phase 2 — vehicle identity and parts intelligence

### VIN evidence pipeline
- Capture VIN on physical vehicle; preserve original image and OCR derivative separately.
- Validate syntax and check digit where applicable; retain uncertainty and OCR alternatives.
- Decode using named, versioned/source-documented service; record source, request VIN, timestamp, version, raw response/normalized response and retrieval lineage.
- Compare decoder results with physical observations, labels, registration or other authorized identifiers where available; record discrepancies and ambiguity.
- Bind corroborated vehicle/configuration identity to evidence session. VIN decoding alone is not proof that vehicle was involved in a collision.

### Parts intelligence
Connect: vehicle identity → configuration → assembly → component → location → damage observation → repair/replace/inspect decision.
Record OEM part number, alternate/superseded number, vehicle and trim/configuration applicability, left/right/front/rear distinction, assembly hierarchy, supported repair/replacement criteria, source citations/revision/effective dates, confidence and unresolved compatibility. AI-suggested part numbers are unverified until sourced and applicability confirmed.

## 6. Phase 3 — capture geometry, camera alignment and silhouette projection

This changes “take 16 photos” into a geometrically useful acquisition protocol.

### 6.1 Calibration
Where available and appropriate, retain camera intrinsics \(K\), focal/effective parameters, principal point, lens distortion coefficients, camera model, sensor/resolution, orientation, pose and camera-to-vehicle reference pose, calibration method/date, and calibration quality/error. Correct/characterize distortion before pixel-to-metric claims.

Pinhole projection is conventionally expressed:
\[
\mathbf p \sim K [R\mid t] \mathbf P
\]
where \(\mathbf P\) is a 3D point in the defined world/vehicle frame and \(\mathbf p\) its image projection (homogeneous coordinates). The equation and coordinate conventions must be correctly implemented and versioned; it is not evidence that pose/calibration is available.

### 6.2 Alignment protocol
For each capture slot define target vehicle plane/surface, expected camera position/orientation, target distance or allowable interval, level/horizon guidance, required landmarks, tolerances, occlusion rules and retake criteria. Alignment should be derived from actual capture and pose/reference estimates, not decorative UI. Quantify deviations only when estimates are supported:
\[
\Delta\theta=\theta_{actual}-\theta_{target},\quad
\Delta d=d_{actual}-d_{target}
\]
If the system has only an image and no reliable sensor/reference/visual estimate, do not fabricate pose.

### 6.3 Vehicle coordinate frame
Specify and version origin, handedness, axes, sign direction, units and transformations. A candidate is longitudinal front-to-rear, lateral driver-to-passenger, vertical ground-up, but the exact standard must be formalized. Every measurement names its coordinate frame and transform lineage.

### 6.4 Silhouette projection
Pipeline: vehicle segmentation → silhouette → landmarks → pose estimation → reference geometry/configuration alignment → projection → residual/difference → uncertainty → human review.

A silhouette residual is **not automatically collision damage**. Differences may arise from perspective, pose/alignment, model/configuration mismatch, lighting/shadows, steering, load, suspension, occlusion, manufacturing variation, previous damage or collision deformation. Residuals remain measurements/observations until supported analysis addresses alternatives.

## 7. Phase 4 — damage localization and quantification

### Detection signals
Use independently useful signals where justified: segmentation, edge discontinuity, surface-curvature anomalies, panel gaps, reflections/highlight distortion, deformation patterns, broken/missing parts, material-specific features and cross-view correspondence. Keep source image/derivative/model version and evidence for each.

### Localization contract
Record component, side/position, image coordinates, polygon/bounding region/mask, relevant capture slots/views, evidence-supported observations, conflicting evidence and occlusion status.

### Quantification
Only where calibration/reference supports it: area, length, width, relative displacement, panel-gap deviation, surface deviation, and estimated depth only where method supports depth. Record units, frame, uncertainty/interval, method, input calibration and limitations. Never claim (for example) a 34-mm deformation depth from a single uncalibrated image.

A measurement is a function of evidence and calibration:
\[
\hat{x}=f(I,K,R,t,S)
\]
where \(I\) is image/evidence, \(K\) calibration, \(R,t\) pose, and \(S\) scale/reference/geometry information. Account for input uncertainty where defensible:
\[
\sigma_{\hat{x}}^2 \approx J\Sigma J^T
\]
where \(J\) is the measurement function sensitivity/Jacobian and \(\Sigma\) covariance of relevant inputs. If uncertainty cannot be calculated reliably, disclose limitation rather than manufacture precision.

## 8. Phase 5 — damage reasoning and causation boundaries

Keep separate propositions:

| Proposition | Meaning |
|---|---|
| Observed | A feature is visible in source evidence |
| Measured | Quantified by documented method and reference |
| Damage classification | Feature is consistent with a defined damage category |
| Collision association | Evidence supports association with the reported event |
| Causation | Evidence supports causal conclusion; stronger and separate inference |
| Repair recommendation | Technical recommendation from evidence and applicable sources |

Inference graph example:
- Observation O-104: visible surface discontinuity in front bumper, tied to original image and location.
- Measurement M-042: segmented area/dimensions where scale exists, method and uncertainty.
- Finding F-031: deformation consistent with localized impact damage; rationale, alternatives and confidence/limitations.
- Event association: compare incident account, additional views, prior-condition evidence, temporal/custody information and other sources.

Support contradictory evidence, pre-existing damage, inconclusive, missing views, competing explanations, reviewer disagreement, withdrawn findings and revision. Never force confident conclusions. “Consistent with” is not causation.

## 9. Phase 6 — technical assessment and repair intelligence

After localization, connect to actual vehicle configuration and source-backed repair information. For affected component: verify identification and applicability; assess whether evidence supports repair, replace, inspect or no action; identify applicable OEM procedures; safety-critical adjacent systems; diagnostics; dependencies/labor/associated parts; source/revision; unknowns requiring inspection.

Images cannot establish all hidden damage. A damaged bumper cover photograph cannot conclusively establish reinforcement, absorber, bracket, rail, wiring, sensor mount or restraint-system condition. Distinguish visually observed damage from parts needing physical inspection, measurement, scan, disassembly or OEM procedure. Do not issue roadworthiness or repair authorization from unsupported image inference.

## 10. Phase 7 — deterministic forensic report

Report is deterministic rendering from versioned evidence/finding data, not free-form AI prose.

Report outline:
1. Case/session, vehicle identity, dates, actors and authorization.
2. Evidence inventory: originals, IDs, hashes, provenance, capture.
3. Capture coverage: protocol/version, slots, omissions, quality/alignment, exceptions.
4. Vehicle identity: VIN evidence, decode source, corroboration, configuration, discrepancies.
5. Observations: objective text and image references/annotations.
6. Measurements: method, inputs, units, coordinate frame, result and uncertainty.
7. Damage findings: component/location, evidence, classification, alternatives, status.
8. Technical assessment: parts, procedures, applicability, safety and limitations.
9. Conclusions: supported/provisional/inconclusive, unknowns, review and scope.
10. Integrity/reproducibility: manifest, chain/checkpoint status, versions, report hash, revision history.

Every annotation references original evidence. Every measurement references inputs. Every conclusion references findings supporting it. If evidence or findings change, generate a new report revision; preserve prior issued reports. Provide structured machine-readable report plus stable human-readable rendition where feasible.

## 11. Phase 8 — validation and scientific acceptance

### A. Mathematical unit tests
Independent known-answer tests for transforms, projection, distortion correction, landmarks, scale, polygon area, uncertainty propagation, residuals, canonical encoding, hashes and Merkle structures (where implemented). Expected values must be independently derived/verified.

### B. Synthetic controlled geometry
Known camera pose/intrinsics, dimensions, deformation, object placement, lighting, noise. Recover within tolerances defined *before* tests. Include negative cases.

### C. Real-world dataset
Versioned curated vehicles/conditions: undamaged, previous damage, configurations, cameras, lighting, rain/glare, shadow, occlusion, distances/angles, severity, materials and collision types. Ground truth established independently of algorithm where possible.

### D. Blind/held-out evaluation
Separate development, calibration, held-out test and external validation if available. Developers do not tune against final held-out. Pre-register acceptance thresholds and methods.

### E. Metrics
Detection precision/recall, localization error, measurement error, false positives/negatives, calibration error, coverage by vehicle/capture condition, occlusion performance, reviewer agreement, and correct inconclusive-rate. Report denominator, confidence interval, cohort and failure modes. Do not make unsupported general accuracy claims.

## 12. Phase 9 — first executable vertical slice

Do not build six disconnected engines simultaneously. Deliver **V1: one vehicle, one damage region, one defensible measurement**:
1. Register synthetic collision/session.
2. Capture/register original evidence.
3. Verify original hashes and persistent provenance.
4. Validate/decode VIN with source and corroboration limits.
5. Identify one component.
6. Capture controlled view with calibration/reference.
7. Detect and segment one damage region.
8. Perform one calibrated geometric measurement.
9. Quantify uncertainty.
10. Create evidence-linked finding.
11. Generate versioned reproducible report.
12. Independent person/tool verifies originals, provenance, methods, calculation and conclusion.

Start synthetic known-answer fixtures. Then non-sensitive controlled test vehicles and independently measured reference conditions. Real participant evidence stays out of scope until gates and authorization are met.

## 13. Phase 10 — implementation discipline and gates

| Gate | Acceptance |
|---|---|
| G1 | Contract defined/versioned |
| G2 | Real implementation integrated |
| G3 | Mathematical correctness independently tested |
| G4 | Failure/adversarial cases tested |
| G5 | Database/API integration verified |
| G6 | Exact PR head CI green |
| G7 | Review and merge |
| G8 | Controlled end-to-end reproducibility |
| G9 | Independent validation appropriate to claim |
| G10 | Release/field acceptance where applicable |

Passing G6 is not forensic quality. M0–M8 order/dependencies are defined in `docs/forensics/FORENSIC_SUBSTANTIATION_PROGRAM.md`; this document provides the complete engineering contract.

## 14. Current implementation state — truth snapshot (must be checked live)

- Canonical repository: `C2C-Connect/claim2car-connect`; legacy `claim2car-faos-v1` is superseded historical reference.
- Documentation PR #175 merged (commit `cf985ee92ed6624467bc8dbeaea9e25ff9e207fa`) established program and focus.
- PR #177 merged: synchronized README, CTO execution plan, execution handoff/status, this thread handoff, acceptance matrix, core engine manual, product premise and foundational audit. Merge/check status should be verified against GitHub before relying on a snapshot.
- PR #176 is the active draft implementation: `feat/persistent-forensic-provenance-m1`, head last recorded `36fdd083ebbbe1268e6e2f51d40dfe60b9523404`. Initial Python event/genesis commitment and verifier/known-answer tests only. Last recorded exact-head CI 13/13 successful; check current state live.
- M1 is **not accepted or merged**: SQL migration/backfill/parity, persisted hashes, append enforcement, complete server verification, manifest chain-tip binding, DB adversarial/restart/concurrency/tenant tests and independent verifier agreement remain.
- External trust checkpoint/signature/notarization is separate. No forensic certification, field accuracy, collision causation, deployment/accepted staging, live payment or dispatch is claimed.
- OCI staging remains undeployed/unverified and is not the current next engineering task; M1 is.

## 15. New-chat handoff

On resume, read `docs/THREAD_HANDOFF_2026-11-23.md`, this specification, `docs/forensics/FORENSIC_SUBSTANTIATION_PROGRAM.md`, `docs/EXECUTION_HANDOFF.md`, `docs/EXECUTION_STATUS.md`, `docs/acceptance/ACCEPTANCE_MATRIX.md`, the foundational audit, product premise and core-engine manual. Check main and PR #176 live. Continue implementing M1 from SQL migration/backfill/parity onward; do not re-plan, widen scope, claim acceptance, or merge before the gate. After each verified increment synchronize handoff/status/acceptance references and report commit, exact tests/checks and limitations.