# Claim2Car Connect — CTO Master Execution Plan

**Document ID:** C2C-CTO-EXEC-001  
**Version:** 1.0  
**Effective:** 2026-11-07  
**Owner approval:** Founder approved the five-slice execution plan on 2026-11-07.  
**Canonical repository:** `C2C-Connect/claim2car-connect`  
**Baseline reviewed:** `9b22b7136bc0128888756367b2b72923549098d5`

## 1. Mandate

Complete Claim2Car Connect as an integrated, secure, usable, deployable product. The five slices are sequential execution programs, not five prototypes. Preserve the full product ambition while making each component independently reviewable and demonstrably complete.

For each component: inspect baseline → specify requirements and acceptance → architect → structure interfaces/data/code → implement → add tests → execute tests → fix defects → commit on an isolated branch → open/review PR → merge after required checks and review → deploy to the authorized environment where applicable → verify deployed behavior → record evidence and limitations.

A file, green CI job, merged PR, synthetic demo, or health-only deployment is not by itself proof of product completion.

## 2. CTO operating authority

The CTO execution lead manages technical sequencing, repository inspection, architecture, implementation, tests, documentation, branches, commits, pull requests, and deployment preparation. Founder authority remains required for material business-policy changes, spending/paid infrastructure, hardware purchases, legal commitments, partner agreements, production deployment, live data distribution, payments, live dispatch/location sharing, and consequential AI authority.

Within an approved slice, routine engineering may proceed without file-by-file approval. Bring the founder only concise material decision requests and approval gates. Do not ask for decisions already explicitly made.

## 3. Binding product and commercial rules

- Dealer fee: flat **$375**, due on qualified-acquisition close.
- Repair-shop fee: flat **$275**, triggered by recorded vehicle acceptance.
- Shop acceptance authorizes tow dispatch/routing to that accepting shop; the tow operator is routed to deliver the vehicle there.
- **No vehicle-owner cash incentive or consent payout of any amount.** Do not restore it from historical specifications, migrations, fixtures, APIs, reports, or copied prototypes.
- The **$110 operator payout remains unresolved**. Its eligibility, trigger, payer/payee, split, ledger treatment, reversals, disputes, and settlement are not approved. No payout logic or active payout output until separately approved.
- Do not infer payment collection/settlement semantics or dispatch gating on failed payment beyond the recorded decisions.
- Live sends, payment collection, external dispatch, production publication, and real participant data use remain gated by the applicable legal, partner, security, and founder approvals.
- Human review remains authoritative; synthetic benchmarks do not establish real-world model accuracy.

## 4. Evidence, security, and roadside-safety invariants

- Actor identity, role, and tenant authority are server-derived and enforced at the database boundary.
- Preserve original evidence bytes; compute and verify integrity server-side; bind artifacts to the authorized session and consent scope.
- Upload/retry paths are idempotent; conflicting payloads, supersession, withdrawal, and recovery are explicit and auditable.
- Recipient authorization is checked server-side; sensitive data is not leaked through ordinary logs.
- Hashes support integrity verification, not truth, provenance by themselves, or automatic legal admissibility.
- Capture never delays emergency response, police, traffic control, stabilization, loading, or scene clearance. Operators may pause, skip, or abort without penalty.
- Measure added scene time and operator workload; do not claim zero impact.
- Legal review is required for jurisdiction-specific towing/consent, compensation/referral/anti-steering, privacy, retention, communications, evidence, and partner workflows.

## 5. Current baseline (reviewed 2026-11-07)

### Established in the canonical repository

- M1 capture-session state machine, consent/VIN guards, guided workflow controller, local draft persistence, resumable sync logic and offline tests.
- Original-byte storage/retrieval, manifest digest, server-side hash verification, attributed reviewer decisions.
- Tenant-authority and database migration/security foundations with substantial acceptance tests.
- Transactional outbox, idempotent consumer scaffolding, OpenTelemetry facade and property-based tests.
- Synthetic dispatch/routing contracts, navigation deep-link builder and CIECA-aligned carrier message model.
- Heuristic quality gate, reviewer-decision dataset contract, confidence-priority human triage and drift monitoring.
- Deterministic damage-localization baseline and synthetic benchmark/adoption gate.

### Not yet established as complete live product capabilities

- A complete operator-facing native/React/Capacitor application and reviewer workbench.
- Full integrated application runtime across the separate root `app/` and `backend/app/` surfaces.
- Persistent pilot database and integrated evidence-storage operations in an approved environment.
- Real-device capture-to-review demonstration and device qualification.
- Field-calibrated quality gates or validated real-world damage/physics accuracy.
- Live dealer/shop partner workflows, document distribution, carrier delivery, dispatch, navigation, payment collection or settlement.
- Counsel-approved pilot operating charter and partner/data permissions.

