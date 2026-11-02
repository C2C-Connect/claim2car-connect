# Claim2Car Connect — M0/M1 Execution Charter and Scope Baseline

Status: Draft for owner review
Repository: C2C-Connect/claim2car-connect
Applies to: project governance, milestone execution, repo stabilization, and milestone readiness

## 1. Purpose

This document defines the execution baseline for M0 and M1 in the canonical repository for Claim2Car Connect.

It is intended to:
- stabilize the canonical repo and the scope boundary
- distinguish approved work from deferred, research, or prototype work
- define the minimum deliverables required before M2 begins
- establish clear ownership and approval gates
- prevent legacy or prototype claims from being treated as active implementation truth

This charter supplements the project governance baseline and does not replace it. It is intended to align with the existing acceptance-doc baseline and the repo’s current scope narrative.

## 2. Governing principles

The following principles govern all work in M0 and M1:

- The canonical implementation repository is C2C-Connect/claim2car-connect.
- Historical or prototype repositories remain references only; they are not active implementation sources of truth.
- The project objective is broader than a pilot demo; the pilot is a milestone inside the full product.
- Not included in the pilot does not mean removed from the product.
- Not yet validated does not mean not planned.
- Prototype or historical design does not automatically become approved implementation.
- Any claim involving legal admissibility, evidence certainty, or compliance posture requires explicit approval and supporting evidence.
- Product, policy, and technical decisions must be traceable to an approved baseline or a documented approval gate.
- Scope additions require approval; scope drift is not allowed during M0/M1 unless explicitly approved.

## 3. Scope boundary for M0/M1

The active scope for M0 and M1 is intentionally narrow.

### 3.1 In scope for M0/M1
- repo stabilization
- decision and scope baseline confirmation
- backlog split and classification
- migration and infrastructure baseline review
- evidence and audit integrity baseline
- capture-to-seal prerequisite definition
- minimum consent and data-handling contracts
- minimum traceability for review and audit
- controlled demonstration readiness for the first milestone checkpoint

### 3.2 Out of scope for M0/M1
Unless separately approved, the following remain outside the active work boundary during M0/M1:
- live financial settlement or payment rails
- live dealer dispatch or commercial routing beyond simulation
- public blockchain anchoring
- broad market expansion features
- large-scale business reporting / BI
- full pilot deployment operations
- carrier integrations
- repair-shop auctions
- owner incentive implementation or logic
- fleet-scale MDM rollout beyond validation cohort
- any unapproved legal or evidentiary claims

### 3.3 Research and deferred items
The following remain clearly labeled as research, proposal, or deferred work and are not treated as approved implementation:
- vision-model claims
- acoustic validation feasibility
- pricing assumptions and conversion assumptions
- ACV/RTV validation
- public anchor strategy
- external legal claims beyond approved counsel review
- environment provisioning beyond controlled and approved staging work

## 4. M0 — Alignment and constraints

### Purpose
M0 establishes the project alignment baseline and solidifies the approved constraints before implementation expands.

### Required outputs
The following outputs are required before M1 implementation proceeds beyond repo hardening:

1. Governance baseline confirmation
   - confirm canonical repo
   - confirm product objective
   - confirm pilot boundary
   - confirm approved constraints and excluded items

2. Scope freeze
   - define the current active scope
   - define approved non-goals
   - classify research and deferred items separately
   - document the backlog split

3. Approved decision register
   - owner incentive excluded
   - fee_factor remains zero unless counsel approves otherwise
   - BYOD-first with limited MDM validation cohort
   - 12-v1 remains frozen baseline; 16-v1 is a parallel versioned option
   - triage remains in recommend mode pending threshold approval
   - internal hash chaining / Merkle pattern remains default; no public anchoring in the pilot
   - no public claim of legal certainty without review and evidence support

4. Approval map
   - identify which decisions require legal review
   - identify which decisions require architecture review
   - identify which decisions require pilot-owner approval
   - identify which decisions require product-owner approval

5. Repo stabilization plan
   - identify stale prototype claims
   - label deprecated historical guidance
   - identify existing acceptance docs and pinned baselines
   - confirm the active working branch and repo state
   - ensure the repo reflects the current intended scope

### M0 exit criteria
M0 is complete when all of the following are true:

- project governance baseline is explicitly confirmed
- active vs deferred scope is documented
- open approval items are tracked
- no active work is being performed under undefined or contradictory scope
- repo is stable enough to support disciplined M1 execution
- key project decisions are recorded in a visible decision log

### M0 ownership
- Product owner: scope confirmation and decision approval
- Engineering lead: repo stabilization and implementation readiness
- Legal/compliance: approval for evidentiary and compliance-related claims
- Pilot owner: pilot boundary validation and operational constraints

## 5. M1 — Baseline hardening

### Purpose
M1 hardens the canonical repo and prepares the project for the first substantive engineering checkpoint: capture-to-seal readiness.

### Required outputs
The following outputs are required for M1 completion:

1. Canonical repo stabilization
   - confirm the active repo state and branch conventions
   - remove or clearly mark stale or contradictory historical claims
   - ensure the project direction is consistent across README, governance, and acceptance docs
   - keep approved implementation evidence distinct from prototype history

2. Baseline evidence package
   - record all active baselines
   - document the current acceptance and milestone references
   - maintain a lightweight ledger of work status and dependencies
   - identify proof required for each planned milestone step

3. Capture-to-seal foundation definition
   - define the minimum evidence model
   - define consent and artifact handling requirements before UI implementation
   - define save/resume and artifact integrity expectations
   - define minimum review workflow before routing or settlement logic

4. Engineering backlog split
   - pilot-critical work
   - post-pilot work
   - research and validation work
   - compliance-dependent work

5. Execution discipline
   - no broad feature expansion
   - no new economic logic without explicit approval
   - no informal reuse of historical prototype assumptions as design truth
   - every milestone item must have a stated owner and validation path

### M1 exit criteria
M1 is complete when all of the following are true:

- repo baseline is stable and aligned with approved scope
- stale or contradictory project claims are corrected or clearly labeled
- evidence and audit boundaries are clearly documented
- capture-to-seal scope is explicitly defined
- a minimal baseline work ledger is in place
- M2 can begin with a narrow, traceable milestone plan rather than broad exploratory work

### M1 ownership
- Engineering lead: technical baseline, repo health, milestone evidence
- Product owner: scope alignment and feature gate decisions
- Compliance/legal: approval of evidence, route, and policy claims
- Pilot owner: operational readiness and pilot boundary validation

## 6. Required approval gates

The following items require explicit approval and are not treated as routine implementation tasks:

- changes to product scope beyond M0/M1 boundary
- legal or evidentiary claims
- routing policy changes beyond the approved pilot rule set
- payments or any commercial settlement logic
- public blockchain or public anchoring approach
- deployment or staging operations beyond approved synthetic validation
- any change to the baseline capture sequence without a documented review
- owner incentive logic or economic terms

These items must be recorded in the decision register with:
- decision summary
- approver
- date
- reason
- link to evidence or supporting material

## 7. Decision register

| Decision | Status | Owner | Notes |
| --- | --- | --- | --- |
| Canonical repo is active implementation source of truth | Approved | Product owner | Repository is C2C-Connect/claim2car-connect |
| Pilot is a milestone inside the full product | Approved | Product owner | Not a substitute for the end-state product |
| Owner incentive excluded | Approved | Product owner / legal | No production logic, workflow, pricing, or roadmap inclusion |
| BYOD-first with limited MDM validation cohort | Approved | Pilot owner | Hardware approach remains pilot-scoped |
| fee_factor must remain zero unless counsel approves otherwise | Approved | Product owner / legal | Route policy remains constrained |
| Triage remains recommend mode until threshold is approved | Approved | Product owner / engineering | Human review must remain in place |
| Internal integrity pattern remains default | Approved | Engineering lead | Default SHA-256 + Merkle chain; public anchoring deferred |
| Legal/evidentiary claims require explicit approval | Approved | Legal/compliance | No informal legal certainty claims |
| Research items remain explicitly marked as research | Draft | Product owner | Requires classification boundary enforcement |

## 8. Active work ledger

The following items should be tracked during M0/M1:

| Item | Status | Owner | Required evidence |
| --- | --- | --- | --- |
| Governance confirmation | Not started | Product owner | Approved governance baseline |
| Scope freeze and ownership map | Not started | Product owner | Approved scope boundary |
| Repo stabilization audit | Not started | Engineering lead | Stable repo baseline and clean project narrative |
| Historical claim review | Not started | Engineering lead | Stale/prototype references identified and classified |
| Evidence and audit baseline review | Not started | Engineering lead | Evidence model and integrity baseline documented |
| Consent/data-handling contract definition | Not started | Product owner + engineering | Contract and workflow traceability recorded |
| Capture-to-seal definition | Not started | Engineering lead | Required behavior and acceptance boundary defined |
| M1 readiness review | Not started | Product owner | Exit criteria reached and documented |

## 9. Immediate next actions

The project should begin with the following actions, in order:

1. Confirm the governance and scope baseline.
2. Confirm the owner matrix and approval gate assignments.
3. Freeze the M0/M1 scope boundary.
4. Review the repo for stale or contradictory historical claims.
5. Define the required M1 evidence package.
6. Document the consent and evidence-handling baseline before UI expansion.
7. Prepare the project for M2 capture-to-seal milestone readiness.

## 10. Final statement

This charter exists to create a disciplined and evidence-first baseline for the canonical project repo. It is intentionally narrow: M0 and M1 are not broad product delivery phases; they are the stabilization and decision foundation that allows the project to safely proceed into the next milestone with clear scope control.

This document should be reviewed and approved before it is merged into the active project governance baseline.

## 11. M0/M1 summary section for executive review

### M0 — Alignment and constraints

Purpose:
- confirm the approved decision register
- freeze the active scope
- identify the final backlog split
- classify research, deferred items, and required approvals

Required outputs:
- governance baseline confirmation
- approved scope boundary
- approved non-goals
- decision register
- repo stabilization plan
- approval map

Exit criteria:
- governance baseline approved
- active vs deferred scope documented
- open approvals tracked
- repo stable enough for M1
- no active work under undefined scope

Owner:
- Product owner: scope and decision approval
- Engineering lead: repo stabilization
- Legal/compliance: evidentiary and compliance claims
- Pilot owner: operational constraints

### M1 — Baseline hardening

Purpose:
- preserve and stabilize the canonical repo foundation
- merge useful historical work without broadening scope
- ensure the repo is ready for the capture-to-seal milestone

Required outputs:
- canonical repo stabilization
- baseline evidence package
- capture-to-seal definition
- backlog split
- execution discipline plan

Exit criteria:
- repo stable and aligned to approved scope
- stale claims corrected or labeled historical
- evidence and audit boundaries documented
- capture-to-seal scope explicitly defined
- M2 can begin with a narrow and traceable milestone

Owner:
- Engineering lead: technical baseline and evidence
- Product owner: scope alignment
- Compliance/legal: approval for evidence and policy claims
- Pilot owner: operational readiness

## 12. M0/M1 execution checklist

### M0 — Alignment and constraints
- [ ] Confirm the canonical repo and project objective
- [ ] Confirm the pilot vs full-product boundary
- [ ] Confirm the approved decision register
- [ ] Freeze the active scope
- [ ] Define approved non-goals
- [ ] Split backlog into:
  - [ ] pilot-critical
  - [ ] post-pilot
  - [ ] research / validation
  - [ ] compliance-dependent
- [ ] Identify required legal/compliance approvals
- [ ] Identify required product and pilot approvals
- [ ] Review the repo for stale or contradictory historical claims
- [ ] Document unresolved risks and assumptions
- [ ] Confirm M0 exit criteria are met

### M1 — Baseline hardening
- [ ] Confirm repo stabilization plan
- [ ] Remove or label stale/prototype claims
- [ ] Validate current repo direction against README and governance
- [ ] Record active baselines and evidence references
- [ ] Document minimal capture-to-seal requirements
- [ ] Define minimal consent and evidence-handling expectations
- [ ] Define save/resume and integrity requirements
- [ ] Define review workflow before routing or settlement work
- [ ] Create a lightweight work ledger
- [ ] Confirm M1 exit criteria are met
- [ ] Prepare the repo for M2 milestone entry

### Approval gates
- [ ] Product scope changes reviewed
- [ ] Legal/evidentiary claims reviewed
- [ ] Routing policy changes reviewed
- [ ] Commercial or payment logic reviewed
- [ ] Public anchoring strategy reviewed
- [ ] Staging/deployment work reviewed
- [ ] Baseline capture sequence changes reviewed
- [ ] Owner incentive-related decision reviewed
