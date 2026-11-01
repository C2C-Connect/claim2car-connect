# Claim2Car Connect — Database Acceptance Contract

**Document ID:** C2C-DB-AC-001
**Version:** 1.0 — PROPOSED, pending owner adoption
**Scope:** Database foundation, tenant isolation, durable event journal, evidence integrity, and completion controls
**Acceptance principle:** No gate passes without reproducible evidence tied to a specific source revision and test environment.

> Status at adoption: this contract becomes authoritative only when the owner approves and merges it.
> Until then, no gate in this document is awarded any status. Passing these gates does not establish
> production readiness, validate real-world accident measurements, certify legal admissibility, or
> demonstrate the complete end-to-end commercial product.

**Provenance:** Adapted from the owner-supplied proposal "Database Acceptance Contract — 14-Gate
Baseline" (C2C-DB-AC-001, drafted October 2026). No adopted copy of that proposal was located in
the repository materials reviewed; this document is the proposed adoption of it.

## 1. Purpose

This contract defines the minimum acceptance requirements for the Claim2Car Connect database
foundation. It governs whether the database layer is sufficiently correct, isolated, durable, and
verifiable to support the next controlled vertical slice. It is the database layer of a two-layer
acceptance structure; the product-lifecycle gates are defined separately in
`docs/acceptance/product-contract.md` (PRODUCT-01–14). The two frameworks are layered, not merged.

## 2. Gate status definitions

* **NOT IMPLEMENTED** — Required capability or verification does not exist.
* **IMPLEMENTED — UNVERIFIED** — Code exists, but acceptance evidence is insufficient.
* **FAIL** — A required assertion failed or a prohibited behavior was demonstrated.
* **PASS** — All specified assertions passed and the evidence was recorded.
* **BLOCKED** — Verification could not run reliably because of an identified environmental or dependency issue.

A successful CI workflow is not, by itself, proof that all gates pass. A skipped test, placeholder
test, or unexecuted verification cannot count as a pass.

## 3. The 14 database gates

### DB-01 — Reproducible environment and configuration

**Requirement:** The acceptance environment is reproducible, explicitly configured, and isolated from production data and credentials.

**Verification:** Start the database from a clean, documented environment. Verify required extensions, roles, schemas, and dependencies. Verify required configuration is supplied explicitly. Confirm tests cannot silently connect to an unintended database.

**PASS:** A clean environment can be initialized and identified deterministically; configuration errors fail clearly; no production credentials or data are required.

**Evidence:** Environment manifest, sanitized configuration, startup logs, clean-run results.

### DB-02 — Migration integrity and schema versioning

**Requirement:** Database migrations produce the intended schema in a deterministic, controlled order.

**Verification:** Apply every migration to an empty database. Verify expected tables, indexes, constraints, functions, triggers, policies, and extensions. Verify migration version tracking. Test failure during migration and document recovery behavior. Verify the documented upgrade path from the supported prior schema.

**PASS:** All required migrations apply successfully in order; schema assertions match the contract; migration failures do not leave an undocumented, falsely successful state.

**Evidence:** Migration logs, schema inspection, version records, migration-failure tests.

### DB-03 — Restricted application privileges

**Requirement:** The application role has only the privileges required for its approved operations.

**Verification:** Inspect role attributes and effective privileges. Attempt prohibited schema changes, privilege escalation, and direct writes to protected tables. Verify the application role is not a superuser and cannot bypass row-level security.

**PASS:** Every prohibited operation is denied, and the application role has no unintended elevated privilege.

**Evidence:** Role inspection, effective privilege matrix, positive and negative authorization tests.

### DB-04 — Tenant isolation and row-level security

**Requirement:** A tenant can access only data authorized for that tenant, including under direct database queries through the application role.

**Verification:** Create at least two synthetic tenants with distinct records. Test reads, inserts, updates, and deletes across tenant boundaries. Verify row-level security is enabled and forced on every in-scope tenant table. Test missing, invalid, and mismatched tenant context. Verify tenant identifiers cannot be spoofed to obtain unauthorized access.

**PASS:** Cross-tenant access is consistently denied across every applicable operation and table; missing or invalid tenant context fails closed.

**Evidence:** Per-table policy inventory, adversarial tenant-isolation tests, database query results.

