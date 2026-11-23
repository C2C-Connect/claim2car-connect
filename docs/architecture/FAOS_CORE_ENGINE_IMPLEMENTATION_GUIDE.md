# Claim2Car Connect™ Forensic Operating System (FAOS)

## Active engineering handoff: forensic substantiation (2026-11-23)

The owner has narrowed active work to substantiating claims, starting M1 persistent provenance. Read docs/THREAD_HANDOFF_2026-11-23.md and docs/forensics/FORENSIC_SUBSTANTIATION_PROGRAM.md for current implementation status and ordered gates. Initial PR #176 Python hash/verifier code is only a draft slice; SQL persistence, manifest chain-tip binding, DB adversarial testing and independent verification remain. This manual’s target capabilities, thresholds, equations, models, examples and vendor references are requirements/hypotheses—not evidence of implementation or validation. Do not claim forensic certification, accuracy, causation, trusted timestamping or independent notarization. Dispatch and payments remain gated.


## Active engineering handoff: forensic substantiation (2026-11-23)

The owner has narrowed active work to substantiating claims, starting M1 persistent provenance. Read docs/THREAD_HANDOFF_2026-11-23.md and docs/forensics/FORENSIC_SUBSTANTIATION_PROGRAM.md for current implementation status and ordered gates. Initial PR #176 Python hash/verifier code is only a draft slice; SQL persistence, manifest chain-tip binding, DB adversarial testing and independent verification remain. This manual’s target capabilities, thresholds, equations, models, examples and vendor references are requirements/hypotheses—not evidence of implementation or validation. Do not claim forensic certification, accuracy, causation, trusted timestamping or independent notarization. Dispatch and payments remain gated.

## Core Engine Implementation Guide & Subsystem Engineering Manual

**Owner-supplied governing target:** 2026-11-22  
**Status:** Binding product direction; implementation and validation are tracked separately in the acceptance matrix.  
**Repository:** C2C-Connect/claim2car-connect

This manual consolidates the owner's FAOS operating vision into durable engineering requirements. It is a product premise and target architecture—not a claim that every named device, model, algorithm, threshold, vendor integration, blockchain anchor, performance result, financial rule, or legal outcome is implemented or validated. Requirements must be translated into executable contracts, implemented, tested, and field/operationally validated. The latest acceptance matrix and execution snapshot remain the source of truth for actual status.

## Product doctrine

Claim2Car is to become an integrated forensic operating system for the post-collision journey: capture and preserve evidence; identify the vehicle; establish what is observable and supported; explain uncertainty; enable authorized review; route appropriate opportunities and services; produce auditable reports; and track resolution. Evidence, provenance, consent, security, traceability, and user accountability are not add-on features.

**Build the product, not the presentation of a product.** No planning-only increments, mock data presented as live, fake integrations, or unverified completion claims. Execute implementation → tests → diagnosis/fix → exact revision verification → merge → deploy → real end-to-end validation. Synthetic records are confined to tests and controlled demonstrations.

## 1. System invariants and target architecture

### 1.1 Sensor-edge / field ingestion
Target frontline flow: a managed fleet baseline of 11-inch M4 iPad Pro hardware in MDM/kiosk mode, using camera, LiDAR where available, CoreMotion and permitted audio sensors. The fixed hardware premise is intended to standardize capture and sensor availability. Device enforcement, MDM, sensor bridges, LiDAR capability, and actual device qualification must be separately verified. Do not silently treat a browser or nonqualified device as equivalent; report capability gaps.

Target functions:
- locally validate VIN before remote decode (US-regulated VIN check-digit rule where applicable; international standards/jurisdiction handling is explicit);
- guide a versioned 16-point perspective walkaround (8 exterior angles, 4 structural views, 2 cabin perspectives, 2 telemetry frames; exact contract, ordering, exceptions and recovery are versioned);
- run image-quality, lighting, blur, stability and contextual gates; retake recommendations are not evidence deletion;
- capture optional spatial, motion, audio, and touch/sensor telemetry only with permission, hardware capability and documented purpose;
- assign stable event/artifact/session/actor identifiers and trustworthy timestamps with clock-source uncertainty disclosed;
- seal originals locally, maintain a session-scoped FIFO resumable queue, and synchronize without losing originals.

