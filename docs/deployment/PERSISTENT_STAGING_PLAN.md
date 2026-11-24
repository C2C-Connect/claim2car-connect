# Claim2Car Connect — Persistent Integrated Staging Plan

**Document ID:** C2C-INFRA-STAGING-001  
**Version:** 1.0 — proposal only  
**Date:** 2026-11-24  
**Repository base:** `55f69790df123a4602196c3c474e143808c4b87e`  
**Status:** Designed. No infrastructure has been provisioned or modified.  
**Approval required before provisioning:** Owner approval of the proposed monthly spending ceiling and confirmation of service availability in the selected region.

## 1. Executive recommendation

**Provider:** Oracle Cloud Infrastructure (OCI)  
**Primary region:** US Midwest (Chicago), `us-chicago-1`  
**Database:** OCI Database with PostgreSQL, PostgreSQL 16, PostGIS 3.4.2  
**Application:** OCI Compute VM.Standard.E4.Flex running the integrated Claim2Car application and worker in containers  
**Evidence storage:** Private OCI Object Storage bucket, create-only object keys, server-side encryption with customer-managed Vault key  
**Ingress:** Public OCI Load Balancer with managed TLS certificate; application and database remain private  
**Secrets:** OCI Vault and workload identity/instance principals  
**Observability:** OpenTelemetry Collector, OCI Monitoring, OCI Logging, OCI APM, and Grafana dashboard

This is the recommended staging design because OCI now offers a managed PostgreSQL service with PostgreSQL 16 and PostGIS 3.4.2 support. The PostGIS extension is administrator-enabled and the documented PostGIS extension family is available in the OC1 realm. Chicago is an OC1 region. **The exact regional service entitlement and quota for OCI Database with PostgreSQL in `us-chicago-1` must still be confirmed in the tenancy console before provisioning.** If the service is not available there, stop and return for owner approval of an alternate region; do not silently move the data to another region.

