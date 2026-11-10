# Route-to-Control Matrix — Claim2Car Connect (M1)

**Version:** m1-v2 (Slice 4 evidence-readiness route, 2026-11-10)
**Plan reference:** v1.3 workstream D, phase 3; technical verification matrix §9
**Enforcement:** `tests/security/test_route_control_matrix.py` (executable)
**Change control:** any route addition or control change requires a matrix update,
test update, and security review. Version bump required.

## Control classes

| Class | Meaning |
|---|---|
| PUBLIC_HEALTH | No auth; returns liveness only; no data |
| READINESS_PROBE | No auth; reflects real dependency/authority state; no business data |
| AUTHENTICATED_TENANT | Bearer service credential → server-derived actor/tenant via DB role binding; tenant scoping enforced server-side |
| INTERNAL_DISABLED | Route exists but the operation is disabled pending integration; client input cannot enable it |
| INTERNAL_SERVICE_AUTH | Internal business operation requires configured C2C_INTERNAL_SERVICE_TOKEN Bearer credential; service identity only, not end-user/tenant authorization |
| PUBLIC_VERIFY | Intentionally public integrity verification; exposes documented verification response and requires abuse-control review before external publication |
| INTERNAL_ANALYSIS | Internal analysis surface only; CORS allowlist is not authentication or network access control |

## M1 public surface — foundation app (`app/main.py`)

| Route | Method | Control | Negative test evidence |
|---|---|---|---|
| /health/live | GET | PUBLIC_HEALTH | tests/api/test_health.py |
| /health/ready | GET | READINESS_PROBE (real DB authority probe; 503 when not ready) | tests/api/test_health.py; CI api-health workflow |

Inventory enforcement: the foundation app exposes ONLY these two routes
(`test_foundation_app_exposes_only_health_routes`). No business API is public.

## Capture API (`app/capture_api.py`)

| Route | Method | Control | Negative test evidence |
|---|---|---|---|
| /v1/capture-sessions | POST | AUTHENTICATED_TENANT | 401: missing/unknown/expired/disabled token (test_capture_api.py); client cannot choose tenant/actor/login (body-forbidden test) |
| /v1/capture-sessions/{session_id} | GET | AUTHENTICATED_TENANT | 401 set; query/header tenant override ignored (server-derived only); 403 CAPTURE_AUTHORITY_DENIED on cross-tenant access; 404 unknown session |
| /v1/capture-sessions/{session_id}/evidence-readiness | GET | AUTHENTICATED_TENANT | Creator operator/supervisor only; reports current owner-consent and vehicle-reference gates without returning evidence or owner identity |

## Intake API (`app/intake_api.py`)

| Route | Method | Control | Negative test evidence |
|---|---|---|---|
| /v1/capture-sessions/{session_id}/draft | GET | AUTHENTICATED_TENANT | 401 set; 403 INTAKE_ACCESS_DENIED (wrong tenant / DraftAccessDenied) |
| /v1/capture-sessions/{session_id}/draft | PUT | AUTHENTICATED_TENANT | 401 set; 409 revision conflict; 422 invalid payload (no echo of private input) |

## Internal analysis surface (`backend/app/main.py`) — NOT public M1

| Route | Method | Control | Notes |
|---|---|---|---|
| /health/live, /health/ready | GET | PUBLIC_HEALTH / READINESS | Separate app instance |
| /api/v1/analysis/health | GET | INTERNAL_ANALYSIS | Health metadata only |
| /api/v1/analysis/physics, /run | POST | INTERNAL_SERVICE_AUTH | Fail-closed service Bearer token; no end-user/tenant authorization |
| /api/v1/triage/health | GET | INTERNAL_ANALYSIS | Health metadata only |
| /api/v1/triage/adjudicate | POST | INTERNAL_SERVICE_AUTH | Fail-closed service Bearer token; no end-user/tenant authorization |
| /api/v1/dispatch/health | GET | INTERNAL_ANALYSIS | Advertises disabled state honestly |
| /api/v1/dispatch/build | POST | INTERNAL_DISABLED | Raises regardless of client-supplied provenance (tests/api/test_dispatch_build_containment.py) |
| /api/v1/dispatch/redact | POST | INTERNAL_SERVICE_AUTH | Fail-closed service Bearer token; no end-user/tenant authorization |
| /api/v1/verify/ and /api/verify/ | POST | PUBLIC_VERIFY | Public verification semantics; process-local ledger |
| /api/v1/verify/{session_id} | GET | PUBLIC_VERIFY | Public-exhibit lookup; process-local ledger |

CORS: explicit allowlist via `C2C_ANALYSIS_ALLOWED_ORIGINS` only; wildcard-with-
credentials is forbidden and enforced by test. Internal analysis physics/run,
triage adjudication, and dispatch redaction routes now require the fail-closed
`C2C_INTERNAL_SERVICE_TOKEN` Bearer dependency; missing/malformed configuration
returns 503 and invalid/missing credentials return 401. This shared service token
is not end-user identity, actor attribution, or tenant authorization. Health
routes and public verification routes remain intentionally unauthenticated.
Business-route isolation between the M1 surface and analysis surface is asserted
by test. Keep the analysis app private until private ingress and tenant-aware
authorization are independently established.

## Database-level enforcement (reference)

RLS with FORCE ROW LEVEL SECURITY on all 10 tenant tables, role-based logins
(`faos_app` non-superuser, no BYPASSRLS), security-definer `faos.tenant_id()` —
proven by tests/database/* (tenant authority integration, tenant context
regression, access hardening) and the authority-cutover CI workflow.

## Client trust boundary (plan v1.3 §9)

Client-supplied tenant, role, actor, reviewer decision, seal state, acceptance,
payment state, or dispatch authority can never override server authority —
enforced by the AUTHENTICATED_TENANT dependency design (identity derived from
the token digest server-side; body/query/header identity fields are ignored)
and the state machine's server-owned transitions (contracts/m1_state_machine.py).
