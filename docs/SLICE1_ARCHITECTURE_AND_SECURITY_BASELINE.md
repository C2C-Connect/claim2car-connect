# Slice 1 — Architecture and Security Baseline

**Document ID:** C2C-S1-ARCH-SEC-001  
**Revision:** 1.0  
**Reviewed:** 2026-11-08  
**Branch:** `cto/slice-1-control-reconciliation`  
**Reviewed head:** `5071ff1c931bc8cf8d9533c71677afa8b5b0feee` (the branch head at this review; any subsequent commit requires refreshed evidence).

## 1. Evidence boundary

This document records repository/code inspection and CI evidence at the reviewed head. It does not claim a production deployment, live ingress inspection, independent penetration test, or field validation.

The latest-head workflow query returned 11 completed workflow runs, all with conclusion `success`. The full-suite run (`42524756939`, job `full-suite`) completed dependency installation, disposable PostgreSQL and routing-database setup, migrations, `python -m pytest tests/ -q`, evidence upload, and database teardown successfully. The restricted staging verification run (`42524757025`) passed API/dispatch containment regressions, built and started the restricted image with a dynamic port and restricted filesystem, and verified the exact revision and live HTTP safety boundaries. Its `Deploy verified restricted staging` job was skipped, and its `Report deployment remains disabled` step was skipped by design. The remaining nine successful workflow runs covered controlled demonstration, offline guided capture, controlled-test intake/PostgreSQL, offline VIN lookup, database authority, frontend VIN/decoder/transport, legacy database components, restricted intake container, and FastAPI foundation verification. These are CI workflow results, not 14 independently enumerated check-runs, a production deployment, or independent security/field validation.

## 2. Runtime topology — verified from repository entrypoints

### A. Foundation / M1 runtime

- Entrypoint: `app/main.py`.
- Exposes only `GET /health/live` and `GET /health/ready`.
- Readiness probes configured PostgreSQL role and tenant/RLS authority state; it is not a business API.
- Capture and intake are separate app factories in `app/capture_api.py` and `app/intake_api.py`. They use bearer credentials resolved by `app/identity.py`, with actor/tenant binding resolved server-side.
- Capture/intake apps are not mounted into the health-only foundation `app.main.create_app()` surface.
- Frontend currently consists of capture workflow/VIN modules and tests under `frontend/src/modules/capture`; repository inspection does not establish a complete operator-facing application shell or native camera project.

### B. Analysis / M5 runtime

- Entrypoint: `backend/app/main.py`.
- Independently instantiates and mounts analysis, triage, and dispatch routers.
- It is not composed into `app/main.py`.
- `Dockerfile.railway` copies `app/railway_staging.py` and starts `python -m app.railway_staging`; that staging entrypoint creates the health-only foundation app. The Dockerfile also copies `backend/`, but copying code into an image does not mount its routers or make those routes reachable.
- Therefore, the reviewed deployment configuration does not establish public reachability of the backend analysis routes. Actual provider ingress and running cloud state have not been independently enumerated in this review.

### C. Data / persistence

- Database migrations, tenant authority, capture-session and intake-draft adapters, routing migrations, and tests are present.
- Presence of these components and passing disposable-database CI do not establish a persistent, provisioned pilot database or integrated production evidence object store.
- Root app and backend app currently have separate runtime composition and should not be combined by import convenience alone.

## 3. Backend route inventory and control boundary

A fail-closed service-authentication dependency has now been added to analysis physics/run, triage adjudication, and dispatch redaction. These routes require a configured `C2C_INTERNAL_SERVICE_TOKEN` (43–128 URL-safe characters) and matching Bearer token. If the secret is absent or malformed, the routes return 503; missing/incorrect credentials return 401. Health routes remain public. Dispatch build remains hard-disabled (503). Verification routes remain intentionally public and require a separate public-data/abuse-control decision before external publication.

This is a **service-level authentication boundary**, not end-user identity, actor attribution, or tenant authorization. It is an interim gate for internal service access; before user- or tenant-scoped workflows use these endpoints, server-side actor/tenant authorization and ownership checks are still required.

### Registered routes and controls

The following routes are registered by `backend/app/main.py`. Route registration is not proof of deployment reachability. The security behavior below was exercised by the latest-head CI workflows; no provider ingress or live cloud route enumeration is claimed.