### 1.2 Quality-gate target parameters (not universal truth)
Owner reference values to be evaluated with real, representative data and calibrated per-device/environment:
- Laplacian sharpness variance: target Σ² ≥ 160 in normal light, ≥ 90 low light; mean luminance target 40–220 (8-bit scale).
- Motion/stability: acceleration magnitude deviation/threshold target 0.60 m/s²; define coordinate frame, gravity handling, sensor sampling, and calibration before using.
- Acoustic quiet: target ambient ≤ −40 dBFS over a 30-second tap-test interval, FFT size 2048, smoothing 0.8; implement only with consent and hardware qualification.
- Quality gates provide reasoned retake/advisory and provenance. They must not discard/alter original bytes or falsely claim forensic validity. The current browser gate is advisory; thresholds are provisional and not equivalent to the target.

### 1.3 Edge integrity and offline-first sync
Target: WebCrypto SHA-256 artifact hashes, canonical manifest/event chain, append-only local evidence store and IndexedDB outbox; sync FIFO by session, resumable and idempotent. Any failure in a session halts that session's ordered drain while independent sessions can continue. Retries use bounded exponential backoff with jitter. Retain original payloads until server acceptance and verified durable receipt; queue records should not be falsely called WORM absent storage-level write-once enforcement and key/device controls. Record encryption-at-rest, key derivation, rotation/recovery, and purge behavior.

### 1.4 Gateway and persistence
Target service boundaries: authenticated FastAPI ingestion, durable PostgreSQL 16 + PostGIS relational source of truth, distributed idempotency (Redis or database-native durable constraints/locks), and append-only forensic event records. The manual references MongoDB/Motor as an event-ledger option; this is not a requirement to introduce a second database unless justified. Do not implement a Redis-only idempotency guarantee that can outlive or diverge from durable database state. Use transaction/outbox patterns, uniqueness constraints, idempotent processing, retention controls, tenant isolation and reconciliation. Choose one authoritative event-store strategy and document migration/backup/restore.

### 1.5 Cryptographic provenance and evidence chain
- Hash original artifacts at intake and bind artifact ID, session, actor, sequence, capture time/time-source, metadata, consent, quality result and storage reference in a canonical manifest.
- Maintain sequential chain links and reproducible verification; preserve prior entries, append corrections/superseding events.
- A Merkle tree/root is useful for batch proof, but is not interchangeable with an individual SHA-256 hash, digital signature, chain, or public anchor.
- Public Polygon anchoring is a target only. If pursued, disclose public metadata leakage, fees, key custody, chain/network, transaction proof, failure handling and revocation limits. Never invent a transaction/root. Blockchain alone does not authenticate who created evidence or make it admissible.
- FRE 901/902(13)/(14) are evidentiary frameworks, not automatic legal certification. The system supports authentication with documented processes; legal admissibility is jurisdiction- and case-dependent.

### 1.6 Session and tenant isolation
Session-scoped, actor- and tenant-bound data; ordered synchronization; least privilege; consent and authorization enforcement; independent session queues; durable audit. Fail closed on cross-tenant/session binding errors, hash mismatch, duplicate/dropped sequence, malformed evidence, revoked consent where applicable, or conflicting authoritative state. A failure should preserve the evidence and explain the hold rather than silently destroy it.

## 2. Vehicle identity and configuration

VIN contract:
- 17-character VIN validation with forbidden I/O/Q characters and weighted Modulo-11 check digit for jurisdictions that require it (US 49 CFR 565.15);
- normalization, structured validation errors, and explicit distinction between checksum-valid and physical-vehicle-authenticated;
- decode via source-attributed adapter such as NHTSA vPIC; preserve provider, raw/normalized response, retrieval time, decode errors, field-level source and confidence;
- cache policy may use 30-day TTL as a starting hypothesis, with refresh/staleness policy and rate-limit handling;
- mass inputs require units, provenance and uncertainty; target clamp 500–5000 kg is a safety bound, not a substitute for rejecting bad source values or disclosing clamping.

Do not invent “140+ attributes” for an incomplete response. Unknown remains unknown; conflicting attributes require resolution.

## 3. Technical assessment: DARCI and multimodal AI

### 3.1 DARCI deterministic mechanics (target, not validated disposition authority)
Intended Rust/WASM calculations include kinetic energy E_k=0.5mv², work-energy force approximation F=E_k/d, stress σ=F/A, yield ratio r_y=σ/σ_y, brittle-fracture risk proxy, spatial deformation entropy H=−Σp_i log₂p_i, and a versioned physics score P_TL,physics. Inputs must be bounded, unit-checked, finite, sourced, and accompanied by uncertainty and applicability limits.

