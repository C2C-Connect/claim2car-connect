# Claim2Car Product Premise: Forensic Intelligence, Truth, and Resolution

**Status:** Owner-aligned governing product premise and architecture direction  
**Applies to:** Product strategy, domain modeling, architecture, implementation, AI/automation, reporting, acceptance, and future agent handoffs  
**Canonical repository:** `C2C-Connect/claim2car-connect`

> **Claim2Car does not simply process accidents. It establishes, documents, explains, and coordinates the truth that can responsibly be established about them.**

This document records the product vision agreed with the owner. It is intended to survive conversation and agent handoffs. Future contributors must treat it as a durable north star, not as a claim that every capability described here already exists.

## 1. What we are building

Claim2Car is an end-to-end post-accident intelligence and resolution platform.

Its central responsibility is to take a real-world vehicle collision from the moment it is reported through evidence collection, vehicle identification, technical assessment, explainable findings, reporting, authorized distribution, and coordinated next steps. It should help the people involved understand what is known, what can reasonably be concluded, what remains uncertain, what needs inspection or specialist attention, and what should happen next.

The platform's core output is not merely a claim record, photo folder, estimate, lead, or workflow status. It is a trustworthy, traceable, explainable incident record and a coordinated path toward resolution.

The system must be capable of:
- accepting a collision and identifying the involved vehicle(s), people, and relevant context;
- collecting and preserving original evidence under explicit authority and consent;
- determining whether the evidence is complete, usable, internally consistent, and sufficient for a particular assessment;
- identifying the vehicle and understanding its relevant configuration and technical characteristics;
- analyzing visible damage and other observations while distinguishing them from hidden or unverified damage;
- evaluating evidence and observations to produce supported findings, limitations, uncertainty, and appropriate escalation;
- generating accurate, reproducible, understandable reports;
- delivering each report or work packet only to authorized recipients;
- explaining findings and next steps to the driver in practical language;
- coordinating qualified downstream participants and services, with explicit acceptance and authorization boundaries; and
- recording the resolution of the collision event without falsely implying that every insurance, repair, payment, legal, or other downstream matter is complete.

The broader commercial ambition is to coordinate the post-accident economy responsibly: connect drivers, qualified operators, repair facilities, dealerships, insurers, towing and other authorized providers, and financial workflows around a reliable incident record. This network is a consequence of trustworthy intelligence and controlled orchestration—not a reason to weaken evidence standards or turn uncertain findings into sales claims.

## 2. The Post-Accident Truth Standard

Every material conclusion must be traceable, explainable, appropriately qualified, and open to independent scrutiny.

1. **Every factual assertion has a source.** Identify the originating artifact, person, system, measurement, record, or external reference.
2. **Every analysis has a method.** Record the applicable model, rule set, technical reference, version, reviewer, or procedure.
3. **Every conclusion has supporting evidence.** Show the observations and reasoning that support it.
4. **Every uncertainty is disclosed.** Missing evidence, ambiguity, conflicting sources, model limitations, and unobserved conditions must not be hidden.
5. **Every decision is reproducible.** Preserve the inputs, versions, rules, and decision history needed to understand and, where feasible, independently reproduce the result.
6. **Every correction is accountable.** Preserve prior states and record who changed or superseded a finding, why, and under what authority.
7. **Every report distinguishes epistemic status.** Clearly separate directly observed facts, externally sourced facts, measurements, model-generated inferences, human judgments, and unresolved questions.

The system must never manufacture certainty to make a workflow appear complete.

### 2.1 Evidence, observation, inference, and conclusion are different things

These concepts must remain distinct in domain models, APIs, user interfaces, reports, and audit records:

