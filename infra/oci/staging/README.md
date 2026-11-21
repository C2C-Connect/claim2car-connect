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

The stack is infrastructure code, not evidence of an applied deployment. It does not format/mount volumes, configure PostgreSQL, create Vault secrets, publish an OCIR image, or expose an application endpoint. After volumes are safely mounted and the host preflight passes, follow [the OCI Run Command deployment runbook](../../../docs/OCI_RUN_COMMAND_DEPLOYMENT.md) to enable the restricted private deployment and synthetic acceptance workflow. Those are subsequent controlled deployment steps.


## Host bootstrap behavior

The instance receives `cloud-init.yaml` as base64 user data. It installs Podman and storage-inspection utilities, creates the non-login runtime identity UID/GID 10001, prepares the PostgreSQL/evidence mountpoints, and enables the Podman socket. The bootstrap is intentionally non-destructive: it does not partition, format, encrypt, or mount block devices, and it does not install application secrets or start the application. After attaching volumes, identify each device against the OCI volume OCID using the OCI control plane and stable device metadata before any filesystem operation. Then configure persistent mounts, verify ownership, and run `claim2car-host-preflight`; it fails unless both dedicated volumes are mounted at their exact paths.
