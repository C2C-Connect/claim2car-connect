# Health-only FastAPI foundation

## Run locally

Install `python -m pip install -r requirements-api.txt`, provide APP_DATABASE_URL
securely for an approved restricted application login, then run:

```sh
python -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
```

No database URL fallback, migrations, seeds, cloud provisioning or business writes
occur at application startup. Missing configuration still allows liveness but
returns HTTP503 for readiness. The default bind in this command is loopback only.

## Endpoint contract

- GET /health/live: HTTP200, `{"status":"alive"}`; never opens a database connection.
- GET /health/ready: HTTP200 only when the configured login is non-superuser,
  non-BYPASSRLS, a member of faos_app, the binding registry exists, tenant_id() is
  security-definer-owned by faos_writer, and the ten expected tables have RLS and
  FORCE RLS. The query reads catalogs only; it does not read tenant data or the
  private authority registry. Otherwise HTTP503; exception details/DSNs are not
  returned. Both outcomes carry `scope: infrastructure-only` and no-store headers.
- No packet intake, authentication, dealer routing, payment or other business
  mutation endpoint is exposed. OpenAPI/docs routes are disabled in this increment.

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
