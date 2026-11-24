# Claim2Car Connect — Release Acceptance Registry and DB Crosswalk

**Document ID:** C2C-REL-AC-001  
**Version:** 1.0 — execution registry  
**Snapshot:** 2026-11-24 22:54 UTC  
**Repository:** `C2C-Connect/claim2car-connect`  
**Base revision for this registry branch:** `55f69790df123a4602196c3c474e143808c4b87e`  
**Authority:** Current owner Developer Execution Directive. This registry does not amend owner decisions or award acceptance.

## 1. Governing rule

The seven release gates (GATE-01 through GATE-07) are a release-level acceptance layer. The fourteen database gates (DB-01 through DB-14) are a database-foundation subset. Passing some or all DB gates does **not** pass a release gate, certify the product, establish deployment, or authorize operational use.

The owner directive sets the current certification baseline at **0/14 DB gates certified for this release record; overall release acceptance NOT ACCEPTED**. The repository's older acceptance matrix records a historical 14/14 database award against an earlier candidate. That historical result is retained as history only and is not silently promoted into current release certification. The current PR #185 database-authority workflow is candidate evidence, not a release award, until its exact artifact is reviewed and the owner-directed registry criteria are satisfied.

No gate passes on a green workflow badge alone. Each pass requires the named executable checks, a clean current-head run in the required environment, retained evidence, and the required approver. Skipped, cancelled, queued, stale, placeholder, synthetic-only, or environment-mismatched results do not pass a gate.

## 2. Current repository and workflow evidence snapshot

### 2.1 Live refs

| Ref | State | Exact SHA | Use in this registry |
|---|---|---|---|
| `main` | Current base observed | `55f69790df123a4602196c3c474e143808c4b87e` | Registry base; no current-head workflow proof retrieved in this snapshot |
| PR #185, `cto/m1-runtime-manifest-registration` | Open, not merged | `0431dbaf6e1a3bb3348f6d94c094e893543e513c` | M1 manifest-registration candidate |
| PR #186, `feat/evidence-linked-damage-assessment-pdf` | Open, not merged; stacked on PR #185 | `0a4b6087049d2483d8cf4ecc68fa0faaaa3126de` | Evidence-linked report candidate |

PR #186 must not merge before PR #185 is accepted, merged, and PR #186 is rebased and reverified against the resulting main revision.

### 2.2 Exact-head workflow runs observed

**PR #185 — SHA `0431dbaf6e1a3bb3348f6d94c094e893543e513c`**

| Workflow | Run | Result at snapshot | Evidence |
|---|---:|---|---|
| Full test suite | #1125 | Success | https://github.com/C2C-Connect/claim2car-connect/actions/runs/45502012107 |
| Database authority cutover | #1196 | Success; artifact retained, artifact contents not yet independently inspected | https://github.com/C2C-Connect/claim2car-connect/actions/runs/45502012240 |
| Legacy database component | #1240 | Success | https://github.com/C2C-Connect/claim2car-connect/actions/runs/45502012125 |
| FastAPI foundation | #1182 | Success | https://github.com/C2C-Connect/claim2car-connect/actions/runs/45502012063 |
| Integrated runtime container smoke | #671 | In progress after targeted rerun; result pending | https://github.com/C2C-Connect/claim2car-connect/actions/runs/45502012031 |
| Other PR workflows | 8 additional workflow types | Success | Exact run inventory is available from the PR head's workflow-run listing |

The cancelled integrated-runtime run is not a pass. The targeted rerun request is not a result.

**PR #186 — SHA `0a4b6087049d2483d8cf4ecc68fa0faaaa3126de`**

| Workflow | Run | Result at snapshot | Evidence |
|---|---:|---|---|
| Full test suite | #1129 | Success | https://github.com/C2C-Connect/claim2car-connect/actions/runs/45504282583 |
| Database authority cutover | #1200 | In progress | https://github.com/C2C-Connect/claim2car-connect/actions/runs/45504282825 |
| Integrated runtime container smoke | #675 | In progress | https://github.com/C2C-Connect/claim2car-connect/actions/runs/45504282240 |
| Legacy database component | #1244 | Success | https://github.com/C2C-Connect/claim2car-connect/actions/runs/45504282176 |
| FastAPI foundation | #1186 | Success | https://github.com/C2C-Connect/claim2car-connect/actions/runs/45504282314 |
| Controlled-test intake PostgreSQL | #1032 | Success | https://github.com/C2C-Connect/claim2car-connect/actions/runs/45504282358 |
| Browser IndexedDB queue | #795 | Success | https://github.com/C2C-Connect/claim2car-connect/actions/runs/45504282214 |
| Offline VIN lookup controller | #1033 | Success | https://github.com/C2C-Connect/claim2car-connect/actions/runs/45504282594 |
| Restricted intake container | #1017 | Success | https://github.com/C2C-Connect/claim2car-connect/actions/runs/45504282442 |
| Frontend VIN/decoder/transport | #1172 | Success | https://github.com/C2C-Connect/claim2car-connect/actions/runs/45504282245 |
| Offline guided capture | #993 | Success | https://github.com/C2C-Connect/claim2car-connect/actions/runs/45504282431 |
| Controlled synthetic demonstration | #991 | Success | https://github.com/C2C-Connect/claim2car-connect/actions/runs/45504282508 |
| Restricted container | #629 | Success | https://github.com/C2C-Connect/claim2car-connect/actions/runs/45504282469 |

