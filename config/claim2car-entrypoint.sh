#!/bin/sh
set -eu

storage_root="${C2C_ARTIFACT_STORAGE_ROOT:-/var/lib/claim2car/evidence}"
if [ "$storage_root" != "/var/lib/claim2car/evidence" ]; then
  echo "UNEXPECTED_EVIDENCE_STORAGE_ROOT" >&2
  exit 78
fi
if [ ! -d "$storage_root" ] || [ -L "$storage_root" ]; then
  echo "EVIDENCE_STORAGE_ROOT_MISSING_OR_SYMLINKED" >&2
  exit 78
fi

# A root launch remains supported for local development. The protected staging
# deploy launches as UID/GID 10001 and must not mutate the mounted volume.
if [ "$(id -u)" -eq 0 ]; then
  chown 10001:10001 "$storage_root"
  chmod 0700 "$storage_root"
  exec setpriv --reuid=10001 --regid=10001 --init-groups --no-new-privs "$@"
fi

owner="$(stat -c '%u:%g' "$storage_root")"
mode="$(stat -c '%a' "$storage_root")"
if [ "$(id -u)" != "10001" ] || [ "$(id -g)" != "10001" ] || [ "$owner" != "10001:10001" ] || [ "$mode" != "700" ]; then
  echo "EVIDENCE_STORAGE_OWNER_OR_MODE_INVALID" >&2
  exit 78
fi
exec "$@"
