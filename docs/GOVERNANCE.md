# Claim2Car Connect — Project Governance and Decision Register

**Status:** Active  
**Effective:** 2026-11-02  
**Supersedes:** All prior pilot, M0/M1, and review-posture governance documents

## 1. Canonical Repository and Scope

- Canonical implementation repository: `C2C-Connect/claim2car-connect`
- Historical and prototype repositories are reference/backlog sources only. They are not active sources of truth.
- This repository is the sole active engineering repository for the product.

**Product objective**  
Build the complete Claim2Car Connect platform: roadside capture → cryptographic sealing → physics-first multi-modal triage → brand-matched commercial routing → auditable handoff → continuous self-audit.

## 2. Owner Decision (Binding)

On 2026-11-02 the product owner issued the Full Build Directive. That directive is binding.

Key consequences:

- Every feature, formula, workflow, portal, report, queue, and integration described in the Claim2Car Architecture reference document is in scope for development.
- Legal, evidentiary, commercial, fee, marketplace, and payout features are to be implemented in full. They are flagged “pending attorney review before publication.”
- A single `LEGAL_REVIEW.md` lists every claim or feature the attorney must examine. That list replaces all previous legal/compliance gates.
- Performance and business numbers (180 ms, 30–50 ms, $0.008, 99.98 %, etc.) are design targets. They are measured and reported; they are not preconditions for implementation.
- Development proceeds without intermediate permission requests. The only stop condition is technical impossibility (with a stated closest alternative).

## 3. Explicit Commercial & Incentive Rules

| Item | Rule |
|------|------|
| Operator (tow) payout | $110. Triggered when e-signature is verified **and** S_i ≥ 0.65 **and** dealer acceptance occurs. Implemented via internal payout ledger. |
| Owner / vehicle-owner cash incentive | **Permanently excluded.** No $80 (or any other) owner payout exists in product scope, data model, workflows, UI, reports, or documentation. Legal counsel directed removal for liability reasons. |
| Dealer acquisition fee | $375–$425 range, pay-on-close. fee_factor is active in scoring. |
| Shop auction floor | $250. Full two-stage Sovereign Repair Auction is in scope. |
| Marketplace & auctions | Fully in scope. |
| Anchoring | Internal append-only ledger is the default. Full public verify flow is required. Chain-anchor adapter interface is maintained for possible later external anchoring. |

## 4. Approved Engineering Decisions

- Capture protocol: 16-v1 is the default. 12-v1 remains a selectable, versioned alternative. Both are recorded on every session.
- Integrity: SHA-256 sequential chaining + Merkle roots are mandatory. Broken chain blocks sealing.
- Physics primacy: 55 % DARCI / 45 % visual ensemble. Deterministic physics and Shannon entropy overrides cannot be disabled by visual models.
- All constants, weights, and thresholds live in `config/forensic_constants.*` and are versioned.
- Conflicts among reference-document versions are resolved by the rules in the Full Build Directive and logged in `SPEC_DECISIONS.md`.
- Outside services: only free NHTSA endpoints are permitted. Everything else is self-hosted or internal behind an adapter.

## 5. Milestone Discipline

Work follows the seven-milestone sequence defined in the Full Build Directive. Each milestone must be end-to-end complete (code, migrations, seeds, unit + integration tests, README, SPEC_DECISIONS / LEGAL_REVIEW updates, benchmarks) before the next begins. All milestones remain in scope.

## 6. Document Hierarchy

1. Full Build Directive (owner decision)  
2. This GOVERNANCE.md  
3. `LEGAL_REVIEW.md`  
4. `SPEC_DECISIONS.md`  
5. Architecture reference document (functional specification)  
6. Code and tests

Any conflict is resolved in favor of the higher document.

## 7. Change Control

Material changes to scope, commercial rules, or integrity guarantees require an explicit owner decision recorded in this file and in `SPEC_DECISIONS.md`. Day-to-day implementation decisions do not.
