# Claim2Car OCI private staging foundation

This stack describes a private OCI compute host and two separate encrypted-in-transit block-volume attachments for PostgreSQL data and original evidence. It uses the existing Claim2Car VCN/private subnet and never assigns a public IP.

## Deliberate safety boundaries

- The stack permits only `VM.Standard.A1.Flex`, defaulting to 1 OCPU and 6 GB RAM. OCI Always Free eligibility, regional capacity, tenancy quotas, and aggregate free-tier usage must still be confirmed in the OCI Console before apply. A shape name is not a price guarantee.
- Default storage is 50 GB boot + 50 GB PostgreSQL + 100 GB evidence, bounded by a 200 GB stack budget. Existing tenancy volumes may consume part of the free allowance; inspect billing/usage before apply.
- No ingress rule is created by default. Supply only verified Bastion/VPN source CIDRs and private application ingress CIDRs. Never use `0.0.0.0/0` for SSH or the application.
- The existing subnet's security lists are separate from this instance NSG. Audit and remove any broad ingress rules from the subnet security lists before treating the host as secure; an NSG does not cancel permissive subnet security-list rules.
- The image OCID, compartment, VCN, and subnet are explicit inputs. No tenancy identifiers or credentials are stored in this repository.
- OCI provider authentication is supplied out-of-band through the standard OCI SDK configuration or workload identity. Do not commit API keys, private keys, state files, or real `terraform.tfvars`.
- A guarded, manual GitHub Actions apply workflow is available on `main`. It requires the `confirm_apply=yes` input, the protected `oci-staging` environment for planning, and the separate `oci-staging-apply` environment for apply. GitHub environment reviewer approval is enforced only if reviewers/protection rules are configured in repository settings. It creates a saved plan, rejects destructive actions, and applies only that exact plan. CI PR workflows perform formatting and static validation; no pull-request workflow applies infrastructure.

## Controlled GitHub Actions path

For the repository-managed path, configure the protected GitHub environments and required secrets/variables before use. Run the manual **Bootstrap private OCI Terraform state bucket** workflow first, then **OCI staging infrastructure plan (manual, no apply)** to validate credentials and inspect a non-destructive plan. For provisioning, run **OCI staging apply (manual, guarded)** from `main` with `confirm_apply=yes`; it produces a one-day saved plan, rejects delete/replace actions, and requires the separate `oci-staging-apply` environment approval before applying that exact plan. Never approve a plan without reviewing resource counts and tenancy costs. The local Terraform path remains available for operators using their own OCI profile.

### GitHub environment configuration prerequisites

In repository **Settings → Environments**, configure `oci-staging` and `oci-staging-apply`. Add required reviewers / deployment protection to `oci-staging-apply` before relying on it as an approval gate. **GitHub environment secrets and variables do not flow from `oci-staging` into `oci-staging-apply`; configure the apply environment separately.** The apply job now fails before Terraform initialization if its required OCI credentials, OCIDs, or state-bucket variables are missing. Store these **environment secrets** in both environments as needed:

- `OCI_USER_OCID`, `OCI_TENANCY_OCID`, `OCI_API_FINGERPRINT`, `OCI_API_PRIVATE_KEY`
- `OCI_COMPARTMENT_OCID`, `OCI_VCN_OCID`, `OCI_PRIVATE_SUBNET_OCID`, `OCI_STAGING_IMAGE_OCID`
- `OCI_STAGING_SSH_PUBLIC_KEYS`
- Optional JSON arrays: `OCI_ADMIN_INGRESS_CIDRS_JSON`, `OCI_APP_INGRESS_CIDRS_JSON` (empty arrays default to no ingress; public CIDRs are rejected)