### Deployment truth

The existing Railway configuration is a restricted synthetic containment rehearsal. It mounts health checks and disabled dispatch construction only; it is not the integrated claims application and reports `business_ready: false`. Do not call it a product deployment. Earlier staging prose identifying `P_BRITTLE_BETA` and `DEFAULT_TAX_RATE` as missing is stale at the reviewed baseline: both constants exist in `config/forensic_constants.py`. Their presence does not prove the complete backend imports or is deployable.

### Security finding requiring Slice 1 closure
The internal backend routes in `backend/app/api/analysis.py` and `backend/app/api/triage.py` currently define business POST endpoints without an authentication dependency. `backend/app/api/dispatch.py` also exposes redaction and verification routes without an authenticated actor boundary; dispatch build is disabled. `backend/app/main.py` applies a CORS allowlist, but CORS is not authentication or network access control. The route-control matrix labels these routes `INTERNAL_ANALYSIS`; that classification is an operational assumption, not an enforced security boundary in the route handlers. **Do not expose this backend entrypoint on a public network until a private network boundary or server-side authentication/authorization is implemented and tested.** Slice 1 must verify actual ingress and route reachability, define the enforcement point, and add negative tests before any integrated deployment.

## 6. Five-slice execution sequence

# Slice 1 — Control, reconciliation, and architectural foundation

**Objective:** establish a trustworthy baseline, enforce binding decisions, and resolve architecture before product expansion.

### 1A — Repository baseline and topology
1. Reconfirm canonical repository, main SHA, open PRs, workflows, and release state.
2. Inventory `app/`, `backend/app/`, `frontend/`, `database/`, migrations, config, tests, workflows, Dockerfiles, and deployment assets.
3. Map entrypoints, imports, API routes, service ownership, data stores, and runtime image composition.
4. Trace identity/tenant boundaries and route exposure for each surface.
5. Identify duplicated, dead, experimental, or inaccessible components without premature deletion.
6. Record test commands, workflow coverage, exact baseline results, and known failures.
7. Produce current architecture and dependency diagrams.

### 1B — Commercial and prohibited-incentive audit
1. Search all accessible repositories and active branches for owner incentive/payout behavior.
2. Inspect models, migrations, seeds, fixtures, tests, config, UI, APIs, reports, formulas, and documentation.
3. Separate historical/negative-test language from executable payout behavior.
4. Remove prohibited active owner payout fields and paths; do not create replacement owner compensation.
5. Remove unresolved operator payout values from active API/report output while retaining the unresolved decision record.
6. Keep structural denylist/negative tests that prevent compensation language from re-entering prohibited outputs.
7. Add regression tests for prohibited fields, calculations, and payout creation.
8. Audit dealer/shop fee constants and acceptance triggers against the approved $375/$275 rules.
9. Audit that no operator payout logic is activated.
10. Record search scope, findings, exceptions, code changes, and tests.

### 1C — Governance and acceptance reconciliation
1. Reconcile README, governance, specification decisions, legal review, milestone status, acceptance contracts, and deployment docs.
2. Mark specified/implemented/tested/field-validated/complete accurately.
3. Correct stale claims and contradictory acceptance language.
4. Create one traceability matrix linking requirement → code → tests → workflow evidence → deployment/field evidence → decision.
5. Establish evidence indexing by source SHA and workflow run.
6. Define evidence-branch retention and cleanup policy; do not delete evidence branches before inventory and retention decision.

### 1D — Architecture decisions
1. Define the pilot runtime composition of the root and backend application surfaces.
2. Define service boundaries, module ownership, API versioning, and internal/external route exposure.
3. Define identity/tenant authority propagation.
4. Define database and transaction ownership.
5. Define storage and evidence lifecycle interfaces.
6. Define health/readiness semantics that distinguish infrastructure readiness from business readiness.
7. Define the DARCI/analysis integration boundary without enabling unvalidated consequential output.
8. Record architecture decisions and migration strategy before broad integration.

**Exit gate:** prohibited payout behavior is absent and regression-protected; commercial rules are reconciled; application topology and runtime composition are documented; acceptance truth and evidence are traceable; no unresolved architectural ambiguity is hidden by a deployment workaround.

# Slice 2 — Operator and reviewer product experience

**Objective:** turn existing workflow/domain logic into a usable field application and reviewer workbench.

