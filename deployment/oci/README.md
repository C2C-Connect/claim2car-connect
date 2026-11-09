# Claim2Car OCI deployment package (PR #29 child branch)

This package targets a single OCI Compute VM running Docker Compose. It is a deployment candidate, not evidence of a live deployment or acceptance. No OCI resources, images, DNS records, secrets, or billing changes have been created.

## Suitability and limits

The existing `Dockerfile.integrated` supports one integrated API container, PostgreSQL-backed tenant sessions, and a POSIX persistent evidence directory. The storage implementation requires local filesystem semantics such as atomic hard links and `fsync`; do not mount evidence on NFS or an object-store FUSE mount. This package therefore uses a local persistent volume for live evidence and requires encrypted off-host backups before any real evidence is accepted.

A single VM is a low-complexity pilot candidate only if the selected VM shape and storage allocation can run the image and hold both primary data and retained backups. It is a single failure domain. This is not suitable for a production availability commitment until restore and failover objectives are approved and demonstrated. The OCI Always Free A1 allowance is region-limited to the tenancy's home region, has finite OCPU/memory and boot-volume limits, and capacity is not guaranteed; verify eligibility and current quota in the OCI Console before choosing it ([Always Free resources](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm)). Avoid changing the account billing type as a workaround. OCI instance principals can avoid long-lived API keys on the VM; they require an instance dynamic group and scoped policies ([instance principal guidance](https://docs.oracle.com/en-us/iaas/Content/Identity/Tasks/callingservicesfrominstances.htm)). Monitoring alarms use resource metrics, and the compute monitoring agent must be enabled for supported metrics ([monitoring setup](https://docs.oracle.com/en-us/iaas/Content/Compute/Tasks/enablingmonitoring.htm), [Monitoring overview](https://docs.oracle.com/en-us/iaas/Content/Monitoring/Concepts/monitoringoverview.htm)).

## Package contents

- `compose.yaml`: integrated app, PostgreSQL 16, and Caddy TLS edge; PostgreSQL has no host port and sits on an internal Docker network.
- `bootstrap-roles.sql`: least-privilege base roles for the primary database; passwords and tenant login roles are provisioned separately.
- `Caddyfile`: HTTPS reverse proxy and baseline response headers. DNS must point at the VM, and ports 80/443 must be reachable for certificate issuance/renewal.
- `.env.example`: non-secret image and domain settings only.
- `start.sh`: refuses to start unless the dedicated data volume is mounted and root-only secret files exist.
- `backup.sh` and systemd unit/timer: quiesced paired database/evidence backup to OCI Object Storage using instance-principal auth, with archive checksum and remote object HEAD verification.
- `backup.env.example`: bucket name and object prefix only; no credentials.

The app, PostgreSQL, and Caddy images must be verified and pinned by immutable digest. Prefer mirroring the base images to the private OCI Registry. The app image must be built from the reviewed PR #29 commit. Do not publish or deploy an image until the relevant CI succeeds and the OCI registry/repository choice and cost are approved.

## Required OCI setup before provisioning