Set environment **variables** `OCI_STATE_BUCKET` and `OCI_STATE_NAMESPACE`; `OCI_REGION` defaults to `us-chicago-1`. The state bucket must be created/secured with the manual bootstrap workflow before Terraform initialization. OCIR publishing separately needs `OCIR_USERNAME` and `OCIR_AUTH_TOKEN` secrets plus `OCIR_NAMESPACE` and `OCIR_REPOSITORY` variables.

## Use

1. Confirm the private subnet, NAT/service-gateway routes, security lists, Bastion/VPN path, image compatibility, regional A1 capacity, free-tier usage, and billing estimate in OCI.
2. Copy `terraform.tfvars.example` to `terraform.tfvars` and enter the verified OCIDs locally.
3. Authenticate with the OCI CLI/SDK using a local profile or an approved workload identity.
4. Run `terraform init`, `terraform fmt -check -recursive`, `terraform validate`, and `terraform plan`.
5. Review the plan and tenancy cost/quotas before a separately controlled apply. Do not apply from a pull-request workflow.
6. After creation, format and mount the two attached volumes by stable OCI device identifiers, configure PostgreSQL 16/PostGIS on the database volume, and mount original evidence at `/var/lib/claim2car/evidence` owned by UID 10001. Verify reboot persistence before deploying the integrated container.

The stack is infrastructure code, not evidence of an applied deployment. It does not yet configure PostgreSQL, create Vault secrets, publish an OCIR image, or expose an application endpoint. Those are subsequent controlled deployment steps.


## Host bootstrap behavior

The instance receives `cloud-init.yaml` as base64 user data. It installs Podman and storage-inspection utilities, creates the non-login runtime identity UID/GID 10001, prepares the PostgreSQL/evidence mountpoints, and enables the Podman socket. The bootstrap is intentionally non-destructive: it does not partition, format, encrypt, or mount block devices, and it does not install application secrets or start the application. After attaching volumes, identify each device against the OCI volume OCID using the OCI control plane and stable device metadata before any filesystem operation. Then configure persistent mounts, verify ownership, and run `claim2car-host-preflight`; it fails unless both dedicated volumes are mounted at their exact paths.

## Private runtime deployment via OCI Instance Agent Run Command
### Exact GitHub/OCI inputs

The private deployment workflow uses the `oci-staging-apply` environment. Set these variables there (and also in `oci-staging` where noted for Terraform plan/apply):

- `OCI_ENABLE_PRIVATE_RUNCOMMAND_DEPLOY=true` and `OCI_OCIR_AUTH_SECRET_OCID` in both protected environments.
- `OCI_STAGING_INSTANCE_OCID` to the instance OCID output from Terraform in `oci-staging-apply`.
- `C2C_POSTGRES_IMAGE` to the official `docker.io/postgis/postgis` image, with a version tag and immutable digest (for example, `docker.io/postgis/postgis:16-3.5@sha256:<digest>`). The root wrapper rejects any other database repository.
- `OCI_REGION=us-chicago-1`, `OCIR_NAMESPACE`, and `OCIR_REPOSITORY`.
- OCI API user key credentials and `OCI_COMPARTMENT_OCID` in `oci-staging-apply`.
- `OCIR_USERNAME` and `OCIR_AUTH_TOKEN` in `oci-staging-apply`; the runner uses password-stdin to verify the digest currently published for the image's commit tag, then removes its temporary Docker auth config. The token is never included in Run Command content.

The deployer IAM group must have command create/cancel and execution-read permission; use OCI's `instance-agent-command-family` and `instance-agent-command-execution-family` policy resource types. The deployment wrapper itself permits sudo only for its root-owned entry point, validates the fixed registry and exact app repository, and does not accept arbitrary shell commands.