| Concept | Meaning | Example |
|---|---|---|
| Evidence | An original or referenced artifact offered for examination | Original photograph, document, video, or authenticated record |
| Observation | A directly recorded property of evidence or an inspected object | Visible deformation at a specific panel location |
| Measurement | A quantified observation with method and units | Measured gap, dimension, alignment, or diagnostic value |
| Inference | An interpretation derived from evidence and a stated method | A component may have been displaced |
| Finding | A conclusion supported to a stated degree by evidence and method | Visible damage is consistent with a particular impact area |
| Decision | An authorized action or disposition based on findings and policy | Request more evidence, refer for physical inspection, or release a report |

A photograph is not itself proof of every condition it appears to suggest. A VIN identifies a vehicle; it does not prove damage. A model score is not evidence. A visible-damage assessment does not establish the condition of components that cannot be seen.

### 2.2 Uncertainty and hidden damage

For each assessed item, the system should be able to express statuses such as:
- confirmed by direct observation or validated source;
- probable, with the supporting rationale and confidence basis;
- potential / suspected, requiring further evidence;
- requires physical inspection or specialist diagnosis; or
- cannot presently be determined.

For example, an exterior bumper photograph cannot establish the condition of the radiator support, crash structure, cooling system, restraint system, sensors, or other concealed components. The system must identify such limits and route the matter appropriately rather than imply that visible imagery establishes hidden condition.

Confidence must be calibrated against relevant validation data. An uncalibrated model score must never be presented as a probability of truth or allowed to override missing, contradictory, or insufficient evidence.

## 3. Frontline capture and adjudication reference

The detailed field workflow—from VIN acquisition and vehicle decoding through 16-point AR-guided capture, edge quality gates, offline evidence synchronization, technical adjudication, and recipient-specific reporting—is specified in the [Frontline Capture and Forensic Adjudication Reference Architecture](FRONTLINE_CAPTURE_ADJUDICATION_REFERENCE.md). That document explicitly separates owner-provided target design from verified implementation and identifies the scientific, security, privacy, and operational validation required before thresholds or model outputs can become authoritative.

## 4. The end-to-end collision journey

The intended product journey is one connected, auditable lifecycle. The stages below describe the target capability; implementation status must be verified separately.

### 3.1 Collision and vehicle intake
- Create a durable collision identity and establish tenant, actor, authority, consent, and correlation context.
- Capture relevant incident circumstances and identify involved vehicles and participants.
- Resolve vehicle identity from VIN and other supported sources; preserve the source and validation status of each attribute.
- Bind the applicable capture-protocol version to the session. The owner-approved 16-slot protocol is the new-session direction; historical 12-slot evidence must remain interpretable under its original version.
- Guide the operator or driver through required views, conditional views, image quality, retries, and missing information.
- Make the intake status and remaining requirements visible.

### 3.2 Evidence integrity and sufficiency
- Preserve original submitted bytes and source metadata; derived images, crops, annotations, and transformations are separate derivative artifacts.
- Record provenance, actor, tenant, session, timestamps, sequence, protocol, consent basis, request identity, and integrity metadata.
- Validate artifact readability, declared type, size, completeness, duplicates, expected sequence, and applicable capture requirements.
- Detect and disclose inconsistencies or integrity failures; do not silently repair or replace original evidence.
- Evaluate sufficiency for the specific question being asked. A complete capture checklist does not automatically mean the evidence is sufficient to answer every technical question.
- Request targeted additional evidence or route to human/specialist review when necessary.

### 3.3 Vehicle intelligence and technical context
- Resolve vehicle make, model, year, trim/configuration, and relevant technical attributes using traceable sources.
- Keep decoded, owner-provided, externally sourced, and inferred attributes distinguishable.
- Associate assessments with the correct vehicle and collision; support multiple vehicles without mixing their evidence.
- Use authoritative technical references where available and record source, version, and applicability.
- Never infer a vehicle attribute solely because it is common for a model year or trim.

