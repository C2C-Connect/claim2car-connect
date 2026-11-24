# Claim2Car Connect — Release Acceptance Registry and DB Crosswalk

**Document ID:** C2C-REL-AC-001  
**Version:** 1.1  
**Snapshot:** 2026-11-24 23:15 UTC  
**Repository:** `C2C-Connect/claim2car-connect`  
**Registry branch base:** `55f69790df123a4602196c3c474e143808c4b87e`  
**Authority:** Current owner Developer Execution Directive. This file records evidence; it does not authorize merges, deployment, payments, dispatch, or participant use.

## 1. Governing rule

GATE-01 through GATE-07 are release-level acceptance gates. DB-01 through DB-14 are a database-foundation subset. Passing 14/14 DB gates does **not** pass any release gate automatically and does not establish deployment or operational acceptance.

The directive's earlier 0/14 DB status was the baseline before the latest exact-head authority runs. Newer live GitHub artifacts supersede that dated count:

- PR #185 run #1196 awarded DB-01–DB-14 **14/14 PASS** at prior candidate SHA `0431dbaf6e1a3bb3348f6d94c094e893543e513c`; the current PR #185 head is now `a7174d45a02cc6b8312a00b1ca31671019726728` after an additional seal-replay uniqueness assertion, and its authority rerun #1203 is in progress.
- PR #186 run #1200 awarded DB-01–DB-14 **14/14 PASS** at candidate SHA `0a4b6087049d2483d8cf4ecc68fa0faaaa3126de`.

