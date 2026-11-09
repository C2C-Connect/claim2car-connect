# Railway exit inventory and decision

**Inventory date:** 2026-11-09  
**Repository candidate inspected:** `e224d4f37b641f91741e27582d6d2248d1d0a344` (`cto/review-pr29`)  
**Railway workspace:** one project visible  
**Railway project:** `cozy-possibility` (`463d410b-09a3-4117-a3b5-05e6646e7807`)  
**Environment:** `production` (`0558adbd-0eb8-480c-b87d-a4b99a6b4cd3`)  
**Service:** `claim2car-connect` (`525467fe-b3b5-447c-aa1c-d31a96fe777e`)

## Observed resources

- The workspace dashboard listed one project and the project canvas showed one application service. The account workspace selector showed the current workspace and an option to create another; no other existing workspace was listed.
- The service source was `C2C-Connect/claim2car-connect` on GitHub. Railway showed the connected repository as current.
- The service had no active deployment. Railway reported that its deployment had been removed after remaining crashed too long. History listed three removed deployment records for the same commit.
- The removed service used the default Railpack builder. Its visible settings did not select the repository's restricted staging Dockerfile. The deployment log inspected for the 2026-11-05 17:13 CST attempt shows Uvicorn starting `app.intake_api:create_intake_app` and repeatedly crashing at `app/intake_api.py:26` with `ValueError('CAPTURE_RUNTIME_CONFIGURATION_REQUIRED')`.
- This Railway service was not running the separate restricted health-only CI image. It did not reach an active deployment or expose a public endpoint.
- The service had no public domain. It had an internal `claim2car-connect.railway.internal` DNS name.
- Auto deploy was disabled. The service Variables page showed no user-defined environment variables. It listed seven Railway-provided system variables; no values were exported.
- The workspace had one API token, created 2026-11-05; its token value was masked and not copied. No workspace SSH keys were registered.
- The project canvas showed no database or other service. No attached volume was visible. The workspace had no Railway-managed custom domains. The People page listed one admin member; two-factor authentication was off.
- Workspace settings showed a **Trial Workspace** plan with a $5 credit balance. Railway says deployments shut down when credits are exhausted. There was no payment method on file, no billing history, and no paid plan.

## What was preserved

- The application source and Git history are in the connected GitHub repository.
- The service's startup failure signature is recorded above. The raw logs were not exported; the inspected log contained a repeated startup stack trace and the configuration error.
- The provider-neutral cleanup change removes Railway-specific staging/deployment wiring and retains restricted container safety verification.
- No Railway user-defined runtime variables, database, attached volume, public domain, or active deployment were found during this inspection.
- No secret values were copied into this document.

## Executive decision

Railway is not required to run the repository's application code. The Railway service was a failed, non-public application deployment, not a running product or the separate restricted health-only CI runtime. Its startup failed because required capture runtime configuration was missing. There is no active deployment or user-defined runtime configuration to migrate. The project provides no current production capability and should not receive additional spend.

Do not claim production readiness based on the Railway deployment history. The acceptance matrix correctly records the integrated persistent deployment gate as unpassed. Before removing any Railway resource, retain this inventory and confirm the service, deployment history, and project itself are no longer needed. Permanent deletion must be separately confirmed at the point of deletion.

The technical exit path is to keep the OCI container build provider-neutral and complete a self-operated persistent deployment with PostgreSQL/PostGIS, durable evidence storage, backups and restore verification, secrets handling, TLS, monitoring, and operator runbooks. The current repository does not yet establish those operational controls or an available host. The Railway deployment workflow and account are not part of the production release process. Provider-neutral restricted-container verification remains CI-only and does not establish a production release process.

## Not inspected

- Logs and build artifacts for the other removed deployment records.
- Workspace audit logs and detailed usage history.
