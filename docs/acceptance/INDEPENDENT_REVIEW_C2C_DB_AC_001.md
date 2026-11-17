# C2C-DB-AC-001 v1.0 — Independent Review & Owner Adoption Package

**Repository:** `C2C-Connect/claim2car-connect`  
**Review target:** `docs/acceptance/database-contract.md` (Document ID `C2C-DB-AC-001`, v1.0) and the PR #47 database implementation delta  
**Main baseline:** `f35b50bf4fb222de2ac4eb3eced466371a8be293`  
**PR #47 candidate:** `776265a555df9f844837ba788ca4b456a9491319`  
**Tested synthetic merge checkout:** `ccca9dd8375119715fdebddf70d9294e28b1c3ea`  
**Contract blob SHA:** `2619ad3ba3634200aa0a839f6ace9f3e15746190`  
**Package status:** OWNER ADOPTED — INDEPENDENT REVIEW EXPLICITLY WAIVED FOR V1.0 ADOPTION; REVIEW NOT PERFORMED  
**Contract status:** OWNER_ADOPTED_PENDING_POST-ADOPTION_GATE_RUN  
**Formal gate awards:** 0/14 — post-adoption acceptance run required  
**Overall database acceptance:** NOT ACCEPTED

> This package organizes contract, implementation, and verification evidence for an independent reviewer. It is not an independent review, owner approval, database certification, production-readiness statement, or authorization to use real participant data. Candidate and tested-checkout SHAs are distinct and must remain separately identified.

## 1. Decision requested

An independent database/security review remains recommended as a follow-on assurance activity. The Product Owner explicitly waived independent review as a prerequisite to v1.0 adoption on 2026-11-17. No independent review has been performed or is claimed in this package. Any later reviewer must assess the normative contract and implementation delta, including migration 0019, and record findings against exact SHAs.

Record one of:
- **APPROVE** — contract and supporting evidence are adequate for owner adoption, subject to explicitly listed non-blocking observations.
- **APPROVE WITH REQUIRED CHANGES** — identify precise amendments or evidence gaps that must be closed before adoption.
- **REJECT / NOT READY** — identify material defects, unsupported criteria, or insufficient evidence.

The reviewer must not infer production readiness, legal admissibility, physical-device acceptance, customer acceptance, or full product completion from this database-only review.

## 2. Materials in scope

1. `docs/acceptance/database-contract.md` — normative C2C-DB-AC-001 v1.0 (blob SHA above).
2. `tests/database/verify_gates.py` — executable DB-01 through DB-14 verifiers and mapped test evidence.
3. `scripts/database_authority_diagnostics.py` — post-cutover database diagnostics and tenant-isolation evidence.
4. `scripts/run_counted_tests.py` and `scripts/run_guarded_database_acceptance.sh` — counted-test and fail-closed test execution.
5. `.github/workflows/database-acceptance-diagnostics.yml` — CI orchestration and evidence publication.
6. `docs/acceptance/ACCEPTANCE_MATRIX.md` — release/acceptance status and limitations.
7. PR #47 migration `authority_migrations/0019_manifest_root_protocol_binding.sql`, plus its integration regression in `tests/database/test_migration_controls_integration.py`.
8. PR #47's complete diff against the stated main baseline, including changes to verifier inventory, diagnostics, protocol documentation, and operator workbench copy.

## 3. Current candidate and verification evidence

The following evidence is tied to PR #47 candidate `776265a555df9f844837ba788ca4b456a9491319` and GitHub-generated synthetic merge checkout `ccca9dd8375119715fdebddf70d9294e28b1c3ea`, with main baseline `f35b50bf4fb222de2ac4eb3eced466371a8be293`.

