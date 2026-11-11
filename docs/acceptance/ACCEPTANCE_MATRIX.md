# Claim2Car Connect — Acceptance & Release Gate Matrix

**Canonical repository:** `C2C-Connect/claim2car-connect`  
**Candidate branch:** `cto/spec-production-implementation` (PR #29)  
**Latest code-bearing verification candidate:** `b537ec8d96eb74e9c1d54d5f1b52dd76423acb5f` (2026-11-10)  
**Machine contract:** `m1-v1`  
**Status rule:** code, CI, field validation, review, and release authorization are recorded separately. A passing synthetic test does not establish product acceptance or production readiness. The candidate revision is not merged and has no submitted independent review.

## Current verification snapshot — 2026-11-10

**Branch head at verification:** `b537ec8d96eb74e9c1d54d5f1b52dd76423acb5f`  
**Main base:** `21bcd4e677d71cb985e83815d5b70b8d3504f471`  
**Divergence:** 223 commits ahead, 0 behind.  
**PR #29:** open and Draft; unmerged.  
**GitHub PR test merge candidate:** `3313f3b30d094ff5aeb4168998ddfedeb62f9515`.

### Current-head CI evidence

All 13 workflow runs associated with the candidate completed successfully:

- Full repository suite: **713 passed, 200 subtests passed, 23 warnings** — [run 42912960647](https://github.com/C2C-Connect/claim2car-connect/actions/runs/42912960647).
- Database authority/cutover: [run 42912961234](https://github.com/C2C-Connect/claim2car-connect/actions/runs/42912961234). Its counted database suite discovered and executed **281 tests, 0 failures, 0 errors, 0 skipped**. The authenticated HTTP test `test_authenticated_http_capture_survives_runtime_restart_and_fails_closed` passed. The synthetic HTTP journey covers claim creation, owner consent, VIN reference, all currently canonical 12 slots, quality attestations, manifest sealing, cross-tenant reviewer denial, runtime/service-object restart, independent reviewer retrieval, original-byte readback, tamper rejection, and consent withdrawal/deletion.
- Integrated runtime container build/smoke: [run 42912960932](https://github.com/C2C-Connect/claim2car-connect/actions/runs/42912960932) — passed. This now runs on pull requests. It verifies the integrated image, exact build revision, non-root UID, evidence-volume ownership/writeability, shell availability, and internal service-auth boundaries; it is not a persistent cloud deployment or full database-backed container journey.
- Chromium/Playwright IndexedDB browser test: [run 42912960788](https://github.com/C2C-Connect/claim2car-connect/actions/runs/42912960788) — passed with synthetic bytes and a mocked upload callback.
- Offline guided-capture checks: [run 42912960961](https://github.com/C2C-Connect/claim2car-connect/actions/runs/42912960961) — passed.
- Legacy database component checks: [run 42912960755](https://github.com/C2C-Connect/claim2car-connect/actions/runs/42912960755) — passed.
- Controlled-test intake PostgreSQL: [run 42912960879](https://github.com/C2C-Connect/claim2car-connect/actions/runs/42912960879) — passed.
- FastAPI foundation: [run 42912960632](https://github.com/C2C-Connect/claim2car-connect/actions/runs/42912960632) — passed.
- Frontend VIN/decoder/transport: [run 42912961155](https://github.com/C2C-Connect/claim2car-connect/actions/runs/42912961155) — passed.
- Controlled synthetic demonstration: [run 42912960996](https://github.com/C2C-Connect/claim2car-connect/actions/runs/42912960996) — passed.
- Offline VIN lookup: [run 42912960896](https://github.com/C2C-Connect/claim2car-connect/actions/runs/42912960896) — passed.
- Restricted intake container: [run 42912960800](https://github.com/C2C-Connect/claim2car-connect/actions/runs/42912960800) — passed.
- Restricted Railway staging verification: [run 42912961132](https://github.com/C2C-Connect/claim2car-connect/actions/runs/42912961132) — synthetic containment smoke passed; the deploy job was **skipped**.

### Authority and acceptance interpretation

The authority workflow applied and verified the migration plan through `0017_event_contract_parity.sql` on isolated PostgreSQL 16.4/PostGIS 3.4.3 test infrastructure. Its diagnostics report the 14 tenant-scoped application tables with RLS enabled and forced and exercise tenant-isolation/privilege checks.

**This is not formal acceptance certification.** The structured diagnostic classifies itself as `post-cutover-authority-diagnostics-not-gate-certification`; `complete_gate_results` is `NOT RUN`, `gate_passes_awarded` is `0`, and `overall_acceptance` is `NOT ACCEPTED`. The authority workflow passing means its migration and diagnostic assertions succeeded; it does not mean the product acceptance gates passed.

### Still not complete / not claimed

- No integrated persistent staging or production deployment. The Railway restricted deployment job remains skipped.
- No provisioned/verified integrated staging PostgreSQL service, durable evidence volume, sealed runtime secrets, TLS/private ingress, monitoring, or backup/restore evidence.
- The integrated container CI smoke is a disposable local container test; it does not prove the container's full capture-to-review path against a persistent database and cloud object store.
- The HTTP-to-PostgreSQL-to-original-bytes journey is synthetic CI evidence, not real participant evidence or field acceptance.
- The code snapshot at this revision still implements `claims2car-12-v1`. The founder-approved target is `claims2car-16-v1` as the default, with `claims2car-12-v1` retained as a selectable, versioned alternative and historical 12-v1 sessions preserved. Exact 16-v1 slot IDs/order and the cross-layer compatibility contract remain implementation blockers; no historical session may be silently reclassified.
- Owner authentication/invitation and identity proofing remain unimplemented; owner actor credentials are provisioned out-of-band.
- Supplemental incident disclosure remains `draft_pending_legal_review` and incident intake remains disabled by default.
- Safari/iPad/physical-device qualification, roadside validation, field-calibrated quality thresholds, and real-world model accuracy remain unverified.
- Production model weights and validated physics/AI accuracy are not established.
- Live Square payment settlement, external carrier/partner delivery, and live dispatch remain disabled.

This snapshot supersedes older verification counts and candidate SHAs below. Older entries remain for historical traceability and must not be interpreted as current-head evidence.

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

**Remaining implementation blocker — exact 16-v1 contract:** The architecture source is internally inconsistent. One section describes 12 standard framing angles plus up to 4 specialized detail angles, while enumerating 8 exterior + 2 undercarriage + 2 interior + 2 legal/document views (14 before the optional details). Another mandatory-16 breakdown enumerates 8 exterior + 2 interior + 1 license-plate + 1 insurance-document + 3 damage close-ups (15). The Slice 2 controller also uses a third set of 12 slot identifiers that does not match `contracts/shot-list.json`. Reconcile one exact 16-slot ID/order and map it to API, manifest, controller, browser, and reviewer contracts before implementation. Do not guess, silently rename, or reclassify existing 12-v1 evidence.

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

**Validated candidate code revision:** `c6f36810affb72f61a4e4fb3e6d8345705cffb73` (PR #29; still draft and unmerged).

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

**Implementation candidate:** PR #31, Slice 2 workbench branch.

- New sessions default to `claims2car-16-v1`; `claims2car-12-v1` is explicitly selectable.
- Authority migration 0018 backfills existing sessions as 12-v1, adds a constrained protocol-version column, sets the default for new sessions to 16-v1, and makes the version immutable with a database trigger.
- Claim-case creation, controlled-session creation, session readback, and claim-case readback carry the selected version. Idempotent retries cannot change it.
- The authenticated protocol-registry API and operator workbench expose the default and the selectable legacy alternative.
- The existing 12-v1 manifest/capture contract remains executable. Evidence registration, quality recording, and sealing reject a 16-v1 session until its exact slot contract is approved; 16-v1 never falls through to 12-v1.

**Still open:** the exact authoritative 16 slot IDs/order/semantics remain unresolved because the source architecture contains conflicting enumerations. The separate Slice 2 browser controller's 12-slot list also differs from the API 12-v1 contract. These lists must be reconciled explicitly. No 16-v1 manifest or capture completion is claimed.

See `docs/release/CAPTURE_PROTOCOL_VERSIONING.md` for the immutable-session rules and remaining work.
