# OCI staging persistent volume mount preparation

## Identity verification
After Terraform attaches the PostgreSQL and evidence volumes, use the read-only OCI attachment mapper:
\`python3 scripts/oci_volume_device_map.py --instance-id <instance-ocid> --postgres-volume-id <pg-volume-ocid> --evidence-volume-id <evidence-volume-ocid> --json-output /root/claim2car-volume-map.json\`
The mapping file is mode 0600 and contains verified OCIDs and guest block-device paths.

## Dry run
\`python3 scripts/oci_staging_volume_mount.py --mapping-json /root/claim2car-volume-map.json --postgres-volume-ocid <pg-ocid> --evidence-volume-ocid <evidence-ocid> --dry-run\`
It verifies exact volume IDs, block devices, disk/partition state, mount state, filesystems, signatures and mountpoint safety. Blank disks are reported as requiring an explicit format gate. No disk or mount changes occur.

## Initial format of newly created empty disks (irreversible)
Only for newly created, verified-empty OCI volumes, add:
\`--format-empty --confirm-format-ocids <pg-ocid>,<evidence-ocid>\`
The confirmation must exactly match both OCIDs. Existing XFS volumes mount without formatting. Unknown filesystems/signatures, partitions, already-mounted devices, symlinks, nonempty mountpoints, conflicting fstab entries and OCID mismatch are rejected.

Mounts are persisted by UUID. The script changes only mount-root ownership to UID/GID 10001 (no recursive chown), verifies UUID separation, then run \`claim2car-host-preflight\` before app deployment.
