# Claim2Car — M1 Intake & Evidence Preservation Acceptance Registry

**Document ID:** C2C-M1-AC-001  
**Version:** 2.0.1  
**Scope:** M1 Intake & Preservation only  
**Authority:** Owner-approved M1 boundary. This registry does not authorize field deployment, real participant evidence, payment, dispatch, or marketplace activity.
**Status snapshot:** 2026-11-27. This registry is proposed in open draft PR #187 and is not part of `main` until merged.

## 1. M1 product promise

M1 accepts an authorized incident intake, records consent and actor attribution, captures the versioned 16-point evidence package (with explicit safety exceptions), preserves original bytes, synchronizes reliably across offline/online states, independently verifies the persisted evidence and custody chain on the server, and allows an authorized reviewer to retrieve the evidence and record an attributable decision.

M1 is an evidence intake and preservation product. It is not an automated damage adjudicator.

## 2. Four-layer epistemic boundary

| Layer | M1 status | Rule |
|---|---|---|
| Acquisition | In scope | Preserve original media bytes and available device/sensor metadata. Capture calibration metadata only when the device/API actually supplies it. |
| Measurement | Contracted, not an M1 acceptance claim | Record only measurements with documented method, calibration/reference, coordinate frame and uncertainty. LiDAR volumetric crush measurement is deferred. |
| Inference | Advisory/research only | Preserve source/model/method versions, applicability, assumptions, alternatives and missing priors. CRASH3 and structural-yield inference are not M1 adjudication authorities. |
| Decision | Human-governed | M1 supports authorized review and explicit abstention. No autonomous repairability, total-loss, structural-safety, causation or financial eligibility verdict. |

## 3. M1 acceptance gates

Each gate requires implementation evidence on the current main revision, exact-head automated verification, retained artifacts where applicable, and a controlled end-to-end demonstration. Passing one gate does not silently pass another.

| Gate | Acceptance requirement | Required evidence | Current status |
|---|---|---|---|
| M1-01 Authorization & consent | Authenticated actor and tenant; disclosure version; explicit scope/acceptance; withdrawal and retry semantics fail safely; no consent inferred from session creation. | API/database tests for unauthorized, declined, withdrawn, duplicate, retry, tenant-isolation and audit behavior. | PARTIAL — PR #196 is open/draft at exact head `5b6560082d509c597b1cce68f99c1781a10b80dc` and all 13 workflow types passed. It adds durable intent/receipts for registered originals with owner-triggered retries; derivative/report, backup/PITR, offline-device and legal-hold lifecycle remain open. |
| M1-02 Versioned capture | Exact 16-point protocol identity and ordering; 12-slot legacy sessions remain interpretable; retakes supersede rather than erase; unavailable/unsafe slots are explicit exceptions and never represented as captured. | Protocol contract, operator workflow tests, safety pause/abort tests, quality/retake and package-completeness tests. | IMPLEMENTED IN SOFTWARE / FIELD-UNQUALIFIED — physical device and operator qualification remain open. |
| M1-03 Original evidence preservation | Original bytes, artifact ID, SHA-256, byte length, MIME, actor/session/protocol and immutable storage reference are bound to a registered manifest. Derivatives remain separate and parent-linked. | Original-byte round trip, manifest/artifact binding, mismatch and mutation rejection, fresh-process retrieval. | VERIFIED COMPONENT IN MERGED PR #185; current `main` is `3ee88aa022efb12a2d428ab31f91721eb41bfbcc`. The current combined-status query returned no entries for that SHA, so post-merge exact-main workflow evidence is not established. PR #196 deletion covers registered originals only. |
| M1-04 Offline/online synchronization | Durable encrypted local queue; stable artifact/request IDs; FIFO retry; idempotent server ingest; conflict and partial failure do not silently lose or duplicate evidence. | Browser IndexedDB and API integration tests, interrupted upload/restart/retry and tamper tests. | IMPLEMENTED IN SOFTWARE / FIELD-UNQUALIFIED — field-device recovery qualification remains open. |
| M1-05 Independent server verification | Server recomputes persisted event chain and original artifact digests; registered manifest root is bound to the exact seal event, chain tip/sequence/version, tenant/session/protocol context; failures block downstream use and create durable audit events. | PostgreSQL authority tests, authenticated HTTP seal/replay, fresh-runtime verification, one-byte tamper rejection and tenant isolation. | VERIFIED COMPONENT IN MERGED PR #185; exact-main evidence for current `main` SHA `3ee88aa022efb12a2d428ab31f91721eb41bfbcc` remains unestablished by the available status query. |
| M1-06 Reviewer retrieval & decision | Authorized reviewer retrieves verified originals and manifest; reviewer identity, decision, reason and referenced artifacts are recorded; invalid/unverified context fails closed. | Separate reviewer identity, cross-tenant denial, original retrieval, attributable decision and tamper-failure tests. | VERIFIED COMPONENT IN MERGED PR #185; exact-main integration evidence for current `main` remains unestablished. |
| M1-07 Operational readiness | Consent lifecycle, storage encryption, backup/restore, recovery, monitoring, access/device qualification and a repeatable controlled demonstration are evidenced. | Restore drill, key/access controls, device qualification, monitoring evidence, controlled end-to-end run and incident/recovery procedures. | NOT ACCEPTED — PR #194 audit retains open consent, encryption/backup, device qualification and monitoring findings. |

