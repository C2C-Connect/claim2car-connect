# Slice 1 — Compensation and Branch Evidence Audit

**Document ID:** C2C-S1-COMP-AUDIT-001  
**Revision:** 0.1 — partial evidence record, not Slice 1 exit evidence  
**Reviewed:** 2026-11-08  
**Canonical repository:** `C2C-Connect/claim2car-connect`  
**Main revision inspected:** `a54ce7a08553ea7a35f70167b868ecb1ff4eb813`  
**Working branch:** `cto/slice-1-control-reconciliation`  
**Working revision inspected:** `50b8b5fa466643334ee51a424ffacdb929af4c85`

## 1. Binding rules

- Owner/vehicle-owner cash incentives and consent payouts are permanently prohibited at every amount and across all active product surfaces.
- The $110 operator amount remains unresolved and disabled. Its existence as a historical/configuration decision record does not authorize eligibility, trigger, obligation, payment, or settlement logic.
- Dealer fee: flat $375 on qualified-acquisition close.
- Repair-shop fee: flat $275 on recorded vehicle acceptance; acceptance authorizes routing to that accepting shop.
- Historical references, negative tests, and denylist terms may be retained where they explain or enforce the prohibition. They must not be mistaken for active product behavior.

## 2. Search and inspection scope completed

This partial pass inspected GitHub code-search results against the canonical repository's default branch (`main`), fetched the complete contents of the relevant files listed below, and inspected the corresponding working-branch changes in PR #24.

It also enumerated the repository's accessible branches: **155 total** at the time of inspection, including **131 branches with the `acceptance-evidence/` prefix** and **24 other branches**. Of the acceptance-evidence branches, the names include 41 `api-` branches and 34 `vin-` branches. The branch inventory is not a code-content audit.

**Important limitation:** GitHub code search used here searches the default branch, not every branch. The 155 branches and any other repositories accessible to the organization have not all been searched file-by-file. Therefore this document does not claim a complete repository-wide, all-branch, or all-repository audit. No branch or historical file was deleted.

## 3. Findings and disposition

| Surface / reference | Finding | Classification / disposition |
|---|---|---|
| `backend/app/main.py` on main | Health/readiness response exposed `operator_payout_usd` and `owner_payout: None`. | Active output-field defect on main; removed on PR #24 branch. |
| `backend/app/api/triage.py` on main | Adjudication response exposed `operator_payout_usd` and `owner_payout: None`. | Active output-field defect on main; removed on PR #24 branch. |
| `backend/app/reports/forensic_pdf.py` on main | Seven-page dossier attestation included operator payout and owner-payout keys. | Active report-output defect on main; removed on PR #24 branch. |
| `config/forensic_constants.py` | `OPERATOR_PAYOUT_USD = 110.0` remains with comments explicitly stating trigger/eligibility/ledger treatment are open; no owner payout constant is defined. | Retained decision record only; no payout activation authorized. Further search for indirect use remains part of the audit. |
| `tests/test_darci.py`, `tests/test_layer3.py`, `tests/test_dispatch.py` | Tests assert the operator amount remains a constant and owner payout constants are absent. | Historical/configuration guard tests; review naming/semantics as part of future cleanup, not a payment feature. |
| `app/carrier_messages.py` | Banned-term list includes historical incentive terms, including the former amount. | Intentional denylist safeguard; retain. |
| `tests/review/test_reviewer_dataset.py`, `tests/review/test_review_pipeline.py`, `tests/dispatch/test_carrier_messages.py` | Adversarial inputs containing prohibited compensation language are rejected or excluded. | Negative tests; retain. |
| `contracts/disclosure-v1.json` | Disclosure states no payment or compensation is offered or implied for participation. | Consistent with binding rule; retain. |
| `docs/LEGAL_REVIEW.md` | Explicitly marks all owner/vehicle-owner cash incentives and consent payouts as excluded. | Consistent decision record; retain. |
| `docs/GOVERNANCE.md`, `docs/SPEC_DECISIONS.md` | Claimed the historical amount had been eradicated from all repositories and documents. | Unsupported overclaim. PR #24 corrects language to distinguish prohibited active behavior from retained historical references and safeguards. |
| Root `GOVERNANCE.md` | Repeated superseded language that placed the operator payout in scope and pointed to old milestone status. | PR #24 replaces it with a navigation-only summary of current binding rules. |
| `docs/PROGRESS-M1-M2.md`, `docs/PROGRESS-M3-M4.md`, `docs/PROGRESS-M3-M5.md`, `docs/MILESTONE_5.md` | Historical sandbox/batch documents use “complete” labels that can be misread as current integrated-product acceptance. | PR #24 adds dated historical-snapshot notices; original task history and labels are preserved. |
| `tests/test_dispatch.py` on PR branch | Added an adversarial test that passes legacy compensation keys into dossier generation and asserts they do not appear in rendered output. | Regression coverage added; latest workflow verification is tracked separately. |

## 4. PR #24 implementation scope

PR #24 removes the owner-payout and unresolved operator-payout output fields from the backend health/readiness response, triage adjudication response, and seven-page dossier attestation output. It also removes the operator amount from the public constants response. It adds service authentication to selected internal analysis/triage/redaction operations; that shared token is not end-user identity or tenant authorization.

The PR does **not** establish that all possible historical references have been removed, that every repository/branch has been searched, that the $110 decision is resolved, or that any payout is enabled. The dispatch HTTP build route remains hard-disabled.

## 5. Remaining audit work before Slice 1 exit

1. Inspect the remaining non-evidence branches and all accessible repositories for active owner/operator payout behavior and contradictory commercial rules.
2. Classify the 131 acceptance-evidence branches by provenance, unique evidence, retention value, and whether they are safe to archive; do not delete before this review.
3. Search full repository contents—not only indexed excerpts—for indirect operator-amount use, payout calculations, serialization, templates, database fields, migrations, seeds, and UI references.
4. Reconcile all remaining current governance, acceptance, README, API, and deployment claims against the five-slice plan.
5. Add or retain negative tests that prove prohibited owner compensation cannot be emitted or created, without requiring historical references to be erased.
6. Record exact commands, branch/ref scope, test run IDs, limitations, and final acceptance evidence.

**Status:** Partial audit evidence recorded. Prohibited output fields are removed on the PR branch and targeted dossier regression coverage is added. Full accessible-branch/repository audit and Slice 1 governance exit criteria remain open.
