# Claim2Car Connect — Project Governance and Decision Register

Status: Active

This document is the working governance baseline for the canonical project repository.

- Repository: C2C-Connect/claim2car-connect
- Project objective: complete Claim2Car Connect platform, shipped in stages with explicit pilot boundaries
- Governing rule: not included in the pilot does not mean removed from the product
- Product objective: capture → seal → triage → route → handoff → audit

## 1. Canonical repo and scope

- Canonical implementation repo: C2C-Connect/claim2car-connect
- Historical and prototype repos remain useful as reference and backlog sources, but they are not active implementation sources of truth.
- This repo is the only active engineering repo for the product work.
- All active work must stay aligned to the approved project scope and milestone plan.

## 2. Approved project rules

### 2.1 Product objective

We are building the complete Claim2Car Connect platform, not only a capture demo or foundation service.

The project objective is:
- roadside incident capture
- trusted evidence sealing
- physics-first triage
- brand-matched dealer routing
- auditable commercial handoff
- staged rollout with explicit pilot boundaries

### 2.2 Pilot objective

The pilot is a milestone inside the full product, not a substitute for it.

The pilot loop is:
1. Authenticate operator and start incident
2. Capture VIN, required evidence, and consent
3. Sync offline capture reliably
4. Validate and seal evidence package
5. Produce versioned triage outcome or review result
6. Route eligible total-loss replacement leads to consent-compatible, brand-matched dealers
7. Record commercial handoff and obligations
8. Preserve auditable trail from capture through disposition

### 2.3 Scope rules

- Not included in the pilot does not mean removed from the product.
- Not yet validated does not mean not planned.
- Prototype or historical design does not automatically become approved implementation.
- All unvalidated claims must be classified as research, proposal, or backlog.

## 3. Approved engineering decisions

### 3.1 Owner incentive
Owner incentive is explicitly excluded from all product scope, pilot scope, workflow logic, pricing logic, and roadmap.

Approved rule:
- no owner incentive in the product
- no owner incentive in the pilot
- no owner incentive in workflow logic
- no owner incentive in pricing logic
- no owner incentive in data model
- no owner incentive in roadmap
- any reintroduction requires separate legal review and a new product approval

### 3.2 Dealer fee
Pilot dealer fee:
- $375 on acceptance

### 3.3 Operator payout
Pilot operator payout:
- $110 after seal + acceptance

Live payment rails remain disabled unless explicitly approved.

### 3.4 Fee-based routing
Routing must not use fee_factor as a live ranking input until counsel approves it.

Approved rule:
- fee_factor = 0 unless counsel approves a different value
- hard filters remain first: brand, consent, area, capacity
- ranking follows tier, capacity, and proximity until changed by approved policy

### 3.5 Triage automation
- triage operates in recommend mode until agreement reaches at least 90%
- human review remains required before broad automatic routing in the pilot
- every triage result must record the source inputs and reason

### 3.6 Hardware
- BYOD-first for the pilot
- with a small MDM-managed iPad cohort for validation and comparison
- hardware choice is a pilot decision and must be recorded as such

### 3.7 Capture sequence
- preserve the existing 12-v1 shot list as the frozen baseline
- add 16-v1 as a versioned parallel protocol for comparison and extension
- the shot list must be versioned per incident and cannot be silently redefined without a workflow review

### 3.8 Chain-of-custody integrity
- any broken hash chain blocks sealing
- a successful seal requires a valid hash chain and a verified evidence bundle
- the quality/confidence score is informational; the hard integrity gate is the authorization mechanism

### 3.9 Blockchain anchoring
- no public blockchain anchoring in the pilot unless separately approved
- use SHA-256 chaining and Merkle batch roots as the default internal integrity pattern
- leave a pluggable anchor interface, but default to no-op until separate approval

### 3.10 Legal and evidentiary claims
- no claim of court admissibility or legal certainty is made without counsel review and evidence support
- forensics and legal claims are treated as validation items, not as proven facts simply because they appear in older documents

## 4. Decision conflicts and resolutions

