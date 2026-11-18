# OCI Integrated Staging Runbook

**Target:** Oracle Cloud Infrastructure, region `us-chicago-1`  
**Status:** selected target; infrastructure deployment not yet completed  
**Data scope:** synthetic staging only

## 1. Architecture decision

OCI is the selected infrastructure target for Claim2Car's integrated staging environment. The application authority database must be PostgreSQL 16 with PostGIS. The previously configured OCI MySQL DB System is not compatible with the required PostgreSQL/PostGIS schema, row-level security, migration runner, and database authority checks; do not point Claim2Car at that MySQL instance.

The provider-neutral restricted container remains a CI-only containment check. The integrated application image is `Dockerfile.integrated`; it is not the restricted health-only image.

## 2. Existing foundation and boundaries

The owner has already created an OCI tenancy/compartment foundation and a private VCN/subnet with NAT and Oracle-services egress. Exact OCIDs, private CIDRs, API keys, and resource identifiers are intentionally not stored in this public repository.

A private VCN DNS name is not a public internet domain. Keep the first staging deployment private and access it through OCI Bastion or an approved VPN. Public claimant/operator access requires a separately approved public domain, TLS certificate, and ingress design.

Before provisioning or exposing any compute instance, review the security lists and restrict administrative ingress. Do not leave broad SSH ingress in place. Prefer Bastion/VPN administration and no public IP on the application/database host.

## 3. Target service layout

- **Compute:** one private OCI Compute instance for the first controlled staging slice. Use an Always Free-eligible shape only if the account/region confirms eligibility and capacity. Do not silently substitute a paid shape.
- **Application:** build the integrated image from `Dockerfile.integrated`; run as non-root UID 10001.
- **Database:** PostgreSQL 16 with PostGIS, separate migration and least-privilege runtime identities, RLS/forced policies, and the accepted migration inventory through 0019. Add pgRouting only where the routing subsystem requires it; dispatch remains disabled.
- **Evidence storage:** a dedicated persistent block volume mounted exactly at `/var/lib/claim2car/evidence`, owned by UID 10001 and not shared across replicas. The integrated readiness probe requires this exact root to be a mount point and to pass a write/fsync/remove/directory-fsync probe.
- **Database storage:** persistent database data volume, separate from the evidence volume.
- **Secrets:** OCI Vault or an approved secret manager for database credentials, runtime actor tokens, VIN pepper, internal service token, and OCIR credentials. Never put raw tokens, private keys, or OCIDs in source files.
- **Image registry:** create or confirm an OCI Container Registry repository; publish immutable commit-tagged images.
- **Backups:** database backups plus evidence-volume backups to encrypted OCI Object Storage with retention/versioning. Perform a restore rehearsal and reconcile the restored database manifest references to the restored original bytes.

## 4. Deployment sequence

1. Confirm OCI resource IDs and account eligibility in the OCI Console; do not paste API keys or private keys into chat or commit them.
2. Tighten security-list ingress and confirm the private subnet's NAT/service-gateway routes.
3. Provision an eligible private compute instance and separate persistent database/evidence volumes. Record OCIDs in OCI-side inventory, not this repository.
4. Install the container runtime and mount volumes. Verify filesystem ownership and mount persistence across a reboot before starting the app.
5. Provision PostgreSQL 16/PostGIS; create migration/runtime roles and apply the repository's authoritative migration plan through migration 0023.
6. Provision runtime credentials through OCI Vault and create a dedicated synthetic staging tenant with distinct operator, owner, and reviewer identities.
7. Build and push the exact integrated image to OCIR; deploy the same SHA to the private compute host.
8. Verify `/health/live`, `/health/ready`, and `/health/build`; the readiness endpoint must fail if PostgreSQL or the persistent evidence mount is unavailable.
9. Run authenticated synthetic capture-to-review, restart the service, retrieve and hash-check the same original bytes, and run cross-tenant denial tests.
10. Back up PostgreSQL and evidence storage, restore to an isolated target, and verify manifest-to-original-byte consistency before declaring staging operational.

## 5. Cost and release guardrails

- Use only resources confirmed as Always Free eligible unless the owner separately approves a paid resource.
- Review the OCI cost estimate before any apply/create action. Resource names containing “free” do not guarantee that every attached volume, network, load balancer, backup, or data-transfer operation is free.
- No production database, real claimant/vehicle evidence, live payments, external dispatch, or partner distribution is authorized by this staging runbook.
- The existing MySQL DB System must not be used as a PostgreSQL substitute.
- Do not expose the integrated service publicly until identity proofing, TLS, network ingress, security review, backup/restore, legal disclosure, and incident response controls pass.

## 6. Outstanding prerequisites

- Confirm exact compartment, VCN, subnet, image, and OCIDs inside OCI.
- Confirm Always Free compute and block-volume capacity in the selected region; otherwise obtain explicit cost approval.
- Provision PostgreSQL/PostGIS and persistent database/evidence volumes.
- Confirm or create OCIR repository and configure OCI/GitHub deployment credentials.
- Choose and configure private administration access (Bastion/VPN).
- Configure Vault secrets and synthetic owner/operator/reviewer credentials.
- Implement and verify the OCI deployment workflow; no OCI deployment workflow is currently present.
- Complete backup/restore and authenticated restart-persistence rehearsal.

**Current disposition:** NO-GO for integrated staging deployment until the above prerequisites are provisioned and verified. Continue synthetic CI and implementation work without claiming a cloud deployment.
