# Claim2Car Connect — Foundational Vision & Technical White Paper

**Version:** 1.0  
**Date:** 26 November 2026  
**Status:** Governing target-system reference; not an implementation claim.

## Executive summary

Claim2Car Connect is a controlled evidence acquisition and substantiation platform for the accident-response economy. It begins at incident intake and preserves original observations, organizes them into a structured incident record, supports traceable measurement and evidence-grounded inference, and enables authorized human and operational decisions. Its differentiator is not photo volume, a VIN decoder, a hash badge, a damage label or a polished PDF. It is the traceable chain from original evidence to every conclusion and action.

The FAOS engineering framework is governed by four layers: **Acquisition → Measurement → Inference → Decision**. Each layer has its own records, methods, provenance, uncertainty and authority. Acquisition records what the device or operator observed. Measurement derives quantities with method, units, calibration and uncertainty. Inference proposes a supported interpretation with assumptions and missing inputs. Decision records an authorized operational action, normally with human accountability for consequential outcomes.

The long-term product can connect vehicle owners, tow operators, collision repairers, dealers, insurers, fleet operators, data providers and payment/technology partners through a more consistent incident record and auditable workflow. The opportunity is to reduce duplicate capture, repeated data entry, poor handoffs, incomplete referrals and information asymmetry—not to replace every participant or guarantee a legal, repair or financial result.

## Mission and ecosystem value

The mission is to make accident-related information safer to acquire, easier to verify, more useful to authorized decision-makers and more accountable as it moves through the response ecosystem.

Potential value:
- Owners receive clearer consent, status and authorized sharing.
- Tow operators receive guided intake and less repetitive paperwork, with safety pause/abort taking priority.
- Repair facilities and dealers receive structured, recipient-specific information and a clear acceptance workflow.
- Insurers/carriers may receive better organized FNOL support when schemas, agreements and security are approved.
- Platform operations gain measurable service quality, auditable lifecycle events and reconciled commercial obligations.

Network effects and economic disruption are hypotheses to be measured through completed/accepted/paid outcomes, service time, referral quality, duplicate work, error rates and unit economics. Projected leads or gross margin are not cash flow. Pilot economics must include labor, operator compensation, device/cellular cost, support, storage, processing, taxes, insurance, acquisition, payment fees, refunds, chargebacks and working capital.

## Product scope and workflow

### M1 — Intake and evidence preservation

1. Authenticate the operator and bind actor, tenant, tow company, device asset and capture session.
2. Create an incident and capture session with stable identifiers and idempotency.
3. Obtain purpose-specific consent and representative authority; record exact disclosure version and scope.
4. Record VIN observations, source location, OCR candidates, check-digit applicability and decoder response separately.
5. Execute a versioned 16-point capture protocol. Each required slot is captured or has a permitted, reasoned exception. Retakes are new revisions; originals are not overwritten. Safety pause/abort always wins.
6. Preserve original bytes and available acquisition metadata. Create artifact references, digests and ordered custody events.
7. Synchronize offline/online through durable, resumable and idempotent upload. Server independently verifies the received bytes and registered manifest/chain context.
8. Allow an authorized reviewer to retrieve verified originals and record an attributable, reason-coded decision.
9. Produce a bounded evidence inventory/report with clear limitations and purpose-specific access.

M1 does not require LiDAR volumetric measurement, autonomous structural adjudication, collision causation, repair authorization, total-loss decisions, marketplace, dispatch, navigation, live payment or carrier delivery.

### Later commercial workflow

A later commercial lifecycle may include opportunity qualification, recipient-specific dossier, acceptance/rejection of a specific vehicle, close, fee obligation, dispatch prerequisites, operator assignment, authorized destination, navigation handoff, arrival, physical handoff, invoice/collection, settlement and reconciliation. These are distinct events and state machines. Acceptance is not arrival; navigation handoff is not proof of delivery; fee obligation is not settlement.

## Product capability map

Identity and tenant access; incident/session lifecycle; consent and authorization; VIN observation/validation/decoder adapters; 16-point capture protocol; device and sensor acquisition; offline queue and resumable sync; original artifact storage and custody; quality assessment; calibrated measurement; AI/model inference; human review; deterministic reports; recipient authorization and distribution; dealer/shop matching; dispatch/navigation; financial ledger and provider adapters; operational monitoring; analytics and model governance.

