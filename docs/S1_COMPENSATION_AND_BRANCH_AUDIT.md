# Slice 1 — Compensation and Branch Evidence Audit

**Document ID:** C2C-S1-COMP-AUDIT-001  
**Revision:** 0.2 — partial evidence record, not Slice 1 exit evidence  
**Reviewed:** 2026-11-08  
**Canonical repository:** `C2C-Connect/claim2car-connect`  
**Main revision inspected:** `a54ce7a08553ea7a35f70167b868ecb1ff4eb813`  
**Working branch:** `cto/slice-1-control-reconciliation`  
**CI-tested source/test revision:** `50b8b5fa466643334ee51a424ffacdb929af4c85`  
**Current PR branch head at revision 0.2:** `ee1bb80939970199e95cb857ba79c7ee8d0f98a9`

## 1. Binding rules

- Owner/vehicle-owner cash incentives and consent payouts are permanently prohibited at every amount and across all active product surfaces.
- The $110 operator amount remains unresolved and disabled. Its existence as a historical/configuration decision record does not authorize eligibility, trigger, obligation, payment, or settlement logic.
- Dealer fee: flat $375 on qualified-acquisition close.
- Repair-shop fee: flat $275 on recorded vehicle acceptance; acceptance authorizes routing to that accepting shop.
- Historical references, negative tests, and denylist terms may be retained where they explain or enforce the prohibition. They must not be mistaken for active product behavior.

## 2. Search and inspection scope completed

This partial pass inspected GitHub code-search results against the canonical repository's default branch (`main`), fetched the complete contents of the relevant files listed below, and inspected the corresponding working-branch changes in PR #24.

It also enumerated the repository's accessible branches: **155 total** at the time of inspection, including **131 branches with the `acceptance-evidence/` prefix** and **24 other branches**. Of the acceptance-evidence branches, the names include 41 `api-` branches and 34 `vin-` branches. The branch inventory is not a code-content audit. Compare results against `main` show that, among 22 legacy non-evidence branches compared (excluding `main` and the active CTO PR branch), 13 are strictly behind `main` with zero unique commits and 9 are diverged with unique commits. The active CTO branch is separately 31 commits ahead and 2 behind.

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


## 6. Legacy branch comparison — high-risk findings

### 6.1 Branches with no unique commits

These 13 branches compare as strictly behind `main` with zero commits ahead and zero changed files relative to `main`:

- `C2C-Connect-patch-1`
- `acceptance/capture-core`
- `database-acceptance-run/20261014-104900`
- `deploy/railway-restricted-staging`
- `docs/acceptance-contracts`
- `feature/random-joke-generator`
- `five-slices/evidence-storage-03`
- `five-slices/ex00-audit-01`
- `five-slices/intake-deployment-02`
- `five-slices/render-staging-04`
- `fix/railway-stale-commit-readiness`
- `sandbox/m1-m2-snapshot`
- `sandbox/m3-m4-m5-snapshot`

Classification: stale branch refs with no unique commits relative to current main. They are candidates for archival/deletion only after evidence-retention and branch-protection review. None were deleted.

### 6.2 Diverged branches with unique commits