### 3.4 Damage and condition intelligence
- Identify visible components and localize observable damage with evidence references.
- Classify damage type and severity only to the level supported by the input and validated method.
- Separate cosmetic appearance from potential structural, mechanical, electrical, restraint, sensor, and safety implications.
- Identify inaccessible or concealed areas and state when teardown, diagnostic scan, measurement, roadworthiness check, or physical inspection is needed.
- Preserve model/version, input references, output, confidence calibration basis, limitations, and human review/override history.
- Escalate safety-critical or ambiguous cases rather than allowing an automated workflow to issue an unsupported clearance.

- Treat normalized image coordinates and bounding-box area as image-space observations only; never convert them directly into physical area, crush depth, structural severity, or repair scope.
- Treat model class labels as unreviewed hypotheses and raw detector scores as uncalibrated scores unless a separately validated calibration process establishes otherwise.
- A two-dimensional exterior image cannot establish concealed structural, mechanical, electrical, restraint, cooling, or ADAS condition; require the appropriate measurement, diagnostic procedure, teardown, or qualified physical inspection.

### 3.5 Evidence-backed evaluation and decision
- Determine which questions can be answered from the available record and which cannot.
- Reconcile conflicting sources without silently selecting the convenient one.
- Apply versioned rules and authorization policies.
- Produce a reasoned disposition such as evidence sufficient for a limited finding, additional evidence required, specialist review required, or unable to determine.
- Keep technical assessment separate from commercial routing, eligibility, and payment decisions. A commercial incentive must never alter a technical finding.

### 3.6 Explainable findings and report generation
A report should be understandable to a driver and sufficiently detailed for an authorized professional to scrutinize. Depending on the report's purpose and authority, it should include:
- collision and vehicle identifiers;
- scope, purpose, author, generation time, and applicable versions;
- evidence inventory and provenance references;
- observations and measurements;
- damage inventory and location;
- technical findings and supporting evidence;
- methodology, source references, and model/rule versions;
- confidence basis, uncertainty, missing evidence, and limitations;
- safety flags and required inspection/escalation;
- repair assessment or estimate only when supported by the applicable evidence and process;
- human review, corrections, and decision history; and
- clear recommendations and next steps.

Reports must not imply certification, appraisal authority, legal admissibility, insurer acceptance, repair authorization, or a complete physical inspection unless those conditions have actually been satisfied by an authorized process.

### 3.7 Authorized distribution
- Determine recipients from explicit authority, consent, purpose, and disclosure policy.
- Generate recipient-appropriate reports and work packets; do not assume every party is entitled to every data field.
- Record the exact artifact/version sent, recipient, delivery channel, authorization basis, time, delivery result, and acknowledgment where available.
- Make revocation, correction, reissue, and failed-delivery states auditable.
- External delivery and live integrations remain subject to their separate legal, security, and release gates.

### 3.8 Driver guidance and collision-event resolution
The driver should be able to understand:
- what has been recorded and assessed;
- what is established, what is only suspected, and what remains unknown;
- whether a safety or inspection issue needs immediate attention;
- what actions are required next, by whom, and in what order;
- which authorized parties have received relevant information; and
- what constitutes completion of the collision-record process.

The collision event may be resolved or closed when its defined record, review, communication, and disposition criteria are satisfied. This does **not** mean that downstream insurance adjustment, repair, payment, litigation, or other independently owned processes are complete. Those processes need their own state, actor, authority, and audit trail. Closure must not erase or rewrite the historical record.

## 5. Foundational system responsibilities

The following are logical responsibilities, not a mandate to create premature microservices. Implement them as cohesive modules within the existing modular-monolith architecture unless measured operational needs justify separation.

1. **Truth and Accuracy Assurance** — evidence sufficiency, provenance, validation, uncertainty, calibration, reproducibility, and quality controls.
2. **Vehicle Intelligence Registry** — vehicle identity, configuration, authoritative references, source lineage, and collision-to-vehicle relationships.
3. **Damage Intelligence Engine** — visual/technical observations, component localization, damage classification, limitations, and escalation.
4. **Decision and Explanation Engine** — versioned policy, evidence reconciliation, explainable findings, review, and authorized disposition.
5. **Event Resolution Orchestrator** — collision lifecycle, task coordination, report readiness, authorized distribution, next-step tracking, and resolution criteria.

