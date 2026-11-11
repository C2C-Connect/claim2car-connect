# FastAPI foundation and integrated runtime

## Run locally

Install `python -m pip install -r requirements-api.txt`, provide APP_DATABASE_URL
securely for an approved restricted application login, then run:

```sh
python -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
```

The default runtime mode is `restricted_staging`: no database URL fallback,
migrations, seeds, cloud provisioning or business writes occur at startup.
Missing configuration still allows liveness but returns HTTP503 for readiness.
The default bind in this command is loopback only.

The integrated runtime is an explicit opt-in for a separately provisioned
environment. It requires `C2C_RUNTIME_MODE=integrated`, a private
`C2C_CAPTURE_CONFIG_FILE`, `C2C_ARTIFACT_STORAGE_ROOT` on administrator-owned
persistent POSIX storage, and a random ASCII `C2C_VIN_HMAC_PEPPER` with at least
32 characters. The capture config contains the health DSN, one least-privilege
tenant login DSN per credential, and server-owned actor/tenant/role bindings.
Owner roles must be explicitly configured; omitted roles default to operator.
Never place these values in source, image layers, or logs.

## Endpoint contract

- GET /health/live: HTTP200, `{"status":"alive"}`; never opens a database connection.
- GET /health/ready: HTTP200 only when the configured login is non-superuser,
  non-BYPASSRLS, a member of faos_app, the binding registry exists, tenant_id() is
  security-definer-owned by faos_writer, and all twelve required tenant tables—including claim cases and separately consented incident-intake records—have RLS and
  FORCE RLS. The query reads catalogs only; it does not read tenant data or the
  private authority registry. Otherwise HTTP503; exception details/DSNs are not
  returned. Both outcomes carry `scope: infrastructure-only` and no-store headers.
- `restricted_staging` exposes only the liveness/readiness routes documented below.
- `integrated` mounts tenant-authenticated intake at `/api/v1/*` and fail-closed,
  service-authenticated analytical routes at `/internal/v1/{analysis,triage,dispatch}/*`.
- Consent, HMAC VIN references, and immutable original-byte uploads require
  the integrated mode and provisioned persistent storage/pepper settings.
- GET /api/v1/capture-sessions/{session_id}/evidence-readiness is authenticated and creator-scoped; it reports whether active owner consent and a valid vehicle reference permit evidence capture, without returning evidence bytes or owner identity.
- The integrated browser shell uses an IndexedDB original-byte queue with tenant/actor/session scoping, FIFO retry, stable idempotency identifiers, and local purge after confirmed consent withdrawal. This is a controlled-test recovery aid, not encrypted or field-qualified storage; see the acceptance matrix.
- Integrated capture records advisory quality for all twelve frozen capture
  slots, seals only after server-side hash verification, and exposes a
  tenant-scoped reviewer queue and byte-preserving review-artifact endpoint. A separately configured reviewer or supervisor
  records the final human decision; failed quality advisories do not block
  roadside progression.
- OpenAPI/docs routes remain disabled. Payments and external delivery are not
  part of this runtime.

Readiness is a bounded infrastructure prerequisite check, not migration checksum
attestation, tenant enrollment/authorization, end-to-end business readiness or
formal acceptance. An unbound faos_app login may satisfy infrastructure readiness
while correctly having no authority to read or write any tenant's data. The full
migration ledger and isolation tests remain separate required evidence.

Each readiness request opens and closes a connection with a three-second libpq
connection timeout, two-second SQL statement timeout and read-only default
transactions. These settings are not a hard end-to-end latency SLA. The initial
implementation has no shared pool and is intended for controlled/internal health
probing, not unrestricted high-rate public exposure. TLS/network policy and a
fully locked dependency set remain deployment-review work.

## Verification and boundaries

The api-health job runs counted ASGI unit tests with mocked database I/O, then
starts real loopback Uvicorn processes and performs HTTP probes against an
unmigrated database, legacy-only schema, full-authority schema, and a stopped
synthetic database. Each stage starts a fresh API process; this is not a claim of
same-process failover or crash recovery. A readiness503 is the expected PASS in
negative stages; liveness remains200. Tests also assert /packets POST is404.

Candidate manifests guard the new files. PR verification remains read-only;
separate trusted branch/manual publication writes only allowlisted JSON reports.
API unit counts, live stage assertions,195 existing component methods and200
isolation cells are different evidence categories and must not be added together
as equivalent tests. Execution results are pending until the new CI run is reviewed.
AWS is explicitly deferred. React/Capacitor, authenticated packet persistence and
multi-dealer business routing remain separate implementation increments.