The supplied equations are simplified approximations: impact speed, crush distance, force distribution, area, material properties, vehicle structure, and voxel distributions are often unobserved or uncertain. Do not treat E_k/d as a measured collision force or the yield ratio/entropy as validated total-loss criteria. Thresholds and guards (e.g., H > 2 bits, r_y > 1, or score floors) are hypotheses requiring independent engineering validation, calibration, and human review. No physics rule may autonomously issue a legal/insurance total-loss determination in the current product.

### 3.2 Vision and multimodal analysis target
Target pipeline reference: YOLOv11 damage detection (52 classes, confidence target ≥0.55), SAM2 polygon segmentation, Depth Anything V2 + compatible metric depth/LiDAR fusion, and a context-capable LMM for airbag, fluid, cabin intrusion, warning-light and high-voltage observations. Model versions, licenses, runtime, hardware, latency, training/validation data, calibration, false-negative/positive rates, and output provenance must be recorded.

These named models are aspirational architecture candidates, not current live dependencies unless verified. A model may produce localized observations or risk signals; hidden damage and repairability require inspection. Missing models, low confidence, out-of-distribution input, or disagreement must trigger abstention/escalation, not fabricated output.

### 3.3 Consensus and human review
Owner's proposed ensemble: P_ensemble=0.55 P_TL,physics + 0.45 P_TL,AI, with routing threshold 0.55 and structural override proposals (H > 2.0 bits or r_y > 1.0). The weights, probability calibration, entropy meaning, override and routing threshold are not statistically validated. Preserve as a research/engineering target; do not encode as production authoritative triage until dataset, calibration, bias/safety analysis, external validation and legal review exist. Human adjudication must remain explicit and auditable. “Bayesian” must not be used as a label unless actual probability model/calibration justifies it.

### 3.4 Forensic integrity score target
Proposed score: S_i=0.30C_gps+0.45C_hash+0.25C_meta, target threshold 0.65. Hash continuity proposal: C_chain=sqrt(coverage·uniqueness); duplicate, missing, modified or unbound evidence should invalidate relevant integrity claims and place the case on hold. A numerical score must not hide critical failures; hard integrity violations override aggregate score. Document component definitions, units, ranges, missing-data behavior, calibration and independent test evidence. Current integrity outputs must be described only according to implemented contracts.

## 4. Triage, legal thresholds, commerce and dispatch

### 4.1 Jurisdiction-aware loss analysis
Target evaluates applicable 51-jurisdiction total-loss rules (including examples: California 75%, Florida 80%, Texas Total Loss Formula) using pre-loss ACV, repair estimate, salvage and statutory method. Jurisdiction and policy terms determine the correct formula. Keep legal/statutory rules versioned, source-cited, effective-dated, reviewed, and explainable. Never use a generic threshold or AI/physics score as a legal total-loss decision. ACV and repair estimates require source lineage and uncertainty.

### 4.2 Total-loss dealer path / BFPI
Proposed ACV blend: 40% BlackBook + 40% Manheim MMR + 20% market database; fallback proposal max(4000,32000·0.86^age); structural risk penalty min(0.45,0.60R_struct); adjusted ACV; loan amortization/equity; “Gold Lead” if equity > $2,500. Target dealer acquisition fee $375–$425 pay-on-close. These figures/formulas are commercial hypotheses and provider contracts/data are not presumed available. Never imply pricing feeds are live, generate valuation from fabricated market values, or expose sensitive lien/financial data without consent/authorization. Existing binding repository commercial rules supersede conflicting manual proposals unless the owner expressly changes them.

### 4.3 Repair auction
Target B2B auction: 10-minute window, 60-second anti-snipe extension, $250 floor commission, certified shops, transparent bid/acceptance/eligibility/audit, lead aging freshness 0.5^(ageHours/6). This is not live unless verified. Avoid real bidding, dispatch or charges until participant onboarding, eligibility, consent, legal terms, operational controls, fraud prevention, and payment gates pass.

### 4.4 Dispatch, reports and settlement
Target ACORD 1 XML AutoLoss extension, recipient-specific role-gated payloads, court-oriented PDF dossier, optional blockchain anchor and idempotent Square ACH. No template or example may contain fake identifiers/roots/transactions and be mistaken for real output. Report provenance, source, model/rule versions, limitations, reviewer, consent, recipient and delivery receipt. ACH/Square remains sandbox until independently authorized and verified. Commercial dispatch/settlement requires idempotency, reconciliation, reversal/error state, authorization and audit.

