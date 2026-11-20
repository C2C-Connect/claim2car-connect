# OCI Terraform state bucket bootstrap

This one-time bootstrap creates the OCI Object Storage bucket required by the OCI-native Terraform backend. The bucket is private, versioned, tagged, and protected from Terraform destruction. It does **not** create application infrastructure.

## Bootstrap and migrate the bootstrap state

Run from this directory on a trusted workstation or OCI Cloud Shell with an authenticated OCI SDK profile and Terraform >= 1.12.0.

1. Confirm the OCI profile is authenticated and points to the intended tenancy and `us-chicago-1`.
2. Copy `terraform.tfvars.example` to `terraform.tfvars`; set the verified C2C compartment OCID. Never commit this file.
3. Initialize without the remote backend and review/apply the bucket creation locally:
   ```sh
   terraform init -backend=false
   terraform fmt -check
   terraform validate
   terraform plan
   terraform apply
   ```
4. Read the `state_bucket_name` and `state_namespace` outputs. Verify in OCI Console that the bucket is **NoPublicAccess** and **Versioning Enabled**.
5. Configure OCI IAM so the automation identity has the object permissions needed for this bucket (inspect/read/create/delete objects; bucket management only if required for bootstrap). Prefer a bucket-scoped policy predicate and do not grant broad tenancy-level object access.
6. Migrate the bootstrap stack's local state into the newly created bucket:
   ```sh
   terraform init -migrate-state -force-copy \
     -backend-config="bucket=$(terraform output -raw state_bucket_name)" \
     -backend-config="namespace=$(terraform output -raw state_namespace)" \
     -backend-config="key=claim2car/bootstrap.tfstate" \
     -backend-config="region=us-chicago-1" \
     -backend-config="config_file_profile=DEFAULT"
   ```
7. Re-run `terraform plan` and confirm it reports no changes. Keep a secure backup of the local state until the remote state is verified.

## Configure GitHub

In the repository's `oci-staging` environment, set variables `OCI_STATE_BUCKET` and `OCI_STATE_NAMESPACE` to the verified outputs. Configure the existing OCI API-key secrets and Terraform input secrets required by the staging plan workflow. Grant the automation identity the minimum bucket-specific object access needed for state and lock objects. Protect the separate `oci-staging-apply` environment with required reviewers.

The bucket's version history incurs storage charges for retained versions; monitor usage and do not delete prior state versions casually. The bootstrap resource has `prevent_destroy` enabled.

## State locations

- Bootstrap state: `claim2car/bootstrap.tfstate`
- Staging infrastructure state: `claim2car/oci-staging.tfstate`

The OCI native backend uses object-store locking. The state bucket is a prerequisite and must exist before the staging workflow can initialize its backend.
