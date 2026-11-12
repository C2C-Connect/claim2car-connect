# Claim2Car Connect — Acceptance & Release Gate Matrix

**Canonical repository:** `C2C-Connect/claim2car-connect`
**Canonical main baseline:** `4c52f169239c79e45ef979f91b2e66b8e51b6336`
**Current implementation candidate:** branch `feat/db-01-14-executable-acceptance-gates`
**Capture protocol:** `claims2car-16-v1` is the new-session default; explicit historical `claims2car-12-v1` compatibility is preserved.
**Database contract:** `C2C-DB-AC-001 v1.0 proposed`; owner adoption and independent review remain a separate blocker.

## Current verification snapshot — 2026-11-12

### PR #41 — capture protocol 16-v1

PR #41 was merged into `main` after all 13 PR workflows passed on candidate head `f184f0fa3f79db660ae826ba2a7663ccf22f2373`.

- PR: [#41](https://github.com/C2C-Connect/claim2car-connect/pull/41)
- Merge commit / current main baseline at merge: `4c52f169239c79e45ef979f91b2e66b8e51b6336`
- Full pytest suite: **758 passed, 200 subtests passed**.
- Database authority and legacy database workflows: passed; each reported 297 tests.
- All 13 PR workflows completed successfully; no failed workflow remained.
- The authority diagnostics correctly continued to report `gate_passes_awarded: 0` before executable gate implementation.

### DB-01 through DB-14 — implementation in progress

The new branch `feat/db-01-14-executable-acceptance-gates` adds individually callable `verify_db_01` through `verify_db_14` functions, maps each gate to recorded database test IDs and post-cutover SQL evidence, rejects missing/failed/skipped evidence, and produces structured gate results.

Additional direct-SQL regression coverage is being added for Unicode canonicalization, numeric spelling, rejected-event immutability, and exact preservation of historical payload bytes across migrations.

**No gate is certified by this matrix snapshot.** The implementation branch still requires GitHub Actions execution and review. The database contract remains proposed pending owner adoption and independent review. No `gate_passes_awarded: 14` or `overall_acceptance: ACCEPTED` claim is made until the executable runner actually passes all 14 gates and the contract adoption blocker is resolved.

### Remaining acceptance and release boundaries

- Issues #33–#38 remain open until their corresponding SQL parity, replay, immutability, and CI evidence is verified on the gate implementation branch.
- Issue #39 remains open pending independent review and formal adoption of the database acceptance contract.
- Synthetic PostgreSQL acceptance does not establish production readiness, real participant/field acceptance, legal admissibility, measurement accuracy, or complete commercial deployment.
- Live Square settlement, external carrier/partner delivery, and live dispatch remain disabled unless separately authorized and verified.

## Commercial and safety controls

| Requirement | Enforcement surface | Verification | Status |
|---|---|---|---|
| Dealer fee is fixed at $375 (37,500 cents) | `config/forensic_constants.py`; `backend/app/anchor/ledger.py`; persistent ledger migration and adapter | `tests/contracts/test_commercial_prohibitions.py`; `tests/dispatch/test_integer_financial_ledger.py`; full-suite CI | Dealer fee posting is fail-closed in both the Python ledger and SQL authority function until a verified qualified-acquisition-close event is integrated; shop acceptance posting remains a component, not a live partner workflow |
| Shop fee is fixed at $275 (27,500 cents) on recorded acceptance | `app/dispatch_routing.py`; persistent integer-cents ledger | Commercial and ledger suites | Implemented and regression-tested on the PR #29 candidate; live partner acceptance is not deployed |
| Owner cash incentives are prohibited | Commercial constants, ledger guard, dossier output guard | Commercial and dossier suites | Implemented and regression-protected on the PR #29 candidate |
| $110 operator payout remains disabled pending policy decision | Integer-cents ledger gate and active-output checks | Commercial and ledger suites | Disabled on the PR #29 candidate; no settlement is authorized |
| Roadside pause, unsafe-slot skip, and scene abort remain available | `frontend/src/modules/capture/slice2_workbench_controller.mjs` | `frontend/tests/slice2_workbench.test.mjs` | Implemented on the PR #29 candidate; 12 assertions pass in the local Node run and the GitHub full-suite workflow passes |
| Independent human reviewer inspects sealed evidence and records a supported review outcome | Integrated reviewer queue, verified-session detail API, original-byte retrieval API, and review-record API | Capture evidence service tests; integrated runtime route tests; full-suite CI | Initial connected reviewer workbench is implemented on PR #29: sealed manifest and original bytes are re-verified before artifact metadata is returned; originals are retrievable by an independent reviewer; NOTE_ONLY and HUMAN_QC_REQUIRED are recorded. Qualified-device/field validation, reviewer assignment/escalation, and final claim adjudication remain incomplete. |

## Security, evidence, and product gates

| Gate | Exit requirement | Evidence | Current status |
|---|---|---|---|
| GATE-01 Governance | Commercial rules reconciled across active outputs, ledger, and docs | Commercial and ledger suites; this matrix | Candidate implementation is present on PR #29; not independently reviewed or accepted on `main` |
| GATE-02 Security | Server-derived actor and tenant authority, PostgreSQL RLS, original-byte integrity, authenticated internal routes | Database/security suites; integrated route and capture evidence service tests | Candidate code and CI cover configured actor roles, owner consent events, keyed VIN references, original-byte registration, server-side manifest sealing, and independent reviewer authorization; persistent integrated deployment remains unverified |
| GATE-03 Product | Operator capture and reviewer workbench demonstrated end-to-end on qualified iPad hardware | Slice 2 controller tests; integrated web-shell/API tests; verified-original review tests | Not passed; a connected integrated shell now supports case creation/resume, separate owner consent, canonical-slot original uploads, advisory operator attestations, manifest sealing, verified reviewer retrieval, and limited human-review outcomes. Qualified iPad/browser/device demonstration and field validation have not been performed. |
| GATE-04 Data | Persistent database/object storage, backup restore, consent withdrawal deletion | RLS event journal and POSIX original-byte store; capture evidence service tests | Partial; withdrawal now deletes registered original objects and blocks subsequent use. Storage encryption and backup/restore remain unverified |
| GATE-05 Deployment | One integrated runtime deployed and verified in persistent staging | `app.main:create_app(runtime_mode="integrated")` composes intake and internal analytical routes; Railway CI verifies the separate restricted runtime | Not passed; integrated mode remains opt-in, and the latest Railway workflow skipped deployment. No persistent integrated staging deployment is evidenced |
| GATE-06 Operations | Pilot owner, onboarding, grading, and reconciliation procedures | No field evidence in this branch | Not passed |
| GATE-07 Legal & partner | Counsel review and signed partner/data agreements | `docs/LEGAL_REVIEW.md` | Not passed |
| GATE-08 Measurement | Scene-time, retakes, and model performance calibrated against shop ground truth | Synthetic benchmarks only | Not passed; no field validation claimed |
| GATE-09 Commercial | Integer-cents accounting, payment sandbox/live settlement, and authorized carrier delivery | Persistent tenant-scoped integer ledger, reversal, idempotency and audit-export integration tests; deterministic dossier tests | Partially implemented; payment settlement and external distribution are not enabled |

## Artifact and model gates

| Requirement | Evidence | Status |
|---|---|---|
| Local model weight digest provenance and benchmark-gated adoption | `backend/app/vision/adapters.py`; `tests/dispatch/test_inhouse_vision_adapter.py` | Adapter and synthetic gate tests implemented; production model weights are not present and accuracy is not validated |
| Recipient-scoped deterministic dossier generation and withdrawal revocation | `backend/app/reports/forensic_pdf.py`; `tests/dispatch/test_four_tier_dossiers.py` | Implemented locally; distribution remains disabled pending legal, partner, security, and consent review |
| Complete commercial lifecycle demonstration | `app/commercial_ecosystem_demo.py` | Added; execution depends on the POSIX storage runtime used by the Linux CI container |

## Release discipline

The current Railway configuration is a restricted synthetic containment service. It is not the integrated product. Live dispatch, payments, partner/carrier delivery, production publication, and real participant data remain disabled until their legal, security, partner, operational, and deployment gates have actual evidence.

## Persistent claim-case register and owner-bound evidence journey — 2026-11-10

**Candidate revision:** `1c9a1b839f56396a758b1c0bc8837f8a5e5a2ea1`  
**Implementation status:** Implemented and automated-test verified on PR #29 using synthetic test identities and synthetic image bytes; not field-validated or deployed.

- Added authority migrations `0010_claim_case_registry.sql` through `0013_claim_case_capture_session.sql`.
- Added `faos.claim_cases` with tenant-scoped identifiers, immutable creator/time/state metadata, RLS, and a server-owned idempotent creation function. App identities read; creation occurs through a narrowly granted database function; app identities have no table update/delete grant.
- Each persistent claim record provisions a distinct capture session with a first journal event explicitly identifying it as a persistent claim session, not a controlled-test session.
- The first provisioned owner actor credential to record consent is bound to the case. A different owner actor in the same tenant cannot take over or consent to that case.
- Added authenticated create/list/reopen APIs, bounded listing, creator scoping, explicit session scope, and operator UI controls that open the linked capture session.
- Kept the standalone `POST /v1/capture-sessions` route explicitly controlled-test only.
- Added PostgreSQL end-to-end coverage for the persistent claim session: owner consent, keyed VIN HMAC (raw VIN not journaled), original bytes for every canonical capture slot, advisory quality, manifest sealing, reviewer queue/details, integrity-checked original retrieval, and a supported human-review outcome.

**Deliberate boundary:** the complete automated journey uses synthetic VIN and synthetic image bytes. The case currently stores identity, creator/time/state, and capture-session association; incident details/location/narrative, claimant personal information, and policy details are not yet stored. Owner binding relies on a server-provisioned owner actor credential; this is not end-user login, identity proofing, or claimant invitation. The end-to-end test is not field acceptance, live participant-data approval, automated adjudication, or proof of a deployed customer-facing environment.

**Founder-approved capture-protocol direction — 2026-11-10:** `claims2car-16-v1` is the default target; `claims2car-12-v1` remains a selectable, explicitly versioned alternative. Historical 12-v1 sessions and manifests must retain their original protocol identity and interpretation. This supersedes the earlier open question about which count is the target.

**Resolved by Owner Executive Approval — canonical 16-v1 contract:** The binding 16 ordered slot IDs and descriptions are in `contracts/shot-list-16-v1.json`. The implementation maps those exact IDs through the API, evidence manifest, capture service, root workbench, guided workflow, and reviewer controller. The prior conflicting architecture enumerations are superseded for new sessions by this owner-supplied contract; the original 12-v1 contract remains unchanged for historical sessions and explicit selection.

**Verification evidence at the candidate revision:**
- Full repository suite: **685 passed, 192 subtests passed, 21 warnings** — GitHub Actions run [42755651654](https://github.com/C2C-Connect/claim2car-connect/actions/runs/42755387422).
- Database authority cutover and post-cutover tenant-isolation diagnostics: passed — run [42755651694](https://github.com/C2C-Connect/claim2car-connect/actions/runs/42755387498).
- FastAPI foundation, restricted intake container, offline capture, frontend VIN/transport, controlled-test PostgreSQL, synthetic demonstration, Railway restricted smoke, and PR #29 checks: passed.
- Railway restricted staging verification passed — run [42755641253](https://github.com/C2C-Connect/claim2car-connect/actions/runs/42755387517). The actual deploy job was skipped; this is not deployment of the integrated Claim2Car application.

**Next implementation slice:** reconcile the 12-versus-16 capture-slot contract; establish the incident intake data contract and consent/disclosure scope; replace static owner actor credentials with the approved owner authentication/invitation path; then deploy the integrated app to restricted staging and validate with approved test participants before any production release.


## Structured incident intake and supplemental owner consent — 2026-11-10

**Implementation:** PR #29 candidate branch, migrations `0014_claim_case_incident_intake.sql` and `0015_incident_event_kinds.sql`; synthetic PostgreSQL integration coverage added and verified.

**Verification at candidate `10b2f7b5ba26393a0d67cf4579fc890cf9bd416a`:** full repository suite passed; database authority migration/cutover and tenant-isolation diagnostics passed, including direct-table-read denial and actor-filtered read verification; API health, controlled intake PostgreSQL, integrated-container smoke, frontend, VIN, CodeQL, and restricted Railway smoke checks passed. The Railway deploy job remained skipped. These are CI/synthetic results, not field acceptance or a live deployment.

- Added a separate owner consent event with disclosure version `incident-intake-v1` and scope `incident_details`. It is distinct from the existing `disclosure-v1` capture/evidence consent.
- Added a tenant-scoped, RLS-forced `faos.claim_case_incident_intake` table. The first version collects only incident timestamp, category, city, two-letter state/territory code, and ZIP code.
- Explicitly excluded street address/GPS, free-text narrative, claimant contact information, date of birth, policy number, and payment information.
- Incident details are stored outside the append-only event journal so the structured row can be deleted on supplemental withdrawal or withdrawal of the underlying capture consent. The journal records consent and request references, not the incident fields.
- Owner identity must be the already-bound owner actor for the persistent claim case. Operator credentials cannot submit owner consent or incident details.
- API exposure is gated by `C2C_INCIDENT_INTAKE_ENABLED=true`; the default is disabled. The disclosure contract is marked `draft_pending_legal_review`. No real participant data use is authorized by this code increment.
- This is a first structured intake slice, not the complete incident/claimant/policy intake contract. Owner access still relies on a server-provisioned owner actor credential; end-user authentication, identity proofing, and claimant invitation remain outstanding.


## Actor-scoped incident detail read path — 2026-11-10

- Migration `0016_claim_case_incident_read_boundary.sql` revokes direct `SELECT` on incident details from the shared application database role.
- The application reads incident details through a restricted database function that filters by the server-resolved actor ID against the case creator or bound owner. The API additionally enforces the actor role and case-creator/owner rules before invoking it.
- Added owner and case-creating-operator read paths; other same-tenant operators and reviewers are denied. Reviewer access is not included in this supplemental disclosure scope.
- The owner-facing disclosure now states who can view these details and that they are not automatically sent to insurers, repair shops, or dealerships.
- The operator shell can load the details after the owner separately consents. Withdrawal removes the row, so the read path no longer returns it.
- The database authority diagnostic now verifies that the shared application role cannot directly select this table and must use the actor-filtered read function.

**Verification at candidate `10b2f7b5ba26393a0d67cf4579fc890cf9bd416a`:** the complete database authority/cutover workflow and full repository suite passed (**693 passed, 23 warnings, 192 subtests**), including the owner/creator readback and denial-to-other-operator integration test. API health, integrated-container smoke, controlled PostgreSQL intake, VIN, frontend, CodeQL, and restricted Railway verification also passed; the actual Railway deploy job remained skipped.

**Remaining boundary:** owner authentication is still based on a provisioned actor credential; this does not establish the real person's identity. The feature remains disabled by default and the disclosure remains pending legal review.


## Browser-persistent original evidence queue — 2026-11-10

**Candidate revision:** `0ebe7337b74c5fe82ba7b2e39cc1c08aedbf7737` (current code and verification revision; subsequent commits update documentation only).

**Implemented on PR #29:**
- The integrated operator shell stores selected original image bytes in IndexedDB before attempting upload. It does not transform or recompress the bytes.
- Queue records are scoped to the authenticated tenant, actor, and capture session. A separate tenant/session index supports local cleanup after consent withdrawal.
- Each queued original receives stable request and artifact UUIDs plus a browser-computed SHA-256 digest. Retries reuse those identifiers so the existing server idempotency behavior can recognize an accepted request whose response was lost.
- Upload is serial in queue order and stops at the first failure. The operator can retry manually, on the browser's `online` event, or when reopening a session.
- After server acceptance, the browser removes the local binary payload and retains only receipt metadata. Status refreshes do not load queued image bytes into the UI.
- A server-authoritative evidence-readiness route reports whether the case creator has active owner consent and a valid vehicle reference. The operator UI checks this before queueing while online and again before synchronization. During a connectivity interruption, the current page may rely on the last server-verified readiness result held in memory.
- The owner can withdraw capture consent. After server confirmation, the same browser purges all local queue entries for that tenant/session. If withdrawal occurs on another device, the operator device can purge its pending queue on its next synchronization attempt or case reopen while online and after checking server readiness.

**Verification at the implementation revision:**
- Offline guided-capture workflow, queue behavior assertions, and integrated browser-module syntax checks passed — [run 42781775036](https://github.com/C2C-Connect/claim2car-connect/actions/runs/42781775036).
- Full repository suite passed — [run 42781775011](https://github.com/C2C-Connect/claim2car-connect/actions/runs/42781775011).
- Database authority/cutover verification passed — [run 42781774737](https://github.com/C2C-Connect/claim2car-connect/actions/runs/42781774737).
- Restricted intake container verification passed — [run 42781774732](https://github.com/C2C-Connect/claim2car-connect/actions/runs/42781774732). This is not an integrated Claim2Car deployment.
- Restricted Railway smoke passed — [run 42781774969](https://github.com/C2C-Connect/claim2car-connect/actions/runs/42781774969); its deploy job was skipped. No integrated staging deployment is claimed.
- Actual Chromium/IndexedDB browser verification passed — [run 42781774794](https://github.com/C2C-Connect/claim2car-connect/actions/runs/42781774794). It exercised offline local writes, page-reload recovery, FIFO fail-stop, stable retry identifiers, local binary removal, tenant/actor isolation, and tenant/session purge using synthetic bytes and a mocked upload callback.

**Important limits — not field acceptance:**
- Pure queue-logic assertions also use an injected in-memory store. The separate Chromium run exercises the real IndexedDB adapter, but uses synthetic bytes and a mocked upload callback; it does not exercise the integrated app-to-API upload path.
- Safari/iPad storage behavior, browser eviction, physical-device restart recovery, quota exhaustion, and real-world roadside connectivity interruption have not been field-tested.
- IndexedDB is not an encrypted vault, WORM store, or production durability guarantee. This feature remains a controlled-test aid and is not authorized for real participant evidence.
- The last verified readiness result is held in page memory, not a signed offline consent permit. After a page restart while offline, new evidence cannot be queued until the server can revalidate readiness. If consent is withdrawn elsewhere while the operator device remains offline, already queued local bytes cannot be remotely erased until that device reconnects.
- No claim is made that this completes the offline-first field-capture requirement. Native/device-qualified storage, explicit local retention controls, integrated app-to-API browser tests, and iPad field validation remain open.


## Event-journal SQL/Python contract parity — 2026-11-10

**Validated historical candidate code revision:** `c6f36810affb72f61a4e4fb3e6d8345705cffb73`. PR #29, PR #31, and wrapper PR #40 have since been consolidated and merged into `main` at `3aa87f9d1523a68a1df09c6930ab57efbd182ba4`. The verification below is historical evidence for the candidate revision, not a claim that its historical run proves the current database acceptance gates.

- Added authority migration `0017_event_contract_parity.sql`. It requires RFC3339 timestamps with an explicit timezone, checks calendar validity, enforces compact canonical JSON with lexically ordered object keys and consistent UTF-8 string encoding, and aligns the SQL event-kind allowlist with Python.
- The shared Python serializer now emits deterministic compact JSON, preserves legitimate decimal quality metrics using fixed decimal notation, and is used by capture, manifest-sealing, and review event producers.
- Direct SQL writes that bypass Python validation are rejected by database constraints. The migration does not rewrite historical rows; incompatible existing rows block migration for explicit investigation.
- Replaced defect-characterization assertions with full-plan PostgreSQL integration coverage using a restricted, tenant-bound application login. Tests verify rejection/no-history-mutation for timezone-naive and malformed timestamps, whitespace, unordered keys, and exponent-form numbers; they also verify canonical UTF-8/decimal round-trip and the complete event-kind allowlist.
- The test fixture registers the authenticated database login-to-tenant binding required by the authority model; it does not rely on superuser execution for application writes.

**Verification at candidate revision `c6f3681...`:**
- Full repository pytest suite: **691 passed, 200 subtests passed, 23 warnings** — [GitHub Actions run 42789801371](https://github.com/C2C-Connect/claim2car-connect/actions/runs/42789801371).
- Database authority full-plan migration, restricted-login integration, post-cutover diagnostics, and tenant-isolation checks: **passed** — [run 42789801486](https://github.com/C2C-Connect/claim2car-connect/actions/runs/42789801486).
- Controlled synthetic demonstration: [passed](https://github.com/C2C-Connect/claim2car-connect/actions/runs/42789801288).
- Chromium/Playwright IndexedDB persistence and recovery: [passed](https://github.com/C2C-Connect/claim2car-connect/actions/runs/42789801223).
- FastAPI foundation and API health: [passed](https://github.com/C2C-Connect/claim2car-connect/actions/runs/42789801311).
- Offline guided capture: [passed](https://github.com/C2C-Connect/claim2car-connect/actions/runs/42789801497).
- Restricted intake container: [passed](https://github.com/C2C-Connect/claim2car-connect/actions/runs/42789801572).
- Railway restricted-container smoke: [passed](https://github.com/C2C-Connect/claim2car-connect/actions/runs/42789801199); the separate deployment job was **skipped**. This is not an integrated staging or production deployment.

**Boundary:** the successful database workflow uses isolated/disposable PostgreSQL test databases and synthetic records. It does not establish production database migration safety against unknown live historical rows, durable cloud storage, backup/restore, production deployment, Safari/iPad qualification, field validation, or legal admissibility. Hashes and canonical journal serialization establish consistency and replayability, not the truth of a claim or capture provenance.

**Next P0 slice:** exercise the complete authenticated HTTP path against the full authority schema and durable artifact store, including process restart, manifest seal/readback, independent reviewer retrieval, cross-tenant denial, consent withdrawal, and tampered-byte rejection. Keep deployment disabled until that integrated path and the persistent storage/recovery controls have evidence.


## Capture protocol version binding — 2026-11-11

**Implementation history:** PR #31 was consolidated through PR #29 and merged to `main` via PR #40 at `3aa87f9d1523a68a1df09c6930ab57efbd182ba4`. The exact owner-approved 16-v1 contract and end-to-end version binding are implemented in the current PR #41 candidate; merge and acceptance remain gated on its current CI.

- New sessions default to `claims2car-16-v1`; `claims2car-12-v1` is explicitly selectable.
- Authority migration 0018 backfills existing sessions as 12-v1, adds a constrained protocol-version column, sets the default for new sessions to 16-v1, and makes the version immutable with a database trigger.
- Claim-case creation, controlled-session creation, session readback, and claim-case readback carry the selected version. Idempotent retries cannot change it.
- The authenticated protocol-registry API and operator workbench expose the default and the selectable legacy alternative.
- Both 16-v1 and 12-v1 contracts are executable. Evidence registration, quality recording, sealing, and reviewer retrieval resolve the exact immutable protocol stored on the session; neither version falls through to the other.

**Implementation status:** the owner-authorized 16-v1 slot list is now committed in `contracts/shot-list-16-v1.json`. New-session defaults, legacy selection, protocol-specific manifests, capture validation, reviewer verification, browser workbench rendering, and exterior-only crush-physics mapping have dedicated coverage. This establishes software-contract implementation, not real-device/field acceptance or persistent staging acceptance.

See `docs/release/CAPTURE_PROTOCOL_VERSIONING.md` for the immutable-session rules and remaining work.