### 2A — UX and application architecture
1. Define operator/reviewer roles, permissions, and workflows.
2. Map each screen and action to a domain state and API contract.
3. Specify offline, loading, retry, conflict, error, resume, and recovery behavior.
4. Specify accessibility, field usability, and device/runtime support.
5. Define frontend shell, navigation, state management, authentication, and API client.
6. Produce screen flows and acceptance tests.

### 2B — Operator experience
1. Build application shell, sign-in/session handling, navigation and case list.
2. Implement incident/case create, resume, and recovery.
3. Implement disclosure/consent with version, scope, actor, timestamp, and withdrawal state.
4. Implement VIN entry, validation, lookup result, and explicit unknown/unavailable path.
5. Implement guided 16-v1 capture slots and versioned capture protocol selection.
6. Implement camera access, original-byte preservation, capture metadata, and session association.
7. Implement retake/supersession and missing-evidence behavior.
8. Implement local draft persistence, offline queue, resumable uploads, retry, and conflict handling.
9. Implement sync status, completion, pause, skip, and safe abort.
10. Implement operator-facing error recovery and support guidance.
11. Test the complete workflow on the selected reference device.

### 2C — Reviewer experience
1. Implement authenticated reviewer sign-in and authorization.
2. Implement case queue, assignment, ownership, and escalation.
3. Implement evidence retrieval/display and consent/provenance context.
4. Display integrity status, missing evidence, and superseded artifacts.
5. Implement notes, reason codes, defer, request-retake, and terminal decision.
6. Implement supervisory correction/review and full audit timeline.
7. Test wrong-tenant, unauthorized, incomplete, and conflicting access cases.

### 2D — Device qualification
1. Qualify one reference device before fleet procurement.
2. Verify native camera access and original bytes.
3. Test storage, offline behavior, restart recovery, and interrupted upload.
4. Test GNSS only where authorized; validate LiDAR repeatability against ground truth if used.
5. Test low light, motion, latency, battery, thermal behavior, permissions, and device management.
6. Record device model, OS, app version, protocols, test evidence, and limitations.

Reference target: Apple iPad Pro 11-inch M5, 512GB, Wi-Fi + Cellular; purchase is not assumed.

**Exit gate:** an authorized operator completes a real-device capture workflow with consent, VIN handling, original evidence, durable save/resume, interruption recovery, and sync; an authorized reviewer retrieves the evidence and records an attributable decision. No real-world pilot claim without intended-environment validation.

# Slice 3 — Persistent database, evidence, APIs, and integrated staging deployment

**Objective:** run the complete application against persistent infrastructure with verifiable security and recovery.

### 3A — Database environment
1. Select provider, region, PostgreSQL/PostGIS version, environment owner, and cost boundary.
2. Separate CI, staging, and production credentials.
3. Create least-privilege migrator, application, reviewer, and operations roles.
4. Apply migrations from an empty database and supported upgrade paths.
5. Verify migration ordering, checksums, idempotency, and rollback/recovery limits.
6. Verify RLS and tenant isolation using actual deployed roles.
7. Test concurrency, retries, revocation, and cross-tenant denial.
8. Configure backups and execute restore/recreation drills.
9. Document environment and recovery operations.

### 3B — API integration
1. Specify and implement authenticated case create/resume/readback.
2. Specify and implement consent, VIN, capture, upload, manifest, seal, and artifact retrieval.
3. Specify and implement retake/supersession and reviewer queue/decision APIs.
4. Derive actor/tenant authority from server-verified credentials.
5. Validate request schemas, size/content limits, error handling, and rate limits.
6. Test authorization and tenant isolation on every protected route.
7. Document API versioning and compatibility.

### 3C — Evidence storage
1. Select encrypted object storage and access policy.
2. Bind artifacts to tenant, case, slot, metadata, and consent scope.
3. Preserve originals and verify server-side digest.
4. Implement exact-retry idempotency and visible conflicting-payload rejection.
5. Prevent incomplete uploads from sealing.
6. Implement short-lived retrieval authorization, access auditing, retention, deletion, and withdrawal.
7. Test backup/recovery and object lifecycle.

### 3D — Integrated application
1. Connect operator UI to authenticated APIs.
2. Connect reviewer UI to authorized retrieval and decision APIs.
3. Connect persistent database, evidence storage, manifest, and audit history.
4. Integrate root and backend services according to Slice 1 architecture decision.
5. Resolve actual imports, settings, dependencies, and startup behavior.
6. Verify exposed routes, readiness, logging, telemetry, and secret handling.
7. Run end-to-end tests against persistent infrastructure.

