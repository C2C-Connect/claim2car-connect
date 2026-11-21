# Claim2Car OCI private staging foundation

This stack describes a private OCI compute host and two separate encrypted-in-transit block-volume attachments for PostgreSQL data and original evidence. It uses the existing Claim2Car VCN/private subnet and never assigns a public IP.

## Deliberate safety boundaries

- The stack permits only `VM.Standard.A1.Flex`, defaulting to 1 OCPU and 6 GB RAM. OCI Always Free eligibility, regional capacity, tenancy quotas, and aggregate free-tier usage must still be confirmed in the OCI Console before apply. A shape name is not a price guarantee.
- Default storage is 50 GB boot + 50 GB PostgreSQL + 100 GB evidence, bounded by a 200 GB stack budget. Existing tenancy volumes may consume part of the free allowance; inspect billing/usage before apply.
- No ingress rule is created by default. Supply only verified Bastion/VPN source CIDRs and private application ingress CIDRs. Never use `0.0.0.0/0` for SSH or the application.
- The existing subnet's security lists are separate from this instance NSG. Audit and remove any broad ingress rules from the subnet security lists before treating the host as secure; an NSG does not cancel permissive subnet security-list rules.
- The image OCID, compartment, VCN, and subnet are explicit inputs. No tenancy identifiers or credentials are stored in this repository.
- OCI provider authentication is supplied out-of-band through the standard OCI SDK configuration or workload identity. Do not commit API keys, private keys, state files, or real `terraform.tfvars`.
- A guarded, manual GitHub Actions apply workflow is available on `main`. It requires the `confirm_apply=yes` input, the protected `oci-staging` environment for planning, and the separate `oci-staging-apply` environment for apply approval. It creates a saved plan, rejects destructive actions, and applies only that exact plan. CI PR workflows perform formatting and static validation; no pull-request workflow applies infrastructure.

## Controlled GitHub Actions path

For the repository-managed path, configure the protected GitHub environments and required secrets/variables before use. Run the manual **Bootstrap private OCI Terraform state bucket** workflow first, then **OCI staging infrastructure plan (manual, no apply)** to validate credentials and inspect a non-destructive plan. For provisioning, run **OCI staging apply (manual, guarded)** from `main` with `confirm_apply=yes`; it produces a one-day saved plan, rejects delete/replace actions, and requires the separate `oci-staging-apply` environment approval before applying that exact plan. Never approve a plan without reviewing resource counts and tenancy costs. The local Terraform path remains available for operators using their own OCI profile.

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
