# Claim2Car Connect — Release Acceptance Registry and DB Crosswalk

**Document ID:** C2C-REL-AC-001  
**Version:** 1.0 — execution registry  
**Snapshot:** 2026-11-24 23:08 UTC  
**Repository:** `C2C-Connect/claim2car-connect`  
**Base revision for this registry branch:** `55f69790df123a4602196c3c474e143808c4b87e`  
**Authority:** Current owner Developer Execution Directive. This registry does not amend owner decisions or award acceptance.

## 1. Governing rule

The seven release gates (GATE-01 through GATE-07) are a release-level acceptance layer. The fourteen database gates (DB-01 through DB-14) are a database-foundation subset. Passing some or all DB gates does **not** pass a release gate, certify the product, establish deployment, or authorize operational use.

The owner directive's 0/14 status was the baseline before the latest exact-head authority runs. Newer live GitHub artifacts now supersede that dated count: PR #185 run #1196 formally awarded DB-01–DB-14 **14/14 PASS** at candidate SHA `0431dbaf6e1a3bb3348f6d94c094e893543e513c`, and PR #186 run #1200 formally awarded DB-01–DB-14 **14/14 PASS** at candidate SHA `0a4b6087049d2483d8cf4ecc68fa0faaaa3126de`. Both reports state `overall_acceptance: ACCEPTED`, with 408/408 and 409/409 post-cutover database tests respectively and zero skipped tests. The reports' tested checkout SHAs are the expected PR merge refs (`40a9e5298b2e6eb484177319552ff4ccc5042448` for PR #185 and `63ba944f0809212e968199b6afd8ab5dfac086f5` for PR #186), each merging the candidate head into its declared base. **Database acceptance is therefore 14/14 on these exact candidates; overall release acceptance remains NOT ACCEPTED.** This discrepancy from the earlier 0/14 snapshot is recorded, not hidden.

No gate passes on a green workflow badge alone. Each pass requires the named executable checks, a clean current-head run in the required environment, retained evidence, and the required approver. Skipped, cancelled, queued, stale, placeholder, synthetic-only, or environment-mismatched results do not pass a gate.

## 2. Current repository and workflow evidence snapshot

### 2.1 Live refs

| Ref | State | Exact SHA | Use in this registry |
|---|---|---|---|
| `main` | Current base observed | `55f69790df123a4602196c3c474e143808c4b87e` | Registry base; no current-head workflow proof retrieved in this snapshot |
| PR #185, `cto/m1-runtime-manifest-registration` | Open, not merged | `0431dbaf6e1a3bb3348f6d94c094e893543e513c` | M1 manifest-registration candidate |
| PR #186, `feat/evidence-linked-damage-assessment-pdf` | Open, not merged; stacked on PR #185 | `0a4b6087049d2483d8cf4ecc68fa0faaaa3126de` | Evidence-linked report candidate |

PR #186 must not merge before PR #185 is accepted, merged, and PR #186 is rebased and reverified against the resulting main revision.

### 2.2 Live workflow results observed at the current PR heads

All 13 workflow runs associated with each PR head are now completed successfully. This corrects the earlier snapshot that showed the integrated-runtime runs as cancelled/in progress. A green workflow result remains distinct from gate certification.

**PR #185 — candidate SHA `0431dbaf6e1a3bb3348f6d94c094e893543e513c`**

| Workflow | Run | Result | Evidence |
|---|---:|---|---|
| Full test suite | #1125 | Success; 1,065 passed, **7 skipped**, 31 warnings, 218 subtests | https://github.com/C2C-Connect/claim2car-connect/actions/runs/45502012107 |
| Database authority cutover | #1196 | Success; 408/408 counted DB tests, 0 skipped; executable DB-01–DB-14 report says 14/14 PASS | https://github.com/C2C-Connect/claim2car-connect/actions/runs/45502012240 |
| Legacy database component | #1240 | Success | https://github.com/C2C-Connect/claim2car-connect/actions/runs/45502012125 |
| FastAPI foundation | #1182 | Success | https://github.com/C2C-Connect/claim2car-connect/actions/runs/45502012063 |
| Integrated runtime container smoke | #671 | **Success** (not cancelled) | https://github.com/C2C-Connect/claim2car-connect/actions/runs/45502012031 |
| Frontend VIN, decoder and transport | #1168 | Success | https://github.com/C2C-Connect/claim2car-connect/actions/runs/45502012118 |
| Controlled synthetic demonstration | #987 | Success | https://github.com/C2C-Connect/claim2car-connect/actions/runs/45502012262 |
| Restricted intake container | #1013 | Success | https://github.com/C2C-Connect/claim2car-connect/actions/runs/45502012377 |
| Restricted container | #625 | Success | https://github.com/C2C-Connect/claim2car-connect/actions/runs/45502012069 |
| Browser IndexedDB evidence queue | #791 | Success | https://github.com/C2C-Connect/claim2car-connect/actions/runs/45502012295 |
| Offline VIN lookup controller | #1029 | Success | https://github.com/C2C-Connect/claim2car-connect/actions/runs/45502012373 |
| Offline guided capture | #989 | Success | https://github.com/C2C-Connect/claim2car-connect/actions/runs/45502012054 |
| Controlled-test intake PostgreSQL | #1028 | Success | https://github.com/C2C-Connect/claim2car-connect/actions/runs/45502012058 |

The DB authority artifact is retained as artifact ID `14969394508`, SHA-256 `e74655af0c528ea76afe11beace4bb9a347d9fdbae2920ea7a90544fae67e1d5`: https://github.com/C2C-Connect/claim2car-connect/actions/runs/45502012240/artifacts/14969394508. Its metadata records candidate SHA `0431dbaf6e1a3bb3348f6d94c094e893543e513c`, tested checkout `40a9e5298b2e6eb484177319552ff4ccc5042448`, 30 migrations through `0030_runtime_manifest_registration.sql`, 408/408 counted tests with zero skips, and 14/14 executable DB gate results. It also labels its DB-level `overall_acceptance` as `ACCEPTED`; that label conflicts with the owner-directed release registry baseline of 0/14 formally certified and overall release acceptance NOT ACCEPTED. Preserve both facts: technical DB runner result = 14/14 PASS; owner certification in this release registry = 0/14 certified pending owner review. The artifact's separate `publish-evidence` job was skipped, but the authority job itself successfully uploaded this artifact.

The authority artifact identifies tested checkout `40a9e5298b2e6eb484177319552ff4ccc5042448`, a pull-request merge ref, rather than the branch-head SHA. The candidate SHA is separately recorded and matches the PR head. Keep both SHAs visible; do not describe the tested checkout as the raw branch commit.

**PR #186 — candidate SHA `0a4b6087049d2483d8cf4ecc68fa0faaaa3126de`**

| Workflow | Run | Result | Evidence |
|---|---:|---|---|
| Full test suite | #1129 | Success; 1,074 passed, **7 skipped**, 41 warnings, 219 subtests | https://github.com/C2C-Connect/claim2car-connect/actions/runs/45504282583 |
| Database authority cutover | #1200 | Success; 409/409 counted DB tests, 0 skipped; executable DB-01–DB-14 report says 14/14 PASS | https://github.com/C2C-Connect/claim2car-connect/actions/runs/45504282825 |
| Legacy database component | #1244 | Success | https://github.com/C2C-Connect/claim2car-connect/actions/runs/45504282176 |
| FastAPI foundation | #1186 | Success | https://github.com/C2C-Connect/claim2car-connect/actions/runs/45504282314 |
| Integrated runtime container smoke | #675 | **Success** (not in progress) | https://github.com/C2C-Connect/claim2car-connect/actions/runs/45504282240 |
| Frontend VIN, decoder and transport | #1172 | Success | https://github.com/C2C-Connect/claim2car-connect/actions/runs/45504282245 |
| Controlled synthetic demonstration | #991 | Success | https://github.com/C2C-Connect/claim2car-connect/actions/runs/45504282508 |
| Restricted intake container | #1017 | Success | https://github.com/C2C-Connect/claim2car-connect/actions/runs/45504282442 |
| Restricted container | #629 | Success | https://github.com/C2C-Connect/claim2car-connect/actions/runs/45504282469 |
| Browser IndexedDB evidence queue | #795 | Success | https://github.com/C2C-Connect/claim2car-connect/actions/runs/45504282214 |
| Offline VIN lookup controller | #1033 | Success | https://github.com/C2C-Connect/claim2car-connect/actions/runs/45504282594 |
| Offline guided capture | #993 | Success | https://github.com/C2C-Connect/claim2car-connect/actions/runs/45504282431 |
| Controlled-test intake PostgreSQL | #1032 | Success | https://github.com/C2C-Connect/claim2car-connect/actions/runs/45504282358 |

The DB authority artifact is retained as artifact ID `14972002960`, SHA-256 `8b8e387915e000cd9c431409dc8de719c736030263632a4b15e00a185e632670`: https://github.com/C2C-Connect/claim2car-connect/actions/runs/45504282825/artifacts/14972002960. Its metadata records candidate SHA `0a4b6087049d2483d8cf4ecc68fa0faaaa3126de`, tested checkout `63ba944f0809212e968199b6afd8ab5dfac086f5`, migration `0031_damage_assessment_report_event.sql`, 409/409 counted DB tests with zero skips, and 14/14 executable DB gate results. It likewise reports DB-level `overall_acceptance: ACCEPTED`, which is not owner certification of the full release. The candidate SHA and merge-ref tested checkout are both recorded; they are not interchangeable.

**Skip accounting:** the full-suite jobs for both PRs each report seven skips because the general suite runs against the explicit legacy schema baseline through migration 0007. The seven cases are:
- `CompletionReceiptTests.test_receipt_inspection_fails_closed_on_root_binding_tamper`
- `CompletionReceiptTests.test_receipt_write_rejects_root_binding_tamper`
- `ManifestRootTests.test_authority_fixture_roles_are_bound_to_tenant`
- `ManifestRootTests.test_privileged_context_binding_tamper_fails_verification`
- `ManifestRootTests.test_registered_binding_rejects_tampered_chain_tail`
- `ManifestRootTests.test_registered_root_contains_and_verifies_seal_chain_binding`
- `RegisteredCompletionTests.test_registered_root_context_binding_tamper_fails_closed`

These are schema-specific N/A skips in the legacy-baseline run, not missing coverage: all seven are executed and PASS in the separate post-cutover authority lane. That lane reports 408/408 counted tests, zero skips for PR #185, and 409/409 counted tests, zero skips for PR #186. Nevertheless, the general full-suite jobs still report seven skipped cases. The owner's literal PR rule says zero skipped tests; therefore do not silently waive this discrepancy. Keep the components at Implemented until the owner-approved interpretation is recorded or the workflow matrix is changed to report these cases without skipping while preserving the legacy-baseline checks.
## 3. Database gate registry — DB-01 through DB-14

**Required environment:** isolated synthetic PostgreSQL 16 with PostGIS 3.4 and required extensions; separately identified admin, migrator, and restricted application roles; full ordered migration inventory; no production credentials or participant data.  
**Executable runner:** `python tests/database/verify_gates.py` after the counted database suite and post-cutover diagnostics.  
**Approver:** Product Owner for formal acceptance; independent review status must be stated accurately and may not be implied.  
**Current result for these candidate revisions:** DB-01–DB-14 are **14/14 PASS / formally awarded** in PR #185 run #1196 and PR #186 run #1200. The artifacts were downloaded and inspected: both reports contain 14 explicit PASS rows, `gate_passes_awarded: 14`, `overall_acceptance: ACCEPTED`, and clean counted-test summaries (408/408 and 409/409; zero failures, errors, or skips). These awards are database-layer acceptance only, not GATE-01–GATE-07 release acceptance. Rerun after any source change or rebase.  
**Blocking:** Yes, DB-01 through DB-14 are release-blocking through GATE-02 and other dependent release gates.

| Gate | Requirement | Required executable test selectors / SQL evidence | Current result | Required evidence / environment | Blocking |
|---|---|---|---|---|---|
| DB-01 | Reproducible environment and configuration | `test_candidate_manifest.CandidateManifestTests.*`; `test_migration_plan.MigrationPlanTests.*`; `test_migration_preflight.MigrationPreflightTests.*`; clean full initialization and legacy-upgrade integration tests | PASS — PR #185 #1196 and PR #186 #1200 | Sanitized environment manifest, explicit connection identities, extensions, clean startup and rerun logs, migration inventory | Yes |
| DB-02 | Migration integrity and schema versioning | `test_migration_plan.MigrationPlanTests.*`; `test_migration_preflight.MigrationPreflightTests.*`; `test_migration_controls_integration.MigrationControlsIntegration.*`; candidate-manifest tests | PASS — PR #185 #1196 and PR #186 #1200 | Empty-database apply, ordered migration versions and SHA-256 inventory, failure/recovery and rollback evidence | Yes |
| DB-03 | Restricted application privileges | `test_access_hardening.TestAccessHardening.*`; `test_adapter_validation.TestAdapterValidation.*`; `test_identity_boundary.IdentityBoundaryTests.*`; tenant-authority registry denial; completion and manifest-root application-role denial | PASS — PR #185 #1196 and PR #186 #1200 | Effective privilege matrix and negative SQL assertions in PostgreSQL under application role | Yes |
| DB-04 | Tenant isolation and forced RLS | `test_remaining_integration.TestRemainingIntegration.*`; `test_identity_bound_prototype.IdentityBoundPrototype.*`; `test_schema_integrity.SchemaIntegrityTests.*`; `test_tenant_authority_integration.TenantAuthorityIntegration.*`; checks G04-DIRECT-SQL-TENANT-SWITCH, UNBOUND-SHARED-LOGIN-DENIED, POSTCUTOVER-PER-TABLE-ISOLATION | PASS — PR #185 #1196 and PR #186 #1200 | Full per-table forced-RLS inventory; two-tenant adversarial matrix; direct SQL and spoofed-context denials | Yes |
| DB-05 | Tenant-context lifecycle | `test_tenant_context_regression.TenantContextRegression.*`; `test_completion_lock.CompletionLockTests.*`; `test_locked_evaluation.LockedEvaluationTests.*` | PASS — PR #185 #1196 and PR #186 #1200 | Commit, rollback, exception, pool-reuse, missing-context and tenant-switch traces | Yes |
| DB-06 | Event schema and domain-contract validation | `test_event_contract_regression.EventContractRegression.*`; adapter validation; SQL/Python parity and historical-payload-preservation integration tests; timestamp, compact JSON, key-order, numeric-spelling and Unicode SQL checks | PASS — PR #185 #1196 and PR #186 #1200 | Canonical event contract, timezone-aware timestamp checks, Python/SQL parity, valid/invalid fixtures | Yes |
| DB-07 | Durable event append and idempotency | `test_journal_integration.TestJournalIntegration.*`; bound-login append/retry/readback integration; event-contract regression | PASS — PR #185 #1196 and PR #186 #1200 | Persisted append/readback, identical retry, conflicting key reuse, transaction interruption and durable idempotency evidence | Yes |
| DB-08 | Sequence integrity and concurrent writes | `test_journal_integration.TestConcurrentJournal.*`; `test_completion_concurrency.CompletionConcurrencyTests.*`; completion-lock tests | PASS — PR #185 #1196 and PR #186 #1200 | Repeated concurrent writers, ordering/sequence histories, deterministic conflict/retry outcomes | Yes |
| DB-09 | Event immutability and history integrity | Access-hardening, event-contract and journal-integration tests; historical payload preservation and noncanonical-history rejection | PASS — PR #185 #1196 and PR #186 #1200 | INSERT/SELECT-only journal privilege evidence, mutation-denial tests, chain recomputation and tamper results | Yes |
| DB-10 | Evidence-manifest integrity and root registration | `test_completion_coverage.CompletionCoverage.*`; `test_manifest_roots.ManifestRootTests.*`; `test_registered_completion.RegisteredCompletionTests.*`; 16-v1 protocol-binding integration | PASS — PR #185 #1196 and PR #186 #1200 | Expected digest fixtures, root-to-session/tenant/protocol binding, duplicate/conflict/cross-tenant and tamper tests | Yes |
| DB-11 | Completion receipts and protected completion state | `test_completion_receipts.CompletionReceiptTests.*`; `test_atomic_completion.AtomicCompletionTests.*`; `test_completion_concurrency.CompletionConcurrencyTests.*` | PASS — PR #185 #1196 and PR #186 #1200 | Authorized creation, protected-table privilege denials, duplicate/conflict and receipt-to-root consistency | Yes |
| DB-12 | Revocation, tampering, and invalidation | Atomic-completion, registered-completion, receipt-inspection and persisted-evidence-recovery tests; BINDING-REVOCATION-NEXT-TRANSACTION SQL check | PASS — PR #185 #1196 and PR #186 #1200 | Revocation/tamper/missing-reference cases; downstream fail-closed reads; durable audit evidence | Yes |
| DB-13 | Restart, recovery, and replay | `test_process_recovery.ProcessRecovery.*`; `test_process_recovery.PersistedEvidenceRecovery.*`; receipt-inspection and tenant-authority vertical-slice tests | PASS — PR #185 #1196 and PR #186 #1200 | Before/after persisted snapshots, process restart, independent readback, replay and invalid-history tests | Yes |
| DB-14 | Failure handling, end-to-end acceptance, and evidence reporting | `test_counted_runner.CountedRunnerTests.*`; `test_evidence_finalizer.EvidenceFinalizerTests.*`; all preceding gate checks in one run | PASS — PR #185 #1196 and PR #186 #1200 | Machine-readable same-run report, exact source SHA, migration inventory, environment, zero skipped tests, artifacts and overall NOT ACCEPTED/ACCEPTED result | Yes |

The selectors above are sourced from `tests/database/verify_gates.py`; they are not a substitute for executing the runner. The runner's mapped test identifiers and SQL checks must be present in the retained report.

## 4. Release gate crosswalk — GATE-01 through GATE-07

Every row explicitly lists its database dependencies, additional evidence not supplied by DB gates, and current-head workflow proof. The listed DB dependencies are necessary supporting controls only; they never satisfy the release gate by themselves.

| Release gate | DB dependencies | Additional evidence DB gates do not provide | Current-head workflow proof |
|---|---|---|---|
| **GATE-01 — Governance and commercial compliance** | DB-06, DB-07, DB-09, DB-11, DB-12, DB-14 | Owner-approved commercial terms; prohibited owner incentive blocked in contracts, denylist, tests and ledger; operator compensation remains disabled; dealer/shop fee earning events; signed partner terms; counsel review; documented authority for consent, distribution, payment and dispatch. | **NONE.** PR #185 Full suite #1125 (SHA `0431dbaf6e1a3bb3348f6d94c094e893543e513c`) and DB authority #1196 are technical evidence only, not owner/counsel/partner approvals. No current-head workflow can substitute for signed governance evidence. |
| **GATE-02 — Security and database authority** | DB-01 through DB-14 (all fourteen) | Application/API authorization, server-derived actor and tenant, forced RLS across all tenant tables, private internal routes, secret handling, TLS configuration, threat review, and evidence that the deployed configuration matches the tested configuration. | Candidate exact-head DB evidence: PR #185 DB authority #1196 at SHA `0431dbaf6e1a3bb3348f6d94c094e893543e513c` awarded DB-01–DB-14 14/14 PASS (408/408, zero skips); PR #186 DB authority #1200 at SHA `0a4b6087049d2483d8cf4ecc68fa0faaaa3126de` awarded 14/14 PASS (409/409, zero skips). This satisfies the database subset only. Additional release-security evidence and deployed-configuration equivalence remain outstanding. |
| **GATE-03 — Operator and reviewer product experience** | DB-03, DB-04, DB-05, DB-06, DB-07, DB-08, DB-09, DB-13, DB-14 | Usable authenticated operator and reviewer journey; consent UX; protocol version shown to every consumer; VIN and capture workflow; reviewer access to original bytes; attributed review and reason; human usability and error recovery. | Candidate exact-head evidence: PR #185 Full suite #1125, FastAPI #1182 and Integrated runtime smoke #671 all passed at SHA `0431dbaf6e1a3bb3348f6d94c094e893543e513c`; PR #186 Full suite #1129, FastAPI #1186 and Integrated runtime smoke #675 also passed at SHA `0a4b6087049d2483d8cf4ecc68fa0faaaa3126de`. This is synthetic automated journey evidence, not an operational field or persistent-staging journey. |
| **GATE-04 — Durable storage, consent-deletion and PITR drills** | DB-01, DB-02, DB-04, DB-07, DB-09, DB-10, DB-12, DB-13, DB-14 | Durable immutable original-byte storage; deletion of original bytes and mutable incident rows on withdrawal; durable revocation journal event; downstream fail-closed behavior; encrypted storage; backup policy; point-in-time recovery and witnessed restore drill; post-restore integrity verification. | Candidate exact-head evidence: PR #185 DB authority #1196 and Full suite #1125 at SHA `0431dbaf6e1a3bb3348f6d94c094e893543e513c`; synthetic local durable-store consent deletion and tamper cases pass. No encrypted remote object-store lifecycle or PITR/restore drill is recorded. **No release-gate proof.** |
| **GATE-05 — Persistent integrated staging** | DB-01, DB-02, DB-03, DB-04, DB-05, DB-07, DB-08, DB-09, DB-10, DB-11, DB-12, DB-13, DB-14 | Actual persistent integrated environment: PostgreSQL 16/PostGIS 3.4, durable encrypted object storage, real auth, TLS, managed secrets, backups and restore drills, monitoring/alerts, deployed immutable image, and a successful operator-to-reviewer journey after restart. Restricted Railway/container smoke is not staging. | PR #185 Integrated runtime smoke #671 and PR #186 Integrated runtime smoke #675 both passed. They are container smoke tests, not a persistent deployed staging environment with real PostgreSQL, durable remote storage, TLS, managed secrets, backups, monitoring and restore drills. **No release-gate proof.** |
| **GATE-06 — Physical-device qualification** | DB-04, DB-05, DB-07, DB-10, DB-13 | Physical reference iPad Pro 11-inch M5 qualification; recorded device and OS; camera capture, framing, low-light and motion cases, offline interruption/recovery, queue encryption at rest, upload/retry, thermal and battery behavior. Simulator and desktop browser runs do not qualify. | **NONE.** No current-head physical-device workflow or signed device qualification report was found. |
| **GATE-07 — Counsel, partner agreements and sandbox reconciliation before live payment** | DB-06, DB-07, DB-08, DB-09, DB-11, DB-12, DB-13, DB-14 | Counsel sign-off; signed dealer/shop/operator agreements; owner authorization; Square sandbox success, duplicate, failure, UNKNOWN, reversal and reconciliation scenarios; webhook signature/dedup evidence; internal ledger as source of truth; explicit live-money release authorization. | **NONE.** No current-head workflow run in this snapshot demonstrates the complete required sandbox reconciliation matrix plus counsel and signed-partner evidence. PR #185/#186 general CI does not prove this gate. |

**Zero-dependency declaration:** No release gate is assigned zero DB-gate dependencies in this crosswalk. If later evidence shows a release gate has no DB dependency, it must be recorded as `NONE — no DB-gate dependency` explicitly rather than left blank.

## 5. Component-level acceptance status

| Component | Level | Current-head SHA | Workflow evidence | Gates satisfied | Gates remaining | Blockers |
|---|---|---|---|---|---|---|
| Runtime manifest registration (PR #185) | Implemented | `0431dbaf6e1a3bb3348f6d94c094e893543e513c` | 13/13 workflows completed successfully; Full suite #1125 (1,065 passed, 7 skipped); DB authority #1196 (408/408 counted, 0 skipped, 14/14 executable DB results; artifact 14969394508); Integrated smoke #671 success. | No release gate formally certified by this registry. The five PR-specific behaviors have direct integration-test coverage in `test_authenticated_http_capture_survives_runtime_restart_and_fails_closed`. | GATE-02, GATE-03, GATE-04, GATE-05; formal DB-01–DB-14 certification remains 0/14 in this release record. | Seven full-suite skips violate the no-skip merge rule; DB artifact's DB-level ACCEPTED label must not be mistaken for owner certification; verify artifact and merge-ref checkout SHA distinction. |
| Evidence-linked damage reports (PR #186) | Implemented | `0a4b6087049d2483d8cf4ecc68fa0faaaa3126de` | 13/13 workflows completed successfully; Full suite #1129 (1,074 passed, 7 skipped); DB authority #1200 (409/409 counted, 0 skipped, 14/14 executable DB results; artifact 14972002960); Integrated smoke #675 success. | No release gate formally certified by this registry. PDF/JSON source-link and disclosure behavior has unit-test coverage. | GATE-02, GATE-03, GATE-04, GATE-05; formal DB-01–DB-14 certification remains 0/14 in this release record. | Seven full-suite skips; no durable report registry or restart retrieval; no durable report-tamper/audit test; PR remains stacked on #185 and must be rebased after #185 lands. |
| Persistent integrated staging | Designed | No deployed revision | No deployment run proving persistent staging | None | GATE-04, GATE-05 and all dependent gates | No persistent staging deployment, PITR/restore drill, or operational journey. |
| Physical-device qualification | Designed | No qualified device revision | No physical-device run | None | GATE-06 | Physical iPad Pro 11-inch M5 qualification evidence absent. |
| Square sandbox reconciliation | Implemented status not established by this registry | No current-head SHA/run established | No complete current-head sandbox evidence located | None | GATE-01, GATE-07 | Success/duplicate/failure/UNKNOWN/reversal/reconciliation evidence and signed governance terms absent. |

The DB authority workflow reports are retained technical evidence. Their 14/14 executable results do not change the owner-directed certification baseline of 0/14 for this release registry, and they do not certify any of GATE-01 through GATE-07.
## 6. PR-specific acceptance criteria carried into this registry

### PR #185 — runtime manifest registration

Before it can be considered Verified or merged, current-head evidence must prove all five owner criteria:

1. **Persistent registration:** migration `0030_runtime_manifest_registration.sql` registers the sealed root in PostgreSQL authority within the live capture seal transaction. The test reads the persisted `faos.manifest_roots` row and confirms the registered seal reference.
2. **Idempotency:** the same seal request is replayed; HTTP returns success with `root_registered: true`, `replayed: true`, and the same manifest digest. The registration function returns REGISTERED/DUPLICATE and verifies the existing binding.
3. **Restart survival:** immediately after sealing, a separate Python process reconstructs the reviewer API using persisted PostgreSQL journal rows and the durable original-byte store; it retrieves the manifest and original bytes. A fresh runtime is then reconstructed and independently rechecks the persisted root.
4. **Independent verification:** the fresh runtime verifies the registered root binding and reads the original object through the byte store, which recomputes SHA-256 against the persisted manifest digest. The test asserts the returned original bytes and digest.
5. **Tamper rejection:** the test mutates a persisted original object, expects HTTP 409 with `EVIDENCE_ARTIFACT_INTEGRITY_FAILURE`, verifies one durable `ARTIFACT_INTEGRITY_FAILURE_RECORDED` event with artifact ID, expected digest and failure code, and confirms repeated tamper reads do not duplicate the audit event.

**Evidence:** `tests/database/test_capture_http_integration.py::test_authenticated_http_capture_survives_runtime_restart_and_fails_closed`, exercised by PR #185 Full suite #1125 and DB authority #1196 at candidate SHA `0431dbaf6e1a3bb3348f6d94c094e893543e513c`. The DB authority artifact records 408/408 counted tests, zero DB-lane skips, 30 ordered migrations through 0030, and 14/14 executable DB gate results. Artifact: https://github.com/C2C-Connect/claim2car-connect/actions/runs/45502012240/artifacts/14969394508.

**Status:** all five behaviors have direct code/test evidence at the candidate. The component remains **Implemented**, not Verified for merge, because the general full suite has seven skipped tests under the owner's zero-skip rule, the authority artifact's DB-level `overall_acceptance: ACCEPTED` conflicts with the owner-directed 0/14 formal certification baseline, and the tested checkout SHA is the PR merge ref `40a9e5298b2e6eb484177319552ff4ccc5042448` rather than the raw branch SHA. No owner certification or merge authorization is implied.

### PR #186 — evidence-linked damage assessment reports

Before it can be considered Verified or merged, current-head evidence must prove all of the following:

1. **Immutable source reference:** each finding links to its original artifact ID, immutable storage key and SHA-256; the original artifact remains authoritative. The PDF's visual rendering is a derivative, not a replacement for original bytes.
2. **Per-box provenance:** each finding's JSON carrier entry contains `slot_id`, normalized coordinates, camera-angle values and provenance, reviewer actor and review timestamp, and a non-null source-image reference (artifact ID, storage key and digest). The model rejects findings without an attached source image.
3. **Disclosure parity:** the PDF and JSON carrier payload both state: **“A bounding box is a suspect-region identifier only. It is not a measured dimension, calibrated geometry, or a structural-severity claim.”**
4. **Durable report registry:** report revisions and metadata must be stored durably and retrieved by a fresh process after restart. This is **not implemented** in the current PR: its description explicitly says report versions remain in process memory, and migration `0031_damage_assessment_report_event.sql` only adds an allowed event kind; it does not create a durable report registry or durable report-object lifecycle.
5. **Report tamper audit:** mutation of a persisted report must fail closed and create a durable audit event. No durable report registry/tamper/restart journey is present in the current PR.

**Evidence:** PR #186 Full suite #1129, DB authority #1200 and Integrated runtime smoke #675 all completed successfully at candidate SHA `0a4b6087049d2483d8cf4ecc68fa0faaaa3126de`. The DB authority artifact records 409/409 counted tests, zero DB-lane skips and 14/14 executable DB gate results: https://github.com/C2C-Connect/claim2car-connect/actions/runs/45504282825/artifacts/14972002960. The full suite reports seven skipped tests. The current PR description and code/migration scope confirm that durable report registry integration remains separate work.

**Status:** criteria 1–3 have implementation and unit-test evidence; criteria 4–5 are unmet. The component remains **Implemented**, not Verified. PR #186 is stacked on PR #185; after #185 is accepted and merged, #186 must be rebased onto the resulting `main` and all required workflows rerun at its new head.
## 7. Live-source discrepancies requiring explicit reconciliation


### 7.1 Historical PR #29 state discrepancy

The supplied condensed snapshot describes PR #29 as Draft/unmerged with 222 commits and 93 files. Live GitHub now reports PR #29 as **closed and merged**, with 296 commits and 103 changed files; its recorded head is `25b1067d87649318d518f49ab2e12f1a905a2acc`. Current `main` is `55f69790df123a4602196c3c474e143808c4b87e`. The repository is authoritative for current state. The earlier 222/93 figures remain historical, not a live baseline. Since PR #29 has already merged, the proposed per-slice extraction cannot be performed as if it were still an unmerged branch; audit the landed paths and subsequent corrective PRs instead. Do not rewrite history or attempt to undo the merge under this registry.


The owner directive's canonical capture identifiers are `12-v1` and `16-v1`. The live code on the PR #185 branch sets `DEFAULT_CAPTURE_PROTOCOL = claims2car-16-v1`, keeps `claims2car-12-v1` as a supported legacy protocol, and also exposes `claims2car-16-v2` as a separate FAOS protocol. The repository's versioning document records the exact 16-v1 view list as owner-approved on 2026-11-11 and enabled. The 16-v2 protocol is not named in the current owner decision and is therefore a separate, non-default protocol whose semantics must not be merged into 16-v1.

Required handling:
- preserve `claims2car-16-v1` and `claims2car-12-v1` as distinct immutable contracts;
- preserve any existing `claims2car-16-v2` sessions as their own immutable protocol; never relabel them as 16-v1;
- persist and display the exact protocol identifier stored at session creation in every report, reviewer view and carrier payload;
- do not make 16-v2 the default or silently change protocol enablement;
- record this additional version as a live-source discrepancy in any gate depending on capture protocol.

The owner directive governs the canonical 12-v1 / 16-v1 target; the live repository is the source of truth for the additional 16-v2 implementation. This registry does not rewrite historical protocol records or certify compatibility.

## 8. Owner and environment approvals

| Approval / condition | Required approver | Current status |
|---|---|---|
| Formal DB-01–DB-14 acceptance | Owner, with retained exact-head gate report | 14/14 PASS awarded in PR #185 #1196 and PR #186 #1200; rerun after rebase/source change |
| GATE-01 governance and commercial rules | Owner and counsel where applicable | Pending |
| GATE-05 persistent staging cost ceiling | Owner, after written provider/region/cost/backup/restore/secrets/monitoring plan | Pending |
| Physical device qualification (GATE-06) | Owner after review of physical-device evidence | Pending |
| Live payment authorization (GATE-07) | Separate written owner authorization after counsel, agreements and sandbox reconciliation | Not authorized |
| Operator compensation | Owner | Canonical record remains `OPERATOR_PAYOUT_USD = 110.0`; disabled; zero executable code path; no ledger emission; owner approval pending |

No unsigned draft proposing $100 changes the canonical $110 disabled record. No staging authorization in this registry waives the requirement for a written plan and approved spending ceiling. No merge is authorized by this file.

## 9. Change control

- Update this registry only with exact current refs, workflow run numbers, run URLs, artifact identifiers, environment identity, and test results.
- Recompute the crosswalk when a gate's implementation, test mapping, or dependency changes.
- A rerun on a new SHA supersedes no older result until the new run is complete and its artifact is reviewed.
- A green run, a historical report, or DB acceptance cannot be promoted to a release-gate pass without the additional evidence listed in Section 4.
- Do not weaken, rename, remove, or bypass DB or release gates.
- PR #185 and PR #186 remain unmerged until their individual criteria are satisfied and the owner approves the exact SHA in writing.
