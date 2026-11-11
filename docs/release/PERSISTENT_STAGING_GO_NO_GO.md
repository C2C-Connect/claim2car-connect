# Claim2Car Persistent Staging and Rollout Go/No-Go

**Scope:** integrated persistent staging first; supervised field pilot and commercial production are separate later decisions. This checklist operationalizes the nine release gates in the CTO Master Execution Plan. It does not award acceptance automatically.

## Candidate and integration strategy

- [ ] Freeze one exact candidate commit SHA and record its parent/base, build revision, PRs, and artifact digests.
- [ ] Inventory the complete diff against `main`; identify migrations, API/schema changes, security boundaries, feature flags, and rollback implications.
- [ ] Obtain independent review of each mergeable increment. A self-authored check or green CI run is not an independent review.
- [ ] Require current-head CI for the exact candidate SHA. Reject stale checks, missing required lanes, and unexplained skips.
- [ ] Inspect job- and step-level conclusions. In particular, distinguish restricted Railway verification from integrated Railway deployment.
- [ ] Preserve a rollback point and document the migration/data-compatibility strategy before any persistent environment is changed.

### PR #29 / PR #31 scope decision

At the audit baseline, PR #29 represented 224 commits and 93 changed files ahead of `main`. That is too broad to treat as one low-risk production merge. PR #31 was a 20-commit, 13-file Slice 2 increment, but it is stacked on PR #29's implementation branch rather than based on `main`. The stack is useful for review isolation; it is not yet a sequence of independently mergeable mainline releases.

**Required strategy:** inventory PR #29's 93-file diff and partition it into dependency-ordered, independently reviewable slices. For each slice, create or retarget a branch based on the latest accepted mainline SHA, carry only that slice's changes, run its own CI and review, and merge in dependency order. Keep PR #31's workbench increment attached to the prerequisite runtime/API/security changes it actually depends on. Do not merge the 224-commit branch wholesale merely because its checks pass.

Suggested dependency order:
1. Governance, commercial prohibitions, route/security controls, runtime topology and architecture decisions.
2. Database authority/migrations, tenant-scoped capture persistence, evidence lifecycle and API contracts.
3. Operator/reviewer workbench and capture protocol version binding.
4. Persistent integrated staging, operational observability, backup/restore and recovery.
5. Qualified-device and roadside field validation, legal/partner approval and supervised pilot.
6. Marketplace, dispatch, carrier, Square settlement and other commercial workflows only after their prerequisites and separate authorization.

This is a dependency plan, not a claim that all listed slices are already implemented or accepted.

## Gate A — Governance and commercial rules

- [ ] Dealer fee remains $375 and posts only on qualified-acquisition close.
- [ ] Shop fee remains $275 and posts only on recorded vehicle acceptance.
- [ ] Owner cash incentive is absent from active behavior.
- [ ] $110 operator payout remains disabled until a separate policy decision.
- [ ] No payment, dispatch, external distribution, or consequential AI behavior is enabled by a synthetic demo or CI result.
- [ ] Legal/public product claims match the actual implementation and evidence.

**Current known controls:** the acceptance matrix records the $375/$275 rules, prohibited owner cash incentive, and inactive $110 operator amount. Live partner workflows and settlement remain unproven.

## Gate B — Security, identity, tenant authority and evidence integrity

- [ ] Server derives actor, tenant, and role authority; no client-supplied tenant/role is trusted.
- [ ] PostgreSQL RLS/forced policies, role grants, internal service auth, and cross-tenant denial are verified against the exact candidate.
- [ ] Owner identity proofing/invitation and distinct consent credential lifecycle are implemented for the intended staging/pilot scope.
- [ ] Original bytes, manifest sealing, hashes, reviewer retrieval, tamper detection, consent withdrawal and deletion are tested end-to-end.
- [ ] Secrets are stored in the environment secret manager; raw tokens are never committed or embedded in runtime JSON.
- [ ] Route exposure and private ingress are verified from outside the service boundary.

**Current known blocker:** owner authentication/invitation and identity proofing remain incomplete; owner actor credentials are provisioned out-of-band.

## Gate C — Operator and reviewer product experience

- [ ] Canonical protocol registry defines `claims2car-16-v1` as the default and `claims2car-12-v1` as an explicit selectable alternative.
- [ ] Exact 16-v1 slot IDs/order and capture semantics are approved from authoritative source material; do not infer the missing slot.
- [ ] Protocol version is bound to each capture session and immutable manifest; historical 12-v1 sessions retain their original identity.
- [ ] Browser/controller/API/backend contract parity is tested for each version.
- [ ] Roadside pause, unsafe-slot skip, scene abort, interruption recovery and sync are validated on supported physical devices.
- [ ] An authorized operator completes capture with consent and original-byte evidence; an independent reviewer retrieves it and records an attributable decision.

**Current known blocker:** exact 16-v1 slot IDs/order and cross-layer version compatibility are unresolved. Safari/iPad/physical-device and roadside validation are not complete.

