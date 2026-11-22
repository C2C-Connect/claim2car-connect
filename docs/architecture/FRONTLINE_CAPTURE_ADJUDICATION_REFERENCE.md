# Frontline Capture and Forensic Adjudication — Reference Architecture

**Status:** Owner-supplied target workflow; engineering reference pending validation  
**Date recorded:** 2026-11-18  
**Applies to:** Field capture, vehicle identity, offline evidence handling, technical assessment, adjudication, reporting, and recipient delivery  
**Governing product premise:** [Forensic Intelligence Product Premise](PRODUCT_PREMISE_FORENSIC_INTELLIGENCE.md)

> This document records the owner's intended frontline workflow and technical ambition. It is a target architecture, not evidence that the named devices, thresholds, services, algorithms, integrations, or performance figures are already implemented or validated. Every capability must pass the acceptance rules in this document before it is represented as operational or forensic-grade.

## 1. Intended operating journey

The target workflow begins at the physical vehicle and continues through a controlled backend assessment:

1. Identify the physical vehicle and validate the captured VIN locally.
2. Decode and source-attribute vehicle configuration before capture.
3. Guide the operator through a versioned, 16-point capture sequence.
4. Evaluate image quality and capture context at the edge, with retake guidance.
5. Preserve originals and a verifiable, ordered evidence manifest while offline.
6. Synchronize each session safely and idempotently when connectivity permits.
7. Validate evidence and provenance on the server before analysis.
8. Run separately versioned technical and vision assessments, with abstention when inputs are insufficient.
9. Produce evidence-linked findings, uncertainty, and a reasoned disposition.
10. Generate role-appropriate reports and distribute them only to authorized recipients.
11. Present the vehicle owner with clear next actions and an auditable collision-resolution status.

The stages are a single product journey, but each has an independently testable contract. A successful VIN decode does not establish damage. A complete photo sequence does not prove evidence sufficiency. A model score does not establish a total loss. A generated PDF does not prove authorized delivery.

## 2. Identity acquisition and vehicle intelligence

### 2.1 Local VIN acquisition and validation

The field client should support optical VIN capture from permitted vehicle locations and manual correction with an auditable operator action. The client should normalize case and whitespace, validate the expected VIN character set and length, and apply the appropriate check-digit rule before making a decode request.

For US-regulated vehicles subject to 49 CFR 565.15, the ninth character is the check digit. The position weights are:

`[8, 7, 6, 5, 4, 3, 2, 10, 0, 9, 8, 7, 6, 5, 4, 3, 2]`

Letters are mapped using the regulatory transliteration table; I, O, and Q are not valid VIN characters. Multiply each mapped value by its position weight, sum the products, and take the remainder modulo 11. Remainders 0–9 map to digits; remainder 10 maps to X. The ninth position has weight zero for the calculation.

**Jurisdiction matters.** Do not apply the North American check-digit rule as a universal rejection rule for every global VIN. Validation must identify the relevant market/standard and distinguish invalid, unsupported, incomplete, and unverified inputs. A check digit detects many transcription errors; it does not prove that the physical VIN belongs to the vehicle in front of the camera. Where risk warrants it, compare multiple physical VIN locations and source the result.

