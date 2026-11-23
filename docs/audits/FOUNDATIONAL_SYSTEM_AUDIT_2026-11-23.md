# Claim2Car Connect — Foundational System Audit

**Audit started:** 2026-11-23  
**Status:** IN PROGRESS — initial repository inspection, not a certification or exhaustive audit  
**Audit baseline:** `main` at `44a40af41ef4f20366ac66227f431a900ba0cd83` (PR #168 merged)  
**Purpose:** Inspect existing mechanics against the product/FAOS requirements, identify verified gaps and risks, and convert the highest-priority findings into tested corrective changes. This document is an engineering work ledger; it is not a security certification, forensic validation, legal opinion, or field acceptance.

## Method

For each subsystem, trace the served entry point and actual implementation; identify what tests exercise and what they do not; separate verified facts from hypotheses; rank by severity and exploitability/impact; remediate in small code increments; test the exact PR head; and update this ledger with evidence.

Severity:
- **P0 / Critical:** immediate safety, evidence trust, data compromise, or uncontrolled consequential action.
- **P1 / High:** material confidentiality, integrity, authorization, availability, or operational correctness gap that should block field deployment.
- **P2 / Medium:** important reliability, usability, maintainability, or validation gap.
- **P3 / Low:** improvements that do not currently block controlled execution.

## Confirmed initial findings

### AUD-001 — Canonical integrated runtime stores offline evidence bytes unencrypted (P1)
**Evidence:** The integrated runtime in `app/main.py` serves `app/web/index.html` and `app/web/assets/*` at `/` and `/assets`. Its offline queue module, `app/web/assets/offline_evidence_queue.mjs`, writes original file bytes directly to IndexedDB. The module header explicitly states this is not an encrypted vault. The served shell likewise warns that browser storage is not encrypted.

A separate `frontend/app` workbench contains an AES-GCM/HKDF queue implementation, but it is mounted under `/prototype`, is not the canonical `/` entry point, and is not equivalent to the integrated runtime. The README's statement that the canonical integrated app has an AES-GCM encrypted queue is therefore inconsistent with the served root implementation.

**Impact:** Sensitive crash/vehicle images may persist as plaintext in browser-origin storage on a shared, lost, compromised, or unlocked device. Browser storage is not a secure enclave; encryption is defense in depth, not a guarantee.

**Remediation:** Reconcile the canonical runtime with the encrypted queue implementation; bind the key to a transient credential/session material, never persist the credential or key; define migration/handling for legacy plaintext queue records; ensure ciphertext integrity and stable IDs; verify reload, token change, expired-token, offline, retry, and withdrawal behavior. Never imply device/WORM durability.

**Verification needed:** inspect cryptographic queue API and current tests; test the actual `/` served shell and assets, not only `/prototype`; add browser tests proving plaintext originals are not persisted in the canonical queue.

### AUD-002 — Two workbench implementations create drift risk (P1)
**Evidence:** The integrated root serves `app/web/*`; a separate workbench at `frontend/app/*` is exposed under `/prototype`. The capture/offline-queue mechanics and user-facing claims differ. This means testing one shell cannot automatically establish correctness of the production-intended entry point.

**Impact:** Security fixes, UX changes, protocol support, recovery behavior, and tests can diverge. Users/operators may encounter a different implementation from the one whose tests or docs describe.

**Remediation:** Establish one canonical frontend and explicit retirement/containment of the prototype. Until consolidation is complete, add tests that identify both routes and assert their status/behavior, and maintain a discrepancy checklist.

### AUD-003 — README implementation claims conflict with canonical runtime (P1)
**Evidence:** README describes an AES-GCM encrypted offline IndexedDB recovery queue in the canonical integrated shell. The root served module stores plaintext. The frontend prototype's warning describes AES-GCM, but its footnote also notes offline capture and resumable upload qualification gaps. The acceptance matrix additionally states that browser eviction, quota, Safari/iPad, and physical-device recovery have not been field-tested.

**Impact:** Users and reviewers can misunderstand current protections and readiness.

**Remediation:** Correct documentation to match the actual canonical runtime immediately, then update claims only after tests verify the root route. Keep controlled-test, production, and field-qualified statuses distinct.

### AUD-004 — Offline capture is a recovery queue, not complete offline operation (P1)
**Evidence:** The integrated workbench requires server-verified readiness before queuing new evidence. Its acceptance notes state readiness is in page memory, not a signed offline consent permit; after a restart while offline, new capture cannot queue until server revalidation. Consent withdrawn elsewhere cannot be observed by an offline device until it reconnects. Browser quota/eviction and real-device durability remain unqualified.

**Impact:** Field conditions may interrupt capture or create ambiguous consent/recovery state. A queued original is not equivalent to a durable, consent-authorized evidence package.

**Remediation:** Specify the offline authorization/consent model, safe capture boundaries, revocation semantics, quota handling, and recoverable user-visible states; do not claim true offline readiness until tested on supported devices.

### AUD-005 — Image quality is advisory and uncalibrated (P1 for field use)
**Evidence:** Current capture quality checks are advisory; the acceptance checkpoint states thresholds are not field-calibrated and do not reject or mutate originals.

**Impact:** Poor imagery can be accepted into the evidence package, while unvalidated thresholds could provide false reassurance if treated as authoritative.

**Remediation:** Preserve original bytes; qualify quality guidance against representative conditions and supported devices; report confidence/limitations; test low light, blur, glare, obstruction, orientation, and incorrect views. Keep operator/human review explicit.

### AUD-006 — Forensic integrity scoring and authorization boundaries require a complete trace (P1)
**Evidence:** PR #168 exposed integrity signals and diagnostics in the triage API, but the public API receives explicit GPS-spoof/hash-tamper request inputs. The current handoff records that integrity contract alignment and downstream dispatch authorization require attention. API diagnostics are not proof that original evidence was independently verified.

**Impact:** Caller-supplied signals must not substitute for server-derived chain/manifest verification, and score outputs must not authorize downstream action absent strict verified evidence.

**Remediation:** Trace the full original-byte registration → immutable/append-only manifest → chain verification → score computation → triage → dispatch boundary. Distinguish caller hints from server-derived facts; make tampering/chain failure fail closed for consequential actions; verify formula/version against the governing manual; ensure no dispatch action is enabled as part of the audit without an explicit release gate.

### AUD-007 — Identity is a controlled-test credential model, not complete end-user authentication (P1)
**Evidence:** `app/identity.py` describes opaque static credentials provisioned out-of-band; credentials are SHA-256 digests, expiry checked on each resolution, revocation requires configuration reload. The current identity surface does not provide self-service owner enrollment, account recovery, invitation, credential rotation/revocation workflow, or field-ready identity assurance.

**Impact:** Credential lifecycle, recovery, owner proofing, and operational access management remain controlled-test limitations.

**Remediation:** Design and implement a bounded user identity lifecycle; keep tenant/role binding server-side and database-authoritative; add revocation/rotation and audit; threat-model lost/stolen devices and compromised tokens.

### AUD-008 — Persistent deletion and retention semantics need end-to-end proof (P1)
**Evidence:** Capture withdrawal/deletion flows exist, but browser offline queues, remote devices, server originals, backups, logs, and retention exceptions are distinct stores. Offline devices cannot immediately receive a revocation. Current documentation does not establish a complete end-to-end deletion SLA/receipt covering every copy.

**Impact:** Consent withdrawal could be misunderstood as immediate deletion of all copies; legal/operational retention and forensic preservation requirements may conflict.

**Remediation:** Define data inventory, retention schedule, deletion semantics, tombstones/receipts, pending remote cleanup, backup expiration, legal hold, and exception handling. Test every store and make the receipt precise.

### AUD-009 — Valuation and jurisdictional outputs require provenance and validation (P1)
**Evidence:** `backend/app/valuation/acv.py` contains a tri-source 40/40/20 blend and a fallback depreciation curve; jurisdiction thresholds are coded in `backend/app/jurisdiction/thresholds.py`. The inspected ACV module states it has no runtime dependency on commercial market datasets.

**Impact:** Fallback/model outputs may be mistaken for market-supported or legally authoritative values. Rules may become stale or vary in applicability.

**Remediation:** Expose source, observation date, coverage, fallback status, uncertainty, formula version, and review state; validate thresholds against current authoritative sources and effective dates; require human review for consequential conclusions.

### AUD-010 — Sandbox payments/webhooks do not yet equal financial lifecycle completion (P1)
**Evidence:** `app/payments/square_sandbox.py` explicitly fixes Sandbox and does not post, settle, refund, or mutate the financial ledger. Webhook reconciliation persists verified receipts and returns status outcomes but is not itself final ledger posting.

**Impact:** End-to-end commercial obligations, fulfillment, reconciliation, refund/dispute, and accounting correctness remain unproven.

**Remediation:** Audit the complete obligation → checkout → verified webhook → persistent event → ledger posting → reconciliation → reversal/refund/dispute lifecycle. Maintain sandbox-only controls until separately authorized.

### AUD-011 — Collision lifecycle persistence exists, but complete event/outbox workflow needs tracing (P1)
**Evidence:** `database/collision_lifecycle.py` establishes tenant-authorized PostgreSQL lifecycle identity/link operations. Its module description identifies related participants, claims, events, and outbox records as the broader aggregate.

**Impact:** A durable root record alone does not prove all workflow events, external actions, retries, and reconciliation are transactional or durable.

**Remediation:** Trace state transitions, version/actor/reason timestamps, optimistic concurrency, idempotency, outbox consumers, dead-letter/retry, tenant scope, and audit reconstruction.

### AUD-012 — Infrastructure and recovery readiness remain unaccepted (P1)
**Evidence:** Latest handoff reports OCI staging not deployed/accepted, no participant field acceptance, no live payments/dispatch, and protected owner-controlled configuration remains a blocker.

**Impact:** CI-green code does not prove deployment, runtime operations, persistence recovery, monitoring, incident response, or field usability.

**Remediation:** Keep staging private; run reviewed deployment; validate network boundaries, least privilege, storage, migrations, backup restore, restart recovery, monitoring, security response, and evidence retrieval. No real participant evidence before release gates.

## Initial priority order for corrective work

1. **AUD-001 + AUD-002:** Canonical root offline queue encryption and frontend discrepancy—verify actual served path; resolve legacy plaintext records safely; regression tests.
2. **AUD-006:** End-to-end integrity provenance and consequential authorization boundary.
3. **AUD-004 + AUD-008:** Offline authorization, withdrawal, deletion, retention, and recovery semantics.
4. **AUD-007:** Credential lifecycle, owner identity assurance, and revocation.
5. **AUD-009:** Provenance/uncertainty and jurisdiction-rule maintenance.
6. **AUD-010 + AUD-011:** Financial/collision lifecycle completeness and idempotent event/outbox behavior.
7. **AUD-012:** Deployment, backup/restore, operational readiness, and field qualification.

## Audit status tracking

| Finding | Status | Evidence / next action |
|---|---|---|
| AUD-001 | CONFIRMED / remediation not yet implemented | Canonical root IndexedDB queue stores plaintext; implement encrypted storage + actual-root tests |
| AUD-002 | CONFIRMED | Root and prototype differ; decide canonicalization and eliminate drift |
| AUD-003 | CONFIRMED | README claim mismatches root queue |
| AUD-004 | CONFIRMED limitation | Offline readiness requires server revalidation; define and test safe offline model |
| AUD-005 | CONFIRMED limitation | Advisory, uncalibrated quality thresholds; qualification required |
| AUD-006 | OPEN / deeper trace required | Audit source-of-truth integrity and dispatch authorization |
| AUD-007 | CONFIRMED limitation | Static out-of-band credential lifecycle |
| AUD-008 | OPEN / deeper trace required | Complete copy inventory and deletion/retention receipt semantics |
| AUD-009 | CONFIRMED limitation | Fallback valuation and hardcoded rules require provenance/validation |
| AUD-010 | CONFIRMED limitation | Sandbox workflow does not post/settle ledger |
| AUD-011 | OPEN / deeper trace required | Verify aggregate events, outbox, retries, and transactional transitions |
| AUD-012 | CONFIRMED release boundary | Staging/field acceptance still unperformed |

## Change log

- 2026-11-23: Initial source-level inspection and confirmed findings recorded. Audit remains in progress; corrective implementation and regression verification are the next actions.
