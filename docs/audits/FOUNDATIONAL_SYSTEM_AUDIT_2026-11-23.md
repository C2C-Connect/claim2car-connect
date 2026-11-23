
## Latest implementation checkpoint — M1 persistent forensic provenance (2026-11-23)

PR #176 is draft/open on feat/persistent-forensic-provenance-m1, head 36fdd083ebbbe1268e6e2f51d40dfe60b9523404. Exact-head CI 13/13 workflows succeeded, including Full test suite, authority cutover and legacy database. The code slice adds Python versioned deterministic genesis/event commitments and a full-chain verifier with known-answer/unit tests; this is **not persistent implementation**. Verified source gaps remain: faos.events has no hashes; readback sequence-replays but does not recompute; manifest root lacks chain-tip/context commitments; SQL/Python payload canonicalization parity unresolved; process-memory ledger and caller-supplied roots remain in public verification. SQL migration/backfill, SQL parity, persistent append, server-owned verification, manifest binding and DB adversarial/restart/concurrency/tenant tests remain. Keep PR draft and dispatch disabled. Detailed trace/next steps in docs/THREAD_HANDOFF_2026-11-23.md.
## Owner-directed focus reset — substantiating forensic claims (2026-11-23)

The next work is deliberately narrowed to the forensic substantiation vertical slice. See **`docs/forensics/FORENSIC_SUBSTANTIATION_PROGRAM.md`** for the implementation sequence and measurable acceptance gates. The audit's highest trust gap is not a cosmetic feature: the current `backend/app/anchor/ledger.py` is a process-memory singleton, not durable independent provenance; it does not recompute/verify the complete prior-entry chain on verification. Related audit findings AUD-017/018 concern persistent event hash-chain and sealed manifest/capture-context commitments.

**First implementation PR (M1):** trace existing PostgreSQL authority, event/migration models, registered originals, seal/manifest, integrity verification, API callers, and dispatch/payment boundaries; map reuse versus gaps; design canonical event and checkpoint contracts; implement persistent tenant-scoped append-only event/anchor records, full-chain recomputation, manifest/artifact/session binding, fail-closed structured verification, restart/idempotency/concurrency/tamper/missing/reorder/fork/tenant tests, and independent verifier agreement. Do not create parallel databases/ledgers. Forensic integrity status must never alone authorize dispatch/payment.

**Following milestones:** evidence binding → VIN/configuration source substantiation → camera calibration/alignment and versioned vehicle coordinate frame → damage localization and one calibrated measurement with uncertainty → source-backed parts/OEM technical assessment → deterministic versioned report → blind/held-out validation. Synthetic known-answer fixtures first. No unsupported metric precision, causation, hidden-damage, forensic-certification, or field-accuracy claims.

---

# Claim2Car Connect — Foundational System Audit