Reference: US regulation, 49 CFR §565.15, [Content requirements](https://www.govinfo.gov/content/pkg/CFR-2024-title49-vol6/pdf/CFR-2024-title49-vol6-sec565-15.pdf).

### 2.2 vPIC decoding, source lineage, and caching

NHTSA vPIC is an appropriate first decoder for supported US-market vehicles. Its API returns decoded key/value variables, supports model-year-specific requests, and documents rate control. Its dataset is based on manufacturer submissions. The returned variable set and completeness must be treated as response data—not as a guaranteed fixed set of “140+” populated attributes for every VIN.

Implementation requirements:

- Use an adapter around vPIC; do not make the mobile client depend directly on a vendor response shape.
- Send model year when known and required to disambiguate decoding.
- Persist the raw response (or a privacy-reviewed normalized snapshot), request time, provider, API/dataset version where available, decode errors, and per-attribute provenance.
- Distinguish decoded, operator-entered, owner-provided, manufacturer-sourced, and inferred attributes.
- Treat blank, unavailable, conflicting, or low-quality values as unknown; never fill them with plausible defaults.
- Respect provider rate limits; use bounded caching and a controlled refresh policy.
- A 30-day cache may be evaluated as a starting TTL, but a sliding expiration must not keep stale data alive indefinitely. Record source freshness and support explicit refresh.
- Curb weight and GVWR are different measurements. Do not substitute one for the other or assume vPIC will supply a reliable curb mass for every VIN.

Official references: [NHTSA vPIC API](https://vpic.nhtsa.dot.gov/api/) and [vPIC overview](https://vpic.nhtsa.dot.gov/About).

### 2.3 Mass and dimensional inputs

The proposed 500–5,000 kg interval can be used as an initial plausibility check for a defined passenger/light-vehicle assessment cohort, not as a universal physical truth. Do not silently clamp a decoded or supplied mass into that interval and then use the altered value as if it were measured.

Store:
- the original value and unit;
- the source and timestamp;
- normalized value and conversion method;
- validation status and applicable vehicle cohort;
- any approved model-input bound or fallback, separately identified; and
- the reason for rejection, abstention, or human review.

If the source value is absent, contradictory, or outside the validated domain, the physics module must abstain or use a clearly labeled, independently justified input path. It must not manufacture a mass.

## 3. AR-guided, versioned 16-point capture

The target field device profile is an 11-inch M4 iPad Pro with a PWA/Capacitor client. Device selection is a deployment assumption to verify, not a substitute for device capability tests. The implementation must detect available cameras, sensors, permissions, storage, and supported APIs at runtime.

### 3.1 Capture sequence

The target 16-point protocol is:

| Group | Required view |
|---|---|
| Exterior perimeter (8) | Front; front-left 45°; left profile; rear-left 45°; rear; rear-right 45°; right profile; front-right 45° |
| Structural / mechanical (4) | Underbody/frame rails; wheel wells/suspension; engine bay/firewall; roofline/A-B-C pillars |
| Cabin / interior (2) | Airbag deployment and restraint indicators; dashboard warnings, center console, and visible structural shift |
| Evidence / telemetry (2) | Odometer; insurance card or registration document |

Each slot must define purpose, subject, required/conditional status, guidance, accepted media types, quality checks, privacy classification, and retry behavior. The exact slot contract is versioned and bound to the session. Historical 12-slot sessions remain interpretable under their original contract; they must not be silently upgraded or judged as if the newer sequence had existed.

Some views may be unavailable, unsafe, inaccessible, or inappropriate for a given vehicle or incident. The workflow needs explicit, reason-coded exceptions and review paths rather than encouraging unsafe operator behavior or false completion. Document capture containing personal or policy data requires a separate access and redaction policy.

### 3.2 Silhouette and alignment HUD

A body-class-specific normalized wireframe can help an operator frame the vehicle consistently. It is a **capture aid**, not a metrology instrument.

The proposed alignment score (at least 0.55) and frame fill (at least 85%) are hypotheses to test. They must not be presented as proof that perspective, scale, parallax, camera pose, or physical dimensions have been corrected. Any metric claim about dimensions or crush displacement requires calibrated camera geometry, known reference dimensions or validated depth sensing, repeatability testing, and an uncertainty budget.

Acceptance must measure capture completion, retake rate, operator variability, false acceptance/rejection, and downstream usefulness across vehicle body classes, lighting, distances, device orientation, and real field conditions.

## 4. Edge quality gates

The intended design evaluates available quality signals locally before an artifact is accepted into the session queue. The first three proposed gates are image/camera signals; the fourth, acoustic quiet, is a separate sensing task and must not be conflated with photographic quality.

### 4.1 Optical sharpness

Laplacian variance is a candidate blur indicator. A threshold such as 160.0, with a low-light fallback such as 90.0, is not universal: it varies with image resolution, resizing, noise, texture, exposure, focus, and device processing.

Requirements:
- calculate against a defined, versioned image representation;
- calibrate by device/camera mode and capture conditions;
- test false acceptance and false rejection on labeled field images;
- combine with other focus/blur signals and operator review; and
- store metric, threshold version, decision, and retake reason.

### 4.2 Exposure and luminance

A single mean RGB brightness interval is not sufficient to detect all shadows, glare, clipping, or uneven illumination. Use histogram and clipped-pixel measures, local-region checks, and camera metadata where available. Thresholds must be calibrated against whether the relevant damage/detail remains inspectable, not selected only for convenience.

### 4.3 Motion and stability

A motion threshold such as 0.6 m/s² is a candidate, not a universal pass/fail rule. Define sensor units, coordinate frame, sampling rate, synchronization, orientation compensation, and device-specific calibration. Combine IMU signals with image motion where appropriate. If the sensor bridge is unavailable, record that fact and use an approved fallback rather than treating missing sensor data as zero motion.

### 4.4 Acoustic capture

The proposed requirement of at most -40 dBFS for 30 seconds is **not an image-capture quality gate**. It is a potential acoustic measurement protocol that needs a separate purpose, calibrated microphone assumptions, controlled test procedure, permission, retention policy, and independent validation.

Ambient scene noise cannot by itself establish a valid chassis tap test or a reliable FFT resonance signature. If acoustic diagnostics are developed, they must be a separate opt-in task with explicit instructions, reference excitation, device/microphone calibration, environmental-noise handling, and a validated interpretation method. Audio must not be collected merely because the camera is being used, and an acoustic permission denial must not block ordinary photo evidence capture.

### 4.5 Gate decisions and user experience

Each quality gate returns a structured result: PASS, RETAKE, EXCEPTION_REVIEW, or NOT_AVAILABLE, with metric provenance and an operator-readable explanation. A pass means the artifact meets that gate's capture criterion; it does not mean the image proves a technical finding.

## 5. Cryptographic evidence sealing and offline synchronization

### 5.1 Preserve originals and derivatives

The client must retain the original captured bytes as the source artifact. Crops, resized previews, overlays, segmentation masks, annotations, transcoded copies, and other transformations are derivative artifacts with explicit parent references and transformation metadata. Never replace the original with a processed image.

### 5.2 Hash chain and server verification

A session sequence may use a chain such as:

`hash_k = SHA-256(photo_bytes_k || previous_hash_{k-1})`

The exact encoding, initial value, algorithm identifier, and manifest schema must be versioned and tested. The server must independently recompute every artifact digest and chain link from received original bytes and compare them with the submitted manifest.

A client-generated hash chain is a tamper-evidence mechanism, not proof that the image is authentic, was captured at the claimed time/location, or came from an untampered camera. Stronger provenance requires explicit threat modeling and, where appropriate, device/app attestation, signed manifests, trusted server receipts/timestamps, and independent corroboration. Do not claim a browser hash proves chain of custody by itself.

### 5.3 IndexedDB and local outbox

IndexedDB is persistent browser storage, not a hardware-backed WORM medium. Application code can update or delete records; browser storage may be cleared or evicted. The client can implement append-only application semantics and detect accidental or unauthorized changes, but it must not call the browser database intrinsically immutable.

Required safeguards:
- encrypt sensitive local data at rest using a device-appropriate key-management design;
- use an append-only session manifest with explicit state transitions;
- persist originals, digests, sequence, session/protocol identity, consent reference, device/app metadata, and synchronization status;
- detect quota exhaustion, eviction, app termination, clock changes, and partial writes;
- provide visible recovery/resume behavior and prohibit false “uploaded/sealed” status;
- verify the full manifest server-side before evidence becomes trusted for assessment; and
- define retention and secure local cleanup after server acknowledgment under the applicable policy.

### 5.4 Session-scoped FIFO sync and idempotency

The desired behavior is ordered, resumable draining within each session, while unrelated sessions can continue independently. A failed upload blocks later dependent sequence entries in that session until retry/reconciliation; it should not freeze all vehicles or sessions.

Use bounded exponential backoff with jitter and explicit retry ceilings. The example 2/4/8/16/32/60-second progression is a candidate policy, not a guarantee that the browser will execute background work at those exact times. PWA and Service Worker execution is platform-controlled; iOS background execution must be verified on the actual fleet device. Provide foreground resume and operator-visible pending/failed states.

Server idempotency must be durable at the database/domain boundary, using tenant/session/request identity and unique constraints. A Redis lock may reduce duplicate work but must not be the sole protection: it can expire, be evicted, or be unavailable. A duplicate request should return the stable result of the original operation (or a clearly documented replay response), not create another artifact, event, assessment, delivery, or payment. HTTP 202 is appropriate only when the operation is actually accepted for asynchronous processing; “ignored” must not conceal a failed or unknown outcome.

## 6. Dual-engine assessment: physics and vision

The intended design has two distinct technical evidence paths:
- a deterministic, versioned physics/engineering model using explicit physical inputs and documented assumptions; and
- a computer-vision pipeline that detects/localizes visible conditions and describes image-supported observations.

They may inform a joint review, but neither should be allowed to manufacture missing inputs or overrule a safety-critical uncertainty without a validated rule.

### 6.1 DARCI physics model

The repository already contains a Python DARCI model and versioned constants. It computes kinetic energy, an energy/deformation force proxy, zone stress estimates, yield ratios, entropy, and a physics total-loss signal. This is existing code, not yet proof of a validated crash-reconstruction or structural-integrity instrument.

Key engineering limits:

- `E_k = 1/2 m v^2` requires a defensible mass and a defensible velocity for the relevant vehicle. VIN decoding does not supply collision speed. A still photograph does not establish pre-impact velocity.
- `F = E/d` is an average-force approximation only under an explicit assumption that the modeled energy is dissipated over the modeled deformation distance. It is not automatically peak impact force or a local force distribution.
- `sigma = F/A` requires a physically justified load path and effective area. Generic zone-area constants do not establish local component stress in a complex vehicle structure.
- Yield strength depends on the actual material, grade, geometry, loading direction, strain rate, temperature, joining, and structural design. Generic mild-steel/AHSS/aluminum constants cannot prove a specific vehicle component has yielded.
- A depth point cloud or a set of crush measurements must be calibrated, registered, and associated with a known reference geometry before physical interpretation.
- Shannon entropy of a small vector of zone depths is a descriptive statistic. An arbitrary threshold such as H > 2 bits cannot mathematically guarantee hidden structural collapse.
- A model override must never be described as an absolute physical guarantee unless independently validated against an applicable ground-truth domain.

DARCI output must include input provenance, units, uncertainty ranges, missing-input flags, formula/constants version, applicability domain, and an abstention state. Keep raw observations separate from modeled estimates. Before field use, validate against independently measured crash-test/inspection cases and qualified structural assessments, including false-negative safety analysis.

### 6.2 Vision pipeline

YOLO, SAM, monocular depth, LiDAR, and multimodal language models are candidate tools, not a validated stack merely because their names appear in a design.

For each component:
- pin model and runtime versions and preserve model artifact identity;
- define supported classes, vehicle domains, image requirements, and known failure modes;
- measure precision/recall, localization error, calibration, latency, and abstention performance on held-out real-world cases;
- distinguish detection confidence from probability that damage exists or is structurally significant;
- ensure segmentation area and monocular/LiDAR depth are calibrated before reporting physical units such as cm² or cm³;
- prevent a language model from inventing observations or silently converting image interpretation into verified fact; and
- keep human review and escalation available for safety-relevant findings.

A model stack must be selected by measured performance, device/server constraints, privacy, cost, licensing, and operational support—not by a fixed vendor list.

### 6.3 Combining signals and making a disposition

A weighted expression such as:

`P_combined = 0.55 P_physics + 0.45 P_vision`

is a weighted score or linear opinion pool unless the inputs and combination method have been calibrated and justified as a probabilistic model. Calling it “Bayesian consensus” does not make it Bayesian. Physics and vision outputs may share correlated inputs (for example, the same images or assumed crush depth); dependence must be modeled.

Before any ensemble probability is exposed:
- define the target event precisely;
- define independent ground truth and a representative validation cohort;
- calibrate each model and the combined output;
- measure reliability, Brier/log loss, discrimination, subgroup performance, and safety-relevant false negatives;
- validate thresholds prospectively; and
- define abstention when inputs are missing, out of domain, or contradictory.

**Technical damage assessment must remain separate from commercial routing.** A threshold must not automatically send a vehicle to a dealer or repair-shop auction based on a physics probability. Total-loss disposition depends on the applicable valuation, repair estimate, salvage, jurisdictional rules, policy/insurer process, and authorized decision-maker. Structural risk can trigger inspection or safety escalation; it does not alone establish economic total loss.

## 7. Evidence integrity: replace composite badges with explicit states

A weighted integrity score combining GPS, hash, and metadata may be useful as an experimental operational indicator, but it must not be represented as proof of authenticity or a universal “GATE PASSED” forensic trust badge.

These signals answer different questions:
- hash verification: do received bytes match the digest/manifest that was committed?
- chain verification: is the artifact order consistent with the committed sequence?
- location metadata: what location did the device report, with what accuracy and provenance?
- timestamp metadata: what clock/source produced the time, and what is independently trusted?
- device/app metadata: what environment claims to have produced the capture?
- corroboration: do independent records support the asserted context?

Represent each result separately, with status, source, limitations, and verification time. A hash mismatch is a serious integrity failure; a matching hash is not proof of truthful capture context. Avoid collapsing distinct claims into a single numeric trust score without a validated threat model and documented interpretation.

## 8. Reports and recipient-specific dispatch

The report dispatcher should create separate, purpose-limited deliverables from one canonical assessment record. Each deliverable must state its intended audience, scope, authorization basis, schema/version, redactions, source references, and limitations.

| Recipient | Intended deliverable | Mandatory controls |
|---|---|---|
| Insurer / authorized claims recipient | Evidence-backed incident dossier and supported structured export | Carrier-specific schema validation, explicit consent/authority, provenance, limitations, delivery receipt |
| Brand dealer | Authorized vehicle/incident summary or acquisition packet | Separate commercial purpose and opt-in; no contact/financial data until authorized; no technical finding altered by lead value |
| Collision repair facility | Repair/inspection packet with visible damage, uncertainty, and required diagnostics | Minimum necessary data, VIN/PII masking where required, no unsupported parts/labor/ADAS claims |
| Vehicle owner / driver | Plain-language findings, uncertainty, safety escalation, report access, next steps | No “safe to drive” clearance without qualified authority; accessible explanation and correction path |

### 8.1 ACORD and structured carrier exports

The repository currently contains an XML builder explicitly described as a simplified ACORD-oriented structure, not a full ACORD-certified schema implementation. Do not label its output “ACORD 1 XML AutoLoss v2.14.0” or promise compatibility with Guidewire, Duck Creek, CCC, or another carrier system without an exact schema/version, conformance tests, partner integration, and acceptance evidence.

Implement carrier adapters only against documented partner requirements. Validate XML against the applicable schema, test realistic sanitized fixtures, and verify delivery/acknowledgment. An XML document that parses is not necessarily ACORD-conformant or accepted by a carrier.

### 8.2 PDF and legal/forensic language

A generated PDF is a report artifact, not an automatic forensic certificate. Do not claim FRE 901/902 self-authentication, legal admissibility, certification, or insurer acceptance solely because a report contains hashes, signatures, Merkle roots, or technical language. Legal assertions require counsel-approved policy and a defined evidentiary process.

### 8.3 Commercial and financial fields

Dealer fees, repair-shop fees, auctions, owner incentives, operator payouts, BFPI scores, and financial posture are governed by separate commercial and legal decisions. They must not be embedded as assumptions in technical adjudication. No payout, auction, referral, or external CRM delivery may be activated by a damage model output alone.

## 9. Repository alignment snapshot

This is a point-in-time code inspection, not an acceptance declaration:

- The repository contains a versioned 16-slot capture default and quality constants for sharpness, luminance, and motion. Their presence does not prove the mobile runtime enforces or validates them.
- The repository contains a Python DARCI implementation and provisional physics constants, including 55/45 ensemble weights and an entropy override. These are model assumptions requiring validation, not established scientific facts.
- The repository contains an outbox abstraction whose inspected default storage is an injectable in-memory dictionary. This is not evidence of a persistent IndexedDB client outbox or a deployed worker.
- The repository contains an ACORD-oriented XML builder whose own module documentation says it is simplified and not a full ACORD certification.
- The inspected default-branch tree did not show the proposed `apps/pwa-field-client`, `services/darci-physics-wasm`, or `services/api-gateway` paths. Their existence and deployment must not be assumed.
- Collision-to-vehicle identity integration is being developed separately and remains unmerged until migration, authorization, consent revocation, restart persistence, and CI are verified.

Future agents must refresh this snapshot against the current default branch and exact commit before relying on it.

## 10. Product-level architecture: from evidence to coordinated resolution

The frontline capture workflow is the entry point to a larger operating platform. It must connect to the existing Collision Lifecycle Record and the platform's durable event spine; it must not become a standalone photo application or a parallel source of collision truth.

The target end-to-end architecture is:

1. **Field experience** — authenticated operator/driver intake, vehicle identity, versioned capture, quality guidance, consent, and offline recovery.
2. **Evidence and identity services** — original artifact storage, manifest verification, source lineage, vehicle registry, participant relationships, and collision association.
3. **Intelligence services** — evidence sufficiency, vehicle configuration, visible-damage observations, measurements, technical analysis, uncertainty, human review, and explainable findings.
4. **Decision and policy services** — versioned rules, authorization, safety escalation, evidence requirements, and approved dispositions. A model output is an input, never an authorization by itself.
5. **Workflow orchestration** — durable task plans, provider requests, acceptance/rejection, dispatch handoffs, completion evidence, verification, recipient delivery, and collision-event resolution.
6. **Participant and partner network** — drivers, operators, repair facilities, dealerships, insurers, towing and other qualified providers, accessed through role- and purpose-limited interfaces.
7. **Transaction and integration services** — quotes, service orders, estimates, invoices, fees, payouts, payment reconciliation, partner adapters, and external delivery. These remain separate state machines with explicit release gates.

The Collision Lifecycle Record remains the collision identity and event boundary. Claims, repair orders, provider engagements, dispatches, reports, deliveries, and financial obligations are linked domain records with their own authority and lifecycle. Do not overload a single status column to represent the whole post-accident journey.

### 10.1 Handoff semantics

Every consequential handoff must persist at least the requesting actor and tenant, purpose/authority, target participant, scoped work, terms/version, idempotency key, request time, response, and resulting state. Model recommendation, request, acceptance, execution, completion, verification, and settlement as distinct events. A timeout is not a rejection; a sent message is not delivery; delivery is not acknowledgment; acceptance is not completion; completion is not verification; and a verified service is not necessarily financial settlement.

Use transactional outbox delivery and idempotent consumers. External providers and integrations are adapters, not alternate sources of truth. Preserve retries, cancellations, corrections, and disputes as auditable events rather than rewriting history.

### 10.2 Independent domain state machines

At minimum, keep these lifecycles separately governed and linked by explicit identifiers/events:

- collision event and resolution;
- vehicle identity and collision association;
- capture session and protocol version;
- evidence artifact, manifest, and sufficiency review;
- consent, disclosure authority, and revocation;
- technical assessment and human review;
- provider engagement and service acceptance;
- dispatch and physical custody transfer;
- repair/inspection work and completion verification;
- report generation, recipient delivery, and acknowledgment; and
- financial obligation, invoice, payout, payment, and reconciliation.

The list is a domain boundary guide, not a requirement to create a microservice or a new database table for every bullet. Implement cohesive modules in the existing modular monolith, with PostgreSQL as the authority and background workers for durable asynchronous work. Split services only when measured scaling, isolation, or operational requirements justify it.

### 10.3 What the platform must never infer

- A VIN decode does not prove vehicle ownership or collision involvement.
- A complete capture sequence does not prove every technical question can be answered.
- A model score does not establish a total loss, roadworthiness, liability, repair authorization, or provider eligibility.
- A provider recommendation does not establish provider acceptance.
- Provider acceptance does not establish service completion or quality.
- A dispatch request does not establish pickup, custody transfer, or delivery.
- A report generated or sent does not establish receipt, acknowledgment, or legal acceptance.
- A service completion does not establish payment; a payment event does not establish collision-record resolution.

Each transition requires its own evidence, authority, and acceptance criteria.

## 11. Implementation sequence and acceptance gates

Build a vertical slice in this order, reusing existing platform boundaries:

1. **VIN identity contract:** local parser/check digit with jurisdiction handling; capture/manual correction audit; vPIC adapter; per-attribute provenance; error/unknown behavior; cache freshness.
2. **Vehicle registry integration:** consent-bound source event, tenant-scoped vehicle identity, collision association, multiple-source lineage, revocation behavior, idempotency, and restart persistence.
3. **Field capture contract:** versioned 16-slot sequence, conditional exceptions, silhouette framing aid, local quality results, operator retakes, device capability checks.
4. **Offline evidence pipeline:** original bytes, derivative lineage, manifest/hash chain, encrypted local queue, quota/recovery handling, session FIFO, foreground resume, durable server idempotency, server recomputation.
5. **Evidence sufficiency and review:** per-question sufficiency, missing/contradictory evidence, human review, safety escalation, reproducible assessment inputs.
6. **Validated analysis contracts:** separate vision and physics outputs, applicability/uncertainty, calibrated abstention; no commercial fork.
7. **Explainable report:** canonical finding references, methodology, source lineage, limitations, review history, versioned output.
8. **Authorized delivery and driver resolution:** recipient/purpose authorization, recipient-specific redaction, persistent delivery status, acknowledgment, next steps, auditable closure.

Every stage must have:
- unit and contract tests;
- real integration tests across API, database, storage, and authorization;
- tenant-isolation, consent-revocation, replay/idempotency, tampering, restart, and failure-recovery tests as applicable;
- field/device tests for mobile capabilities and offline behavior;
- independently sourced accuracy validation for any technical assessment claims; and
- a release-gate update that distinguishes implemented, integrated, tested, accuracy-validated, field-validated, deployed, and operationally accepted.

No hard-coded threshold, probability, safety verdict, or total-loss rule becomes authoritative merely because a test fixture passes. Define its applicability domain, validation dataset, acceptance threshold, owner, version, and review process first.

## 12. Engineering rules for future agents

1. Read this document and the governing Product Premise before changing the frontline workflow.
2. Inspect the current repository, active PRs, exact default-branch SHA, migrations, and workflow results; this document is not a substitute for live repo inspection.
3. Treat the 16-point workflow and named components as the target design, not as proof of current implementation.
4. Do not silently convert provisional thresholds, constants, model names, weights, or commercial rules into production policy.
5. Preserve raw evidence, source lineage, consent, tenant scope, and uncertainty through every stage.
6. Keep physics/vision assessment separate from total-loss, dealer, shop, auction, payout, or other commercial decisions.
7. Do not claim WORM, cryptographic authenticity, chain of custody, ACORD conformance, legal admissibility, accuracy, or production readiness without the corresponding evidence.
8. Continue with small, integrated, tested vertical slices; do not create placeholder services to make an architecture diagram appear complete.

## 13. Governing principle

The field workflow should make it easier to collect better evidence, not make weak evidence look conclusive. The backend should turn validated evidence into reproducible, explainable findings—not turn model scores into unquestionable verdicts. Reports should tell each authorized recipient exactly what is known, how it is known, what remains uncertain, and what action is justified.

That is how Claim2Car earns the right to coordinate the post-accident economy: by making the record trustworthy first.


## Owner FAOS manual traceability (2026-11-22)

The [FAOS Core Engine Implementation Guide](FAOS_CORE_ENGINE_IMPLEMENTATION_GUIDE.md) is the consolidated owner-supplied implementation target for this reference. It extends capture and adjudication into the full operating-system journey: sensor/device qualification, VIN and vehicle provenance, 16-point sequence, quality gates, local cryptographic sealing and FIFO recovery, durable server ingest, DARCI and vision/context models, integrity scoring, consensus/human review, statutory triage, commercial routing, report delivery and settlement. Use the manual for subsystem requirements and acceptance tests.

All supplied numerical values, model names, latency targets, physical overrides, score weights and decision thresholds are provisional until independently validated. They are not current product guarantees and must not become authoritative total-loss, repairability, legal or payment decisions merely because they appear in a specification. Current implemented behavior is determined by code and acceptance evidence.