Both artifacts explicitly contain 14 PASS rows, `gate_passes_awarded: 14`, and `overall_acceptance: ACCEPTED`. Their counted DB lanes executed 408/408 and 409/409 tests respectively, with zero failures, errors, or skips. Their tested checkout SHAs are the corresponding PR merge refs: `40a9e5298b2e6eb484177319552ff4ccc5042448` (PR #185 head merged into main base `55f69790...`) and `63ba944f0809212e968199b6afd8ab5dfac086f5` (PR #186 head merged into PR #185 base `0431dbaf...`). Candidate SHA and tested merge-ref SHA are both recorded because they are different objects.

**Current database status: 14/14 PASS on prior PR #185 and current PR #186 candidate revisions. The new PR #185 head `a7174d45a02cc6b8312a00b1ca31671019726728` is undergoing a fresh exact-head rerun; do not carry forward its prior 14/14 result until run #1203 and the associated current-head artifact complete. Current release status: NOT ACCEPTED; GATE-01 through GATE-07 have not been awarded.**

A workflow badge alone never passes a gate. A pass requires the named executable checks, a clean current-head run in the required environment, retained evidence, and the required approver. Skipped tests do not pass a gate. The two full-suite workflows below each report seven skipped tests; this remains a merge-readiness issue under the owner's zero-skip merge condition even though the database authority lanes themselves had zero skips.

## 2. Live repository and exact-head evidence

### 2.1 Live refs

| Ref | State | Exact SHA | Notes |
|---|---|---|---|
| `main` | Current base observed | `55f69790df123a4602196c3c474e143808c4b87e` | Current base for PR #185 and PR #187 |
| PR #185, `cto/m1-runtime-manifest-registration` | Open, unmerged | `a7174d45a02cc6b8312a00b1ca31671019726728` | Runtime manifest registration; new seal-replay journal uniqueness assertion; CI rerun pending |
| PR #186, `feat/evidence-linked-damage-assessment-pdf` | Open, unmerged; stacked on PR #185 | `0a4b6087049d2483d8cf4ecc68fa0faaaa3126de` | Evidence-linked damage reports |
| PR #187, `docs/release-gate-crosswalk` | Draft, open | `db411dbf1a0ee57f3ee1f91ec72489bd4491ba48` | This registry; based on main |

PR #186 must be rebased onto the resulting main revision after PR #185 merges, and all required workflows must rerun at the rebased head. No merge has been performed.

### 2.2 Current PR #185 head — `a7174d45a02cc6b8312a00b1ca31671019726728`

A direct assertion was added to the HTTP/PostgreSQL integration test: replaying the same `MANIFEST_SEALED` request must leave exactly one journal row for that event ID. This closes the last explicit test-evidence gap in the idempotency criterion. The new head triggered all 13 workflows; at this snapshot 4 have completed successfully and 9 are in progress.

| Workflow | Run | Result | Evidence |
|---|---:|---|---|
| Database authority cutover | #1203 | In progress | https://github.com/C2C-Connect/claim2car-connect/actions/runs/45506000953 |
| Legacy database component | #1247 | In progress | https://github.com/C2C-Connect/claim2car-connect/actions/runs/45506001249 |
| Controlled-test intake PostgreSQL | #1033 | In progress | https://github.com/C2C-Connect/claim2car-connect/actions/runs/45506001105 |
| Offline guided capture | #994 | Success | https://github.com/C2C-Connect/claim2car-connect/actions/runs/45506001327 |
| Browser IndexedDB evidence queue | #796 | In progress | https://github.com/C2C-Connect/claim2car-connect/actions/runs/45506001510 |
| Integrated runtime container smoke | #676 | In progress | https://github.com/C2C-Connect/claim2car-connect/actions/runs/45506001392 |
| Frontend VIN, decoder and transport | #1175 | Success | https://github.com/C2C-Connect/claim2car-connect/actions/runs/45506000974 |
| Full test suite | #1132 | In progress | https://github.com/C2C-Connect/claim2car-connect/actions/runs/45506001046 |
| FastAPI foundation | #1189 | In progress | https://github.com/C2C-Connect/claim2car-connect/actions/runs/45506001336 |
| Offline VIN lookup controller | #1034 | Success | https://github.com/C2C-Connect/claim2car-connect/actions/runs/45506001376 |
| Restricted container | #630 | In progress | https://github.com/C2C-Connect/claim2car-connect/actions/runs/45506001155 |
| Restricted intake container | #1018 | In progress | https://github.com/C2C-Connect/claim2car-connect/actions/runs/45506001292 |
| Controlled synthetic demonstration | #992 | Success | https://github.com/C2C-Connect/claim2car-connect/actions/runs/45506001032 |

**Prior PR #185 head — `0431dbaf6e1a3bb3348f6d94c094e893543e513c`:** all 13 workflows passed; Full suite #1125, DB authority #1196, FastAPI #1182 and Integrated smoke #671 passed. Its DB artifact 14969394508 recorded DB-01–DB-14 14/14 PASS and 408/408 counted DB tests. This is valid historical evidence for that prior head, not current-head proof for `a7174d45...`.

## 3. Database gate registry — DB-01 through DB-14

**Required environment:** synthetic PostgreSQL 16 with PostGIS 3.4 and required extensions; distinct admin, migrator and restricted application roles; complete ordered migrations; no production credentials or participant data.  
**Executable runner:** `python tests/database/verify_gates.py` plus the mapped integration tests and SQL checks.  
**Approver:** Product Owner for formal release use; the technical DB award is not a substitute for owner/counsel approval.  
**Current candidate result:** DB-01–DB-14 **14/14 PASS** on PR #185 run #1196 and PR #186 run #1200. Re-run after any source change or rebase.  
**Blocking:** These gates are release dependencies, principally through GATE-02; their pass does not pass GATE-02 as a whole.

| Gate | Requirement | Executable tests / SQL evidence | Current result | Additional retained evidence | Blocking |
|---|---|---|---|---|---|
| DB-01 | Reproducible environment and configuration | `test_candidate_manifest.CandidateManifestTests.*`; `test_migration_plan.MigrationPlanTests.*`; `test_migration_preflight.MigrationPreflightTests.*`; clean initialization and legacy-upgrade integration | PASS on prior heads — #1196 and #1200; current PR #185 #1203 pending | Environment manifest, role identities, extensions, startup/rerun logs, migration inventory | Yes |
| DB-02 | Migration integrity and schema versioning | `test_migration_plan.MigrationPlanTests.*`; `test_migration_preflight.MigrationPreflightTests.*`; `test_migration_controls_integration.MigrationControlsIntegration.*` | PASS — #1196 and #1200 | Empty-database apply, ordered migration checksums, failure/recovery and rollback evidence | Yes |
| DB-03 | Restricted application privileges | `test_access_hardening.TestAccessHardening.*`; `test_adapter_validation.TestAdapterValidation.*`; `test_identity_boundary.IdentityBoundaryTests.*`; app-role denial checks | PASS — #1196 and #1200 | Effective privilege matrix and negative SQL assertions under application role | Yes |
| DB-04 | Tenant isolation and forced RLS | `test_remaining_integration.TestRemainingIntegration.*`; `test_identity_bound_prototype.IdentityBoundPrototype.*`; `test_schema_integrity.SchemaIntegrityTests.*`; `test_tenant_authority_integration.TenantAuthorityIntegration.*`; G04 direct-SQL and post-cutover table isolation | PASS — #1196 and #1200 | Forced-RLS inventory, two-tenant adversarial matrix, spoofed-context denials | Yes |
| DB-05 | Tenant-context lifecycle | `test_tenant_context_regression.TenantContextRegression.*`; `test_completion_lock.CompletionLockTests.*`; `test_locked_evaluation.LockedEvaluationTests.*` | PASS — #1196 and #1200 | Commit/rollback, exception, pool reuse, missing context and tenant-switch traces | Yes |
| DB-06 | Event schema and domain-contract validation | `test_event_contract_regression.EventContractRegression.*`; SQL/Python parity, timestamp, compact JSON, key-order, numeric and Unicode checks | PASS — #1196 and #1200 | Canonical event contract and valid/invalid SQL/Python fixtures | Yes |
| DB-07 | Durable event append and idempotency | `test_journal_integration.TestJournalIntegration.*`; bound-login append/retry/readback | PASS — #1196 and #1200 | Persisted append/readback, identical retry, conflicting-key and transaction-interruption evidence | Yes |
| DB-08 | Sequence integrity and concurrent writes | `test_journal_integration.TestConcurrentJournal.*`; `test_completion_concurrency.CompletionConcurrencyTests.*` | PASS — #1196 and #1200 | Concurrent writer histories and deterministic conflict/retry results | Yes |
| DB-09 | Event immutability and history integrity | Access-hardening, event-contract and journal-integration tests; historical-payload preservation | PASS — #1196 and #1200 | INSERT/SELECT-only journal privileges, mutation denials and chain recomputation | Yes |
| DB-10 | Evidence-manifest integrity and root registration | `test_completion_coverage.CompletionCoverage.*`; `test_manifest_roots.ManifestRootTests.*`; `test_registered_completion.RegisteredCompletionTests.*`; protocol-binding integration | PASS — #1196 and #1200 | Digest fixtures, root/session/tenant/protocol binding, duplicate/conflict/tamper evidence | Yes |
| DB-11 | Completion receipts and protected completion state | `test_completion_receipts.CompletionReceiptTests.*`; `test_atomic_completion.AtomicCompletionTests.*`; completion concurrency tests | PASS — #1196 and #1200 | Authorized creation, protected-table denials and receipt/root consistency | Yes |
| DB-12 | Revocation, tampering and invalidation | Atomic-completion, registered-completion, receipt-inspection and persisted-evidence-recovery tests; revocation SQL check | PASS — #1196 and #1200 | Revocation/tamper/missing-reference cases and fail-closed reads | Yes |
| DB-13 | Restart, recovery and replay | `test_process_recovery.ProcessRecovery.*`; `test_process_recovery.PersistedEvidenceRecovery.*`; tenant-authority vertical slice | PASS — #1196 and #1200 | Before/after snapshots, process restart, independent readback and replay | Yes |
| DB-14 | Failure handling and same-run evidence finalization | `test_counted_runner.CountedRunnerTests.*`; `test_evidence_finalizer.EvidenceFinalizerTests.*`; all preceding gate checks | PASS — #1196 and #1200 | Same-run report, exact candidate and checkout SHAs, migration inventory, zero DB skips, artifact checksum | Yes |

The runner selectors above are sourced from `tests/database/verify_gates.py`; the retained same-run report is the pass evidence. A row in this table does not imply any GATE-01–GATE-07 result.

## 4. Release gate crosswalk — GATE-01 through GATE-07

Every gate explicitly lists DB dependencies, non-DB evidence, and current-head workflow proof. A release gate with no DB dependencies must say `NONE — no DB-gate dependency`; none of the seven is currently assigned zero dependencies.

| Release gate | DB dependencies | Additional evidence not supplied by DB gates | Current-head proof and status |
|---|---|---|---|
| **GATE-01 — Governance and commercial compliance** | DB-06, DB-07, DB-09, DB-11, DB-12, DB-14 | Owner-approved commercial terms; prohibited owner incentive blocked in contracts/denylist/tests/ledger; operator compensation disabled; dealer/shop earning-event rules; signed partner terms; counsel review; consent and distribution authority. | **NOT ACCEPTED.** PR #185 Full suite #1125 and DB authority #1196 are technical evidence only. No workflow substitutes for owner, counsel or partner signatures. |
| **GATE-02 — Security and database authority** | DB-01 through DB-14 (all fourteen) | App/API authorization, server-derived actor and tenant, private internal routes, secret handling, TLS, threat review, and proof deployed configuration equals tested configuration. | DB subset **14/14 PASS**: PR #185 DB authority #1196 at SHA `0431dbaf6e1a3bb3348f6d94c094e893543e513c` (408/408, zero DB skips); PR #186 DB authority #1200 at SHA `0a4b6087049d2483d8cf4ecc68fa0faaaa3126de` (409/409, zero DB skips). **GATE-02 NOT ACCEPTED** until the additional security and deployed-configuration evidence is complete. |
| **GATE-03 — Operator and reviewer product experience** | DB-03, DB-04, DB-05, DB-06, DB-07, DB-08, DB-09, DB-13, DB-14 | Usable authenticated operator/reviewer journey; consent UX; protocol version visible to consumers; VIN/capture workflow; original-byte retrieval; reviewer attribution/reason; human usability and recovery. | PR #185 Full suite #1125, FastAPI #1182 and Integrated smoke #671 passed; PR #186 Full suite #1129, FastAPI #1186 and Integrated smoke #675 passed. These are synthetic automated journeys, not a field/operational acceptance run. **NOT ACCEPTED.** |
| **GATE-04 — Durable storage, consent deletion and PITR drills** | DB-01, DB-02, DB-04, DB-07, DB-09, DB-10, DB-12, DB-13, DB-14 | Encrypted remote object storage; consent withdrawal deletion of originals and mutable incident rows; durable revocation event; downstream fail-closed behavior; backup policy; PITR and witnessed restore drill; post-restore integrity check. | Synthetic local-store deletion and tamper tests pass in PR #185/#186. No encrypted remote object-store lifecycle or PITR/restore drill is recorded. **NOT ACCEPTED.** |
| **GATE-05 — Persistent integrated staging** | DB-01, DB-02, DB-03, DB-04, DB-05, DB-07, DB-08, DB-09, DB-10, DB-11, DB-12, DB-13, DB-14 | Persistent PostgreSQL 16/PostGIS 3.4, encrypted durable object storage, real auth, TLS, managed secrets, backups/restore drills, monitoring/alerts, deployed immutable image and restart-surviving operator-to-reviewer journey. Restricted Railway/container smoke is not staging. | PR #185 Integrated smoke #671 and PR #186 Integrated smoke #675 passed, but both are disposable CI containers. No persistent staging deployment exists. **NOT ACCEPTED.** |
| **GATE-06 — Physical-device qualification** | DB-04, DB-05, DB-07, DB-10, DB-13 | Physical reference iPad Pro 11-inch M5, recorded OS, camera capture/framing, low-light and motion, offline recovery, encrypted queue at rest, upload/retry, thermal and battery tests. Simulator/desktop tests do not qualify. | **NONE.** No current-head physical-device workflow or signed device qualification report. **NOT ACCEPTED.** |
| **GATE-07 — Counsel, partner agreements and sandbox reconciliation before live payment** | DB-06, DB-07, DB-08, DB-09, DB-11, DB-12, DB-13, DB-14 | Counsel sign-off; signed dealer/shop/operator agreements; owner authorization; Square sandbox success, duplicate, failure, UNKNOWN, reversal and reconciliation; webhook signature/dedup; internal ledger source of truth; separate live-money authorization. | **NONE.** No current-head workflow demonstrates the complete sandbox matrix plus counsel and signed-partner evidence. General PR CI does not prove this gate. Live payment remains disabled. **NOT ACCEPTED.** |

## 5. Component-level status

| Component | Level | Current-head SHA | Evidence | Gates satisfied | Gates remaining | Blockers |
|---|---|---|---|---|---|---|
| Runtime manifest registration (PR #185) | Implemented | `a7174d45a02cc6b8312a00b1ca31671019726728` | New-head CI: 4/13 completed successfully, 9/13 in progress. Prior head `0431dbaf...` had 13/13 green and DB-01–DB-14 14/14 PASS. | DB-01–DB-14 on prior head only | GATE-01 through GATE-05; current-head DB rerun | Current-head Full suite #1132 and DB authority #1203 pending; prior full suite had 7 skips; owner final SHA-specific approval required. |
| Evidence-linked damage reports (PR #186) | Verified on prior stack | `0a4b6087049d2483d8cf4ecc68fa0faaaa3126de` | 13/13 workflows green; Full suite #1129; DB authority #1200; Integrated smoke #675; 409/409 DB tests, zero DB skips; DB-01–DB-14 14/14 PASS. | DB-01–DB-14 on this stack head | GATE-01 through GATE-05; rebase verification | Current PR #186 base is old PR #185 head `0431dbaf...`; rebase onto new PR #185 head and rerun all workflows; prior full suite had 7 skips; stale PR description needs reconciliation. |
| Persistent integrated staging | Designed | No deployed revision | No deployment run | None | GATE-04, GATE-05 | Written plan and approved spending ceiling required before provisioning. |
| Physical-device qualification | Designed | No qualified device revision | No physical-device run | None | GATE-06 | Physical iPad Pro 11-inch M5 qualification absent. |
| Square sandbox reconciliation | Designed / implementation status not established here | No current-head SHA/run established | No complete current-head sandbox evidence located | None | GATE-01, GATE-07 | Full success/duplicate/failure/UNKNOWN/reversal/reconciliation matrix and signed governance terms absent. |

Levels are component-specific. Verified does not mean Deployed or Operational. The 7 full-suite skips remain a merge-readiness blocker even though the relevant database authority lanes have zero skips and formally award 14/14 DB gates.

## 6. PR-specific acceptance criteria

### PR #185 — runtime manifest registration

The current exact-head HTTP/PostgreSQL test is `tests/database/test_capture_http_integration.py::test_authenticated_http_capture_survives_runtime_restart_and_fails_closed`, exercised by Full suite #1125 and DB authority #1196 at candidate SHA `0431dbaf6e1a3bb3348f6d94c094e893543e513c`.

1. **Persistent registration:** migration `0030_runtime_manifest_registration.sql` registers the sealed root in PostgreSQL authority in the live seal transaction. The test reads the persisted `faos.manifest_roots` row.
2. **Idempotency:** replaying the same seal request returns `root_registered: true`, `replayed: true`, and the same manifest digest. The service checks the existing event ID and returns before appending another `MANIFEST_SEALED` event; the SQL registration returns REGISTERED/DUPLICATE and verifies the binding.
3. **Restart survival:** a separate Python process reconstructs the reviewer API using PostgreSQL journal rows and the durable original-byte store, retrieves the manifest and original bytes, then a fresh runtime verifies the persisted root.
4. **Independent verification:** fresh runtime verification checks the registered root binding and reads the original object through the byte store, recomputing SHA-256 against the persisted manifest digest.
5. **Tamper rejection:** mutating a persisted original produces HTTP 409 `EVIDENCE_ARTIFACT_INTEGRITY_FAILURE`, a durable `ARTIFACT_INTEGRITY_FAILURE_RECORDED` event with artifact ID/digest/failure code, and an idempotent repeat read.

The code's seal replay path checks the existing journal event ID before append and the integration test asserts the replay response and unchanged manifest digest. A direct before/after row-count assertion for duplicate `MANIFEST_SEALED` events would further harden the evidence; it is a recommended test refinement, not a known runtime defect.

### PR #186 — evidence-linked damage assessment reports

The current branch's `database/capture_evidence.py` implements `record_damage_assessment_report` and `retrieve_damage_assessment_report`. PDF and JSON carrier bytes are stored in the durable artifact store; the PostgreSQL journal event `DAMAGE_ASSESSMENT_REPORT_GENERATED` stores immutable storage keys, digests, manifest digest, seal event, protocol version, report revision, request digest, finding IDs and review-event binding. Retrieval rebuilds metadata from the journal and reads objects by key with expected-digest verification.

The current HTTP integration test exercises:
1. **Immutable source reference:** original artifact ID, storage key and SHA-256 are carried in the report; the original source byte sequence is not substituted by PDF bytes. Embedded PDF visuals are derived renderings, while the immutable source remains addressable by key/digest.
2. **Per-box provenance:** slot ID, normalized bounding box, camera-angle metadata, reviewer actor/time and non-null source-image reference are present and tied to the sealed manifest.
3. **Disclosure parity:** PDF and JSON both contain: **“A bounding box is a suspect-region identifier only. It is not a measured dimension, calibrated geometry, or a structural-severity claim.”**
4. **Durable report registry:** event-journal metadata and PDF/JSON objects survive fresh-runtime and separate-interpreter retrieval.
5. **Tamper audit:** mutation of persisted PDF bytes fails closed with HTTP 409 and a durable integrity-failure event.

All five behaviors have implementation and current-head test evidence on SHA `0a4b6087049d2483d8cf4ecc68fa0faaaa3126de`; all 13 workflows passed. The PR description still says report versions are process-memory-only, which is stale relative to code/tests and should be reconciled before final owner review. PR #186 must be rebased and rerun after PR #185 merges.

## 7. Live-source discrepancies and historical facts

### 7.1 PR #29 state

The condensed snapshot said PR #29 was Draft/unmerged. Live GitHub reports PR #29 **merged on 2026-11-11**, merge commit `3aa87f9d1523a68a1df09c6930ab57efbd182ba4`, merged head `25b1067d87649318d518f49ab2e12f1a905a2acc`, 296 commits and 103 changed files. Current main later advanced to `55f69790df123a4602196c3c474e143808c4b87e`. The PR description was updated to identify this historical merge and retain the old snapshot as an appendix. No revert or history rewrite was performed. The merge does not imply release acceptance or deployment.

### 7.2 Capture protocol identifiers

The owner directive's canonical identifiers are `12-v1` and `16-v1`. Live code sets `DEFAULT_CAPTURE_PROTOCOL = claims2car-16-v1`, preserves `claims2car-12-v1`, and also exposes `claims2car-16-v2` as a distinct FAOS protocol. The repository's versioning document records the exact 16-v1 view list as owner-approved on 2026-11-11. Preserve all persisted protocol identities; never alias 16-v2 to 16-v1 or reinterpret historical sessions. The additional 16-v2 implementation is a source discrepancy against the owner's current canonical version list and must remain separate/non-default absent explicit owner amendment.

### 7.3 Commercial controls

Canonical record remains `OPERATOR_PAYOUT_USD = 110.0`; disabled, zero active payout code path, no ledger emission, no payout report/API surface, owner approval pending. An unsigned draft proposing $100 does not amend this. Owner cash incentive remains prohibited. Dealer fee $375 is earned only on authorized qualified total-loss acquisition close; shop fee $275 on recorded vehicle acceptance. Square sandbox only; webhooks are reconciliation inputs, never payment authorization; internal ledger is authoritative.

## 8. Owner and environment approvals

| Approval / condition | Required approver | Current status |
|---|---|---|
| DB-01–DB-14 technical acceptance | Executable authority workflow artifact | 14/14 PASS on PR #185 #1196 and PR #186 #1200; rerun after rebase/source change |
| GATE-01 governance/commercial compliance | Owner and counsel where applicable | Pending |
| GATE-05 persistent staging cost ceiling | Owner, after provider/region/cost/backup/restore/secrets/monitoring plan | Pending; no provisioning |
| GATE-06 physical device qualification | Owner after physical-device evidence review | Pending |
| GATE-07 live payment authorization | Separate written owner authorization after counsel, agreements and sandbox reconciliation | Not authorized |
| Operator compensation | Owner | $110.00 canonical record; disabled; approval pending |

No staging provisioning, live money movement, dispatch, real participant data, or production exposure is authorized by this registry.

## 9. Change control

- Refresh this registry only with exact current refs, workflow run numbers, run URLs, artifact IDs/digests, environment identity and test results.
- A new source SHA or rebase invalidates prior exact-head proof until workflows and artifacts are rerun.
- A DB gate pass cannot be promoted to a release-gate pass without the additional evidence in Section 4.
- Do not weaken, rename, remove or bypass any DB or release gate.
- PR #185 and PR #186 remain unmerged until zero-skip merge conditions, exact-head evidence, PR #186 rebase, and owner SHA-specific approval are satisfied.
- This registry PR does not modify main, merge other PRs, provision infrastructure, or activate payments/dispatch.
