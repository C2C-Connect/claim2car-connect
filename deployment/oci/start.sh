#!/usr/bin/env bash
set -euo pipefail

DATA_MOUNT=/srv/claim2car/data
SECRETS_DIR=/etc/claim2car/secrets
COMPOSE_ENV=/etc/claim2car/compose.env
COMPOSE_FILE=/opt/claim2car/deployment/oci/compose.yaml

if [[ $(id -u) -ne 0 ]]; then
  echo "Run this launcher as root." >&2
  exit 2
fi
if ! mountpoint -q "$DATA_MOUNT"; then
  echo "Required encrypted data volume is not mounted at $DATA_MOUNT; refusing to start." >&2
  exit 3
fi
for path in "$SECRETS_DIR/postgres_password" "$SECRETS_DIR/claim2car-runtime.json" /etc/claim2car/runtime.env "$COMPOSE_ENV"; do
  if [[ ! -f "$path" ]]; then
    echo "Required private configuration file is missing: $path" >&2
    exit 4
  fi
  if [[ $(stat -c '%a' "$path") != 600 || $(stat -c '%u' "$path") != 0 ]]; then
    echo "Private configuration file must be root-owned mode 0600: $path" >&2
    exit 5
  fi
done
for key in C2C_IMAGE C2C_POSTGRES_IMAGE C2C_CADDY_IMAGE; do
  reference=$(sed -n "s/^${key}=//p" "$COMPOSE_ENV")
  if [[ ! "$reference" =~ @sha256:[0-9a-f]{64}$ ]]; then
    echo "${key} must be an immutable sha256 image reference." >&2
    exit 6
  fi
done

install -d -m 0700 -o 999 -g 999 "$DATA_MOUNT/postgres"
install -d -m 0700 -o 10001 -g 10001 "$DATA_MOUNT/evidence"
cd /opt/claim2car
exec docker compose --env-file "$COMPOSE_ENV" -f "$COMPOSE_FILE" up --detach --remove-orphans
