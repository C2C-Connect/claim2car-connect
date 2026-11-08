# Slice 1 — Historical Database Evidence Reconciliation

**Document ID:** C2C-S1-DB-RECON-001  
**Revision:** 1.0 — bounded evidence reconciliation, not database acceptance  
**Reviewed:** 2026-11-08  
**Canonical repository:** `C2C-Connect/claim2car-connect`  
**Current main revision inspected:** `a54ce7a08553ea7a35f70167b868ecb1ff4eb813`  
**CI-tested source/test revision:** `50b8b5fa466643334ee51a424ffacdb929af4c85`

## 1. Historical failure evidence — preserve

Evidence branch: `acceptance-evidence/39315674997`  
Workflow run: `39315674997`  
Job: `118276398032`  
Commit: `560b5873ce58acd0571e7ff58b1cda6c93449b09`  
Time: 2026-10-19 20:00:32Z–20:01:04Z

The preserved `diagnostic-report.json` recorded:
- `G04-DIRECT-SQL-TENANT-SWITCH`: **FAIL** — the tested shared `faos_app` role could set `faos.tenant_id` and expose another tenant's session.
- `G06-DIRECT-SQL-timestamp`: **FAIL** — malformed timestamp accepted by direct SQL despite Python-layer rejection.
- `G06-DIRECT-SQL-canonical_payload`: **FAIL** — whitespace/noncanonical JSON accepted by direct SQL.
- Additional leading-whitespace and nested-whitespace probes also failed.
- `gate_passes_awarded: 0`; `overall_acceptance: NOT ACCEPTED`.

The workflow metadata confirms the direct SQL baseline diagnostics step failed, while evidence preservation and artifact upload succeeded. This is historical failure evidence from the October 19 commit, not proof that the same defects remain in current main. Preserve it; do not rewrite it as a passing run.

## 2. Current main remediation observed

### 2.1 Tenant authority and RLS

Current main includes:
- `authority_migrations/0008_tenant_login_authority.sql` and the private `faos.tenant_login_bindings` registry.
- A role-bound `faos.tenant_id()` function; tenant context is derived from the authenticated database login binding rather than trusting a caller-set custom GUC.
- The registry is not readable or writable by the application role.
- `scripts/database_authority_diagnostics.py` tests direct tenant-context switching, an unbound shared login, private registry access, per-table RLS behavior across ten tenant tables, and binding revocation.
- The authority diagnostics explicitly deny cross-tenant reads/appends and unbound-login access.

### 2.2 Direct-SQL timestamp validation

Migration `0006_event_timestamp_validity.sql` adds the `event_timestamp_input_valid` check using PostgreSQL `pg_input_is_valid(occurred_at, 'timestamp with time zone')`.

This is a bounded remediation. The migration comments explicitly say it does **not** enforce full Python ISO/timezone syntax parity. Do not describe it as complete timestamp-contract equivalence.

### 2.3 Direct-SQL JSON compactness

Migration `0007_event_payload_compactness.sql` adds `faos.compact_json_text` and the `event_payload_compact` check constraint. It removes whitespace outside strings and blocks the historical compactness bypass probes.

This is also bounded. The migration comments explicitly leave key ordering, Unicode escaping, and numeric spelling as separate requirements. Do not describe this as full Python canonical JSON parity or complete event authenticity.

### 2.4 Application-side validation

- `app/domain_events.py` validates timezone-aware timestamps and exact compact, sorted-key JSON serialization before adapter calls.
- `tests/database/test_adapter_validation.py` asserts malformed events are rejected before database calls.
- `tests/database/test_event_contract_regression.py` includes invalid timestamp and noncanonical JSON application checks, plus direct SQL malformed-timestamp constraint checks and exact offset-timestamp readback.

## 3. Current CI evidence

On source/test revision `50b8b5fa466643334ee51a424ffacdb929af4c85`:
- Full test suite workflow `42528468397` completed successfully, including disposable PostgreSQL/routing DB setup, migrations, pytest, evidence upload, and teardown.
- Database authority cutover workflow `42528468497`, job `authority-cutover`, completed successfully. Its steps included isolated database startup, bootstrap through the legacy baseline, pre-cutover tests, full-authority migration/integration tests, primary database upgrade through the normal full-authority entry point, post-cutover authority/validation diagnostics, evidence preservation/upload, and database teardown.
- The separate `publish-evidence` job was skipped; the database test job itself succeeded.

These are synthetic CI database results. They are not live production database evidence, provider deployment, a penetration test, or independent legal/field validation.

## 4. Residual direct-SQL parity gap — static finding, not yet reproduced

The current database constraints close the historical whitespace and malformed-input cases, but they do not enforce the complete Python canonicalization contract:

- `faos.compact_json_text` removes whitespace outside JSON strings; it does not sort object keys, normalize Unicode escaping, or normalize numeric spelling.
- Static code inspection indicates that compact but noncanonical values such as `{"b":1,"a":2}`, literal non-ASCII strings where Python emits escapes, or alternate numeric spellings can satisfy the database compactness check.
- `DomainEvent.validate()` reserializes with sorted keys and Python's JSON formatting, then rejects those same values as `NONCANONICAL_PAYLOAD`.
- Therefore, a caller with direct SQL execution rights may be able to append a compact-but-noncanonical event that later fails application readback/replay. This is a potential event-history availability/integrity defect, inferred from the validator and SQL constraint; it has **not** yet been reproduced against PostgreSQL in the current CI workflow.
- Similarly, PostgreSQL's `timestamp with time zone` input-validity check is not identical to Python's timezone-aware ISO contract. A timestamp without an explicit offset may be accepted by PostgreSQL while rejected by the Python validator; this exact direct-SQL variant is not included in the current authority diagnostics.

The current authority-cutover diagnostics test one malformed timestamp and one whitespace-bearing compact-JSON payload. They do not test key-order, Unicode-escape, numeric-spelling, or timezone-naive direct-SQL variants.

**Required follow-up before database acceptance:** add direct-SQL regression probes for those variants, then either enforce the same canonical contract in PostgreSQL or remove/restrict direct execution authority so untrusted actors cannot bypass the validated adapter. Do not silently normalize existing event history. Treat this as a Slice 3 evidence-integrity and pilot-readiness blocker until tested and resolved.

## 5. Remaining limits and acceptance status

1. The historical October failure record remains preserved as a failed run.
2. The specific tenant-switch, unbound-login, malformed-timestamp, and compact-whitespace bypass cases have current migration/diagnostic coverage and passed the database-authority CI workflow on the reviewed revision.
3. Full timestamp parser parity and full canonical JSON parity remain explicitly incomplete.
4. The current diagnostics are not the complete 14-gate database acceptance contract. `database_acceptance_diagnostics.py` explicitly awards zero gate passes; `database_authority_diagnostics.py` describes itself as not full 14-gate acceptance.
5. Live provider database roles, cloud ingress, production RLS behavior, recovery/restore, and independent security review have not been validated here.

**Status:** The three historical failure classes have bounded current-main remediation and successful synthetic CI verification. Full database acceptance remains **NOT ACCEPTED** until the complete contract and all release gates are independently satisfied.