## Gate D — Persistent data, storage, retention and recovery

- [ ] Dedicated PostgreSQL staging database exists with separate migration and runtime actor roles/DSNs.
- [ ] Authority migrations apply in order, rerun idempotently, and have a documented rollback/forward-repair plan.
- [ ] Persistent evidence storage is attached to the integrated service at the configured mount and survives container replacement/restart.
- [ ] Encryption, access controls, retention, consent withdrawal/deletion and object integrity are verified.
- [ ] Backup and restore are rehearsed; recovery point/time objectives and evidence reconciliation are recorded.
- [ ] Synthetic end-to-end capture, restart, reviewer retrieval, tamper rejection and deletion are repeated against the persistent staging services.

**Current known blocker:** no provisioned/verified persistent integrated staging database and evidence volume, encryption, or backup/restore evidence.

## Gate E — Exact integrated staging deployment

- [ ] Dedicated integrated Railway service is identified and separated from the restricted health-only service.
- [ ] Service variables, sealed secrets, private database networking, persistent volume, TLS/ingress, health checks and one-replica storage constraints are verified.
- [ ] GitHub environment secrets/variables are present and least-privileged.
- [ ] Deployment runs from the approved `main` SHA with explicit confirmation and the deployment-enable flag.
- [ ] Migration job succeeds; deployed `/health/build` reports the exact candidate SHA and integrated runtime mode.
- [ ] Post-deployment route/auth checks, evidence write/read, restart persistence, reviewer retrieval and negative tenant tests pass.
- [ ] Deployment record includes service identity, timestamp, SHA, migration ledger, smoke results, logs and rollback reference.

**Critical distinction:** a green restricted Railway smoke with a skipped deploy job is not integrated staging. The integrated staging workflow is manual-only, requires `main`, `confirm_deploy=true`, and `RAILWAY_INTEGRATED_DEPLOY_ENABLED=true`. No such successful integrated deployment is currently evidenced.

## Gate F — Operations and support

- [ ] Named staging/pilot owner, on-call contact, escalation path and incident commander.
- [ ] Monitoring/alerts for API health, database availability, storage capacity, upload failures, queue age, authorization denials and integrity failures.
- [ ] Runbooks for outage, lost device, interrupted upload, duplicate claim, suspected tampering, consent withdrawal and data deletion.
- [ ] Operator/reviewer training, access revocation, audit review and support hours.
- [ ] Stop conditions and safe scene-abort procedure are rehearsed.

## Gate G — Legal and partner approvals

- [ ] Counsel approves disclosures, consent, retention/deletion, privacy notices and incident-intake scope.
- [ ] Incident-intake supplemental disclosure is approved before the feature is enabled.
- [ ] Dealer, repair-shop, carrier and other partner agreements cover exact data flows, fees, responsibilities and liability.
- [ ] Data-sharing and external distribution are disabled until the relevant agreement and approval exist.

**Current known blocker:** supplemental incident disclosure remains pending legal review; incident intake remains disabled by default.

## Gate H — Measurement and validation limits

- [ ] Capture-quality thresholds are calibrated on representative real-world evidence.
- [ ] Vision/physics/model accuracy, limitations, confidence and human-review boundaries are validated and documented.
- [ ] No advisory model output is represented as a final claim, safety, repair, liability or payment decision.
- [ ] Field/device tests record device/browser/OS, network conditions, failures, retries and evidence integrity.
- [ ] Unvalidated production weights or external data dependencies are not described as qualified.

## Gate I — Commercial activation (separate approval)

- [ ] Square sandbox flow is tested first: checkout/authorization, webhook signature, idempotency, refunds/voids, reconciliation and ledger posting.
- [ ] Live Square credentials are held only in the secret manager and supplied through the approved secure channel; never paste them into source or logs.
- [ ] Live settlement requires a separate explicit founder approval after legal, partner, ledger and operational gates pass.
- [ ] Dispatch and external carrier/partner distribution remain disabled until assignment, consent, location-sharing, cancellation, safety and audit controls are accepted.
- [ ] No owner incentive; $110 operator payout remains inactive; $375 dealer and $275 shop rules retain their exact trigger conditions.

## Decision record

A release decision must record each gate as **PASS / FAIL / NOT RUN / NOT APPLICABLE**, with evidence URL, exact candidate SHA, reviewer/approver, timestamp and rationale. A gate is PASS only when its defined exit criteria and evidence are satisfied. NOT RUN is not PASS. A skipped job is not PASS. A synthetic test is not field acceptance. A workflow success is not deployment acceptance.

**Current disposition from the available evidence:** NO-GO for persistent integrated staging deployment until infrastructure/secrets/DB/storage prerequisites are actually provisioned and verified; NO-GO for real participant/field pilot until protocol, identity, legal, device and operational gates pass; NO-GO for live payments or dispatch until separately authorized. Continue implementation and synthetic verification on isolated branches.