### DB-05 — Tenant-context lifecycle

**Requirement:** Tenant context is scoped correctly and cannot leak between transactions or pooled connections.

**Verification:** Test context establishment and validation. Commit and roll back transactions, then inspect context. Reuse connections across different tenants. Test exceptions and aborted transactions. Verify context is reset before a connection is reused.

**PASS:** No transaction, error path, or connection reuse can expose the preceding tenant's context to a subsequent operation.

**Evidence:** Transaction-lifecycle tests, pooled-connection tests, rollback traces.

### DB-06 — Event schema and domain-contract validation

**Requirement:** Persisted domain events conform to a documented, versioned event contract.

**Verification:** Validate required identifiers, event kind, sequence, timestamp, schema version, and payload. Test malformed values, invalid types, missing fields, and unsupported versions. Verify canonical serialization is deterministic where required. Verify invalid events are rejected before they can corrupt durable state.

**PASS:** Valid events are accepted; invalid or unsupported events are rejected deterministically; stored events remain interpretable under the documented schema-version policy.

**Evidence:** Contract specification, schema-validation tests, representative valid and invalid event fixtures.

### DB-07 — Durable event append and idempotency

**Requirement:** Event append operations persist reliably and handle repeated requests according to an explicit idempotency contract.

**Verification:** Append valid events and read them back from the database. Repeat an identical request using the same idempotency key. Reuse a key with conflicting event content. Simulate a failed or interrupted transaction. Verify the defined relationship between event identity, idempotency key, and payload.

**PASS:** Retries cannot create unintended duplicate effects; conflicting reuse is rejected; a reported successful append is durably readable after commit.

**Evidence:** Database integration tests, duplicate-request tests, conflict tests, commit/rollback results.

### DB-08 — Sequence integrity and concurrent writes

**Requirement:** Concurrent event writers cannot silently create conflicting sequence histories or violate the declared ordering rules.

**Verification:** Submit competing writes for the same session or event stream. Test duplicate sequence numbers and gaps where gaps are prohibited. Exercise transaction races and retry behavior. Verify database constraints and locking, rather than relying solely on application-side checks.

**PASS:** Every accepted history satisfies the sequence contract; competing writes resolve deterministically through success, safe retry, or explicit rejection.

**Evidence:** Repeated concurrency tests, resulting event histories, transaction outcomes.

### DB-09 — Event immutability and history integrity

**Requirement:** Accepted event history cannot be silently rewritten or deleted through ordinary application operations.

**Verification:** Attempt direct update and delete operations. Test unauthorized event modification and sequence alteration. Verify any permitted correction or supersession process preserves the original record and records the new action. Verify integrity checks detect unauthorized historical changes within the defined threat model.

**PASS:** Ordinary application access cannot silently rewrite accepted history; permitted corrections are traceable; integrity violations are detectable.

**Evidence:** Privilege tests, mutation-attempt tests, history-integrity verification results.

### DB-10 — Evidence-manifest integrity and root registration

**Requirement:** Evidence manifests and their registered integrity roots are bound to the correct tenant and underlying evidence, according to a documented canonicalization and hashing contract.

**Verification:** Build a synthetic evidence bundle and calculate its expected digest. Verify stable serialization and digest reproduction. Modify evidence, metadata, ordering, or relevant manifest fields. Test duplicate registration, conflicting registration, and cross-tenant attempts. Verify the system distinguishes a valid digest from proof of the truth of the underlying evidence.

**PASS:** Valid evidence produces reproducible integrity results; relevant unauthorized changes are detected; roots cannot be improperly substituted, duplicated, or registered across tenant boundaries.

**Evidence:** Synthetic bundle fixtures, expected digests, tamper tests, root-registration records.

### DB-11 — Completion receipts and protected completion state

**Requirement:** Completion records are generated and protected according to the declared workflow and authorization rules.

**Verification:** Exercise valid and invalid completion attempts. Attempt direct application-role inserts, updates, deletes, and truncation of protected completion tables. Test duplicate completion requests and conflicting requests. Verify receipt references, tenant binding, and evidence-root relationships.

**PASS:** Completion state can be created only through authorized operations; duplicate or conflicting attempts behave deterministically; protected records cannot be directly altered by the ordinary application role.