- Latest full repository suite: **780 passed, 201 subtests passed, 23 warnings** — [run 44175861637](https://github.com/C2C-Connect/claim2car-connect/actions/runs/44175861637); [evidence artifact](https://github.com/C2C-Connect/claim2car-connect/actions/runs/44175861637/artifacts/14369048095).
- Latest counted PostgreSQL suite: **319/319 passed**, zero failures, errors, skips, expected failures, or unexpected successes — [run 44175861670](https://github.com/C2C-Connect/claim2car-connect/actions/runs/44175861670); [evidence artifact](https://github.com/C2C-Connect/claim2car-connect/actions/runs/44175861670/artifacts/14370181890).
- Latest authority diagnostics: **14/14 technical criteria PASS**, 19-migration inventory (0001–0019), 14 tenant-scoped tables and 280 adversarial tenant-isolation assertions — [run 44175861783](https://github.com/C2C-Connect/claim2car-connect/actions/runs/44175861783); [evidence artifact](https://github.com/C2C-Connect/claim2car-connect/actions/runs/44175861783/artifacts/14369971928).
- The specific regression `test_manifest_root_protocol_binding_accepts_16_and_rejects_mismatch` passed. It verifies successful 16-v1 root registration, rejection of a 12-v1 registration against a 16-v1 session, direct mismatched insert rejection as `faos_writer` under valid tenant context, and absence of an extra persisted root.
- The counted database evidence records PostgreSQL 16.4 in an isolated synthetic database, with separate administrative, application, and migrator identities.
- Current candidate CI listing showed **13/13 distinct workflow types successful**; duplicate reruns are not counted as additional workflow types. The restricted Railway verification is not an integrated deployment.

**Formal accounting:** The diagnostic report records `criteria_passes: 14`, `gate_passes_awarded: 0`, and `overall_acceptance: NOT ACCEPTED`. Each criterion is technically PASS in the proposed-contract state, but no formal DB-01–DB-14 gate is awarded until independent review and explicit owner adoption. Do not describe this as 14 formally awarded gates.

Relevant merged work:
- PR #43 — executable DB-01 through DB-14 verifiers.
- PR #44 — structured evidence JSON serialization fix.
- PR #45 — acceptance matrix refresh.
- PR #46 — independent review package preparation.
- PR #47 — migration 0019 candidate; not merged and still Draft pending independent review.

## 4. Independent reviewer checklist

For each item, record **Pass / Concern / Fail / Not reviewed**, a concise rationale, and exact file/test/evidence references.

### A. Contract quality and scope
- Are the 14 gate requirements unambiguous, testable, and proportionate to the database foundation milestone?
- Are gate status definitions and global acceptance rules consistent?
- Are dependencies between gates explicit?
- Are exclusions (production readiness, field/device acceptance, legal admissibility, full product acceptance) sufficiently clear?

### B. Environment and migrations (DB-01–02)
- Is the synthetic environment reproducible and demonstrably isolated from production credentials/data?
- Does migration verification prove clean initialization, supported upgrade, deterministic order, failure handling, and rerun behavior?
- Is the complete 19-migration inventory correctly ordered, checksum-bound, and tied to both candidate and tested-checkout SHAs?
- Does migration 0019 correctly preserve historical 12-v1 roots while supporting 16-v1 and rejecting mismatched session/root protocol versions?

### C. Privilege and tenant authority (DB-03–05)
- Are application, migrator, fixture/writer, and administrative identities appropriately separated?
- Are RLS policies enabled and forced on every in-scope tenant table?
- Do adversarial tests cover read/write/delete, spoofed/missing/malformed tenant context, transaction rollback, and pooled-connection reuse?
- Does the `faos_app` denial test remain intact, and does the complementary trigger-path test exercise the actual `faos_writer` table-writer role with valid tenant context?
- Are any privileged diagnostic fixtures capable of masking application-role weaknesses?

### D. Event and evidence integrity (DB-06–10)
- Are event schema/versioning, canonical serialization, ordering, and SQL/Python parity correctly specified?
- Are idempotency and concurrent-write semantics adequately proven?
- Are immutability controls effective against the stated threat model?
- Are manifest canonicalization, digest/root registration, tenant binding, duplicate/conflict behavior, and tamper detection sufficiently tested?
- Does migration 0019 bind the root to the immutable session protocol rather than trusting only the seal payload or caller-supplied version?
- Does the documentation distinguish integrity/hash evidence from truth, provenance, trusted notarization, or legal admissibility?

### E. Completion, revocation, and recovery (DB-11–13)
- Are completion receipts protected and bound to expected evidence roots and tenant?
- Are revocation and invalidation outcomes fail-closed for downstream reads and operations?
- Does restart/replay evidence prove recovery from persisted state rather than process-local memory?
- Are failure injection and invalid-history cases adequate?

### F. Runner, reporting, and release semantics (DB-14)
- Does the counted-test runner account for every discovered test and reject failures, errors, skips, expected failures, and unexpected successes?
- Are per-gate selectors complete and resistant to accidental under-selection?
- Does the diagnostic report bind candidate SHA, tested checkout SHA, migration inventory, environment, and test evidence?
- Can missing or stale evidence be mistaken for a pass?
- Is the transition from proposed contract to adopted contract and then formal gate awards explicit and safe?

## 5. Known boundaries and non-claims

The current evidence is synthetic CI evidence, not production evidence. The following remain outside this contract's acceptance and/or unverified:

- No production database migration or production data exercise is evidenced by the synthetic test run.
- Production backup/restore, storage encryption, disaster recovery, and operational recovery are not established by the 319-test result alone.
- No persistent integrated staging database, integrated application service, or persistent evidence volume has been deployed and verified.
- Owner login/invitation and identity proofing remain incomplete; provisioned actor credentials are not end-user identity proofing.
- Qualified iPad/Safari and roadside field validation, legal/partner agreements, measurement calibration, and supervised pilot remain separate product gates.
- Live Square settlement, external carrier/partner delivery, live dispatch, production publication, and real participant data remain disabled pending separate authorization and controls.
- A passing digest/hash check establishes consistency with recorded bytes; it does not establish the truth of an incident or the provenance of a capture.

The reviewer should add any further limitations discovered during review.

## 6. Required reviewer record

**Reviewer name:** [to be completed]  
**Organization / affiliation:** [to be completed]  
**Relevant database/security experience:** [to be completed]  
**Independence / conflict-of-interest statement:** [to be completed]  
**Review date:** [to be completed]  
**Reviewed main baseline SHA:** `f35b50bf4fb222de2ac4eb3eced466371a8be293`  
**Reviewed PR candidate SHA:** `776265a555df9f844837ba788ca4b456a9491319`  
**Reviewed synthetic merge checkout SHA:** `ccca9dd8375119715fdebddf70d9294e28b1c3ea`  
**Reviewed contract blob SHA:** `2619ad3ba3634200aa0a839f6ace9f3e15746190`  
**Decision:** [APPROVE / APPROVE WITH REQUIRED CHANGES / REJECT / NOT READY]  
**Findings:** [numbered findings with severity and evidence references]  
**Required remediation:** [specific file/test/contract changes, or none]  
**Reviewer attestation:** [reviewer-authored statement]

A review is not complete until reviewer identity, independence statement, reviewed SHAs, decision, findings, and attestation are recorded in a durable repository artifact or attributable signed review record.

## 7. Owner adoption record — RECORDED

**Owner decision:** ADOPT C2C-DB-AC-001 v1.0  
**Owner:** Claim2Car hub account owner (owner identity/authority expressly attested in the ChatGPT session; this repository entry is recorded at the owner's direction)  
**Adopted contract version:** C2C-DB-AC-001 v1.0  
**Adoption date:** 2026-11-17  
**Owner rationale / conditions:** The owner expressly authorized acceptance and directed the implementation agent to proceed with full autonomy. The owner explicitly waived independent review as a prerequisite to v1.0 adoption. This waiver is not represented as an independent review, reviewer approval, or reviewer attestation. Technical gate awards remain contingent on a new complete post-adoption DB-01–DB-14 run against the exact merged source revision. Production readiness, real-participant authorization, legal admissibility, payment activation, dispatch, and deployment are not granted by this adoption.

**Independent-review disposition:** WAIVED BY OWNER FOR V1.0 ADOPTION; NOT PERFORMED. The reviewer fields in Section 6 intentionally remain uncompleted. A later independent review remains recommended and must be recorded honestly if undertaken.

The owner adoption is effective when this contract revision is merged to `main`. A new complete, traceable DB-01–DB-14 acceptance run must then execute against the adopted contract and exact merged source SHA. Only that subsequent run may award formal gate statuses. Proposed-state results must not be retroactively converted into formal awards.

## 8. Closure criteria for Issue #39

Issue #39 may be closed after the following are evidenced:

1. Independent review is completed and recorded, OR the Product Owner explicitly waives it for the stated contract version and the waiver is recorded without being misrepresented as a review.
2. Any findings from a completed review are resolved or explicitly accepted by the owner.
3. Product Owner adoption is recorded in the repository.
4. The adopted contract and associated implementation are merged to `main`.
5. A new complete DB-01–DB-14 run is executed against the adopted contract and exact source SHA.
6. Formal gate results and overall acceptance are reported exactly as produced; no production-readiness claims are inferred.

For v1.0, criterion 1 is satisfied by the owner's explicit waiver recorded in Section 7; independent review remains NOT PERFORMED. Until the post-adoption run passes and is recorded, Issue #39 remains open, formal gate awards remain 0/14, and overall acceptance remains NOT ACCEPTED.