A workflow being in progress is not a pass. These runs prove only the workflow results at the listed SHA; they do not independently prove a release gate.

## 3. Database gate registry — DB-01 through DB-14

**Required environment:** isolated synthetic PostgreSQL 16 with PostGIS 3.4 and required extensions; separately identified admin, migrator, and restricted application roles; full ordered migration inventory; no production credentials or participant data.  
**Executable runner:** `python tests/database/verify_gates.py` after the counted database suite and post-cutover diagnostics.  
**Approver:** Product Owner for formal acceptance; independent review status must be stated accurately and may not be implied.  
**Current result for this release registry:** all 14 are **NOT CERTIFIED** pending a complete, exact-head, artifact-reviewed acceptance record under this directive.  
**Blocking:** Yes, DB-01 through DB-14 are release-blocking through GATE-02 and other dependent release gates.

| Gate | Requirement | Required executable test selectors / SQL evidence | Current result | Required evidence / environment | Blocking |
|---|---|---|---|---|---|
| DB-01 | Reproducible environment and configuration | `test_candidate_manifest.CandidateManifestTests.*`; `test_migration_plan.MigrationPlanTests.*`; `test_migration_preflight.MigrationPreflightTests.*`; clean full initialization and legacy-upgrade integration tests | NOT CERTIFIED | Sanitized environment manifest, explicit connection identities, extensions, clean startup and rerun logs, migration inventory | Yes |
| DB-02 | Migration integrity and schema versioning | `test_migration_plan.MigrationPlanTests.*`; `test_migration_preflight.MigrationPreflightTests.*`; `test_migration_controls_integration.MigrationControlsIntegration.*`; candidate-manifest tests | NOT CERTIFIED | Empty-database apply, ordered migration versions and SHA-256 inventory, failure/recovery and rollback evidence | Yes |
| DB-03 | Restricted application privileges | `test_access_hardening.TestAccessHardening.*`; `test_adapter_validation.TestAdapterValidation.*`; `test_identity_boundary.IdentityBoundaryTests.*`; tenant-authority registry denial; completion and manifest-root application-role denial | NOT CERTIFIED | Effective privilege matrix and negative SQL assertions in PostgreSQL under application role | Yes |
| DB-04 | Tenant isolation and forced RLS | `test_remaining_integration.TestRemainingIntegration.*`; `test_identity_bound_prototype.IdentityBoundPrototype.*`; `test_schema_integrity.SchemaIntegrityTests.*`; `test_tenant_authority_integration.TenantAuthorityIntegration.*`; checks G04-DIRECT-SQL-TENANT-SWITCH, UNBOUND-SHARED-LOGIN-DENIED, POSTCUTOVER-PER-TABLE-ISOLATION | NOT CERTIFIED | Full per-table forced-RLS inventory; two-tenant adversarial matrix; direct SQL and spoofed-context denials | Yes |
| DB-05 | Tenant-context lifecycle | `test_tenant_context_regression.TenantContextRegression.*`; `test_completion_lock.CompletionLockTests.*`; `test_locked_evaluation.LockedEvaluationTests.*` | NOT CERTIFIED | Commit, rollback, exception, pool-reuse, missing-context and tenant-switch traces | Yes |
| DB-06 | Event schema and domain-contract validation | `test_event_contract_regression.EventContractRegression.*`; adapter validation; SQL/Python parity and historical-payload-preservation integration tests; timestamp, compact JSON, key-order, numeric-spelling and Unicode SQL checks | NOT CERTIFIED | Canonical event contract, timezone-aware timestamp checks, Python/SQL parity, valid/invalid fixtures | Yes |
| DB-07 | Durable event append and idempotency | `test_journal_integration.TestJournalIntegration.*`; bound-login append/retry/readback integration; event-contract regression | NOT CERTIFIED | Persisted append/readback, identical retry, conflicting key reuse, transaction interruption and durable idempotency evidence | Yes |
| DB-08 | Sequence integrity and concurrent writes | `test_journal_integration.TestConcurrentJournal.*`; `test_completion_concurrency.CompletionConcurrencyTests.*`; completion-lock tests | NOT CERTIFIED | Repeated concurrent writers, ordering/sequence histories, deterministic conflict/retry outcomes | Yes |
| DB-09 | Event immutability and history integrity | Access-hardening, event-contract and journal-integration tests; historical payload preservation and noncanonical-history rejection | NOT CERTIFIED | INSERT/SELECT-only journal privilege evidence, mutation-denial tests, chain recomputation and tamper results | Yes |
| DB-10 | Evidence-manifest integrity and root registration | `test_completion_coverage.CompletionCoverage.*`; `test_manifest_roots.ManifestRootTests.*`; `test_registered_completion.RegisteredCompletionTests.*`; 16-v1 protocol-binding integration | NOT CERTIFIED | Expected digest fixtures, root-to-session/tenant/protocol binding, duplicate/conflict/cross-tenant and tamper tests | Yes |
| DB-11 | Completion receipts and protected completion state | `test_completion_receipts.CompletionReceiptTests.*`; `test_atomic_completion.AtomicCompletionTests.*`; `test_completion_concurrency.CompletionConcurrencyTests.*` | NOT CERTIFIED | Authorized creation, protected-table privilege denials, duplicate/conflict and receipt-to-root consistency | Yes |
| DB-12 | Revocation, tampering, and invalidation | Atomic-completion, registered-completion, receipt-inspection and persisted-evidence-recovery tests; BINDING-REVOCATION-NEXT-TRANSACTION SQL check | NOT CERTIFIED | Revocation/tamper/missing-reference cases; downstream fail-closed reads; durable audit evidence | Yes |
| DB-13 | Restart, recovery, and replay | `test_process_recovery.ProcessRecovery.*`; `test_process_recovery.PersistedEvidenceRecovery.*`; receipt-inspection and tenant-authority vertical-slice tests | NOT CERTIFIED | Before/after persisted snapshots, process restart, independent readback, replay and invalid-history tests | Yes |
| DB-14 | Failure handling, end-to-end acceptance, and evidence reporting | `test_counted_runner.CountedRunnerTests.*`; `test_evidence_finalizer.EvidenceFinalizerTests.*`; all preceding gate checks in one run | NOT CERTIFIED | Machine-readable same-run report, exact source SHA, migration inventory, environment, zero skipped tests, artifacts and overall NOT ACCEPTED/ACCEPTED result | Yes |

