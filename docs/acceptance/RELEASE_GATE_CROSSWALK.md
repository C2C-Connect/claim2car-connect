# Claim2Car — M1 Intake & Evidence Preservation Acceptance Registry

**Document ID:** C2C-M1-AC-001  
**Version:** 2.0.0  
**Scope:** M1 Intake & Preservation only  
**Authority:** Owner-approved M1 boundary. This registry does not authorize field deployment, real participant evidence, payment, dispatch, or marketplace activity.

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
| M1-01 Authorization & consent | Authenticated actor and tenant; disclosure version; explicit scope/acceptance; withdrawal and retry semantics fail safely; no consent inferred from session creation. | API/database tests for unauthorized, declined, withdrawn, duplicate, retry, tenant-isolation and audit behavior. | PARTIAL — core consent path exists; PR #194 records deletion/retry semantics as an open audit item. |
| M1-02 Versioned capture | Exact 16-point protocol identity and ordering; 12-slot legacy sessions remain interpretable; retakes supersede rather than erase; unavailable/unsafe slots are explicit exceptions and never represented as captured. | Protocol contract, operator workflow tests, safety pause/abort tests, quality/retake and package-completeness tests. | IMPLEMENTED IN SOFTWARE / FIELD-UNQUALIFIED — physical device and operator qualification remain open. |
| M1-03 Original evidence preservation | Original bytes, artifact ID, SHA-256, byte length, MIME, actor/session/protocol and immutable storage reference are bound to a registered manifest. Derivatives remain separate and parent-linked. | Original-byte round trip, manifest/artifact binding, mismatch and mutation rejection, fresh-process retrieval. | VERIFIED COMPONENT — PR #185 merged as `590724597a65395ece225128b40ec48fa6ece34b`; post-merge exact-main verification still required. |
| M1-04 Offline/online synchronization | Durable encrypted local queue; stable artifact/request IDs; FIFO retry; idempotent server ingest; conflict and partial failure do not silently lose or duplicate evidence. | Browser IndexedDB and API integration tests, interrupted upload/restart/retry and tamper tests. | IMPLEMENTED IN SOFTWARE / FIELD-UNQUALIFIED — field-device recovery qualification remains open. |
| M1-05 Independent server verification | Server recomputes persisted event chain and original artifact digests; registered manifest root is bound to the exact seal event, chain tip/sequence/version, tenant/session/protocol context; failures block downstream use and create durable audit events. | PostgreSQL authority tests, authenticated HTTP seal/replay, fresh-runtime verification, one-byte tamper rejection and tenant isolation. | VERIFIED COMPONENT — PR #185 merge contains runtime manifest registration; post-merge exact-main checks required. |
| M1-06 Reviewer retrieval & decision | Authorized reviewer retrieves verified originals and manifest; reviewer identity, decision, reason and referenced artifacts are recorded; invalid/unverified context fails closed. | Separate reviewer identity, cross-tenant denial, original retrieval, attributable decision and tamper-failure tests. | VERIFIED COMPONENT IN PR #185; confirm current-main exact-head integration after merge. |
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

## 6. Current implementation checkpoint

- PR #185, `Wire chain-bound manifest registration into live capture seal/review path`, was squash-merged to main as `590724597a65395ece225128b40ec48fa6ece34b` on 2026-11-26.
- Its exact candidate head `a7174d45a02cc6b8312a00b1ca31671019726728` had 13/13 workflow types green and DB-01–DB-14 14/14 technical PASS (408/408 counted authority tests, zero DB skips). This evidence is for the candidate head, not a substitute for post-merge main verification.
- PR #186 report rendering remains stacked on an earlier pre-merge #185 head. Rebase onto the merged main commit and rerun the full workflow set before considering merge. Reports must preserve original bytes as authoritative and label bounding boxes as suspect-region identifiers, not measured geometry.
- PR #194 audit remains draft. Its open findings include consent deletion/retry semantics, application-level storage encryption and backup/restore, field/device/accessibility/performance qualification and operational monitoring.
- PR #195 defines the Evidence Measurement and Substantiation Contract v1.0.0; it is a schema/validation increment, not sensor capture, metrology validation or M1 acceptance.

## 7. Release prohibitions

No real participant evidence, production deployment, live payment, dispatch activation, commercial recipient delivery or autonomous structural decision is authorized by this registry. These require separate explicit release gates and approvals. Keep M1 narrow: preserve a trustworthy record and make it independently reviewable.