## Capture platform and device qualification

The intended field model is company-owned, managed and pooled tablets checked out per shift. Operators authenticate individually; device asset identity persists. Sessions retain original actor attribution across interruptions and shift changes. MDM-supervised configuration may provide enrollment, kiosk mode, app deployment, remote lock and wipe, but it does not calibrate sensors.

The exact tablet generation and LiDAR requirement remain a qualification decision. Compare candidate devices against camera/original-byte preservation, calibration metadata availability, native API support, timestamp behavior, sensor sampling, thermal/battery performance, offline recovery, cellular coverage, accessibility and roadside usability. Do not assume universal LiDAR range/accuracy or guaranteed IMU rates.

React/PWA may provide the workflow shell. Capacitor/native plugins are required for native camera, CoreMotion, ARKit/LiDAR or platform-specific lifecycle features. Define native bridge contracts and record exact device/OS/API versions.

## Evidence architecture

### Acquisition
Preserve original image/video bytes, VIN observations, native metadata and available sensor streams. Record actor/device/session, UTC and monotonic time where available, time source and synchronization uncertainty. Do not synthesize unavailable metadata.

### Measurement
A measurement requires source references, method/version, units, coordinate frame, calibration references, uncertainty and limitations. Pixel counts are not physical dimensions. Monocular depth estimates are not calibrated metrology. LiDAR data is device- and condition-dependent. Derivatives never replace originals.

### Inference
Vision models, rules and physics calculations produce inferences, not facts. Record model/method/weight digest, source evidence, assumptions, applicability, alternatives, missing inputs, uncertainty and disagreement. An uncalibrated score or two-of-three vote is not a probability. Missing priors or out-of-domain inputs require abstention / INSUFFICIENT_TELEMETRY.

### Decision
A decision requires an authorized actor or policy, evidence references, reasons, scope, version and time. Consent, tenant authorization, safety, integrity and legal controls are non-compensatory gates. A score cannot override them.

## In-house AI and analytical ensemble

Candidate components include:
- YOLO-family object/damage-region detector for visible components and damage cues.
- SAM2 segmentation for pixel-space masks and region boundaries.
- Depth Anything V2 for relative/monocular depth hypotheses, not calibrated physical depth.
- Device LiDAR/ARKit depth adapter, only on qualified hardware with confidence and coordinate-frame metadata.
- OCR/VIN parser with alternative candidates and source-image lineage.
- VIN decoder adapter with source/version/date and field-level provenance.
- Quality metrics/models for blur, exposure, glare, occlusion, framing and motion, kept advisory until profiles are validated.
- DARCI deterministic mechanics/calculation library for explicitly supported inputs, units, assumptions, sensitivity and unavailable-input handling.
- Language/vision assistant for grounded summaries, reviewer navigation and missing-information prompts; every statement must cite record/artifact IDs and receive human approval when consequential.

The ensemble is created through a governed lifecycle: lawful data rights; precise label definitions; representative datasets; independent annotators/adjudicators; incident/vehicle-level leakage prevention; separate train/calibration/held-out sets; per-class precision/recall; calibration; subgroup/domain-shift analysis; false-negative review; abstention coverage; model cards; weight digests; shadow deployment; drift monitoring and rollback.

The former fixed 55/45 physics/AI weighting is not an accepted rule. Store each model output separately. Combine only through a validated policy that accounts for dependence and uncertainty. Physics constrains claims only when inputs and assumptions are supported. Images cannot establish all hidden damage or collision causation.

## Measurement, physics and repair substantiation

Kinetic energy calculations require supported mass and velocity inputs; they do not directly establish energy absorbed by one vehicle. Work-energy average force is not peak impact force. Average deceleration is not measured peak G. Local stress requires valid load geometry and material/component information. Johnson–Cook modeling requires material-specific parameters, strain/strain-rate history, temperature and validated conditions. Entropy of a defined depth distribution is not a direct indicator of torsion or hidden fracture. No universal entropy or yield threshold may trigger total loss.

