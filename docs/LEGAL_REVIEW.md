# Claim2Car Claims, Legal Review & Publication Register

**Effective:** 26 November 2026  
**Authority:** Current product calibration and owner-approved M1 boundary.  
**Purpose:** Track external claims and legal/commercial publication approvals. This file is not legal advice or evidence of counsel approval.

## Status vocabulary
- **PROPOSED:** idea or target only.
- **SPECIFIED:** contract/requirement exists.
- **IMPLEMENTED-UNVERIFIED:** code exists; behavior not fully verified.
- **TESTED:** named automated tests passed on an exact commit.
- **VALIDATED:** evaluated against representative evidence/ground truth with documented method and limitations.
- **COUNSEL-REVIEWED:** reviewed by qualified counsel for the stated use and jurisdiction.
- **APPROVED:** explicit authorized approval for the stated audience and use.
- **WITHDRAWN / PROHIBITED:** must not appear as an active product capability or claim.

## 1. Governing claim rules
Every outward-facing numeric, forensic, legal, safety, performance, compliance, AI, valuation, commercial or payment claim must identify: exact wording; audience; owner; source/version; definition/scope; evidence and test method; environment/sample size; results/error rates; limitations/failure modes; independent reviewer; approval date; status. A code path, synthetic test, hash, score, model output or green CI run is not validation.

Use qualified language such as “designed to support,” “intended to preserve,” or “will be evaluated for” until the evidence supports stronger wording.

## 2. Active M1 claims and controls

| Claim / feature | Current status | Publication rule |
|---|---|---|
| Original-byte preservation and SHA-256 verification | Software components implemented/tested; post-merge and operational storage verification remain | State exactly which bytes and verification boundary are covered. Hashes do not prove scene truth, capture time/location, identity or admissibility. |
| Persistent event chain and manifest registration | PR #185 recorded merged; candidate CI 13/13 and DB 14/14; exact-main post-merge check pending | Describe as tamper-evident under stated threat model, not immutable or independently notarized. |
| Evidence Measurement and Substantiation Contract v1.0.0 | PR #195 open/draft; exact-head automated contract checks reported green | Contract schema only; no claim of actual camera calibration, LiDAR accuracy, physical metrology or model validation. |
| 16-point capture protocol | Versioned software contracts exist; field/device qualification absent | Describe completeness accounting, exceptions and retakes. Never claim every view is safe or obtainable. |
| Browser offline queue encryption | Automated browser/CI evidence exists; no WORM/secure enclave or field qualification | Do not call IndexedDB immutable or physically tamper-proof. |
| Consent withdrawal | Retry correction in PR #196; exact corrected-head acceptance pending; durable deletion lifecycle incomplete | Do not promise global/immediate deletion across derivatives, backups and offline devices. |
| Human review | Controlled software workflow exists; field/operational acceptance pending | State reviewer scope and evidence available; do not imply expert certification unless actually performed. |

## 3. AI, physics, measurement and vehicle claims

| Claim / feature | Status | Required evidence before stronger claim |
|---|---|---|
| YOLO/SAM2/depth ensemble | Research/adapter scope; production weights and accuracy not established | Lawful representative dataset, independent labels, held-out evaluation, per-class metrics, calibration, subgroup analysis, drift and abstention. |
| 55/45 physics/AI consensus | Withdrawn as an unvalidated fixed weighting rule | Replace with separately versioned outputs and a validated evidence-dependent policy. |
| DARCI collision mechanics / CRASH3 | Research only; not M1 authority | Traceable inputs, units, assumptions, sensitivity, uncertainty, vehicle/material applicability and independent validation. |
| LiDAR volumetric crush / sub-centimeter accuracy | Deferred; device qualification and metrology validation absent | Exact device/OS, range/confidence, calibration, reference measurement and independent error study. |
| Acoustic tap / hidden weld fracture | Research-only; no validated diagnostic claim | Calibrated acquisition protocol, controlled reference specimens, qualified ground truth and false-positive/negative analysis. |
| ACV / repair-to-value / total loss | Not source-validated for consequential decisions | Licensed market sources, vehicle applicability, date/geography/comparables, versioned jurisdiction rules and qualified review. |
| OEM/CAPA parts and repair procedures | Current seed catalog is synthetic/test data, not authoritative OEM data | Licensed/source-backed records, vehicle applicability, supersession, effective dates and qualified technician review. |
| Collision causation / roadworthiness / hidden damage | Not established by image capture or current model outputs | Qualified reconstruction/inspection evidence and appropriate professional review; platform must abstain when evidence is insufficient. |

## 4. Legal, evidentiary and privacy review

- FRE 901 / 902(13) / 902(14) references: **pending qualified counsel review**. The platform does not self-certify admissibility. Any certification requires the actual qualified certifier, basis, certificate artifact, notice and procedure.
- Hash chains, Merkle roots, signatures, trusted timestamps and blockchain anchoring are distinct. No “blockchain proof” or independent notarization claim without a real, verified implementation and threat model.
- Consent language, representative authority, data purpose, recipient categories, retention, withdrawal, downstream copies, backup expiry and legal hold require counsel/privacy review before participant evidence or external distribution.
- SMS/email, recipient dossier sharing, location/navigation sharing and carrier delivery require channel- and recipient-specific authorization and legal review.
- Tax eligibility, lender payoff/APR, statutory total-loss thresholds and jurisdictional legal conclusions must not be inferred from VIN or generic fallback rules.

## 5. Commercial and payment rules

| Item | Planning position | Restriction |
|---|---|---|
| Dealer acquisition fee | $375 on qualified acquisition close | Not earned merely on packet receipt or expression of interest. Contract and close event must be defined. |
| Repair-shop fee | $275 on recorded acceptance in current planning materials | Reconcile with Master Pilot Execution Plan and approved contract; define invoice/collection/refund/dispute semantics. |
| Tow operator amount | $110 carried forward | Trigger, eligibility, split, reversals, disputes and ledger treatment unresolved; do not implement payout until approved. |
| Vehicle-owner cash incentive | PROHIBITED / permanently excluded | No owner payout field, UI, API, report or settlement behavior. Historical references may exist only to document the prohibition. |
| Live Square/payment activity | NOT AUTHORIZED | Sandbox is not live readiness. Requires provider approval, ledger/reconciliation, security, legal and separate release authorization. |

## 6. Publication prohibitions until evidence and approval exist

Do not publish claims that Claim2Car:
- makes evidence “legally conclusive,” guarantees admissibility, eliminates liability or makes spoliation arguments unwinnable;
- creates “tamper-proof,” physically immutable or independently notarized evidence merely through hashes or IndexedDB;
- guarantees universal sub-centimeter LiDAR measurement or fixed sensor sample rates on all devices;
- determines hidden structural damage, collision causation, roadworthiness, repairability or total loss autonomously;
- produces validated AI probabilities from uncalibrated confidence scores or majority votes;
- guarantees ACV, tax eligibility, lender terms, settlement outcomes, revenue, margin or operator payouts;
- has deployed integrated staging, accepted field devices, active carrier delivery, live dispatch or production payments when those gates have not passed.

## 7. Approval record
No item is approved merely because it appears in this register. Record the reviewer, jurisdiction, audience, exact wording, source evidence, limitations, date and approval scope when counsel/owner approval is actually obtained.
