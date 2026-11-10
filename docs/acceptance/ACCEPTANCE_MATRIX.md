# Claim2Car Connect — Acceptance & Release Gate Matrix

**Canonical repository:** `C2C-Connect/claim2car-connect`  
**Candidate branch:** `cto/spec-production-implementation` (PR #29)  
**Last code validation revision:** `0a0ddd7e0f37b8b5e24616d2ad98e7cb44c28ac9`  
**Machine contract:** `m1-v1`  
**Status rule:** code, CI, field validation, review, and release authorization are recorded separately. A passing synthetic test does not establish product acceptance or production readiness. The candidate revision is not merged and has no submitted independent review.

## Commercial and safety controls

| Requirement | Enforcement surface | Verification | Status |
|---|---|---|---|
| Dealer fee is fixed at $375 (37,500 cents) | `config/forensic_constants.py`; `backend/app/anchor/ledger.py`; persistent ledger migration and adapter | `tests/contracts/test_commercial_prohibitions.py`; `tests/dispatch/test_integer_financial_ledger.py`; full-suite CI | Dealer fee posting is fail-closed in both the Python ledger and SQL authority function until a verified qualified-acquisition-close event is integrated; shop acceptance posting remains a component, not a live partner workflow |
| Shop fee is fixed at $275 (27,500 cents) on recorded acceptance | `app/dispatch_routing.py`; persistent integer-cents ledger | Commercial and ledger suites | Implemented and regression-tested on the PR #29 candidate; live partner acceptance is not deployed |
| Owner cash incentives are prohibited | Commercial constants, ledger guard, dossier output guard | Commercial and dossier suites | Implemented and regression-protected on the PR #29 candidate |
| $110 operator payout remains disabled pending policy decision | Integer-cents ledger gate and active-output checks | Commercial and ledger suites | Disabled on the PR #29 candidate; no settlement is authorized |
| Roadside pause, unsafe-slot skip, and scene abort remain available | `frontend/src/modules/capture/slice2_workbench_controller.mjs` | `frontend/tests/slice2_workbench.test.mjs` | Implemented on the PR #29 candidate; 12 assertions pass in the local Node run and the GitHub full-suite workflow passes |
| Independent human reviewer inspects sealed evidence and records a supported review outcome | Integrated reviewer queue, verified-session detail API, original-byte retrieval API, and review-record API | Capture evidence service tests; integrated runtime route tests; full-suite CI | Initial connected reviewer workbench is implemented on PR #29: sealed manifest and original bytes are re-verified before artifact metadata is returned; originals are retrievable by an independent reviewer; NOTE_ONLY and HUMAN_QC_REQUIRED are recorded. Qualified-device/field validation, reviewer assignment/escalation, and final claim adjudication remain incomplete. |

## Security, evidence, and product gates

| Gate | Exit requirement | Evidence | Current status |
|---|---|---|---|
| GATE-01 Governance | Commercial rules reconciled across active outputs, ledger, and docs | Commercial and ledger suites; this matrix | Candidate implementation is present on PR #29; not independently reviewed or accepted on `main` |
| GATE-02 Security | Server-derived actor and tenant authority, PostgreSQL RLS, original-byte integrity, authenticated internal routes | Database/security suites; integrated route and capture evidence service tests | Candidate code and CI cover configured actor roles, owner consent events, keyed VIN references, original-byte registration, server-side manifest sealing, and independent reviewer authorization; persistent integrated deployment remains unverified |
| GATE-03 Product | Operator capture and reviewer workbench demonstrated end-to-end on qualified iPad hardware | Slice 2 controller tests; integrated web-shell/API tests; verified-original review tests | Not passed; a connected integrated shell now supports case creation/resume, separate owner consent, canonical-slot original uploads, advisory operator attestations, manifest sealing, verified reviewer retrieval, and limited human-review outcomes. Qualified iPad/browser/device demonstration and field validation have not been performed. |
| GATE-04 Data | Persistent database/object storage, backup restore, consent withdrawal deletion | RLS event journal and POSIX original-byte store; capture evidence service tests | Partial; withdrawal now deletes registered original objects and blocks subsequent use. Storage encryption and backup/restore remain unverified |
| GATE-05 Deployment | One integrated runtime deployed and verified in persistent staging | `app.main:create_app(runtime_mode="integrated")` composes intake and internal analytical routes; Railway CI verifies the separate restricted runtime | Not passed; integrated mode remains opt-in, and the latest Railway workflow skipped deployment. No persistent integrated staging deployment is evidenced |
| GATE-06 Operations | Pilot owner, onboarding, grading, and reconciliation procedures | No field evidence in this branch | Not passed |
| GATE-07 Legal & partner | Counsel review and signed partner/data agreements | `docs/LEGAL_REVIEW.md` | Not passed |
| GATE-08 Measurement | Scene-time, retakes, and model performance calibrated against shop ground truth | Synthetic benchmarks only | Not passed; no field validation claimed |
| GATE-09 Commercial | Integer-cents accounting, payment sandbox/live settlement, and authorized carrier delivery | Persistent tenant-scoped integer ledger, reversal, idempotency and audit-export integration tests; deterministic dossier tests | Partially implemented; payment settlement and external distribution are not enabled |

## Artifact and model gates

| Requirement | Evidence | Status |
|---|---|---|
| Local model weight digest provenance and benchmark-gated adoption | `backend/app/vision/adapters.py`; `tests/dispatch/test_inhouse_vision_adapter.py` | Adapter and synthetic gate tests implemented; production model weights are not present and accuracy is not validated |
| Recipient-scoped deterministic dossier generation and withdrawal revocation | `backend/app/reports/forensic_pdf.py`; `tests/dispatch/test_four_tier_dossiers.py` | Implemented locally; distribution remains disabled pending legal, partner, security, and consent review |
| Complete commercial lifecycle demonstration | `app/commercial_ecosystem_demo.py` | Added; execution depends on the POSIX storage runtime used by the Linux CI container |

## Release discipline

The current Railway configuration is a restricted synthetic containment service. It is not the integrated product. Live dispatch, payments, partner/carrier delivery, production publication, and real participant data remain disabled until their legal, security, partner, operational, and deployment gates have actual evidence.


