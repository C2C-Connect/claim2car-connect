# Hosting Provider Decision and Transition Record

**Decision date:** 2026-11-17  
**Selected integrated-staging target:** Oracle Cloud Infrastructure (OCI), `us-chicago-1`

## Decision

- OCI is the selected infrastructure target for Claim2Car's persistent integrated staging and eventual production architecture.
- Railway is not the selected integrated deployment provider. Railway-specific deploy workflows, CLI scripts, service configuration, and public project identifiers are retired from the active repository.
- The restricted health-only container remains as provider-neutral CI verification; it does not deploy and does not represent the integrated claims application.
- The integrated application image remains `Dockerfile.integrated`. OCI provisioning and private deployment automation are implemented in mainline (guarded state bootstrap/plan/apply, immutable ARM64 image publishing, read-only network audit, and OCI Instance Agent Run Command deployment), but none of these workflow actions constitute evidence that OCI resources have been provisioned or the integrated service deployed.

## Evidence and boundaries

- OCI private networking foundations have been created by the owner. Exact OCIDs, private network ranges, API keys, private keys, and account secrets are not stored in this repository.
- An OCI MySQL DB System was configured during initial account setup. It is not compatible with the application's PostgreSQL/PostGIS authority schema and must not be used as the Claim2Car application database.
- No integrated OCI compute host, PostgreSQL/PostGIS authority database, persistent evidence volume, backup/restore rehearsal, or successful OCI deployment is claimed by this decision record. The deployment workflow itself is implemented but has not been executed successfully.
- No Railway production deployment, persistent integrated database, or persistent evidence volume is claimed.
- The repository's former Railway trial/project/service metadata is intentionally not copied here; provider account identifiers and billing details do not belong in a public repository.

## Transition controls

1. Keep all cloud credentials in OCI Vault/GitHub environment secrets; never commit them.
2. Use only resources confirmed as Always Free eligible unless the owner separately approves costed resources.
3. Keep the initial OCI environment private; use Bastion/VPN administration and restrict security-list ingress.
4. Use PostgreSQL 16/PostGIS, not MySQL, for the application authority database.
5. Provision separate persistent database and original-evidence storage, then prove backup/restore and restart persistence.
6. Keep real-participant intake, payments, dispatch, and external partner distribution disabled until their separate acceptance and authorization gates pass.

See [OCI Integrated Staging Runbook](../deployment/oci-integrated-staging.md).