- `phase1-foundation-bootstrap` — **202 ahead / 78 behind; 44 changed files.** The branch contains a separate tenant-scoped `app/sessions.py` and capture/session surface. On `DEALER_ACCEPTED`, `record_decision` automatically writes a `SETTLEMENT_RECORDED` event with hard-coded `operator_payout_cents: 11000` ($110) and `dealer_invoice_cents: 37500` ($375). Settlement, dashboard, summary, dealer-packet, carrier-packet, and settlement-list response models/readers expose operator payout values; settlement history/detail and packet HTML display the payout. The branch's `tests/api/session_auth_rls_proof.py` explicitly asserts those amounts. This trigger conflicts with the current unresolved/disabled $110 rule and the current $375 dealer fee trigger (qualified-acquisition close, not simply dealer acceptance). The inspected key files contained no owner-payout field or $80 value, but the full 44-file branch has not been exhaustively scanned. This branch is **not on main and has no deployment evidence**. Preserve its potentially useful capture/RLS/migration work for selective review; do not merge or revive wholesale.
- `fix/cors-and-redact-auth` — **1 ahead / 13 behind; 4 changed files.** Retains `owner_payout` and `operator_payout_usd` fields in backend health/main, triage, and dossier surfaces. Its service-auth helper uses the older `C2C_SERVICE_TOKEN` / `C2C_API_KEYS` scheme and does not provide the current branch's exact fail-closed route coverage. Do not merge wholesale.
- `harden/api-auth-darci-complete` — **1 ahead / 13 behind; 7 changed files.** Also retains `owner_payout` and `operator_payout_usd` output fields in backend main, triage, and dossier surfaces. Its older service-token helper is not equivalent to the current Slice 1 implementation. Its constants include dealer fee range $375–$425 and shop auction floor $250, conflicting with the current flat $375 dealer and flat $275 shop rules. Do not merge wholesale.
- `sandbox/m1-m2` — **2 ahead / 13 behind; 4 changed files.** Contains a small sequential SHA-256 hash-chain helper and sandbox snapshots. Its README/PROGRESS/SNAPSHOT describe the $110 operator payout as the locked commercial rule and label M1 complete/M2 near-complete. Those are historical sandbox claims, not current policy or acceptance. The hash helper is an integrity primitive only; it does not establish source authenticity or legal provenance.
- `slice4/capture-workflow` — **1 ahead / 9 behind; 9 changed files.** Contains a guided-capture prototype with disclosure/consent ordering, VIN format/check-digit validation, a shot-list controller, synthetic event/metadata handling, local draft persistence, and resumable sync tests. Its own source explicitly says it stores no images, performs no vehicle decoding, makes no authenticity/ownership claims, and does not seal or review. Candidate for selective Slice 2 reuse after architecture review; not a complete operator app or field-validated workflow.
- `safety/synthetic-provenance-integration` — **1 ahead / 21 behind; 3 changed files.** Adds a dispatch-build HTTP 503 containment handler and direct-handler tests. Its own verification note says those tests were not executed in the authoring session. The handler does not secure all internal builders or establish tenant authorization. Treat as a containment reference, not proof of integrated safety.
- `docs/m1-source-notes` — **8 ahead / 76 behind; 8 changed files.** Contains non-binding historical source notes and an explicitly unwired lifecycle prototype. Preserve as research/reference; not an implementation or economics authority.
- `full-build-foundation-m1` and `governance-m0m1-baseline` — each **4 ahead / 58 behind; 4 changed files** and their branch tips compare identical. They duplicate the same acceptance charter/checkpoint/script/test snapshot; do not merge both copies.
- The remaining unique branch comparison is the active CTO branch `cto/slice-1-control-reconciliation` (**31 ahead / 2 behind**), tracked by PR #24.

### 6.3 Merge and retention disposition

1. No diverged legacy branch is authorized for wholesale merge.
2. The hard-coded $110 settlement-on-dealer-acceptance path in `phase1-foundation-bootstrap` is a specific prohibited revival risk until the operator payout decision is resolved.
3. The stale `owner_payout` / `operator_payout_usd` fields in the two old auth branches are another reintroduction risk; PR #24 corrects canonical main, but those branches remain stale.
4. The 13 behind-only branches may be considered for archival after the evidence-retention policy is defined. No deletion is authorized by this audit record.
5. The 131 `acceptance-evidence/` branches remain uninspected at content level. They must be indexed and classified before any pruning.
6. Continue to separate salvageable technical assets (RLS proof, migrations, capture workflow, VIN guard, hash-chain prototype) from stale policy, unvalidated behavior, and unsupported completion claims.