The selectors above are sourced from `tests/database/verify_gates.py`; they are not a substitute for executing the runner. The runner's mapped test identifiers and SQL checks must be present in the retained report.

## 4. Release gate crosswalk — GATE-01 through GATE-07

Every row explicitly lists its database dependencies, additional evidence not supplied by DB gates, and current-head workflow proof. The listed DB dependencies are necessary supporting controls only; they never satisfy the release gate by themselves.

| Release gate | DB dependencies | Additional evidence DB gates do not provide | Current-head workflow proof |
|---|---|---|---|
| **GATE-01 — Governance and commercial compliance** | DB-06, DB-07, DB-09, DB-11, DB-12, DB-14 | Owner-approved commercial terms; prohibited owner incentive blocked in contracts, denylist, tests and ledger; operator compensation remains disabled; dealer/shop fee earning events; signed partner terms; counsel review; documented authority for consent, distribution, payment and dispatch. | **NONE.** PR #185 Full suite #1125 (SHA `0431dbaf6e1a3bb3348f6d94c094e893543e513c`) and DB authority #1196 are technical evidence only, not owner/counsel/partner approvals. No current-head workflow can substitute for signed governance evidence. |
| **GATE-02 — Security and database authority** | DB-01 through DB-14 (all fourteen) | Application/API authorization, server-derived actor and tenant, forced RLS across all tenant tables, private internal routes, secret handling, TLS configuration, threat review, and evidence that the deployed configuration matches the tested configuration. | Candidate exact-head evidence: PR #185 DB authority cutover #1196 and Full suite #1125 at SHA `0431dbaf6e1a3bb3348f6d94c094e893543e513c`. The authority artifact has not yet been independently inspected; current certification remains NOT CERTIFIED. PR #186 DB authority #1200 at SHA `0a4b6087049d2483d8cf4ecc68fa0faaaa3126de` is still in progress. |
| **GATE-03 — Operator and reviewer product experience** | DB-03, DB-04, DB-05, DB-06, DB-07, DB-08, DB-09, DB-13, DB-14 | Usable authenticated operator and reviewer journey; consent UX; protocol version shown to every consumer; VIN and capture workflow; reviewer access to original bytes; attributed review and reason; human usability and error recovery. | Candidate exact-head evidence: PR #185 Full suite #1125 and FastAPI #1182 at SHA `0431dbaf6e1a3bb3348f6d94c094e893543e513c`. Integrated runtime smoke #671 was cancelled and its targeted rerun is pending. No operational journey is certified. |
| **GATE-04 — Durable storage, consent-deletion and PITR drills** | DB-01, DB-02, DB-04, DB-07, DB-09, DB-10, DB-12, DB-13, DB-14 | Durable immutable original-byte storage; deletion of original bytes and mutable incident rows on withdrawal; durable revocation journal event; downstream fail-closed behavior; encrypted storage; backup policy; point-in-time recovery and witnessed restore drill; post-restore integrity verification. | Candidate exact-head evidence: PR #185 DB authority #1196 and Full suite #1125 at SHA `0431dbaf6e1a3bb3348f6d94c094e893543e513c`. No current-head object-store deletion proof or PITR/restore drill is recorded. **No gate proof.** |
| **GATE-05 — Persistent integrated staging** | DB-01, DB-02, DB-03, DB-04, DB-05, DB-07, DB-08, DB-09, DB-10, DB-11, DB-12, DB-13, DB-14 | Actual persistent integrated environment: PostgreSQL 16/PostGIS 3.4, durable encrypted object storage, real auth, TLS, managed secrets, backups and restore drills, monitoring/alerts, deployed immutable image, and a successful operator-to-reviewer journey after restart. Restricted Railway/container smoke is not staging. | PR #185 Integrated runtime smoke #671 was cancelled; targeted rerun requested. PR #186 Integrated runtime smoke #675 is in progress at SHA `0a4b6087049d2483d8cf4ecc68fa0faaaa3126de`. Neither is persistent staging proof. **No gate proof.** |
| **GATE-06 — Physical-device qualification** | DB-04, DB-05, DB-07, DB-10, DB-13 | Physical reference iPad Pro 11-inch M5 qualification; recorded device and OS; camera capture, framing, low-light and motion cases, offline interruption/recovery, queue encryption at rest, upload/retry, thermal and battery behavior. Simulator and desktop browser runs do not qualify. | **NONE.** No current-head physical-device workflow or signed device qualification report was found. |
| **GATE-07 — Counsel, partner agreements and sandbox reconciliation before live payment** | DB-06, DB-07, DB-08, DB-09, DB-11, DB-12, DB-13, DB-14 | Counsel sign-off; signed dealer/shop/operator agreements; owner authorization; Square sandbox success, duplicate, failure, UNKNOWN, reversal and reconciliation scenarios; webhook signature/dedup evidence; internal ledger as source of truth; explicit live-money release authorization. | **NONE.** No current-head workflow run in this snapshot demonstrates the complete required sandbox reconciliation matrix plus counsel and signed-partner evidence. PR #185/#186 general CI does not prove this gate. |