| Topic | Resolution |
| --- | --- |
| Capture hardware | BYOD-first with a small MDM iPad validation cohort |
| Capture sequence | Keep 12-v1 as baseline; add 16-v1 as versioned parallel option |
| Operator payout | $110 after seal + acceptance |
| Dealer fee | $375 on acceptance |
| Owner incentive | Excluded entirely |
| Blockchain anchoring | Internal SHA-256 + Merkle default; public anchoring deferred |
| Routing priorities | Hard filters first; fee_factor = 0 until counsel approves |
| Triage automation | Recommend mode until 90% agreement threshold |
| Integrity score | Binary seal gate takes precedence over quality score |
| Legal claims | Counsel review required before any evidentiary claim |

## 5. Platform backlog split

### 5.1 Pilot-critical capabilities
- authenticated operator start / incident creation
- VIN capture and validation
- consent capture with explicit scope and version metadata
- guided capture workflow
- offline capture and safe sync
- evidence sealing and manifest integrity
- explainable triage result or explicit review outcome
- route eligibility and brand match rules
- dealer handoff / action queue
- commercial obligation logging
- audit reconstruction and verify endpoint

### 5.2 Post-pilot expansion
- full AR guidance and staging calibration
- MDM fleet expansion
- public anchoring
- repair-shop auctions
- parts intelligence
- carrier integrations
- business reporting and BI
- broader market expansion features

### 5.3 Research and validation
- vision model accuracy claims
- acoustic gate feasibility
- physics calibration against observed cases
- ACV and RTV validation
- throughput, retry, and failure-cost measurement
- pricing and conversion assumptions

### 5.4 Compliance-dependent or agreement-dependent work
- routing policy adjustments beyond the pilot rule set
- legal evidentiary claims and disclaimers
- external information-sharing agreements
- payment rail enablement
- dealer and tow-fleet contractual terms

## 6. Milestone structure

### M0 — Alignment and constraints
Purpose:
- confirm the approved decision register
- freeze the active scope
- identify the final backlog split
- classify research, deferred items, and required approvals

### M1 — Baseline hardening
Purpose:
- preserve and stabilize the canonical repo foundation
- merge useful historical work without broadening scope
- ensure the repo is ready for the capture-to-seal milestone

### M2 — Capture to seal checkpoint
Purpose:
- deliver the next engineering checkpoint: a working capture and sealing flow

### M3 — Triage and review
Purpose:
- deliver explainable triage and review work before routing expands

### M4 — Routing and commercial handoff
Purpose:
- deliver the pilot loop from triage to accepted lead and auditable handoff

### M5 — Pilot launch
Purpose:
- validate the project in the San Antonio pilot context under controlled conditions

## 7. Pilot exit gates
- G1 volume: at least 100 incidents processed and at least 25 routed
- G2 integrity: 100% sealed packets re-verify; 0 accepted tampered packets in red-team tests
- G3 offline reliability: 0 evidence loss; 0 duplicates
- G4 capture time: median under 10 minutes
- G5 capture completeness: 95% of incidents have all required slots or documented waivers
- G6 triage agreement: at least 90% agreement with reviewer decisions before broad auto-routing
- G7 brand correctness: 0 invalid brand routes
- G8 dealer response: accepted/rejected within SLA for at least 80% of routed leads
- G9 conversion: measured, not assumed
- G10 ledger accuracy: 100% match between obligations and accepted leads
- G11 audit: 10/10 sampled incidents reconstructable from one query
- G12 compliance: 100% routed leads have valid consent records

## 8. Engineering principles
- preserve what is already validated in the canonical repo
- do not broaden scope without approval
- do not reuse historical claims as fact without validation
- treat every formula, threshold, and economic number as needing evidence
- treat legal, compliance, and evidentiary assertions as approval gates
- keep the full roadmap visible even when it is deferred

## 9. Immediate next actions
1. Preserve and stabilize the canonical repo
2. Merge or port only the useful historical work from earlier branches and docs
3. Correct stale or misleading product claims in the active repo
4. Create the execution checklist for M0 and M1
5. Begin M1 implementation work in repo with a clean, narrow, evidence-first plan

This document is the governance baseline for the project start and for all future milestone decisions.