## 4. Explicitly excluded from M1 acceptance

The following are not M1 acceptance criteria and must not be represented as implemented, validated or accepted by passing M1:

- LiDAR-derived volumetric crush/deformation measurement or point-cloud metrology.
- Autonomous structural-yield, material-strength or hidden-damage adjudication.
- Automated CRASH3 energy/force conclusions, collision causation, roadworthiness, repair authorization or total-loss determination.
- Uncalibrated AI ensemble voting or confidence percentages.
- Financial eligibility, Gold Lead status, dealer/shop marketplace, dispatch, navigation, payment or settlement.
- FRE 902(13)/(14) certification by the platform itself, external notarization, trusted timestamping or public blockchain anchoring.

These may be developed in separately versioned research/telemetry modules behind disabled feature flags. Research telemetry must never alter originals, enter M1 decision authority, or be presented as a validated measurement. Enabling a deferred capability requires its own data contract, validation population, independent measurement reference, uncertainty/error envelope, abstention criteria, security review and explicit acceptance gate.

## 5. Evidence and status vocabulary

Use only these implementation states:

- **Specified:** requirement documented; no implementation claim.
- **Implemented-unverified:** code exists; required verification is incomplete.
- **Tested:** named automated tests passed on an exact SHA.
- **Verified component:** integrated behavior and required tests passed on an exact SHA.
- **Field-qualified:** tested on the declared physical device/OS/operator/environment matrix.
- **Accepted:** all applicable M1 gates and required owner approvals passed.
- **Deployed:** immutable build is running in the approved environment and independently verified.
- **Operational:** monitored, recoverable, supported and demonstrated in the approved workflow.

A green workflow is not field qualification, acceptance, deployment or operational status. A database technical gate is not a product release gate.

## 6. Current implementation checkpoint — 2026-11-27

- **Main:** `3ee88aa022efb12a2d428ab31f91721eb41bfbcc`, the PR #198 merge commit. PR #185 is merged at `590724597a65395ece225128b40ec48fa6ece34b`. The combined-status query for the current main SHA returned no entries; candidate-head checks do not establish post-merge exact-main verification.
- **PR #195:** open/draft at `934f7cca7ff9d145d2a187f444c9bbcc4422c0f8`; all 13 distinct workflow types passed. This implements contract validation, not sensor, metrology, model validation or M1 acceptance.
- **PR #196:** open/draft at `5b6560082d509c597b1cce68f99c1781a10b80dc`; all 13 workflow types passed, including the full suite and database authority cutover. It adds a durable per-original deletion outbox and receipts. Retries are initiated by the same owner; derivative/report cleanup, backups/PITR, offline-device acknowledgement and legal-hold semantics are out of scope.
- **PR #186:** open and based on an earlier pre-#198 main revision; rebase and exact-head verification are required before its report implementation is treated as current.
- **PR #187 and #194:** open draft proposals; neither registry nor audit is canonical on main. **PR #188:** infrastructure proposal only; no integrated deployment is established.
- **Release disposition:** M1 remains **NOT ACCEPTED**. Real participant evidence, field use, payment, dispatch and production deployment are not authorized.

## 7. Release prohibitions

No real participant evidence, production deployment, live payment, dispatch activation, commercial recipient delivery or autonomous structural decision is authorized by this registry. These require separate explicit release gates and approvals. Keep M1 narrow: preserve a trustworthy record and make it independently reviewable.
