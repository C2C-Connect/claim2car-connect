# Claim2Car Connect — Project Governance and Decision Register

**Status:** Active  
**Effective:** 2026-11-06 (aligned to Master Pilot Execution Plan v1.3)  
**Supersedes:** All prior pilot, M0/M1, review-posture, and Full Build Directive (2026-11-02) governance documents

## 1. Canonical Repository and Scope

- Canonical implementation repository: `C2C-Connect/claim2car-connect`
- Historical and prototype repositories are reference/backlog sources only. They are not active sources of truth.
- This repository is the sole active engineering repository for the product.

**Product objective**  
Prove the Gavel M1 capture-to-review workflow first, then the separately gated commercial workflow
(roadside capture → cryptographic sealing → physics-first multi-modal triage → distribution →
acceptance → dispatch/navigation → fee collection → auditable handoff → continuous self-audit).

## 2. Owner Decisions (Binding)

The 2026-11-02 Full Build Directive is superseded by the Master Pilot Execution Plan v1.3
(2026-11-06) and the owner's five-slice execution approval (2026-11-06):

- The Gavel M1 boundary (plan v1.3 §2.1) governs engineering acceptance. Commercial,
  payment, distribution, dispatch, and navigation capabilities are separately gated
  workstreams (plan v1.3 phases 12A–12C, Gates C/D) — specified, not M1 criteria.
- Every feature remains "pending attorney review before publication" where listed in
  `LEGAL_REVIEW.md`; live external sends, payment collection, and publication claims
  stay disabled until counsel approves.
- Performance and business numbers (180 ms, 30–50 ms, $0.008, 99.98 %, etc.) are design
  targets. They are measured and reported; they are not preconditions for implementation.
- Development proceeds per the five-slice execution plan with the owner's standing
  approval; the only stop conditions are technical impossibility (with a stated closest
  alternative) or a plan v1.3 legal/commercial gate.

## 3. Explicit Commercial & Incentive Rules

| Item | Rule |
|------|------|
| Operator (tow) payout | $110 amount carried forward (plan v1.3, D-04). Eligibility, trigger, split, reversals, disputes, and ledger treatment remain an open owner decision — no payout logic until approved. Separately confirmed: the shop's recorded acceptance of the vehicle authorizes tow dispatch/routing to that shop, with guided navigation for the delivery run. |
| Owner / vehicle-owner cash incentive | **Permanently excluded from product behavior.** No owner payout of any amount may be implemented or exposed through the data model, workflows, UI, APIs, reports, or settlement. Legal counsel directed removal for liability reasons. Historical references may remain in decision history, negative tests, denylist safeguards, and audit records solely to document the prohibition and prevent reintroduction; their presence is not active product support. The repository-wide and accessible-branch audit remains tracked in Slice 1 until its search scope and findings are recorded. |
| Dealer acquisition fee | **Flat $375, due upon close of the qualified acquisition** (plan v1.3, D-01 — supersedes the $375–$425 range and the earlier $175 figure; not due merely for receiving a packet or expressing interest). |
| Repair-shop fee | **Flat $275, due upon the shop's recorded acceptance of the vehicle** (plan v1.3, D-02 — supersedes the $250 auction floor). Acceptance precedes tow dispatch to that shop. |
| Automatic distribution | On workflow completion, the system automatically distributes the dealer packet dossier, shop repair packet, owner PDF, and insurance-carrier 7-page document to the relevant authorized parties, per the plan v1.3 §3.2 delivery state machine. Versioned, consent-gated, auditable. Live sends remain disabled pending attorney review. |
| Acceptance & guided navigation | On acceptance by the receiving party (dealer or repair shop), the system provides step-by-step guided navigation (Google Maps or equivalent, behind an adapter) to that party's destination; the tow driver receives guided routing to the accepting shop for vehicle delivery (plan v1.3 §4). |
| Marketplace & auctions | Separately gated commercial workstream (plan v1.3 phases 12A–12C). Not M1 scope. |
| Fee-based dealer ranking (fee_factor) | **Disabled** per plan v1.3 D-06. Remains off until governance, explainability, conflicts, and tests are approved. |
| Anchoring | Internal append-only ledger is the default. Full public verify flow is required. Chain-anchor adapter interface is maintained for possible later external anchoring. |

## 4. Approved Engineering Decisions

- Capture protocol: 16-v1 is the default. 12-v1 remains a selectable, versioned alternative. Both are recorded on every session.
- Integrity: SHA-256 sequential chaining + Merkle roots are mandatory. Broken chain blocks sealing.
- Physics primacy: 55 % DARCI / 45 % visual ensemble. Deterministic physics and Shannon entropy overrides cannot be disabled by visual models.
- All constants, weights, and thresholds live in `config/forensic_constants.*` and are versioned.
- Conflicts among reference-document versions are resolved by the rules in the Master Pilot Execution Plan v1.3 and logged in `SPEC_DECISIONS.md`.
- Outside services: only free NHTSA endpoints are permitted. Everything else is self-hosted or internal behind an adapter.

## 5. Milestone Discipline

Work follows the five-slice execution sequence (owner approval 2026-11-06), aligned to the plan v1.3 phase order (0–12). Each slice must be end-to-end complete (code, migrations, seeds, unit + integration tests, README, SPEC_DECISIONS / LEGAL_REVIEW updates, benchmarks) before the next begins. Commercial capabilities remain separately gated (phases 12A–12C).

## 6. Document Hierarchy

1. Master Pilot Execution Plan v1.3 (owner-approved planning baseline)  
2. This GOVERNANCE.md  
3. `LEGAL_REVIEW.md`  
4. `SPEC_DECISIONS.md`  
5. Architecture reference document (functional specification)  
6. Code and tests

Any conflict is resolved in favor of the higher document.

## 7. Change Control

Material changes to scope, commercial rules, or integrity guarantees require an explicit owner decision recorded in this file and in `SPEC_DECISIONS.md`. Day-to-day implementation decisions do not.