These responsibilities must integrate with—not compete with—the established platform foundations:
- Collision Lifecycle Record (CLR) as the collision identity and lifecycle boundary;
- existing claim and capture-session contracts;
- evidence artifact and sealed-manifest verification boundaries;
- tenant-scoped authorization and consent;
- append-only lifecycle/event journal and transactional outbox;
- separately governed state machines for capture/evidence, consent, quality review, provider engagement, financial lifecycle, and event resolution.

Do not introduce duplicate sources of truth for collision identity, evidence, consent, claim state, or financial state. Use explicit links and domain ownership.

### 4.1 The post-accident operating network

The product is not a sequence of disconnected forms, reports, referrals, or provider directories. It is a governed operating network organized around the Collision Lifecycle Record (CLR) and the evidence-backed incident record.

The architecture has four cooperating planes:

1. **Truth plane** — identity, evidence, provenance, observations, measurements, technical assessments, uncertainty, and explainable findings. This plane establishes what the system can responsibly know.
2. **Orchestration plane** — collision lifecycle, task plans, requirements, approvals, recipient authorization, handoffs, service acceptance, status reconciliation, and event resolution. This plane determines what should happen next, who is authorized to do it, and whether it actually happened.
3. **Participant network plane** — drivers/owners, field operators, repair facilities, dealerships, insurers, towing and other qualified providers. Each participant acts within a defined role, purpose, capability, service area, consent boundary, and acceptance contract. A directory listing is not a completed handoff; a referral is not provider acceptance; acceptance is not completion.
4. **Transaction and integration plane** — quotes, estimates, service orders, dispatch, partner messages, invoices, fees, payouts, payment reconciliation, and external system adapters. These workflows are independently authorized, idempotent, auditable, and gated. They consume supported facts and approved decisions; they never rewrite technical findings.

The planes share a common event and identity spine, but retain distinct domain ownership. The CLR identifies the collision; vehicle and participant relationships identify what and who is involved; evidence manifests identify source material; assessment records identify what was concluded and by which method; workflow records identify requested and accepted work; financial records identify obligations and settlement. A single collision may have multiple claims, vehicles, providers, estimates, repair attempts, and financial events. None should be collapsed into one mutable status field.

### 4.2 Lifecycle orchestration is a first-class product capability

The system must model the difference between:

- **recommendation** — the system suggests a qualified next step;
- **offer / request** — an authorized participant is asked to perform work;
- **acceptance** — the participant explicitly accepts the scoped work and terms;
- **execution** — work or service is underway;
- **completion** — the participant reports completion with required evidence;
- **verification** — the platform or authorized party validates the completion;
- **settlement** — any separately authorized financial obligation is reconciled; and
- **resolution** — the relevant collision-record or downstream workflow meets its own closure criteria.

These are not synonyms and must not be inferred from one another. For example, a shop accepting a vehicle may authorize the next dispatch step under policy, but it does not prove that towing occurred, repairs were completed, an insurer paid, or the collision record is fully resolved.

Orchestration should be expressed as durable, versioned workflows and domain events—not a large collection of fragile synchronous calls. Use the transactional outbox and idempotent consumers for reliable handoffs; persist request, acceptance, rejection, timeout, cancellation, completion, verification, and reconciliation outcomes. External systems are adapters at explicit boundaries, not alternate authorities for the canonical incident record.

### 4.3 Network economics must remain subordinate to trust

The commercial opportunity is to reduce friction and coordinate legitimate services across the post-accident lifecycle. The platform may earn revenue from authorized services, transactions, integrations, or network participation, but commercial incentives must not influence evidence collection, technical findings, safety escalation, recipient disclosure, provider qualification, or decision thresholds.