## 5. Data contracts (target)
Relational core: UUID identities; tenant and actor; vehicle incident/session; VIN; sourced configuration; GPS with accuracy; capture sequence/artifact references; consent; quality results; analysis and human review; jurisdiction; triage lifecycle; routing and recipient authorization; settlement status. PostgreSQL 16/PostGIS target. Constraints, indexes, tenant policies and migrations are acceptance-tested. Avoid client-trusted actor/tenant identifiers.

Forensic event record: event_id, session_id, sequence, event_type, actor_id, payload, prev_hash, entry_hash, timestamp, canonicalization/version. Hash the full canonical record and previous hash. Enforce sequence and uniqueness in durable storage. Verify chain by replay, include mutation/omission/reordering/duplicate tests, and record verification output. Append-only application logic is not equivalent to immutable storage.

## 6. Operational acceptance & test strategy
Tests are required for:
- VIN checksum/character/market cases and decode provenance/cache/failure;
- all 16 views: exact order, required/conditional slots, resume, retry, wrong-session/tenant, quality advisory, originals retained;
- image quality on representative real-world data, false rejects/accepts and threshold calibration;
- offline queue reload, FIFO, session isolation, idempotent retry, fail-and-halt, partial response, durable receipt and recovery;
- canonical hashes, chain continuity, missing/duplicate/reordered/altered artifacts, manifest binding, key/security lifecycle;
- physics dimensional/unit boundaries, non-finite/negative/missing inputs, numerical limits, model validation and independent comparisons;
- AI calibration, dataset leakage, subgroup performance, OOD/abstention, disagreement and human override;
- statutory rules with jurisdiction, effective date, source and adversarial cases;
- tenant/role/consent, report access, dispatch idempotency, payment sandbox/reconciliation;
- integrated journey, container, database, backup/restore, operational monitoring and device acceptance.

Use a gate registry with clear statuses: SPECIFIED → IMPLEMENTED → TESTED → VALIDATED → OPERATIONALLY ACCEPTED. BLOCKED and NOT IMPLEMENTED are valid states. Record gate ID, requirement, implementation reference, exact commit, test command/workflow and result, limitations, validation environment, approver and evidence link. CI green is not field validation. A gate must not be awarded based on documentation or synthetic demo alone.

## 7. Prioritization and handoff rules
Work in dependency order: edge identity/capture/originals/offline reliability; server durable acceptance and isolation; integrity/verification; reviewer and explainable assessment; report generation; authorized routing; settlement; production staging/device/field validation. For each increment, implement actual logic and tests, integrate with the running product, verify exact revision, merge after gates, deploy where authorized, and run a real journey. When blocked by credentials or external owner action, record the precise blocker and continue the next executable code/test task.

**Thread-resume instruction:** Before responding in a new chat, read README, this manual, docs/EXECUTION_HANDOFF.md, docs/EXECUTION_STATUS.md, and acceptance matrix; inspect current main, open PRs, checks, and deployment state; continue from the last unfinished verified increment. Do not re-plan, ask the founder to repeat direction, or claim unverified capability.


## Implementation checkpoint — FAOS capture protocol versioning

PR #165 merged the versioned `claims2car-16-v2` contract. It is selectable for controlled tests; `claims2car-16-v1` remains the default and `claims2car-12-v1` remains compatible. The current v2 slot mapping is 8 exterior, 4 accessible structural-corner, 2 cabin/restraint, 1 instrument-cluster telemetry, and 1 physical VIN identity image. The source manual calls for two telemetry frames; that difference is documented as an unresolved protocol-alignment issue. Do not mutate v2 in place; use a new version or a separately typed supplemental telemetry artifact.

The browser quality gate is advisory, not a hard capture rejection. No field calibration/qualification is implied. LiDAR, CoreMotion, acoustic gates, MDM restrictions, DARCI physics, multimodal AI, blockchain anchoring, ACORD live transmission, and live payment settlement remain individually subject to verified implementation and acceptance—not inferred from this manual.


## Canonical forensic requirements source

The complete owner-directed forensic substantiation specification is [COMPLETE_FORENSIC_SUBSTANTIATION_SPEC.md](../forensics/COMPLETE_FORENSIC_SUBSTANTIATION_SPEC.md) (relative path may be adjusted for document location). Use it as the detailed requirement and acceptance baseline; it is not implementation evidence. Keep the active focus on M1 PR #176 until accepted.