Official technical references:
- [OCI Database with PostgreSQL overview](https://docs.oracle.com/en-us/iaas/Content/postgresql/)
- [Supported extensions — PostgreSQL 16 / PostGIS 3.4.2](https://docs.oracle.com/en-us/iaas/Content/postgresql/extensions.htm)
- [PostgreSQL 16 availability](https://docs.oracle.com/en-us/iaas/releasenotes/services/postgresql/)
- [PostGIS extension support announcement](https://docs.oracle.com/en-us/iaas/releasenotes/postgresql/pglogical.htm)

## 2. Scope and hard exclusions

This plan provisions a **persistent integrated staging environment only** after approval. It is not production and is not a participant pilot.

Included:
- `create_app(runtime_mode="integrated")` application runtime.
- Authenticated operator, owner and reviewer routes.
- PostgreSQL 16/PostGIS 3.4.2 authority.
- Durable object storage and immutable source references.
- Managed secrets, TLS, backups, PITR, monitoring and alerts.
- Synthetic-only operator-to-reviewer journey and recovery drills.

Excluded:
- Oracle MySQL, MongoDB and Redis as durable authority.
- Real participant or production data.
- Live Square credentials or live money movement.
- Dispatch, driver assignment or production partner integrations.
- AI/physics outputs as authoritative conclusions.
- Production exposure, public signup or uncontrolled internet access.

The existing Oracle MySQL Free DB system is not used. The PostgreSQL service is a separate OCI product and must be provisioned as PostgreSQL 16.

## 3. Network and security layout

### 3.1 VCN

Use the existing `Claim2Car` VCN in `us-chicago-1` only after the security-list review below. The current network design includes a private subnet at `10.0.1.0/24`; the application and database must not receive public IP addresses.

Recommended layout:

| Tier | Placement | Inbound access |
|---|---|---|
| Public load balancer | Public subnet | HTTPS 443 from internet; HTTP 80 only for redirect |
| Integrated app + worker | Private subnet | App port only from load-balancer NSG; admin access through OCI Bastion |
| PostgreSQL 16/PostGIS | Private subnet / private endpoint | PostgreSQL TLS only from app NSG and approved admin path |
| Object Storage | OCI service gateway/private service path | Service principal access only; no public bucket |
| Vault / Monitoring / Logging | OCI service endpoints | IAM policy and workload identity only |

### 3.2 Required network hardening before provisioning

The existing default security list was previously observed to permit SSH from `0.0.0.0/0` and `::/0`. Do not reuse that rule set for staging.

Before any resource is created:
1. Remove global SSH ingress from both IPv4 and IPv6.
2. Create NSGs per tier; do not use broad default security-list ingress.
3. Allow SSH only through OCI Bastion or a separately approved narrow admin source.
4. Allow the load balancer to reach only the application listener.
5. Allow the application to reach PostgreSQL on the configured TLS port and Object Storage through the service gateway.
6. Deny direct public access to PostgreSQL, app VM, worker, Object Storage bucket and internal diagnostics.
7. Enable VCN flow logs for the staging NSGs and retain them with the staging audit record.

### 3.3 TLS and identity

- Public edge: HTTPS only, TLS 1.2+; managed certificate; HSTS; HTTP redirects to HTTPS.
- Load balancer to app: TLS with backend certificate validation.
- App to PostgreSQL: TLS with CA verification; no plaintext DB connection.
- Application identity: OCI instance principal / dynamic group; no long-lived user API key in the VM.
- Database identity: distinct migration, application, and read-only/reviewer roles; no shared superuser credential in application settings.
- Public verification route: rate-limited, non-enumerable IDs, no PII or GPS.

## 4. PostgreSQL service design

**Service:** OCI Database with PostgreSQL  
**Version:** PostgreSQL 16  
**Extension:** PostGIS 3.4.2, enabled by an administrator through a custom configuration  
**Initial sizing assumption:** 2 OCPUs, 32 GB memory, 200–500 GB optimized storage (final size determined by the OCI cost estimator and tenancy limits)  
**Placement:** Private endpoint, availability-domain-specific placement if cross-region backup copies are enabled  
**Authority:** PostgreSQL only; no MySQL/MongoDB fallback

Pre-provision checks:
- Confirm OCI Database with PostgreSQL is available in `us-chicago-1` for this tenancy and compartment.
- Confirm quota for 2 OCPUs, selected memory, optimized storage and backup resources.
- Confirm `postgis` 3.4.2 is available for PostgreSQL 16 in the selected configuration.
- Confirm the service supports required migrations, forced RLS, SECURITY DEFINER functions, advisory locks, append-only event journal and extension requirements.
- Confirm private endpoint connectivity from the application subnet.

The staging deployment must run the complete ordered migration chain, including migrations 0001–0031 and later approved routing migrations, through `python -m database.migrate`. The deployment record must store migration names and checksums.

## 5. Durable evidence storage and consent deletion

**Bucket:** Private OCI Object Storage bucket, server-side encryption with a customer-managed Vault key.

Storage controls:
- Use tenant/session/artifact-derived immutable object keys.
- Upload with create-only semantics; deny overwrite to the application role.
- Store original bytes unchanged; recompute SHA-256 server-side after durable write.
- Keep original bytes separate from PDF/JSON report carriers and derived previews.
- Store storage key, digest, session, protocol version and manifest reference in PostgreSQL.
- Do not make the bucket public.
- Do not use object-lock retention or versioning settings that prevent required consent withdrawal deletion.

**Consent withdrawal is a deletion workflow, not a retention exception.** On withdrawal, the revocation service must:
1. Stop downstream reads and dispatch immediately.
2. Delete original evidence bytes and all mutable incident rows.
3. Purge any replicas, noncurrent versions or backup copies containing those original bytes, if such copies are enabled.
4. Append a durable cryptographic revocation event to the PostgreSQL journal.
5. Prove downstream reads fail closed and preserve only the permitted revocation/audit record.

For staging, use synthetic evidence only. Object replication and evidence-object backup copies are disabled by default. Before enabling any such copy, prove that deletion propagates to every copy and does not leave recoverable participant bytes behind.

## 6. Backup schedule and recovery objectives

### 6.1 Database backup policy

| Control | Proposed setting |
|---|---|
| Automated full/incremental backup schedule | Daily at 03:00 UTC |
| Automated backup retention | 35 days |
| Point-in-time recovery | Enabled, 10-day restore window |
| Manual pre-migration backup | Before every schema-changing deployment |
| Cross-region backup copy | Weekly to `us-ashburn-1`, only if tenancy is subscribed and AD-specific data placement is selected |
| Monthly restore drill | Required; no production or participant data |

OCI Database with PostgreSQL supports automated daily/weekly/monthly backups with up to 35 days of retention, point-in-time recovery with a configurable window up to 35 days, and cross-region backup copies. Cross-region copying requires availability-domain-specific placement and a subscribed target region.

References:
- [Database system backups and retention](https://docs.oracle.com/en-us/iaas/Content/postgresql/backups.htm)
- [Point-in-time recovery](https://docs.oracle.com/en-us/iaas/Content/postgresql/point-time-recovery.htm)
- [Scheduling backups and backup copies](https://docs.oracle.com/en-us/iaas/Content/postgresql/schedule-backup.htm)
- [Cross-region backup copy](https://docs.oracle.com/en-us/iaas/Content/postgresql/copy-backup.htm)

### 6.2 Monthly restore drill

Run the drill in an isolated recovery subnet using synthetic fixtures:

1. Seed a synthetic case, session, evidence package, sealed manifest, report and revocation test case.
2. Record the exact UTC time of the seed and a later controlled corruption/deletion.
3. Restore a new PostgreSQL system to a timestamp immediately before the controlled event. Never overwrite the live staging database.
4. Restore/reconnect the corresponding synthetic evidence objects and verify object-key/digest bindings.
5. Run migrations/checksum validation and the complete DB-01–DB-14 authority runner.
6. Verify forced RLS, actor/tenant binding, event-chain links, manifest roots, report registry retrieval, idempotency and revocation behavior.
7. Confirm the restored environment does not resurrect bytes that a consent-withdrawal event required to be deleted.
8. Record RPO, RTO, restore timestamp, database identifier, migration inventory, test report, failures and corrective actions.

**Pass condition:** the restored environment passes all applicable DB gates with zero skipped tests and no cross-tenant visibility, missing evidence, resurrected revoked bytes/rows or broken chain links. No application traffic is enabled until revocation replay and object purge are complete.

## 7. Secret and key management

**Service:** OCI Vault / Key Management.

- Create a customer-managed master encryption key for the evidence bucket and a separate key for application/database secrets.
- Store DB credentials, session-signing material, webhook sandbox secrets, object-storage auth and TLS private-key material in Vault/Certificates; never commit them or place them in CI logs.
- Grant the app VM access through instance principals and a narrowly scoped dynamic group.
- Separate secret read permissions from key administration and database administration.
- Rotate database and application secrets every 90 days, and immediately after any suspected exposure.
- Use versioned secret references; deployment should fetch the active version at startup.
- Keep Square sandbox credentials isolated from any live-payment configuration. No live credentials are provisioned.
- Ensure CI uses short-lived, scoped credentials and does not inherit staging secrets.

## 8. Monitoring, logging and alerting

**Stack:** OpenTelemetry Collector on the app host, exporting traces/metrics/logs to OCI APM, OCI Monitoring and OCI Logging. Grafana may be used for a consolidated dashboard if needed.

Required signals:
- API request count, latency, 4xx/5xx rates and authentication failures.
- DB connections, CPU, memory, storage growth, replication/backup state and query latency.
- Object-storage write/read/delete failures and digest mismatch count.
- Manifest seal/verification/tamper events.
- Consent revocation and downstream access-denial events.
- Worker queue age, retries, dead-letter count and idempotency conflicts.
- TLS certificate expiry and failed health checks.
- Backup/PITR policy status and restore-drill age.

Initial alert thresholds (tune only with recorded change control):
- API 5xx above 1% for 5 minutes.
- API p95 latency above 1.5 seconds for 10 minutes.
- DB CPU above 75% for 10 minutes; DB storage above 80%.
- DB connection use above 80% of configured maximum.
- Worker oldest-message age above 5 minutes or dead-letter count above zero.
- Any evidence digest mismatch, manifest-chain verification failure or unauthorized tenant access: immediate high-severity alert.
- Backup failure or PITR window unavailable: immediate high-severity alert.
- TLS certificate expiry within 14 days.

Logs must be structured, timestamped in UTC, tenant-safe and PII-minimized. Do not log raw VIN, original evidence bytes, access tokens or secrets.

## 9. Deployment and verification sequence

Provisioning is not authorized until the owner approves the spending ceiling and the region/quota preflight succeeds.

After authorization, sequence is:

1. Harden VCN security lists and NSGs; confirm no global SSH.
2. Create Vault keys, policies, dynamic groups and secret containers.
3. Create PostgreSQL 16/PostGIS 3.4.2 in the private subnet; enable TLS, backups and PITR.
4. Create private evidence bucket and verify create-only writes, digest checks and deletion semantics.
5. Create app VM and deploy the pinned integrated runtime image; no public VM address.
6. Configure public load balancer, TLS certificates, backend TLS and health checks.
7. Configure OpenTelemetry, OCI Monitoring, Logging, alerts and dashboards.
8. Run `python -m database.migrate`; verify checksums and rollback procedure.
9. Run DB-01–DB-14 in the actual staging environment with zero skipped tests.
10. Execute synthetic operator-to-reviewer journey, process restart, independent manifest verification, report retrieval, tamper rejection and consent withdrawal.
11. Run backup/PITR restore drill and repeat integrity and tenant-isolation checks.
12. Capture all deployment evidence and request owner review before calling the environment Deployed or Operational.

## 10. Teardown and cost controls

- Tag every resource with `project=claim2car`, `environment=staging`, `owner=claim2car`, and `expiry_review=monthly`.
- Enable budget alerts at 50%, 75%, 90% and 100% of the approved monthly ceiling.
- No autoscaling or unbounded object retention.
- Keep database and evidence storage limits explicit; alert before growth thresholds.
- Teardown procedure: disable ingress, stop app/worker, export required synthetic test artifacts and audit logs, delete DB system and backups when authorized, purge Object Storage objects and replicas, delete compute/boot volumes/load balancer, revoke secrets and keys only after dependent artifacts are removed, then verify no billable resources remain.
- Do not delete the owner's existing VCN or unrelated OCI resources.

## 11. Preliminary monthly cost estimate

The estimate assumes 730 hours/month, 2 OCPU/32 GB PostgreSQL, 200–500 GB database optimized storage, 2 OCPU/16 GB app VM, 250 GB evidence storage, a public load balancer, backups, Vault, monitoring/logging and modest staging traffic.

| Cost area | Planning estimate / month | Basis |
|---|---:|---|
| Managed PostgreSQL compute + memory | $230–$285 | 2 OCPU plus selected memory; actual service shape/region quote required |
| PostgreSQL optimized storage + VPUs | $20–$55 | 200–500 GB; selected storage performance |
| App VM + boot volume | $75–$90 | 2 OCPU / 16 GB E4 Flex, boot storage |
| Object Storage + DB backup storage | $15–$45 | 250 GB evidence plus variable backup growth |
| Load balancer / certificates / network | $15–$35 | HTTPS ingress, private backend, modest traffic |
| Vault / logging / monitoring / APM | $20–$45 | Key operations, ingestion and retention assumptions |
| Egress / miscellaneous buffer | $10–$25 | Low-volume staging traffic |

**Estimated range:** approximately **$385–$580 per month**.  
**Proposed owner spending ceiling:** **$550/month**, subject to OCI Cost Estimator validation and actual tenancy pricing. If the estimator exceeds $550/month, do not provision; return with a revised design and cost ceiling request.

Pricing references:
- [OCI Database with PostgreSQL pricing](https://www.oracle.com/cloud/postgresql/pricing/)
- [OCI compute price list](https://www.oracle.com/cloud/price-list/)
- [OCI Object Storage pricing](https://www.oracle.com/cloud/price-list/)

This is a planning estimate, not a vendor quote. OCI Database with PostgreSQL pricing includes OCPU, optimized storage and additional selected resources such as memory and Block Volume VPUs; backups incur standard Object Storage charges. Actual costs depend on shape, storage growth, backup deltas, region, networking and log ingestion.

## 12. Owner approvals required before provisioning

No resources are created until the owner provides written approval for:
1. OCI as the selected provider and `us-chicago-1` as the primary region after the regional service/quota check.
2. A monthly ceiling of $550, or a different written ceiling.
3. The proposed 35-day backup retention, 10-day PITR window and weekly cross-region copy policy.
4. The security-list/NSG hardening changes.
5. The final resource sizing and OCI Cost Estimator output.

**Current state: Designed only. No infrastructure was provisioned, deployed, or modified while preparing this plan.**
