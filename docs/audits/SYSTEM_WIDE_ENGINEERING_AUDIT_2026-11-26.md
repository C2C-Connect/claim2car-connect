# Claim2Car Connect — System-Wide Engineering Audit (26 November 2026)

**Repository:** `C2C-Connect/claim2car-connect`  
**Status:** Source-level audit reconciled with live pull-request search, selected source files and workflow evidence. Not a penetration test, legal opinion, field qualification, forensic validation or release acceptance.

## Executive conclusion

Claim2Car has a substantial software foundation: tenant-scoped PostgreSQL authority, persistent event hashing/readback, encrypted browser evidence queue, capture and consent workflows, server manifest-root registration recorded as merged in PR #185, and a new executable evidence substantiation contract in PR #195. The project is not ready for real participant evidence or field/staging release.

The largest remaining gaps are: post-merge M1 exact-main verification; complete consent deletion/revocation lifecycle; storage encryption and backup/restore proof; identity lifecycle; one canonical workbench and consistent capture protocol; physical-device qualification; durable evidence-linked reports; source-backed OEM/parts/valuation/jurisdiction data; operational monitoring; and persistent integrated deployment.

## Live checkpoint and evidence

| Item | Observed state | Audit interpretation |
|---|---|---|
| PR #185 | Recorded merged at `590724597a65395ece225128b40ec48fa6ece34b` | Candidate head `a7174d45a02cc6b8312a00b1ca31671019726728` had 13/13 workflow types and DB-01–DB-14 14/14 (408/408 counted DB tests). Post-merge exact-main verification remains required. |
| PR #195 | Open/draft; contract source and tests exist on branch | Exact head `934f7cca7ff9d145d2a187f444c9bbcc4422c0f8`; 13/13 workflow types successful; full suite 1,082 passed, 7 skipped, 218 subtests; DB authority 415/415, 14/14 technical gates. Contract checks are not sensor or measurement validation. |
| PR #196 | Open; owner-bound consent deletion retry implementation exists | PR audit checkpoint says fixture corrected and exact-head rerun pending. Workflow runs were visible on a branch commit but could not be conclusively tied to the latest corrected head. Treat as unaccepted until exact-head CI is verified. |
| PR #186 | Open; stale/stacked report implementation | Shared capture/storage files conflict with merged #185 base. Rebase and rerun all checks; prior green runs are stale. |
| PR #187 | M1 registry narrowed to intake/preservation | Correctly excludes advanced LiDAR/physics/AI adjudication, payments, dispatch and marketplace from M1 acceptance. Refresh statuses against #185/#195/#196. |
| PR #194 | Open/draft audit PR | Valuable source-level audit; update its findings and dispositions before treating as current canonical audit. |
| PR #188 | OCI staging proposal | Documentation only; no infrastructure provisioning or deployment evidenced. |

**Documentation drift confirmed:** README still calls #185 pending and points to an older M1 task; acceptance matrix still says #182 is latest and migration 0029 is next; handoff/status/product premise/FAOS guide/program contain older active checkpoint text; legal checklist contains legacy score, WORM, VIN, AI, blockchain and legal claims without a current evidence status. The current main HEAD at PR #197 creation was confirmed by the PR base reference as `590724597a65395ece225128b40ec48fa6ece34b` (PR #185 merge commit). The combined-status endpoint returned no status entries for that merge SHA in this pass; therefore post-merge exact-main workflow evidence was not established.

## Priority findings

1. **M1 post-merge verification (P1):** PR #185 merge is recorded, but candidate-head success is not post-merge main verification. Verify current main, migration 0030, seal/root registration, review queue/details/artifact retrieval, seal actor binding, chain/context binding and original-byte verification.
2. **Consent withdrawal/deletion (P1):** PR #196 addresses same-owner retry after transient original deletion failure. It does not provide a durable per-artifact deletion outbox/receipt, derivative/report cleanup, backup lifecycle, offline-device cleanup acknowledgement or legal-hold semantics.
3. **Storage encryption/recovery (P1):** POSIX artifact storage hashes and verifies bytes but application-level encryption is not established by source inspection. Verify encrypted volume/object store, key custody/rotation, backup/PITR, witnessed restore, orphan reconciliation and cross-store crash recovery.
4. **Identity lifecycle (P1):** static out-of-band credentials lack owner proofing, recovery, self-service rotation and live revocation workflow. Not field-ready identity.
5. **Dual workbenches (P1):** root `/` and `/prototype` remain separate workflow/UI surfaces. Queue cryptography was aligned, but protocol and UX drift remain.
6. **Capture protocol/data minimization (P1):** 16-v1 remains default in the root workbench and includes driver's-license/insurance-document slots; 16-v2 is selectable but not the default. Resolve default and disclosure policy, preserve immutable version identity and separately authorize supplemental documents.
7. **Quality semantics (P2):** persisted quality is advisory/client-asserted Boolean, not independently recomputed metrics tied to the exact original. Keep advisory; do not promote to verified fact.
8. **Reports (P1):** current-main legacy report paths accept caller-asserted values and process-memory versions. PR #186 is the candidate durable report path but is stale and unrebased.
9. **AI/physics (P1):** legacy analysis is synthetic or caller-fed, not validated vehicle-image inference. Fixed 55/45 voting is not a calibrated probabilistic method. Keep consequential inference disabled/advisory.
10. **ACV/jurisdiction/parts (P1):** ACV fallback curve lacks comparable source records; jurisdiction table lacks per-rule authority/effective dates and uses a generic fallback; parts resolver uses synthetic seed catalog rather than verified OEM/CAPA data.
11. **Dispatch/payments (P1):** direct dispatch construction is fail-closed by PR #193; retain this containment. No live commercial lifecycle, dispatch, settlement or reconciliation acceptance is established.
12. **Device/field qualification (P1):** no physical iPad reference unit has passed camera/original-byte, calibration metadata, offline recovery, thermal/battery, accessibility and roadside pause/abort qualification.
13. **Operations/deployment (P1):** encrypted remote backups, retention/immutability, PITR, witnessed restore, monitoring, alerting, incident runbooks and persistent integrated staging are not established.

