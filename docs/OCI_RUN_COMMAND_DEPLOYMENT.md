# OCI Run Command: private staging deploy and synthetic acceptance

This workflow uses OCI Compute Instance Run Command. It does **not** require public SSH, a Bastion tunnel, or a public application endpoint.

## Preconditions

1. Terraform has provisioned the private compute host, PostgreSQL/evidence block volumes, and enabled the **Compute Instance Run Command** Oracle Cloud Agent plugin.
2. Volumes are identified by OCI volume OCID, formatted/mounted at `/var/lib/claim2car/postgres` and `/var/lib/claim2car/evidence`, with UID/GID 10001 and the required modes. Run `claim2car-host-preflight` and confirm PASS. Formatting/mounting is intentionally not automated until the volume identities are verified.
3. Cloud-init has completed. It installs OCI CLI and writes three root-owned, checksum-verifying wrappers. The OCI `ocarun` user is allowed to sudo **only those wrappers**; it is not granted general root.
4. Create an OCI Vault secret containing the OCIR pull token. The Run Command script fetches it using the instance principal. The token is never included in the GitHub workflow input or OCI Run Command text.
5. Configure the OCI IAM policies below.

## IAM configuration (manual prerequisite)

Create a dynamic group, e.g. `Claim2CarStagingRunCommand`, with a matching rule restricted to the exact staging instance:

```
ALL {instance.id = '<staging-instance-OCID>'}
```

Create a policy in the compartment containing the instance and Vault secret (adjust compartment scope if they are separate):

```
Allow dynamic-group Claim2CarStagingRunCommand to use instance-agent-command-execution-family in compartment C2C where request.instance.id = target.instance.id
Allow dynamic-group Claim2CarStagingRunCommand to read secret-bundles in compartment C2C where target.secret.id = '<OCIR-token-secret-OCID>'
Allow group Claim2CarStagingDeployers to manage instance-agent-command-family in compartment C2C
Allow group Claim2CarStagingDeployers to inspect instances in compartment C2C
```

The first two statements grant the instance principal command execution and access to only the specified Vault secret. The latter statements grant the GitHub OCI API-key user the ability to submit and inspect commands. If your OCI identity-domain syntax requires a domain-qualified group name, use that exact name. Do not grant tenancy-wide access.

## GitHub `oci-staging` environment

Required secrets:

- `OCI_USER_OCID`, `OCI_TENANCY_OCID`, `OCI_API_FINGERPRINT`, `OCI_API_PRIVATE_KEY`
- `OCI_COMPARTMENT_OCID`, `OCI_STAGING_INSTANCE_OCID`
- `OCI_OCIR_VAULT_SECRET_OCID` (Vault secret OCID; not the token)
- `OCIR_USERNAME`

Required variables:

- `OCI_REGION` (default `us-chicago-1`)
- `OCIR_NAMESPACE`, `OCIR_REPOSITORY`
- `OCI_STAGING_POSTGRES_IMAGE` (full image reference pinned by digest)

Keep the existing `OCIR_AUTH_TOKEN` secret for image publication. Store the corresponding pull token in OCI Vault for the instance principal.

## Execution

1. Publish the integrated ARM64 image with the manual **Publish integrated Claim2Car image to OCIR** workflow.
2. Copy the exact image reference from its summary (commit tag **and** digest).
3. Run the manual **Deploy private OCI staging and run synthetic acceptance** workflow from `main`; choose `confirm_deploy=yes` and supply the immutable image reference.
4. The workflow checks OCI API authentication and source/image SHA alignment, then creates an OCI Run Command. The instance downloads the bootstrap/deploy/acceptance scripts from the exact source commit and verifies their SHA-256 values.
5. If runtime secret files are absent, it generates synthetic-only credentials on the host. It retrieves the OCIR pull token from Vault through instance principal, deploys the digest-pinned image, and runs the 16-slot synthetic acceptance harness.
6. The workflow reports OCI command execution state and acceptance output. A failed command, deploy, readiness check, revision check, or acceptance exits nonzero. No live payment is enabled.

The acceptance run verifies the 16 capture slots, seal/manifest, reviewer original-byte retrieval, runtime restart persistence, tamper rejection, and consent-withdrawal deletion. It deliberately creates synthetic records only and does not certify camera authenticity, real claim adjudication, production, or field operations.

## Recovery / re-run

The runtime bootstrap is one-time and refuses to overwrite non-empty runtime secrets. Re-running deployment preserves the existing synthetic tenant/tokens and verifies the previous image if rollback is needed. Database migrations are not automatically reversed. Inspect OCI Run Command execution status/output and the host container logs before retrying.

OCI documentation:

- [Running Commands on an Instance](https://docs.oracle.com/en-us/iaas/Content/Compute/Tasks/runningcommands.htm)
- [OCI CLI instance-agent command create](https://docs.oracle.com/en-us/iaas/tools/oci-cli/latest/oci_cli_docs/cmdref/instance-agent/command/create.html)
- [OCI CLI command-execution get](https://docs.oracle.com/en-us/iaas/tools/oci-cli/latest/oci_cli_docs/cmdref/instance-agent/command-execution/get.html)