**Evidence:** Completion integration tests, privilege-denial results, receipt-to-evidence consistency checks.

### DB-12 — Revocation, tampering, and invalidation behavior

**Requirement:** The system responds deterministically when an evidence reference, manifest, completion receipt, or related authorization is revoked or found invalid.

**Verification:** Test revoked and invalidated records. Test altered or missing evidence references. Test stale, conflicting, and inconsistent completion state. Verify downstream reads and decisions cannot silently treat invalidated evidence as valid.

**PASS:** Every defined invalidation condition produces the documented result, and affected records or downstream operations cannot bypass the required checks.

**Evidence:** Revocation scenarios, tamper fixtures, downstream validation results.

### DB-13 — Restart, recovery, and replay

**Requirement:** Durable state survives process restart and can be reconstructed or verified from persisted records without relying on process-local memory.

**Verification:** Write a synthetic event history and evidence/completion records. Stop and restart the application process. Reconnect to the database and retrieve the same committed state. Replay events under the documented replay semantics. Verify deterministic results and behavior for invalid histories. Distinguish successful replay from proof that every possible business-state transition is valid.

**PASS:** Committed state remains recoverable; replay results satisfy the declared invariants; process-local state is not required to reconstruct accepted history.

**Evidence:** Before/after snapshots, restart logs, replay output, consistency assertions.

### DB-14 — Failure handling, end-to-end acceptance, and evidence reporting

**Requirement:** The acceptance suite proves the preceding gates, reports failures accurately, and produces a reproducible acceptance record.

**Verification:** Run all 14 gates against the documented test environment. Include negative tests for each applicable security and integrity boundary. Inject representative database, transaction, and dependency failures. Verify failed, skipped, missing, and blocked tests cannot be counted as passing. Verify the overall result is nonzero when any mandatory gate fails or remains unverified. Record the exact source commit, migration versions, environment, test results, and artifacts.

**PASS:** All mandatory gates pass in the same recorded acceptance run; no gate is skipped or silently downgraded; the run is reproducible and traceable to an exact source revision.

**Evidence:** Machine-readable acceptance report, CI run URL, commit SHA, migration inventory, test results, retained logs.

## 4. Global acceptance rules

1. No inferred passes. Implemented code is not proof of correct behavior.
2. No smoke-test substitution. A preflight may validate selected properties but cannot certify the full contract.
3. No silent skips. Every gate must report PASS, FAIL, BLOCKED, NOT IMPLEMENTED, or IMPLEMENTED — UNVERIFIED.
4. No partial certification. A formal database acceptance milestone requires all 14 gates to pass.
5. Security tests must be adversarial. Verify both allowed behavior and prohibited behavior.
6. Evidence must be reproducible. Every pass is tied to a commit, environment, and recorded result.
7. Scope must be explicit. Synthetic database acceptance does not imply hardware, capture-pipeline, physics, adjudication, production, or customer acceptance.
8. Changes require re-verification. A change to a gate, migration, relevant implementation, or test invalidates affected evidence until rerun.
9. No weakening to obtain a green build. If a gate cannot pass, document the defect or revise the requirement through explicit review; do not relabel an unverified condition as passing.

## 5. Required acceptance report

Each run must produce a report containing: contract version and source commit SHA; database engine/version, enabled extensions, and migration versions; environment identifier and test-run timestamp; for each gate — requirement ID, status, test identifiers, result summary, and evidence links; failures, skipped tests, blocked checks, and known limitations; overall result — ACCEPTED only when all 14 gates pass, otherwise NOT ACCEPTED.

## 6. Definition of database acceptance

The database foundation is accepted only when all 14 gates pass in one traceable, reproducible
acceptance run, with no unresolved mandatory failures or missing evidence. Acceptance authorizes
progression to the next defined engineering milestone. It does not independently certify the complete
Claim2Car product or authorize production deployment.

## 7. Relationship to the existing preflight

`tests/database/verify_gates.py` remains labeled synthetic preflight until it is replaced or
supplemented by the actual gate runner. Its current checks provide useful evidence toward parts of
DB-03–05 and the tenant-context portion of DB-07, but do not establish a full pass for those gates.