### 3E — Deployment
1. Select approved staging service and environment.
2. Configure managed secrets, network restrictions, non-root runtime, read-only filesystem, and pinned dependencies.
3. Build the integrated image and stamp exact source revision.
4. Configure health/readiness, stale-revision protection, monitoring, and rollback.
5. Deploy an exact reviewed candidate revision.
6. Verify HTTPS routes, database, tenant boundaries, storage, operator and reviewer workflows.
7. Record deployment, revision, run evidence, and post-deploy results.

**Exit gate:** integrated application is running in authorized staging with persistent database and evidence storage; end-to-end synthetic workflow, authorization, retries, restarts, integrity, and reviewer actions are verified. Restricted health-only deployment does not satisfy this gate.

# Slice 4 — Field validation, operations, and pilot readiness

**Objective:** prove controlled operation in the intended context before a supervised pilot.

### 4A — Capture and quality validation
1. Define authorized sample protocol and data governance.
2. Define capture conditions, ground truth, failure categories, and reviewer rubric.
3. Establish baseline quality measurements.
4. Test day/night, indoor/outdoor, glare, dirt, rain, obstruction, weak networks, and movement.
5. Measure false acceptance/rejection and retake burden by slot.
6. Calibrate thresholds only from authorized labeled evidence.
7. Keep unvalidated gates advisory or disabled.

### 4B — DARCI and vision validation
1. Inventory real model artifacts, deterministic stubs, proxy signals, and synthetic adapters.
2. Define independent physics/vision/depth measurement inputs.
3. Establish representative labeled dataset, provenance, and adjudicated ground truth.
4. Validate physics and vision independently.
5. Validate depth/LiDAR repeatability independently if used.
6. Measure uncertainty, failure cases, and subgroup behavior.
7. Establish model/version promotion and rollback criteria before candidate testing.
8. Keep outputs advisory until validated; prohibit automated consequential decisions without separate approval.

### 4C — Operations
1. Define operator/reviewer onboarding and training.
2. Define assignment, conflict-of-interest, service hours, and support.
3. Define escalation, correction, appeal, and supervisory review.
4. Define daily reconciliation, case closure, retention, and incident reporting.
5. Assign named support and operational ownership.

### 4D — Legal and pilot charter
1. Identify pilot partners, operators, reviewers, service area, case cap, dates, and contacts.
2. Define approved data flows and participant permissions.
3. Obtain counsel review of towing/consent, privacy, retention/deletion, location, communication, compensation/referral/anti-steering, reporting, and evidence claims.
4. Confirm no money movement unless separately approved.
5. Approve disclosures, consent, privacy, retention, external claims, and pilot SOP.

### 4E — Rehearsal and go/no-go
1. Write runbook and incident/stop procedures.
2. Rehearse onboarding, consent, capture, retake, weak-network recovery, review, withdrawal, deletion, and escalation.
3. Run synthetic end-to-end and tabletop exercises.
4. Conduct only approved minimal real-data rehearsal.
5. Record failures, fix defects, and repeat tests.
6. Conduct formal go/no-go against exact release revision and approvals.

**Exit gate:** named supervised pilot with passed critical scenarios, approved legal/data/partner/device/operations controls, and no unresolved critical security, privacy, or evidence-integrity defect.

# Slice 5 — Full commercial ecosystem

**Objective:** complete downstream commercial, analytical, document, partner, dispatch, and financial workflows after their prerequisites and approvals.

### 5A — Documents and distribution
1. Define versioned schemas and provenance for owner PDF, dealer dossier, shop packet, and seven-page carrier report.
2. Build document generation and templates.
3. Implement versioning/regeneration and source evidence binding.
4. Implement recipient identity, consent scope, authorization, and server-side access checks.
5. Implement generated/queued/sent/delivered/failed/accessed state machine, idempotent retry, delivery receipts, and audit.
6. Implement retention/deletion and partner acceptance testing.
7. Keep live external sends disabled pending counsel and partner approval.

### 5B — Dealer/shop marketplace
1. Define dealer/shop accounts, locations, services, brands, capacity, availability, and eligibility.
2. Define matching, fee configuration, and versioning.
3. Implement dealer and shop matching and offer lifecycle.
4. Implement authorized acceptance/rejection/expiry and concurrent-acceptance protection.
5. Implement auditable acceptance and partner workflows.
6. Enforce dealer $375 on qualified-acquisition close and shop $275 on recorded vehicle acceptance.
7. Validate against real authorized partners.

