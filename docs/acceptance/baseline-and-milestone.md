# Claim2Car Connect — Baseline Record, Gate Dependencies, and Work Ledger

**Document ID:** C2C-BASE-001
**Version:** 1.0 — PROPOSED, pending owner adoption
**Baseline date:** 2026-10-28
**Companion documents:** `docs/acceptance/database-contract.md` (DB-01–14), `docs/acceptance/product-contract.md` (PRODUCT-01–14)

## 1. Pinned baselines

| Baseline | Reference | Commit SHA |
|---|---|---|
| Merged foundation | `main` | `08e1de1652bb2898d81b95e250413d11e821ef82` (PR #1, merged 2026-10-22) |
| Intake-slice candidate | `acceptance/capture-core` | `2edc6e508ceefc7215b2870e836a1a34f3b2e3d8` (draft PR #2; 13 commits / 26 files ahead of main) |
| Counted database test evidence | Run 39855103929, evidence branch `acceptance-evidence/39855103929-1` | Candidate `56f8b970`; 219 executed tests, pre-cutover through 0007 — not a complete primary post-cutover regression suite |

Recorded facts at pinning:

- [PR #1](https://github.com/C2C-Connect/claim2car-connect/pull/1) (merged foundation) and
  [draft PR #2](https://github.com/C2C-Connect/claim2car-connect/pull/2) (intake slice).
- [Counted-tests report](https://github.com/C2C-Connect/claim2car-connect/blob/acceptance-evidence/39855103929-1/acceptance-evidence/39855103929-1/counted-tests.json)
  and [evidence metadata](https://github.com/C2C-Connect/claim2car-connect/blob/acceptance-evidence/39855103929-1/acceptance-evidence/39855103929-1/evidence-metadata.json)
  for run 39855103929 (evidence-publication branch; the reports are tied to candidate `56f8b970`,
  not to the evidence branch tip).
- [README](https://github.com/C2C-Connect/claim2car-connect/blob/main/README.md) — canonical-repo
  declaration, pilot economics, staging-unprovisioned statement, retired prototypes.
- [verify_gates.py](https://github.com/C2C-Connect/claim2car-connect/blob/main/tests/database/verify_gates.py)
  — self-labeled synthetic preflight, not gate certification.
- Branch protection disabled and ruleset contents verified via the GitHub API on 2026-10-28.

- Capture-session HTTP functionality predates the PR-body snapshot (`207a752a`); the two commits after
  it added VIN-draft HTTP operations and loopback HTTP/PostgreSQL verification
  (`app/intake_api.py`, integration test). Any review of PR #2 must use `2edc6e50`, not the older
  snapshot.
- Classic branch protection on `main` is disabled; the single active ruleset enforces deletion,
  non-fast-forward, and Copilot review only. No required status checks exist yet.
- Historical run 39855103929, for candidate `56f8b970090c35818201cfadb6acada89b1f0ffd`, recorded
  `gate_passes_awarded: 0` and classified itself as non-certification evidence. This is not a fresh
  acceptance result for either pinned baseline.
- Staging is unprovisioned. The `san-antonio-pilot-staging` name is planning only.

## 2. Gate dependency map (initial — subject to implementation traceability)

Database guarantees support product requirements; they never satisfy an entire product gate by
themselves. Evidence storage, dealer offers, opportunity states, and settlement records additionally
require their own tenant isolation, authorized writes, and recovery evidence.

| Product gate | Supported by database gates |
|---|---|
| PRODUCT-01 Identity, authorization, consent | DB-03, DB-04, DB-05 (privileges, tenant isolation, context lifecycle) |
| PRODUCT-02 Capture session lifecycle | DB-07, DB-08 (durable append, idempotency, concurrency) |
| PRODUCT-03 Vehicle identity / VIN | DB-06, DB-07 (event contract, durable append) |
| PRODUCT-05 Integrity and provenance | DB-10, DB-12 (manifest roots, tamper/revocation) |
| PRODUCT-08 Adjudication records | DB-09 (event immutability) |
| PRODUCT-13 Audit and recovery | DB-09, DB-13 (immutability, restart/recovery/replay) |
| PRODUCT-14 Integrated acceptance | DB-14 (end-to-end acceptance reporting) |

PRODUCT-04, 06, 07, 09, 10, 12 depend primarily on application, frontend, and workflow code not
governed by the database contract; they inherit its guarantees through the gates above.

## 3. Work ledger

One lightweight ledger tracks the active milestone only. Each item records: requirement, status,
source files and commit, test evidence, validation evidence, blockers, and the acceptance decision.
Existing evidence JSON on `acceptance-evidence/*` branches supplies links and metadata; it never
automatically awards acceptance.

### Active milestone — M1: first controlled demonstration

**Cutline:** authorized test operator → consent → VIN → photos → durable save/resume → human
review. Simulated (labeled) dealer decision flow; no live routing, dispatch, or money movement.

| # | Item | Status | Notes |
|---|---|---|---|
| 1 | Adopt the two acceptance contracts (this document set) | AWAITING OWNER APPROVAL | Owner approval; commit to a new branch and open a draft PR on approval |
| 2 | Enable required status checks on `main` | AWAITING OWNER APPROVAL | Separate settings-change approval; select checks by job context (database, API, authority-cutover verification), not all workflows indiscriminately |
| 3 | Review PR #2 full diff at `2edc6e50` against execution evidence; record demonstrated gaps | NOT STARTED | Include hardening gaps: request size limits, rate controls, broader failure paths. Merge/no-merge is a separate deliberate decision |
| 4 | Slice-specific acceptance for the intake slice (not full 14-gate certification) | NOT STARTED | Bar for PR #2 promotion: slice acceptance + applicable database regressions |
| 5 | Consent + artifact-storage contracts defined before capture UI | IN PROGRESS (Slice 4) | Versioned disclosure contract (`contracts/disclosure-v1.json`) + workflow engine (`app/capture_workflow.py`) landed 2026-11-06; artifact-storage contract (Slice 5) next |
| 6 | M1 workflow increments: consent screen, photo checklist, save/resume, review interface | IN PROGRESS (Slice 4) | Guided-capture controller (`frontend/src/modules/capture/guided_workflow.mjs`) with local persistence + resumable sync landed 2026-11-06; physical-device verification still pending |
| 7 | Minimal synthetic staging rehearsal (when first usable slice is ready) | IN PROGRESS (Slice 5) | Controlled demonstration (`python -m app.controlled_demo`) runs fully synthetic capture-to-review end-to-end with retained Gate A evidence record; CI (`controlled-demo.yml`) retains evidence on every run. Railway staging provisioning still needs separate approval |
| 8 | M1 rehearsal against the gate matrix; demo-readiness review | IN PROGRESS (Slice 5) | Synthetic rehearsal covers disclosure, consent, VIN, capture, durable storage, server hash recomputation (with rejected tamper attempt), seal, and attributed reviewer decision. Physical-device verification and owner demo-readiness review remain open |

### Backlog (not actively tracked)

The 12-phase roadmap (Phase 2 hardening through dealership onboarding) remains the backlog of record.
Phases are pulled into the active ledger one at a time as dependencies clear.

## 4. Decision log

| Date | Decision | Status |
|---|---|---|
| 2026-10-28 | Layer the two 14-gate frameworks (database vs product) instead of merging them | Proposed — published as draft PR, awaiting owner review and approved merge |
| 2026-10-28 | First-demo cutline ends at human review; dealer routing/settlement are labeled simulation in the demo | Proposed — published as draft PR, awaiting owner review and approved merge |
| 2026-10-28 | Move required-check enforcement from late-phase release review to the start of work | Proposed — published as draft PR; the settings change itself requires a separate approval |
| 2026-10-28 | Consent and storage contracts precede capture UI work | Proposed — published as draft PR, awaiting owner review and approved merge |