| Router | Route | Method | Current handler control | Finding |
|---|---|---:|---|---|
| Analysis | `/api/v1/analysis/health` | GET | None | Health metadata; no actor context |
| Analysis | `/api/v1/analysis/physics` | POST | Internal service Bearer | Fail-closed shared service token; no end-user tenant context |
| Analysis | `/api/v1/analysis/run` | POST | Internal service Bearer | Fail-closed shared service token; no end-user tenant context |
| Triage | `/api/v1/triage/health` | GET | None | Health metadata; no actor context |
| Triage | `/api/v1/triage/adjudicate` | POST | Internal service Bearer | Fail-closed shared service token; no end-user tenant context |
| Dispatch | `/api/v1/dispatch/health` | GET | None | Reports disabled state |
| Dispatch | `/api/v1/dispatch/build` | POST | Hard-disabled (503) | Does not invoke builder; keep disabled until trusted provenance and authorization are integrated |
| Dispatch | `/api/v1/dispatch/redact` | POST | Internal service Bearer | Fail-closed shared service token; no end-user tenant context |
| Dispatch | `/api/v1/verify/` and `/api/verify/` | POST | None | Public verification semantics; process-local ledger |
| Dispatch | `/api/v1/verify/{session_id}` | GET | None | Reads process-local ledger record |

CORS allowlisting is not authentication, authorization, or network ingress control. Service authentication now gates the four internal business operations above; it does not supply user identity, actor attribution, tenant scope, or row-level ownership. Health endpoints are public metadata. The verification endpoints remain intentionally public and expose process-local ledger lookup/verification semantics.

**Security disposition:** keep the backend private. The new shared service token is a useful fail-closed internal gate, but it is not sufficient for public exposure or tenant-scoped product integration. Before exposure, require private ingress plus server-side authentication, actor attribution, role/tenant authorization, and negative tests. Public verification needs a deliberate data-minimization, rate-limit, enumeration-resistance, and abuse-control review.

## 4. Compensation output audit — current PR scope

- The PR removes `operator_payout_usd` and `owner_payout` from the backend constants/health response, triage response, and forensic dossier output paths.
- Regression coverage checks that generated dossier output does not contain either field and that owner payout constants are absent.
- The unresolved $110 operator amount remains a historical/configuration decision record; no active payout calculation, eligibility, trigger, payment, or settlement has been approved.
- This scoped change does not constitute a repository-wide legal audit of every historical document, external repository, inaccessible repository, or archived branch. Historical references and negative tests must be classified, not indiscriminately erased.

## 5. Architecture decision required before integration

**Current state:** two separately instantiated FastAPI application trees with different responsibilities and deployment status.

**Decision direction:** retain explicit application composition. The foundation/capture runtime remains the M1 product boundary. Analysis/triage services may later be mounted behind an authenticated internal service boundary only after API contracts, identity propagation, tenant scoping, persistence ownership, error handling, observability, and authorization tests are defined. Do not merge entrypoints or expose backend routes merely to make a single server appear complete.

Before integration, record:
- canonical runtime/entrypoint and deployment target;
- service-to-service identity and actor attribution;
- tenant and case/session ownership mapping;
- authoritative persistence and transaction boundaries;
- evidence/object storage ownership and immutable original-byte handling;
- API versioning, idempotency, retries, timeout and failure semantics;
- health/readiness dependency semantics;
- secrets, ingress, network policy, logs, metrics, tracing and incident response;
- route-by-route positive and negative authorization tests.

## 6. Slice 1 status at this revision

| Workstream | Status | Evidence / remaining work |
|---|---|---|
| PR compensation output cleanup | Implemented on branch; CI tested | Latest full-suite CI success; still requires PR review/merge |
| Triage health import regression | Corrected; CI tested | `config.forensic_constants` import restored; full suite passed |
| Runtime topology | Inspected/documented | Actual cloud ingress and deployed service inventory remain unverified |
| Backend route security | Service authentication implemented on internal business operations; CI tested | Latest-head full-suite and restricted-staging verification workflows passed; shared service token is not end-user/tenant authorization; keep backend private and complete ingress/tenant controls before integration |
| App composition | Separate entrypoints verified | Formal architecture decision and integration contract remain |
| Full-suite baseline | Tested | Latest full-suite job success on reviewed head; no independent validation claim |
| Deployment | Not product-deployed | Restricted staging deployment job skipped; health-only staging configuration is not the integrated app |
| Incentive audit | Scoped output cleanup implemented | Complete repository-wide and accessible-branch search/classification remains |
| Evidence branch retention | Not completed | Index/retention policy required before any pruning |

## 7. Prohibited conclusions

Do not infer from this document that the full product is implemented, that the analysis routes have been penetrated or publicly exposed, that the full product is deployed, that model outputs are field-validated, or that hashes establish factual truth or legal admissibility.