The official OCI Run Command feature executes scripts through Oracle Cloud Agent and does not require inbound SSH. OCI warns not to include credentials in Run Command text; this implementation sends only image metadata and a Vault secret OCID, and retrieves the OCIR token on the instance through its instance principal. See [Oracle Run Command documentation](https://docs.oracle.com/en-us/iaas/Content/Compute/Tasks/runningcommands.htm).


The repo now includes a guarded manual workflow to deploy the integrated ARM64 image to the private instance without SSH or inbound network rules. This path requires the host and IAM setup below and is **not active until the protected environment inputs are configured and Terraform is applied**.

### Required OCI setup

1. Create an OCI Vault secret in the C2C compartment named for the staging OCIR pull credential. Its secret content must be JSON with exactly the needed fields, for example:
   ```json
   {"username":"<OCIR username>","auth_token":"<OCIR auth token>"}
   ```
   Do not put the token in Git, Terraform variables/state, workflow input, Run Command text, or logs.
2. Copy the Vault secret OCID. Set GitHub environment variable `OCI_OCIR_AUTH_SECRET_OCID` in both `oci-staging` and `oci-staging-apply`. Set `OCI_ENABLE_PRIVATE_RUNCOMMAND_DEPLOY=true` in both environments.
3. The Terraform apply user must be allowed to create tenancy-scoped dynamic groups and policies. When the feature is enabled, the stack creates a dynamic group matching only the staging instance and a policy that permits that instance to execute Run Command and read only the OCIR Vault secret OCID.
4. Apply Terraform with `tenancy_ocid`, `enable_private_runcommand_deploy=true`, and `ocir_auth_secret_ocid` configured. This enables the Compute Instance Run Command plugin, installs OCI CLI in a dedicated virtual environment, installs a root-owned deployment wrapper, and grants `ocarun` sudo only for that wrapper—not arbitrary commands.
5. Configure the OCI API user used by GitHub Actions with permissions to create/cancel instance-agent commands and read execution status for the staging instance. A least-privilege group policy can be scoped to the C2C compartment:
   ```
   Allow group <C2C-deployers> to manage instance-agent-command-family in compartment id <C2C-compartment-OCID>
   Allow group <C2C-deployers> to use instance-agent-command-execution-family in compartment <C2C>
   Allow group <C2C-deployers> to read instances in compartment <C2C>
   ```
6. Set these GitHub environment variables in `oci-staging-apply`: `OCI_STAGING_INSTANCE_OCID` (Terraform output), `C2C_POSTGRES_IMAGE` (immutable digest-pinned image), `OCI_REGION`, `OCIR_NAMESPACE`, and `OCIR_REPOSITORY`. The API key credentials and compartment OCID must also be configured in that protected environment.
7. Publish the integrated image with the manual **Publish integrated Claim2Car image to OCIR** workflow. Its summary provides the commit tag and digest. Use the combined immutable ref `<image-tag>@<sha256-digest>` as the deploy workflow input.
8. Run the manual **Deploy integrated Claim2Car image to private OCI staging** workflow from `main`, set `confirm_deploy=yes`, and provide the exact immutable image reference. The runner submits a secret-free Run Command and waits for the instance execution to succeed. The host fetches the deploy script from the image's source commit and verifies its SHA-256 before running it; the OCIR token is retrieved from Vault using the instance principal.

The Run Command payload contains only the source commit, immutable app/database image refs, script checksum, registry host, and Vault secret OCID. Registry username/token remain in OCI Vault and are fetched by the instance. OCI Run Command retains plain-text scripts for a limited period; do not place credentials or private key material in its content.

The dispatcher fails closed on non-main refs, missing inputs, image/repository mismatch, mutable image tags, missing secret OCID, or a command execution that does not finish successfully. It does not mark staging as deployed until the host deployment script returns success. If the deployment command fails, inspect the OCI Run Command execution record; output is deliberately not copied into GitHub logs to avoid accidental secret disclosure.

This adds a deploy mechanism; it does not certify that OCI provisioning or runtime acceptance has occurred. Verify host readiness, both volume mounts, DB/PostGIS readiness, restart persistence, capture evidence retrieval, tenant isolation, and backup/restore after the first real apply/deploy.