### 5C — Dispatch and navigation
1. Define eligibility, assignment, acceptance prerequisites, and tow constraints.
2. Integrate approved real routing provider behind adapter.
3. Validate destination from authorized acceptance record.
4. Implement operator assignment, navigation handoff, en-route, arrival, handoff, exceptions, cancellation, and reassignment.
5. Integrate Google Maps or equivalent handoff.
6. Implement consented location sharing and retention.
7. Test real routes with operators; synthetic Houston grid is not live routing proof.

### 5D — Payment and ledger
1. Resolve $110 operator payout policy before implementing any obligation.
2. Confirm payer/payee, eligibility, trigger, split, accounting, reversals, disputes, and reconciliation.
3. Define dealer/shop obligations and payment lifecycle.
4. Implement auditable ledger, integer minor units, idempotency, retries, uncertain-result handling, and reconciliation.
5. Integrate provider only after authorization; test sandbox.
6. Obtain legal/financial approval before live collection or settlement.
7. Owner cash incentive remains prohibited.

### 5E — Carrier integration
1. Obtain actual carrier schemas and partner requirements.
2. Map fields and validate CIECA conformance where applicable.
3. Implement authenticated outbound messages, outbox, retries, deduplication, acknowledgments, dead-letter/manual recovery.
4. Test partner sandbox and obtain partner acceptance.
5. Enable live delivery only after explicit approval.

### 5F — DARCI and advanced analytics
1. Complete independently sourced physics input contracts and measurement provenance.
2. Validate geometry, damage localization, depth/LiDAR, and physics against ground truth.
3. Validate vision models independently.
4. Establish uncertainty, reproducibility, model versioning, promotion, and rollback.
5. Integrate only validated components into human review.
6. Evaluate acoustic NDT, AR, high-resolution reconstruction, and advanced model ensembles only when prerequisites and demonstrated value justify them.

### 5G — Full-system integration and release
1. Integrate capture, evidence, review, analysis, documents, matching, acceptance, dispatch, payments, and carrier workflows.
2. Verify every state transition, permission boundary, audit event, retry, and recovery path.
3. Test concurrency, failure, rollback, and partner sandbox scenarios.
4. Run full end-to-end acceptance and security review.
5. Obtain legal, partner, and financial sign-offs.
6. Deploy approved commercial release and verify controlled live operations.

**Exit gate:** all approved commercial workflows operate end-to-end with real integration evidence, auditable financial obligations, validated analytical components, and required legal/partner approval.

## 7. Universal Definition of Done

Every task record must include: task ID; requirement and prohibited behavior; baseline inspection; architecture decision; affected files/APIs/schemas/infrastructure; dependencies; implementation; tests and exact command; environment; observed result; known limitations; security/privacy impact; commit SHA; PR; review/merge status; deployment reference; post-deploy verification; and acceptance evidence.

Use statuses precisely:
- **PLANNED:** no implementation.
- **DRAFTED:** design or requirements exist.
- **COMMITTED:** code exists in a commit.
- **MERGED:** present in canonical main.
- **TESTED:** named test/check passed in a stated environment.
- **IMPLEMENTED:** code path exists and is integrated to the stated extent.
- **FIELD-VALIDATED:** tested in intended real operating context.
- **COMPLETE:** all defined acceptance criteria pass with recorded evidence and acceptance decision.
- **BLOCKED:** dependency or approval prevents progress; blocker and closest safe alternative recorded.

Never promote a status by inference.

## 8. Release gates

1. Governance and commercial rules current.
2. Security, identity, tenant authority, evidence integrity pass.
3. Operator/reviewer workflows pass on supported devices.
4. Persistent data, storage, retention, deletion, and recovery verified.
5. Exact candidate deployed and post-deployment verified.
6. Named operations/support and stop conditions exist.
7. Legal/partner approvals cover exact scope and release.
8. Measurement and validation limitations recorded.
9. Commercial/payment activation separately authorized.

A blocked gate is not bypassed by changing its label. Pause or narrow the affected release.

## 9. Founder approval protocol

Routine engineering within an approved slice may proceed under standing authorization. The CTO reports concise status: **Completed / Evidence / Next / Approval needed**. Founder approval remains required for material business-policy changes, paid infrastructure or spending, additional hardware, real participant data use, external distribution, live dispatch/location sharing, payment activation, production deployment, legal/public claims, and consequential AI authority.

## 10. Execution record

The working ledger and PRs record task-level progress. Every slice closes with a source revision, test/deployment evidence, known limitations, and acceptance decision. This plan is the execution sequence; it does not itself certify any component as implemented, tested, validated, or complete.
