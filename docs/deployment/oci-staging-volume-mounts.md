# OCI staging persistent volume mount preparation

## Identity before mutation
Use the read-only OCI attachment identity mapper after the Terraform stack has attached the PostgreSQL and evidence volumes:
\`python3 scripts/oci_volume_device_map.py --instance-id <instance-ocid> --postgres-volume-id <pg-volume-ocid> --evidence-volume-id <evidence-volume-ocid> --json-output /root/claim2car-volume-map.json\`
The file contains the proven OCID-to-device map, mode 0600.

## Dry run
\`python3 scripts/oci_staging_volume_mount.py --mapping-json /root/claim2car-volume-map.json --postgres-volume-ocid <pg-ocid> --evidence-volume-ocid <evidence-ocid> --dry-run\`
The helper checks exact OCIDs, unique device mapping, block devices, no partitions, mount state, filesystem, and signatures. It never formats in dry-run.

## Initial format (irreversible)
For newly created empty OCI block volumes only, formatting is explicitly authorized by both flags:
\`--format-empty --confirm-format-ocids <pg-ocid>,<evidence-ocid>\`
It refuses any existing filesystem, partition, signature, mounted device, or unexpected type. It creates XFS, mounts by UUID, adds validated fstab entries, sets only mount-root ownership (UID/GID 10001), and verifies distinct mount UUIDs. Existing XFS volumes are mounted without formatting. It does not recursively chown data. Run the host preflight after mount and before app deployment.
