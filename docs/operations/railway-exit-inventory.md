# Railway exit inventory and decision

**Inventory date:** 2026-11-09  
**Repository candidate inspected:** `e224d4f37b641f91741e27582d6d2248d1d0a344` (`cto/review-pr29`)  
**Railway workspace:** one project visible  
**Railway project:** `cozy-possibility` (`463d410b-09a3-4117-a3b5-05e6646e7807`)  
**Environment:** `production` (`0558adbd-0eb8-480c-b87d-a4b99a6b4cd3`)  
**Service:** `claim2car-connect` (`525467fe-b3b5-447c-aa1c-d31a96fe777e`)

## Observed resources

- The workspace dashboard listed one project and the project canvas showed one application service. The account workspace selector showed the current workspace and an option to create another; no other existing workspace was listed.
- The service source is `C2C-Connect/claim2car-connect` on GitHub. Railway showed the connected repository as current.
- The service had no active deployment. Railway reported that its deployment had been removed after remaining crashed too long.
- The service had no public domain. It had an internal `claim2car-connect.railway.internal` DNS name.
- Auto deploy was disabled. The builder was Railway Railpack.
- The service Variables page showed no user-defined environment variables. It listed seven Railway-provided system variables; no values were exported. The workspace had one API token, created 2026-11-05; its token value was masked and not copied. No workspace SSH keys were registered.
- The project canvas showed no database or other service. No attached volume was visible. The workspace had no Railway-managed custom domains. The People page listed one admin member; two-factor authentication was off.
- Workspace settings showed a **Trial Workspace** plan with a $5 credit balance. Railway says deployments shut down when credits are exhausted. There was no payment method on file, no billing history, and no paid plan.

## What was preserved

- The application source and Git history are in the connected GitHub repository.
- The repository contains a root `Dockerfile` and Git history for the application. The provider-neutral cleanup change removes Railway-specific staging/deployment wiring and retains restricted container safety verification.
- No Railway user-defined runtime variables, database, attached volume, public domain, or active deployment were found during this inspection.
- No secret values were copied into this document.

## Executive decision

Railway is not required to run the repository's application code. The active Railway project is a failed, restricted health-only staging service, not the integrated claims application. It has no active deployment or user-defined runtime configuration to migrate. The project therefore provides no current production capability and should not receive additional spend.

Do not claim production readiness based on the Railway deployment history. The acceptance matrix correctly records the integrated persistent deployment gate as unpassed. Before removing any Railway resource, retain this inventory and confirm the service, deployment history, and project itself are no longer needed. Permanent deletion must be separately confirmed at the point of deletion.

The technical exit path is to keep the OCI container build provider-neutral and complete a self-operated persistent deployment with PostgreSQL/PostGIS, durable evidence storage, backups and restore verification, secrets handling, TLS, monitoring, and operator runbooks. The current repository does not yet establish those operational controls or an available host. The Railway deployment workflow and account are not part of the production release process. Provider-neutral restricted-container verification remains CI-only and does not establish a production release process.

## Not inspected

- Historical deployment logs and build artifacts.
- The contents of Railway-generated environment variables (these are platform-provided values, not user-defined secrets).