1. User selects an OCI region (for an Always Free attempt, check the account's home region), a DNS hostname under their control, and an explicit monthly spending ceiling. Verify available VM shapes, boot/block volume capacity, quotas, and current prices in the Console; no shape is assumed to be free.
2. User enables MFA and confirms account email/phone and billing profile in OCI directly. Do not send account identifiers, secrets, or payment details in chat.
3. Create a dedicated compartment and a minimal network: public subnet with only TCP 80/443 from the internet; SSH only from the user's fixed administrative IP or use OCI Bastion. Do not expose TCP 5432 or Docker's TCP API. Assign a reserved public IP if the selected design and budget permit it.
4. Create a private OCI Registry repository. Deploy from an immutable image digest. Use a short-lived auth token only for the host's registry login; keep it out of Git and shell history.
5. Store `postgres_password`, `claim2car-runtime.json`, and `runtime.env` in OCI Vault Secrets. Grant only this VM's dynamic group permission to read the named secrets and access objects in the specific backup bucket. Do not grant tenancy-wide object-family access. On the VM, materialize the current secret versions as root-owned files under `/etc/claim2car/secrets` with mode `0600`; `/etc/claim2car/runtime.env` must also be root-owned and mode `0600`. Provision these out-of-band before Compose starts. The runtime JSON has a strict schema in `app/capture_api.py`; create tenant login roles, credentials, and matching DSNs through an authorized administrator process. Never commit these values or paste them into a ticket or chat.
6. Attach an encrypted block volume for PostgreSQL and evidence data, mounted by UUID at `/srv/claim2car/data` before Docker starts. Keep evidence on a local filesystem. Restrict access to the VM and backup objects; bucket must be private and encrypted at rest.
7. Configure OCI Compute monitoring agent and OCI Monitoring alarms/Notifications for instance CPU, memory/disk pressure where supported, and instance availability. Configure an external HTTPS check for `/health/ready`; alert on failed readiness checks. Forward the systemd backup service result or a backup-age check to an alert destination and alert when no successful off-host backup exists within the approved interval. Container health status alone is not an alerting system.

The secret file paths in the Compose file are fixed at `/etc/claim2car/secrets`. The `runtime.env` must provide valid `C2C_INTERNAL_SERVICE_TOKEN` (43-128 URL-safe characters) and `C2C_VIN_HMAC_PEPPER`; use independent randomly generated values. `claim2car-runtime.json` must use DSNs for the Compose service `postgres` and the provisioned tenant login roles. The postgres password used in those DSNs must match the secret mounted by PostgreSQL. Values must never be put in `compose.env` or CI logs.

## First-start sequence (operator runbook)

1. Verify the VM's region, shape, volume capacity, OCI Vault policy scope, private bucket policy, security list/NSG ingress, DNS, and spending ceiling in the OCI Console. Stop if any item is unconfirmed.
2. Attach and mount the encrypted data volume at `/srv/claim2car/data` with an `/etc/fstab` UUID entry. The supplied root-only `start.sh` verifies it is mounted and prepares restrictive directories for PostgreSQL (UID/GID 999) and evidence (UID/GID 10001) before starting Compose. Do not bypass this mount check.
3. Materialize Vault secrets to the fixed root-only paths; verify permissions without printing contents. Log into OCI Registry on the host with a short-lived token. Put the domain and image digest in a root-owned `/etc/claim2car/compose.env`. Put the migration URL in `/etc/claim2car/migration.env`, also root-owned mode `0600`, and create `/etc/claim2car/backup.env` from `backup.env.example` with root ownership and mode `0600`; create `/var/backups/claim2car` root-owned mode `0700` for the systemd service.
4. Start only PostgreSQL with Compose. Run `bootstrap-roles.sql` against the new empty `claim2car` database as the database administrator. Set the `faos_migrator` password from OCI Vault through the root-only operator process and put its DSN in `migration.env` as `MIGRATION_DATABASE_URL`.
5. Before applying migrations, take an encrypted block-volume snapshot and run the off-host backup procedure against the initialized but still empty database. The backup timer captures the database custom dump, PostgreSQL global roles, paired evidence files, image reference, timestamp, and checksums while the app is stopped. The backup archive is uploaded over TLS with the VM's instance principal; OCI Object Storage provides server-side encryption at rest. Verify the bucket's encryption and private access policy.
6. Run the one-off migration container with the reviewed image: `docker compose --env-file /etc/claim2car/compose.env -f deployment/oci/compose.yaml --profile migrations run --rm migrator`. Then verify the migration ledger, database authority readiness, tenant login roles/bindings, and runtime JSON schema. The Compose package deliberately does not auto-migrate or create tenant identities.
7. Build/push the reviewed image with CI-proven SHA, then `docker compose --env-file /etc/claim2car/compose.env -f deployment/oci/compose.yaml pull` and start it using `deployment/oci/start.sh`. Confirm `https://$C2C_DOMAIN/health/ready` and inspect only sanitized health/log output.
8. Install `claim2car-backup.service` and `.timer` in `/etc/systemd/system`, reload systemd, enable/start the timer, and inspect its result without printing secret files. Configure OCI Monitoring/Notifications or an equivalent checked alert route to report missed daily backup objects and failed service runs.
9. Verify the app has no host-published port, PostgreSQL has no host-published port, unauthenticated capture/reviewer routes reject requests, internal analysis rejects missing credentials, and the OCI edge serves a valid renewed certificate. Run an authorized synthetic end-to-end capture/review with labeled test data before any real participants or evidence.

Do not use the placeholders in `.env.example` as live configuration. Compose startup is not a release gate and does not prove that migration, tenant role provisioning, secure secret retrieval, backups, or restore works.

## Backup and restore gate

Database and original evidence bytes are separate durable state. `backup.sh` writes a PostgreSQL custom-format dump, PostgreSQL global roles, a filesystem archive of the evidence directory, the Compose image digest, a UTC timestamp, and SHA-256 checksums. It quiesces writes by stopping the app while it takes the paired backup, then uploads to the private OCI Object Storage bucket using instance-principal auth and verifies the object exists. Verify bucket encryption and private access in OCI. Set an owner-approved retention rule and retain an independent second copy. Avoid mounting object storage as the live evidence filesystem. The backup timer is prepared but has not run; review the script and verify it on synthetic data before enabling it.

Before accepting live evidence, retrieve a backup into an isolated disposable VM/volume, verify `SHA256SUMS`, restore PostgreSQL globals and the database dump, restore the evidence archive and required OCI Vault secret versions, run the repository's database acceptance/recovery checks on an isolated restored copy, verify evidence retrieval against its stored digest, and record restore duration and recovery point. Repeat on a schedule and alert on missing/failed backups. No restore has been performed as part of this change; this gate remains open.

## Release gates that remain open

- OCI account owner confirms region, hostname, spending ceiling, and VM/storage eligibility.
- Runtime roles, tenant bindings, real secret issuance/rotation, and the migration authority path are documented and verified.
- OCI Registry image is built from the selected PR commit and pinned by digest.
- OCI Vault dynamic-group and bucket object policies are scoped to this VM, required secret versions, and named backup bucket; PostgreSQL runtime roles/tenant bindings are reconciled to the capture contract.
- VM, TLS ingress, persistent volume ownership, secret delivery, monitoring/alerts, encrypted backups, and isolated restore are verified.
- PR #29's release matrix is updated from evidence collected from the actual persistent deployment. Keep PR #29 draft and do not merge to `main` before the deployment and release gates pass.

## PR reconciliation status

- PR #29 is the implementation base and remains draft.
- PR #30 is a draft Railway-removal proposal based on an older PR #29 base revision. Its changed files are limited to Railway workflow/config/docs plus renaming the restricted-container safety path; reconcile its unique Railway-removal intent with this OCI path before merging or closing either PR.
- PR #28 is open, non-draft, and GitHub currently reports it as not mergeable. Compared with PR #29's head, GitHub reports one unique PR #28 commit and 144 commits on PR #29's side since their merge base; PR #28's changes touch 138 files. That single commit contains many earlier features and history, so its unique changes have not been reconciled against PR #29; do not close it or delete its branch based on age alone.