**Zero-dependency declaration:** No release gate is assigned zero DB-gate dependencies in this crosswalk. If later evidence shows a release gate has no DB dependency, it must be recorded as `NONE — no DB-gate dependency` explicitly rather than left blank.

## 5. Component-level acceptance status

| Component | Level | Current-head SHA | Workflow evidence | Gates satisfied | Gates remaining | Blockers |
|---|---|---|---|---|---|---|
| Runtime manifest registration (PR #185) | Implemented | `0431dbaf6e1a3bb3348f6d94c094e893543e513c` | Full suite #1125, DB authority #1196, FastAPI #1182 passed; integrated smoke #671 rerun in progress | None formally awarded by this release registry | GATE-02, GATE-03, GATE-04, GATE-05; DB-01–DB-14 certification | Independent inspection of authority artifact; completed integrated smoke rerun; prove restart, idempotency, independent verification, tamper rejection and audit at exact current head |
| Evidence-linked damage reports (PR #186) | Implemented | `0a4b6087049d2483d8cf4ecc68fa0faaaa3126de` | Eleven of thirteen listed workflow runs completed successfully; two are in progress at snapshot | None formally awarded by this release registry | GATE-02, GATE-03, GATE-04, GATE-05; DB-01–DB-14 certification | Complete all exact-head workflows; durable report registry; restart retrieval; immutable original-byte reference; per-box source linkage and disclosure; PDF/JSON parity; tamper audit; rebase after PR #185 |
| Persistent integrated staging | Designed | No deployed revision | No deployment run proving persistent staging | None | GATE-04, GATE-05 and all dependent gates | No approved cost ceiling and no completed provisioning/deployment evidence |
| Physical-device qualification | Designed | No qualified device revision | No physical-device run | None | GATE-06 | Physical iPad Pro 11-inch M5 qualification evidence absent |
| Square sandbox reconciliation | Implemented status not established by this registry | No current-head SHA/run established | No complete current-head sandbox evidence located | None | GATE-01, GATE-07 | Success/duplicate/failure/UNKNOWN/reversal/reconciliation evidence and signed governance terms absent |

Levels are deliberately conservative. A workflow result does not upgrade a component to Verified unless all relevant tests pass at that exact SHA and the gate-specific evidence is retained. Deployed and Operational require the actual persistent staging environment and a demonstrated operator-to-reviewer journey.

## 6. PR-specific acceptance criteria carried into this registry

### PR #185 — runtime manifest registration

Before it can be considered Verified or merged, current-head evidence must prove all of the following:

1. A sealed manifest is durably registered in PostgreSQL's event/manifest authority; no process-memory-only or runtime-derived substitute.
2. Exact seal retries are idempotent and return the existing registered reference without duplicate journal entries.
3. A process restart immediately after sealing preserves manifest retrieval, verification, and linkage to original bytes.
4. A fresh runtime independently recomputes the manifest root from persisted bytes and verifies `link_k = SHA-256(content_k || link_{k-1})`.
5. A one-byte persisted-artifact mutation fails closed and writes a durable audit event; no unhandled exception or silent success.

Current candidate: SHA `0431dbaf6e1a3bb3348f6d94c094e893543e513c`. The DB authority run #1196 and Full suite #1125 are green, but the integrated smoke #671 was cancelled and is being rerun. Do not mark Verified until the five criteria are individually evidenced on the final current head.

### PR #186 — evidence-linked damage assessment reports

Before it can be considered Verified or merged, current-head evidence must prove all of the following:

1. Every finding references the original immutable object by storage key and digest; the original bytes remain authoritative and are not replaced by PDF-rendered copies.
2. Every bounding box has `slot_id`, normalized coordinates, camera-angle metadata, reviewer actor and review timestamp, and a non-null source-image reference tied to the sealed manifest.
3. The PDF and JSON carrier payload both contain the disclosure: **“A bounding box is a suspect-region identifier only. It is not a measured dimension, calibrated geometry, or a structural-severity claim.”**
4. Report versions and metadata are held in a durable registry; a fresh process can retrieve the report and verify its digest. In-memory-only versioning is not acceptable.
5. Tampering with a persisted report fails closed and writes a durable audit event.

Current candidate: SHA `0a4b6087049d2483d8cf4ecc68fa0faaaa3126de`. The latest commit adds HTTP assertions for source storage key, SHA-256, reviewer timestamp, disclosure text, and durable tamper audit. The PR description still states that report versions are stored in process memory; that is a merge blocker until replaced with a durable report registry and tested across restart.

## 7. Live-source discrepancies requiring explicit reconciliation

The owner directive's canonical capture identifiers are `12-v1` and `16-v1`. The current repository acceptance matrix on the base revision also describes `claims2car-16-v2` as selectable, `claims2car-16-v1` as the default, and `claims2car-12-v1` as the legacy alternative. This is a material protocol-version naming and default-state discrepancy, not a cosmetic documentation difference.

Until the actual contracts, migrations, API validators, frontend selector, session-creation defaults, and report/reviewer consumers are reconciled against the owner's canonical `12-v1` / `16-v1` decision:
- do not enable or silently rename any protocol;
- do not reinterpret existing sessions;
- persist and display the exact protocol identifier stored at session creation;
- treat any `16-v2` session as a distinct immutable protocol, not as `16-v1`;
- report the discrepancy in every acceptance decision that depends on capture protocol.

The owner directive supersedes stale repository prose where it conflicts, while the live code remains the source of truth for what is actually implemented. This registry does not rewrite historical protocol records or certify compatibility.

## 8. Owner and environment approvals

| Approval / condition | Required approver | Current status |
|---|---|---|
| Formal DB-01–DB-14 acceptance | Owner, with retained exact-head gate report | Pending; 0/14 certified in this release registry |
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
