# OCI volume device identity preflight

Run this only after the OCI instance and both paravirtualized volumes exist. It asks OCI for the instance's volume attachments and proves that the two configured volume OCIDs each have exactly one `ATTACHED` paravirtualized attachment, a distinct `/dev/` path, and a corresponding guest block device.

```bash
python3 scripts/oci_volume_device_map.py \
  --instance-id "$C2C_STAGING_INSTANCE_OCID" \
  --postgres-volume-id "$C2C_POSTGRES_VOLUME_OCID" \
  --evidence-volume-id "$C2C_EVIDENCE_VOLUME_OCID"
```

The script is read-only. It emits the verified device mapping as JSON and exits nonzero if the OCI response is incomplete, either attachment is not attached/paravirtualized, a device path is missing or duplicated, or the guest device is not present as a block device.

**Important:** this is identity proof, not storage initialization. It does not inspect filesystem contents or authorize destructive operations. Do not run `mkfs`, partitioning, encryption, or mount commands until the returned OCIDs and device paths have been independently reconciled against the OCI Console/control plane and the volumes are confirmed new and empty. Existing filesystems and data must never be overwritten. The script intentionally does not format or mount anything.