Provider matching must be explainable and governed by capability, geography, availability, vehicle/brand fit where relevant, service terms, consent, and user choice. Paid placement or referral economics—if ever authorized—must be disclosed and kept separate from technical ranking and safety decisions. The platform must not sell an unverified lead as a verified fact, or represent a provider's acceptance as an endorsement of an assessment.

The strategic moat is the combination of a trustworthy incident record, repeatable intelligence, accountable orchestration, and a qualified participant network. Building the network without the truth plane creates a lead marketplace; building the truth plane without orchestration leaves users with a report and no path forward. Claim2Car must build both, with independent controls and audit trails.


## 6. Truth and accuracy assurance architecture

Every automated or human-assisted assessment should follow a controlled chain:

**Source evidence and provenance → validation and sufficiency → observations and measurements → analysis with method/version → uncertainty and limitations → review/authorization → explainable finding → report/distribution.**

Controls should include:
- immutable or versioned source artifacts and explicit derivative lineage;
- tenant and actor authorization at every read/write/distribution boundary;
- schema-validated, versioned assessment inputs and outputs;
- explicit evidence references for every material finding;
- separation of model output from human-reviewed outcome;
- calibrated confidence and abstention / escalation behavior;
- reproducible decision inputs, rules, and model versions;
- audit of overrides, corrections, and report reissues;
- adversarial tests for missing, contradictory, malformed, duplicated, replayed, manipulated, or cross-tenant evidence; and
- fail-closed behavior when authority, integrity, provenance, or required evidence cannot be established.

Cryptographic hashes can help detect byte changes and support integrity checks. They do not prove that a depicted event occurred, that an image came from the claimed camera/time/location, that a person is who they claim to be, or that a technical conclusion is correct. Hashes, signatures, Merkle structures, trusted timestamps, chain-of-custody controls, and blockchain are different mechanisms and must never be described as interchangeable. Do not claim legal admissibility from technical integrity controls alone.

## 7. Accuracy validation is a product requirement

A functioning API, passing unit tests, synthetic fixtures, or a high model score does not establish real-world assessment accuracy.

Before a capability is represented as field-ready or relied on for consequential decisions, validate it against independently inspected real-world vehicles and appropriately governed datasets. The validation program should measure, as applicable:
- VIN and vehicle-configuration resolution accuracy;
- component recognition and damage-localization precision/recall;
- damage classification and severity agreement with qualified inspectors;
- false-positive and false-negative rates, including safety-relevant misses;
- agreement and variance against qualified human inspection and documented repair outcomes;
- estimate variance against actual repair scope/cost where estimation is in scope;
- uncertainty calibration and correct abstention/escalation;
- robustness across makes, models, model years, damage types, lighting, weather, camera devices, angles, image quality, and capture conditions; and
- performance drift and subgroup weaknesses.

Use independent ground truth, documented inspection methods, representative sampling, blinded review where practical, and explicit acceptance thresholds established before testing. Synthetic data is useful for software contract and adversarial testing but cannot substitute for field accuracy evidence. Until validation exists, label the capability as experimental or decision-support only and require the appropriate human inspection.

## 8. First complete vertical slice

The first meaningful implementation target is not another disconnected endpoint or a broad collection of empty abstractions. It is one thin, real, end-to-end vehicle assessment journey through the existing platform boundaries:

1. authenticated collision intake;
2. vehicle identification and source-attributed vehicle record;
3. version-bound evidence capture and original-artifact preservation;
4. evidence integrity, completeness, and sufficiency evaluation;
5. evidence-linked observations and damage analysis, with explicit limitations;
6. explainable findings and a reasoned disposition;
7. a generated forensic report with provenance and uncertainty;
8. authorized report retrieval/distribution;
9. driver-facing next actions and escalation; and
10. auditable collision-event resolution, with downstream workflows remaining independently owned.