OEM repair procedures, vehicle-specific service information, sectioning limits, replacement instructions and qualified technician signoff govern repair assessment. Images cannot prove the condition of hidden reinforcement, rails, wiring, sensors or restraints. Valuation requires licensed, current, vehicle- and market-specific data. If evidence or sources are insufficient, return unavailable/undetermined and route to qualified review.

## Reports and recipient delivery

Reports are deterministic renderings from versioned evidence and finding records. They should contain case/session identity, authorization, original evidence inventory, capture coverage/exceptions/retakes, VIN lineage, observations, measurements and uncertainty, model/rule versions, supported/provisional/inconclusive findings, alternatives, reviewer decision, integrity verification and limitations. Each annotation references original evidence; each measurement references inputs; each conclusion references findings. New evidence produces a new report revision; prior issued reports remain preserved.

Redaction is allow-list and purpose-based, not role-only. Each recipient package requires current consent, recipient identity, purpose and access authorization. Delivery, access, download, expiry and revocation are logged. ACORD/carrier formats require actual partner schema validation and agreements.

## Architecture

Recommended baseline: React/Capacitor client; FastAPI modular monolith; PostgreSQL/PostGIS transactional authority; durable encrypted object storage; background workers with transactional outbox/inbox; optional Redis for cache/realtime only; versioned AI adapters; observability and infrastructure-as-code. Avoid introducing MongoDB or another ledger without a demonstrated requirement. Redis SETNX is not durable idempotency; use database uniqueness and transactional results.

Core domains: identity, tenant, incident/session, consent, vehicle identity, capture protocol, artifacts, custody, QA, measurement, inference, review/decision, reports, recipient authorization, commercial opportunity, dispatch, finance, integrations and operations.

## Security, privacy and operations

Enforce tenant isolation, purpose-aware least privilege, encryption in transit/at rest, secret management, key rotation, short-lived access, retention/legal hold, revocation, audit, device-loss response, backups and witnessed restore. Browser IndexedDB is not WORM. PostgreSQL and object storage are separate failure domains; test crash/retry/orphan reconciliation. A successful backup job is not a restore test.

## Commercial and financial controls

Planning figures: dealer acquisition fee $375 on qualified close; shop fee $275 on recorded acceptance under current planning; operator amount $110 carried forward with trigger/eligibility/reversal/ledger unresolved; owner cash incentive excluded. Financial states must separate obligation, invoice, authorization, capture, settlement, payout, reversal, refund, chargeback and reconciliation. Sandbox success is not live payment approval. No live transaction until separate release authorization.

## Delivery and acceptance

M1 acceptance requires exact-head code/test evidence, safe authorized intake, consent, versioned capture accounting, original preservation, offline recovery, server verification, reviewer retrieval and attributable decision. Separate gates govern field-pilot entry, commercial readiness and broader production release. A green workflow is not field qualification, accuracy validation, deployment or operational acceptance.

Longer-term stages: M1 intake/preservation; M1 operational readiness; device/measurement qualification; AI shadow research; source-backed technical assessment and deterministic reports; commercial workflow; sandbox finance; separately authorized production; advanced forensic analytics only after independent validation.

## Non-goals and claim controls

No legally conclusive evidence claim, automatic admissibility, tamper-proof claim, universal sub-centimeter measurement, autonomous structural/total-loss/causation verdict, guaranteed ACV, tax outcome, zero liability or guaranteed margin. Hash, Merkle, signature, trusted timestamp and blockchain are distinct. The platform supports qualified review; it does not replace counsel, reconstruction experts, OEM procedures, licensed data providers or technicians.

## Current implementation boundary

PR #185 is recorded merged; exact-main post-merge verification remains. PR #195 is an open/draft contract implementation with strong exact-head automated results but no sensor/metrology validation. PR #196 consent-deletion retry exact-head acceptance is pending. PR #186 report work requires rebase. PR #187 is the narrow M1 registry. PR #194 is the audit checkpoint. PR #188 is a proposal only. M1 is not accepted; no field-qualified device, integrated staging deployment, participant evidence, live payments or dispatch is established.