**Audit started:** 2026-11-23  
**Status:** IN PROGRESS — initial repository inspection, not a certification or exhaustive audit  
**Audit baseline:** `main` at `44a40af41ef4f20366ac66227f431a900ba0cd83` (PR #168 merged). **Current checkpoint:** PR #171 code merge at `beb72950081201e891a7a3e66f42addd13c9f528`; audit/handoff docs PRs #172 and #173 merged. Verify live `main` head on resume.  
**Purpose:** Inspect existing mechanics against the product/FAOS requirements, identify verified gaps and risks, and convert the highest-priority findings into tested corrective changes. This document is an engineering work ledger; it is not a security certification, forensic validation, legal opinion, or field acceptance.

## Method

For each subsystem, trace the served entry point and actual implementation; identify what tests exercise and what they do not; separate verified facts from hypotheses; rank by severity and exploitability/impact; remediate in small code increments; test the exact PR head; and update this ledger with evidence.

Severity:
- **P0 / Critical:** immediate safety, evidence trust, data compromise, or uncontrolled consequential action.
- **P1 / High:** material confidentiality, integrity, authorization, availability, or operational correctness gap that should block field deployment.
- **P2 / Medium:** important reliability, usability, maintainability, or validation gap.
- **P3 / Low:** improvements that do not currently block controlled execution.

## Confirmed initial findings

### AUD-001 — Canonical root offline evidence queue lacked encryption (P1; REMEDIATED)
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
**Evidence:** In `database/capture_evidence.py`, owner consent withdrawal appends the consent event within the tenant-authorized DB transaction, then deletes registered originals from filesystem storage after that transaction has ended. A storage failure can therefore leave the consent event committed while deletion is incomplete; retry is possible, but the receipt is currently a count, not a per-artifact deletion proof. The operator's local IndexedDB queue is purged when its next online readiness check observes inactive consent; an offline device cannot receive immediate revocation and may retain queued files until reconnection. Browser offline queues, server originals, backups, logs, and retention exceptions are distinct stores.

**Impact:** Consent withdrawal does not imply simultaneous deletion from all copies. Partial server deletion can occur after consent is committed; local offline copies can remain pending until reconnect. Legal/operational retention and forensic preservation requirements may conflict.

**Remediation:** Define data inventory, retention schedule, deletion semantics, tombstones/receipts, pending remote cleanup, backup expiration, legal hold, and exception handling. Add failure injection proving each storage deletion outcome is recorded and retried, and make the receipt precise. Never promise secure erasure from flash storage or backups without evidence.

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


### AUD-013 — Triage API contains synthetic assessment defaults (P1)
**Evidence:** `backend/app/api/triage.py` defaults detection/depth inputs to empty lists, structural risk to 0.3, age to 5, jurisdiction to Texas, GPS accuracy to 15 m, hash/chain/master validity to true/full, metadata completeness to 1.0, and three internal ACV values to $18,500/$17,800/$19,200. An authenticated internal caller can submit only a session ID and receive a result calculated from these defaults.

**Impact:** A downstream consumer may mistake a synthetic/default calculation for an evidence-backed assessment. Internal authentication is not a substitute for explicit source provenance or complete input validation.

**Remediation:** Remove consequential defaults or require an explicit controlled-demo mode. Require server-owned evidence verification and provenance binding for integrity inputs; require market-source identity/timestamp/coverage for ACV comps; represent unknown values as unknown; mark fallback/demo calculations clearly and prevent them from routing or financial decisions.

### AUD-014 — Public anchor verification relies on process-local memory (P1 for persistent verification)
**Evidence:** `backend/app/anchor/ledger.py` defines `AnchorLedger` as an in-process append-only list/dictionary singleton (`LEDGER`). Its own module comment describes this as internal and replaceable. A runtime restart loses entries and the ledger tip; no durable DB or external anchor is established by this implementation.

**Impact:** Anchors created in one process are not a durable long-term verification service. Restart, process replacement, or horizontal scaling can yield missing or divergent ledger state.

**Remediation:** Do not claim durable anchoring. Implement a persistent, transactionally serialized append-only authority (or qualified external anchor) with restart, concurrency, tamper, retention, and cross-instance tests before exposing this as a production trust mechanism.

### AUD-015 — Photo analysis is heuristic and non-persistent (P2)
**Evidence:** `app/vision/photo_baseline.py` uses a deterministic contrast baseline and labels the method `heuristic_contrast_baseline`; the result states `persisted: false`. It is not a trained/validated damage-detection model or a persisted forensic observation.

**Impact:** Results may be over-interpreted as AI damage findings or a persistent analysis record.

**Remediation:** Label the capability clearly, preserve limitations and uncertainty, validate against representative imagery, persist versioned observations only when intended, and keep model outputs from consequential decisions absent validation and human review.


### AUD-016 — Offline evidence metadata initially lacked AES-GCM AAD binding (P1; REMEDIATED)
**Evidence at audit baseline:** Ciphertext authentication did not bind tenant/actor/session, slot, artifact/request IDs, digest, byte length, MIME type, timestamp, or encryption version as AES-GCM additional authenticated data.

**Remediation delivered:** PR #171's canonical queue v2 derives a deterministic AAD tuple from these fields and rejects tampering at decrypt. Prior-format encrypted records and plaintext records are upgraded to v2 before upload.

**Verification:** Exact-head unit and Chromium browser tests tamper with capture metadata and confirm fail-closed decryption/no upload; PR #171 merged after 13/13 workflows passed. Server-side provenance remains authoritative.


### AUD-017 — Persistent capture event journal is sequential/append-only but not cryptographically hash-chained (P1)
**Evidence:** Migration `0002_event_journal.sql` creates tenant-scoped events with a unique sequence and a security-definer `faos.append_event` function that enforces next-sequence ordering, duplicate idempotency, and insert-only permissions. Event rows do not store a previous-event hash or event hash. The separate `backend/app/anchor/ledger.py` hash-chain ledger is process-local and is not integrated with the persistent capture event journal.

**Impact:** Database sequence and restricted mutation permissions provide consistency/access controls, but they do not independently make event history tamper-evident against privileged database modification. The persistent journal cannot currently be cryptographically recomputed as a chain.

**Remediation:** Add versioned hash-chain fields and deterministic canonical event hashing, bind each event to the prior event hash, make the sealed manifest commit to the capture-event chain tip, and provide a verifier with mutation/reordering/truncation tests. Keep legacy event history explicitly versioned and do not claim retroactive chain protection.

### AUD-018 — Sealed manifest does not bind full capture provenance (P1)
**Evidence:** `app/evidence_manifest.py` manifest v0.1 digest binds schema version, session ID, shot-list version, artifact IDs, slots, and original SHA-256 values. The `MANIFEST_SEALED` event stores the digest and artifact IDs. It does not include the event-chain tip, capture actor/time/time-source, device/session metadata, consent event reference, quality-review results, or exception/resolution history.

**Impact:** Original-byte integrity and slot completeness are verified, but the sealed package is not yet a complete cryptographic commitment to the broader forensic capture context required by the core manual.

**Remediation:** Define a versioned provenance manifest that references and commits to the canonical event chain and capture metadata, consent/disclosure version, quality/review, exceptions, and original bytes. Preserve v0.1 compatibility, bind the new version, and independently verify it before any downstream consequential workflow.


### AUD-019 — Server-side original evidence storage has no application-level encryption (P1)
**Evidence:** `app/artifact_storage.py` validates and stores original bytes in tenant/session/artifact-scoped filesystem objects, uses restrictive file permissions and no-follow/atomic-write protections, and verifies hashes on retrieval. The inspected storage implementation writes the original byte payload directly; no application-level envelope encryption is performed. Underlying volume encryption and key management depend on deployment configuration and have not been verified in staging.

**Impact:** Filesystem permissions and integrity checks do not protect confidentiality if storage media, snapshots, backups, or privileged host access are compromised. Unlinking is not secure erasure.

**Remediation:** Establish and verify encrypted-at-rest storage for originals, including volume/snapshot/backup coverage, key custody/rotation, least-privilege access, restore testing, and documented retention. Consider envelope encryption with tenant/session-scoped keys if the deployment threat model requires protection beyond provider-managed disk encryption.


### AUD-020 — Financial journal implementation is in-memory and not connected to the persistent authority (P1)
**Evidence:** `backend/app/anchor/ledger.py` defines `IntegerFinancialLedger` with process-local entry storage. The Square Sandbox client is deliberately restricted to checkout-link creation and verified webhook receipt; it does not post/settle/refund or mutate this ledger. Database webhook reconciliation records receipts/outcomes but is not the completed financial lifecycle.

**Impact:** Passing unit tests for the in-memory journal does not establish durable obligations, ledger postings, restart recovery, reconciliation, reversals/refunds, or accounting integrity. Current sandbox flows are not financial production readiness.

**Remediation:** Establish PostgreSQL as the financial authority; implement transactionally idempotent obligations, postings, verified payment event linkage, reconciliation, refunds/reversals/disputes, actor/tenant authorization, and restart/recovery tests. Keep real-money transactions behind a separate approved release gate.


### AUD-021 — Default capture contract requires supplemental personal documents and does not default to the FAOS v2 views (P1)
**Evidence:** `app/capture_protocols.py` defines `claims2car-16-v1` as the default. Its required 16th slot is `15_license_and_insurance_docs`. The implemented `claims2car-16-v2` instead includes four structural corner views, front/rear cabin restraint views, instrument-cluster telemetry, and vehicle identity; it removes the mandatory license/insurance-document slot. The canonical app and protocol registry still default to v1.

**Impact:** New sessions may request sensitive license/insurance documents as mandatory capture, while the newer FAOS protocol has a more collision-relevant evidence set and less document collection. This can increase roadside friction and privacy exposure, and create version divergence.

**Remediation:** Evaluate and explicitly approve v2 as the default for new sessions, preserve v1 compatibility for existing sessions, and move any supplemental personal-document capture to a separately consented optional flow with purpose, access, retention, and redaction controls. Add tests that default new sessions to the approved protocol and never silently reinterpret existing sessions.


### AUD-022 — Collision lifecycle/outbox foundation lacks full transitions and relay consumers (P1)
**Evidence:** `database/collision_lifecycle.py` currently provides collision root creation, claim/vehicle linking, and tenant-scoped reads/listing. Migration 0020 includes a persistent collision event/outbox table and transactional event append, but repository inspection found no deployed relay/consumer worker for that persistent outbox. The separate `app/outbox.py` implementation uses injectable dictionary storage and is explicitly a semantics/test abstraction, not the PostgreSQL runtime relay.

**Impact:** Durable identity and event/outbox rows do not yet provide complete operational lifecycle state transitions, external delivery, consumer idempotency, retry/dead-letter, or reconciliation. Events may remain queued without an operational delivery path.

**Remediation:** Implement authoritative lifecycle state transitions and a persistent outbox relay/consumer contract with locking/lease, idempotent delivery, bounded retry/dead-letter, observability, replay/reconciliation, and restart/tenant-isolation tests. External dispatch remains disabled until the trust and release gates pass.


### AUD-023 — OCI staging network security has permissive public SSH ingress (P1 deployment blocker)
**Evidence:** The previously reviewed OCI default security list allowed SSH ingress from `0.0.0.0/0` and `::/0`. Staging is not deployed, and this rule must be revalidated in the current OCI console/network configuration before any instance is exposed.

**Impact:** Public SSH ingress expands the attack surface and is inconsistent with a private staging environment unless a separately verified control restricts effective access.

**Remediation:** Remove broad SSH ingress; use a controlled admin IP/NSG, bastion or approved managed access path; audit IPv4 and IPv6 effective rules; verify private-subnet routing and ingress; capture a read-only security audit before apply.

### AUD-024 — Oracle MySQL Free resource does not match the PostgreSQL/PostGIS authority architecture (P2)
**Evidence:** User-created OCI infrastructure includes an Oracle MySQL.Free DB System, while the repository architecture and deployment workflows require PostgreSQL authority and PostGIS. The MySQL resource is not an architectural substitute and its status/usage must be reconciled.

**Impact:** Using the wrong database service would create schema/authority divergence and invalidate acceptance evidence; an unused resource can also create operational confusion.

**Remediation:** Confirm the MySQL resource is unused and safely retire it if appropriate; deploy the required PostgreSQL/PostGIS authority in the approved private network. Do not migrate the application to MySQL or treat the MySQL instance as a completed staging dependency.

## Initial priority order for corrective work

1. **AUD-002:** Keep the prototype contained/retired and prevent implementation drift; canonical queue encryption and AAD binding are now implemented in PR #171.
2. **AUD-006 + AUD-017 + AUD-018:** Integrity provenance, persistent event hash-chain, and complete sealed-package provenance; these are foundational trust mechanics.
3. **AUD-008 + AUD-019:** Consent withdrawal/deletion receipts and verified server-side originals encryption/backup coverage.
4. **AUD-013 + AUD-009 + AUD-021:** Eliminate synthetic triage defaults, establish ACV/jurisdiction provenance, and resolve privacy-sensitive capture-protocol defaults.
5. **AUD-007:** Owner identity assurance, credential rotation/revocation, and recovery.
6. **AUD-010 + AUD-020:** Durable financial obligations, postings, reconciliation, refunds/disputes, and sandbox-to-release controls.
7. **AUD-011 + AUD-022:** Complete collision lifecycle transitions and operational persistent outbox relay/consumer.
8. **AUD-012 + AUD-023 + AUD-024:** Private staging deployment, least-privilege network ingress, correct PostgreSQL/PostGIS authority, backup/restore, monitoring, incident response, and field qualification.

## Audit status tracking

| Finding | Status | Evidence / next action |
|---|---|---|
| AUD-001 | REMEDIATED / PR #171 merged and exact-head CI green | Canonical root queue now AES-GCM encrypts originals; legacy migration, wrong-token, browser, and retry tests passed. Field qualification remains open |
| AUD-002 | CONFIRMED | Root and prototype differ; decide canonicalization and eliminate drift |
| AUD-003 | REMEDIATED | README encryption claim now matches canonical root queue; still no field-qualified durability claim |
| AUD-004 | CONFIRMED limitation | Offline readiness requires server revalidation; define and test safe offline model |
| AUD-005 | CONFIRMED limitation | Advisory, uncalibrated quality thresholds; qualification required |
| AUD-006 | OPEN / deeper trace required | Audit source-of-truth integrity and dispatch authorization |
| AUD-007 | CONFIRMED limitation | Static out-of-band credential lifecycle |
| AUD-008 | OPEN / deeper trace required | Complete copy inventory and deletion/retention receipt semantics |
| AUD-009 | CONFIRMED limitation | Fallback valuation and hardcoded rules require provenance/validation |
| AUD-010 | CONFIRMED limitation | Sandbox workflow does not post/settle ledger |
| AUD-011 | OPEN / deeper trace required | Verify aggregate events, outbox, retries, and transactional transitions |
| AUD-012 | CONFIRMED release boundary | Staging/field acceptance still unperformed |
| AUD-013 | CONFIRMED | Triage API has default synthetic values that can yield a result from a session ID alone |
| AUD-014 | CONFIRMED limitation | Anchor ledger is process-local; no persistent/external anchor established |
| AUD-015 | CONFIRMED limitation | Photo baseline is heuristic and result is not persisted |
| AUD-016 | REMEDIATED / PR #171 merged and exact-head CI green | Versioned AAD binds capture metadata; tests verify tamper failure and legacy upgrade |
| AUD-017 | CONFIRMED | Persistent events enforce sequence but have no cryptographic event hash chain |
| AUD-018 | CONFIRMED | Sealed v0.1 manifest does not commit to event-chain tip or full capture context |
| AUD-019 | CONFIRMED / deployment config unverified | Server originals are filesystem plaintext at application layer; at-rest volume/snapshot encryption not yet accepted |
| AUD-020 | CONFIRMED | Financial journal is process-local and sandbox webhook receipts are not full ledger posting/reconciliation |
| AUD-021 | CONFIRMED | Default v1 requires license/insurance docs; newer v2 has structural evidence and no mandatory document slot |
| AUD-022 | CONFIRMED | Collision lifecycle has root/link/read operations; persistent outbox has no relay consumer; app outbox is in-memory abstraction |
| AUD-023 | CONFIRMED / must revalidate before staging | OCI default security list previously allowed public SSH IPv4 and IPv6 |
| AUD-024 | CONFIRMED infrastructure mismatch | OCI MySQL.Free resource is not the PostgreSQL/PostGIS authority required by the product |

## Change log

- 2026-11-23: Initial source-level inspection recorded 24 findings. PR #171 remediated AUD-001/AUD-016 (canonical offline queue encryption and authenticated metadata) and corrected AUD-003 (README claim). Exact-head 13/13 CI passed. Owner reset focus to forensic substantiation; detailed program and acceptance gates recorded in `docs/forensics/FORENSIC_SUBSTANTIATION_PROGRAM.md`. Next code target M1 is persistent provenance and independently recomputed full-chain verification; audit remains in progress.