A slice is not complete merely because each endpoint exists. It must be integrated across API, persistence, authorization, evidence storage, event history, and user-visible workflow. It must survive process restart, reject cross-tenant access and tampered/mismatched evidence, preserve idempotency, and produce reproducible report content from stored inputs and versions.

Where actual vehicle analysis is not yet validated, implement the contracts and human-review path honestly. Do not fabricate damage findings or represent placeholder logic as intelligence.

## 9. Acceptance and release discipline

Every feature must be reported in distinct evidence categories:

- **Implemented:** code and interfaces exist.
- **Integrated:** connected to the real application, persistence, authorization, and workflow.
- **Automated-tested:** named tests pass at a specific commit.
- **Accuracy-validated:** performance is measured against an independent, relevant ground-truth set.
- **Field-validated:** exercised in an approved real-world environment with documented results.
- **Deployed:** running in the named environment at a verified revision.
- **Operationally accepted:** monitoring, recovery, security, support, and owner-defined gates are satisfied.

Never collapse these into a generic “done” or “production-ready” claim. Green CI is necessary evidence for code quality, not proof of accuracy, field readiness, deployment, legal acceptance, or operational readiness.

The repository's [Acceptance & Release Gate Matrix](../acceptance/ACCEPTANCE_MATRIX.md) remains the source of truth for current implementation and release evidence. This vision document defines what the product is meant to become; the matrix defines what has actually been demonstrated and what remains blocked.

## 10. Architecture and product guardrails

- Preserve the existing modular-monolith direction: FastAPI application, PostgreSQL/PostGIS authority, background workers, and React/Capacitor capture experience. Do not introduce a MySQL rewrite or split services without a demonstrated need.
- Railway is retired as a deployment direction. OCI is the selected integrated-staging target, but do not claim deployment until the actual PostgreSQL/PostGIS, private compute, persistent evidence storage, secrets, backup/restore, and release checks are provisioned and verified.
- Keep live payments, dispatch, external report sends, and real participant-data use behind their respective authorization, legal, security, and release gates.
- Maintain tenant isolation, least privilege, consent, purpose limitation, data minimization, retention/deletion rules, and auditability.
- Separate technical truth from marketplace/commercial outcomes. Providers may be matched and workflows coordinated only under explicit rules; payment or referral incentives must not influence evidence, assessment, or findings.
- Preserve historical protocol and evidence interpretation. New protocol versions must be explicit and immutable per session; never silently reinterpret legacy evidence.
- Prefer vertical, executable increments over documentation-only claims, placeholder services, disconnected endpoints, or speculative infrastructure.
- Keep the owner informed with exact changed files, commit/PR, test evidence, failures, limitations, deployment status, and next action.

## 11. Instructions to future agents

When continuing this project:
1. Read this document before proposing or changing product architecture.
2. Read the README and the Acceptance & Release Gate Matrix for repository orientation and verified status.
3. Inspect the current default-branch head, open PRs, CI, migrations, and relevant implementation before assuming prior handoff notes are current.
4. Treat this document as the owner-aligned product premise, but treat code and current test/deployment evidence as the authority for implementation status.
5. Do not ask the owner to restate this vision. Ask only when a genuinely unresolved product, legal, safety, or commercial decision blocks a concrete action.
6. Continue toward the first complete, evidence-backed assessment and resolution vertical slice, then expand coverage across the post-accident lifecycle.
7. Never claim an assessment, report, delivery, deployment, accuracy level, or release gate has passed without traceable evidence.

## 12. The governing principle

Claim2Car should give people a dependable account of what can responsibly be known after a collision—and a clear, accountable path from that knowledge to the next action and eventual resolution.

The platform earns the right to coordinate the post-accident economy by first earning trust in the record it creates. Accuracy, transparency, explainability, consent, and accountability are not supporting features. They are the foundation of the product.
