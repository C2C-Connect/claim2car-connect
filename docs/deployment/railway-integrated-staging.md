# Integrated Railway staging

This is a **separate service** from the existing restricted health-only Railway service. Do not point the restricted service at `Dockerfile.integrated`, and do not treat its existing smoke test as a product deployment.

## Current state

The repository now has an integrated container, exact-build health endpoint, non-root runtime entrypoint, JSON environment configuration, and a manually gated deployment workflow. No Railway service, database, volume, or paid resource has been created from this repository session. The workflow is intentionally manual and disabled unless `RAILWAY_INTEGRATED_DEPLOY_ENABLED=true`.

## Railway service configuration

Create or identify a dedicated staging service in the existing Railway project, separate from the restricted service.

Set these service variables:

| Variable | Required value |
|---|---|
| `RAILWAY_DOCKERFILE_PATH` | `Dockerfile.integrated` |
| `C2C_RUNTIME_MODE` | `integrated` |
| `C2C_CAPTURE_CONFIG_JSON` | Multiline JSON described below; seal this variable after setting it |
| `C2C_INTERNAL_SERVICE_TOKEN` | High-entropy internal-service bearer secret; seal it |
| `C2C_VIN_HMAC_PEPPER` | High-entropy VIN HMAC secret; seal it |
| `C2C_ARTIFACT_STORAGE_ROOT` | `/var/lib/claim2car/evidence` |
| `C2C_INCIDENT_INTAKE_ENABLED` | `false` until counsel approves the supplemental disclosure |

Railway supports multiline variables and sealed values. The runtime accepts the JSON directly from `C2C_CAPTURE_CONFIG_JSON`; the file-based `C2C_CAPTURE_CONFIG_FILE` path remains supported for local and other deployments. The JSON must contain `health_database_url`, `dsn_by_role`, and `credentials`. Each credential entry contains an actor ID, tenant ID, database role, SHA-256 token hash, expiry, enabled flag, and actor role. Do not put raw bearer tokens in this JSON.

Attach one persistent Railway volume to the integrated service at exactly `/var/lib/claim2car/evidence`. Keep this service at one replica; the evidence store is local filesystem-backed. Configure and rehearse volume backups before storing any real evidence. The image starts a short root entrypoint only to set the mounted directory ownership, then drops the application process to UID 10001. Do not override this with `RAILWAY_RUN_UID=10001` or run the application as root.

The container listens on port 8000. Configure the service health check to `/health/ready`. The deploy smoke also checks `/health/build` for the exact commit SHA and integrated runtime mode, the operator shell, and unauthenticated API boundaries.

## Database requirements

The application uses PostgreSQL and the repository's authority migration stream. The Oracle MySQL DB system is not a compatible target for this application. The GitHub deploy workflow applies `python -m database.migrate` before deploying. If the separate routing database is provisioned, set `ROUTING_MIGRATION_DATABASE_URL` in GitHub Actions and `ROUTING_DATABASE_URL` in the Railway service; otherwise dispatch/routing remains unavailable.

The GitHub runner must be able to reach `MIGRATION_DATABASE_URL` (for example, through a restricted TLS TCP proxy). The runtime JSON should use the database's private service address for the health and tenant-role DSNs where available. The migration DSN must have the DDL privileges required by the authority migrations; it is not used by the running application. Runtime actor DSNs must use tenant login roles bound to the corresponding tenant and granted the intended `faos_app` membership.

## GitHub Actions settings

Set these repository/environment secrets:

- `RAILWAY_INTEGRATED_TOKEN` — project-scoped Railway token for the integrated staging service
- `RAILWAY_INTEGRATED_PROJECT_ID`
- `RAILWAY_INTEGRATED_ENVIRONMENT_ID`
- `RAILWAY_INTEGRATED_SERVICE_ID`
- `MIGRATION_DATABASE_URL` — migration-only PostgreSQL connection string
- `ROUTING_MIGRATION_DATABASE_URL` — optional, only if the separate routing database is provisioned

Set these variables:

- `RAILWAY_INTEGRATED_STAGING_URL` — HTTPS public origin of the integrated service
- `RAILWAY_INTEGRATED_DEPLOY_ENABLED` — leave `false` until service, database, volume, and secrets are configured

The workflow `Integrated Railway staging deployment` is manual-only. It requires the `main` branch, `confirm_deploy=true`, and the deployment-enable variable. It applies migrations, confirms the SHA is still current `main`, uploads to the separately identified integrated service, then runs a live smoke against the exact revision.

## Release limitations

A successful infrastructure smoke is not business acceptance. The incident-intake feature remains disabled by default and pending legal review. Owner credentials are still provisioned rather than issued through a real identity-proofing/invitation flow. The 12-versus-16 capture-slot contract remains unresolved. Do not use real claimant or vehicle evidence until authentication, consent/legal review, storage backup/restore, field validation, and incident response controls are accepted.
