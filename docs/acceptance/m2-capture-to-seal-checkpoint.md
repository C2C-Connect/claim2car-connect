# Claim2Car Connect — M2 Capture-to-Seal Checkpoint

Status: Draft sprint plan
Repository: C2C-Connect/claim2car-connect
Applies to: milestone execution, evidence readiness, and narrow product progression

## 1. Purpose

This document defines the first tangible execution sprint after the M0/M1 baseline work. The goal is to move from repo hardening and scope alignment into a narrow, evidence-driven product slice: capture-to-seal readiness.

This sprint is intentionally constrained. It is not a broad product launch. It is a controlled milestone that demonstrates the core sequence:
- authenticated operator session
- session creation
- VIN validation
- intake draft persistence
- evidence integrity path
- sealed or verifiable record path

The objective is productive momentum without uncontrolled scope growth.

## 2. Decision posture

This sprint follows the governing direction already established in the governance baseline and the M0/M1 execution draft.

Approved posture for this sprint:
- work stays inside the canonical repo
- no public product claims beyond controlled-test evidence
- no live financial or payment logic activation
- no dealer routing activation beyond explicit simulation
- no staging or deployment beyond approved synthetic or controlled-test execution
- no broad feature expansion outside the capture-to-seal slice

## 3. Sprint goal

Deliver a narrow but tangible capture-to-seal milestone package that proves:
- a valid session can be created and bound to an authorized actor
- a controlled intake draft can be saved and read back
- VIN validation is enforced before intake persists
- evidence lineage is preserved and auditable
- the system is ready for the next review gate without expanding scope beyond the checkpoint

## 4. Scope boundary for M2

### 4.1 In scope
- session creation and authorization checks
- intake draft creation and save/readback
- VIN validation and check-digit guard
- evidence journal/log integrity for draft persistence
- readback verification for controlled-test sessions
- strict validation of all data inputs and rejection of unexpected fields
- narrow milestone verification evidence

### 4.2 Out of scope
- live routing logic
- payment rails
- dealer onboarding
- full pilot deployment
- production staging
- owner incentive logic
- broad analytics or BI workflows
- live external integrations beyond explicit controlled-test verification

## 5. Concrete milestone outputs

The following are the required outputs for this sprint:

1. Session creation flow
   - authorized session creation succeeds under valid credentials
   - invalid or unauthorized credentials are rejected
   - no private connection details are exposed in responses

2. Intake draft flow
   - draft creation works under the controlled-test path
   - readback is valid and deterministic
   - conflicting revisions are rejected
   - invalid VINs are rejected before persistence

3. VIN gate enforcement
   - VINs are validated before any persisted intake draft is allowed
   - invalid, malformed, or checksum-failing input is rejected
   - normalization logic does not silently rewrite or invent data

4. Integrity and audit trace
   - each draft write is traceable in the event journal
   - values can be reconstructed from persisted evidence
   - the integrity model remains controlled-test only and not product-certification claim

5. Evidence package
   - test logs or verification outputs for the controlled path
   - pass/fail summary for the milestone slice
   - clear statement of what is and is not validated

## 6. Acceptance criteria

This sprint is complete only when the following are true:

- a valid capture session can be created for an authorized actor
- a valid intake draft can be saved and read back without drift
- invalid VINs are rejected before persistence
- mismatched revision or conflicting write attempts are rejected cleanly
- event or journal evidence reflects the successful controlled-test writes
- the code path remains explicitly labeled as controlled-test, not production or pilot-certification evidence
- the evidence package clearly states the verification scope

## 7. Exit gate for M2

The ticket is done when all of the following are satisfied:

- [ ] session creation path passes validation
- [ ] intake draft save/readback path passes validation
- [ ] VIN validation gate is enforced before persistence
- [ ] conflict and revision checks are enforced
- [ ] evidence package is recorded and reviewable
- [ ] no out-of-scope billing, routing, or deployment logic is included
- [ ] final review confirms the milestone is narrow, valid, and reviewable

## 8. Execution plan

### Sprint tasks

1. Finalize the narrow M2 slice definition
   - confirm the exact M2 boundary
   - ensure no drift beyond capture-to-seal readiness

2. Review existing controlled-test implementation evidence
   - PR #2 merged implementation
   - existing acceptance docs and baseline references
   - current repo constraints and accepted risks

3. Validate runtime behavior for the capture session and draft save path
   - create session
   - save draft
   - read back draft
   - reject invalid VIN and bad revisions

4. Record evidence
   - verification results
   - pass/fail summaries
   - explicit limit of the proof claim

5. Perform milestone review gate
   - confirm the milestone demonstrates the intended slice
   - confirm no unapproved scope creep
   - confirm M2 is ready to close and hand off to the next checkpoint

## 9. Ownership

- Product owner: scope confirmation and milestone approval
- Engineering lead: implementation and test execution
- Compliance/legal observer: review all claims and ensure no overstatement
- Pilot owner: operational boundary review, but not a deployment gate for this sprint

## 10. Sprint cadence

This sprint should move with disciplined velocity:

- no more than one core milestone slice at a time
- clear exit criteria before moving to the next feature
- evidence before expansion
- no broad parallel workstreams unless they are required by the current milestone

The aim is not slowness, but controlled momentum.

## 11. Immediate next actions

The next immediate actions are:

1. confirm M2 scope and exit gate
2. validate the existing controlled-test capture and draft code path against the sprint checklist
3. record evidence in the repo and review it against the fixed exit criteria
4. decide whether the milestone is ready to close or requires a small follow-on patch

This sprint is designed to generate tangible product progress while staying aligned with the governance and acceptance baseline.
