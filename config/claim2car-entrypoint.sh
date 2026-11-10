#!/bin/sh
set -eu

storage_root="${C2C_ARTIFACT_STORAGE_ROOT:-/var/lib/claim2car/evidence}"
if [ "$storage_root" != "/var/lib/claim2car/evidence" ]; then
  echo "UNEXPECTED_EVIDENCE_STORAGE_ROOT" >&2
  exit 78
fi

# Railway attaches volumes as root. Fix only the mount root, then drop all
# privileges before starting the application; the application never runs root.
mkdir -p "$storage_root"
chown 10001:10001 "$storage_root"
chmod 0700 "$storage_root"
exec setpriv --reuid=10001 --regid=10001 --init-groups --no-new-privs --bounding-set=-all "$@"