## PR #195 contract review

The executable contract defines:
- Original vs derivative artifact lineage; originals cannot declare transformations.
- Acquisition modality, UTC timestamp/time source, actor/device, raw-unmodified flag, sensor metadata and optional camera calibration metadata.
- Advisory quality assessments with threshold policy/version.
- Measurements with source acquisition IDs, method/version, units, coordinate frame, calibration acquisition IDs and explicit uncertainty.
- Inferences with evidence references, method/version, proposition/result/status, calibrated-confidence guard, assumptions, alternatives, missing inputs, source references and vehicle applicability.
- Human decisions with inference references, action, reason codes, actor and time.
- Custody attestation with chain tip/sequence/version, manifest digest, Merkle tree version/leaf count, storage claim and qualified-certifier fields.
- Cross-layer reference validation.

This is a valuable contract increment. It does not itself acquire AVCameraCalibrationData, validate LiDAR, prove calibration suitability, establish physical WORM, validate CRASH3, validate OEM rules, train/validate models or certify legal evidence. Reconcile naming/invariants with existing domain types before merging; do not create a parallel model.

## M1 acceptance truth

M1 is intake and evidence preservation, not automated damage adjudication. Required proof:
- Authenticated operator, tenant and device/session attribution.
- Purpose-specific consent and safe withdrawal.
- Immutable protocol identity; 16-point accounting with exceptions, retakes and 12-slot legacy interpretation.
- Original bytes and manifest binding.
- Offline/restart/retry synchronization with durable idempotency.
- Server-side event-chain and original-artifact verification; fail closed on tampering.
- Authorized reviewer retrieval and attributable human decision.
- Operational readiness: encryption, backup/restore, device qualification, monitoring, support and controlled demonstration.

M1 remains **NOT ACCEPTED**. Candidate CI and technical database gates are component evidence only.

## Remediation sequence

1. Verify #185 on current main and close any post-merge M1 gaps.
2. Verify #196 exact corrected head; then implement durable deletion receipts/outbox, derivative/report/backup/device semantics.
3. Merge/reconcile #195 contract after review and exact-head verification; bind it to actual domain service boundaries.
4. Rebase #186 onto current main and make reports durable, server-derived and source-linked.
5. Choose one canonical operator workbench; resolve v1/v2 capture protocol and sensitive-document defaults.
6. Implement owner/operator identity lifecycle.
7. Provision approved persistent PostgreSQL/PostGIS and encrypted object storage; establish backup/PITR and demonstrate restore; instrument operations.
8. Source-back OEM/CAPA, ACV and jurisdiction rules; unknown inputs abstain.
9. Qualify exact physical devices and roadside workflows.
10. Build one controlled measurement/AI vertical slice with synthetic known-answer tests, independent references and held-out validation.
11. Keep payments, partner distribution, dispatch and navigation behind separate release gates.

## Documentation recalibration targets

- README, execution handoff/status and thread handoff: one current top checkpoint; old dated snapshots explicitly historical.
- Acceptance matrix and PR #187 registry: M1 gates, exact evidence, #185 merged, #195 contract-only, #196 pending, field/deployment not accepted.
- Product premise, FAOS guide, forensic program and complete spec: four-layer taxonomy, evidence/uncertainty/abstention, corrected technical claims and M1 exclusions.
- Legal review: replace legacy checklist with claims register and statuses; withdraw unsupported claims; keep owner cash incentive prohibited.
- Historical repositories/branches: inventory and mark reference-only; no bulk deletion of code/history.

## Audit limitations

This audit reconciles the 24 November source-level audit with current PR descriptions, changed-file inventories, selected source code, acceptance registry and workflow runs. It does not repeat every adversarial test against a deployed environment. It does not establish current cloud resource state, protected secrets, external provider accounts, physical device behavior or production monitoring. Main HEAD was confirmed as `590724597a65395ece225128b40ec48fa6ece34b`; post-merge #185 workflow status was not established in this pass. No deployment, participant evidence, live payment or dispatch is authorized by this report.
