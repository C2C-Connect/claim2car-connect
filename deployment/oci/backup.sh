#!/usr/bin/env bash
set -euo pipefail
umask 077

ROOT=/opt/claim2car
COMPOSE_FILE="$ROOT/deployment/oci/compose.yaml"
COMPOSE_ENV=/etc/claim2car/compose.env
BACKUP_ENV=/etc/claim2car/backup.env
DATA=/srv/claim2car/data
SECRETS=/etc/claim2car/secrets

if [[ $(id -u) -ne 0 ]]; then
  echo "Run backup as root." >&2
  exit 2
fi
for path in "$COMPOSE_ENV" "$BACKUP_ENV" "$SECRETS/postgres_password"; do
  [[ -f "$path" && $(stat -c '%a' "$path") == 600 && $(stat -c '%u' "$path") == 0 ]] || {
    echo "Required root-owned mode 0600 file is missing or has unsafe permissions: $path" >&2
    exit 3
  }
done
[[ -d "$DATA/postgres" && -d "$DATA/evidence" ]] || {
  echo "Persistent database/evidence directories are missing." >&2
  exit 4
}
# This file contains only the backup bucket name, not credentials.
source "$BACKUP_ENV"
[[ -n "${C2C_BACKUP_BUCKET:-}" ]] || { echo "C2C_BACKUP_BUCKET is required." >&2; exit 5; }

cd "$ROOT"
compose=(docker compose --env-file "$COMPOSE_ENV" -f "$COMPOSE_FILE")
work=$(mktemp -d /var/backups/claim2car/.backup.XXXXXX)
app_stopped=0
restart_app() {
  if [[ "$app_stopped" == 1 ]]; then
    "${compose[@]}" start app >/dev/null || echo "ALERT: failed to restart Claim2Car app after backup." >&2
  fi
}
cleanup() {
  restart_app
  rm -rf -- "$work"
}
trap cleanup EXIT

# Quiesce all application writes while PostgreSQL and local evidence bytes are paired.
"${compose[@]}" stop --timeout 60 app
app_stopped=1
"${compose[@]}" exec --no-TTY postgres sh -ec \
  'PGPASSWORD="$(cat /run/secrets/postgres_password)" pg_dump --username=postgres --dbname=claim2car --format=custom --no-owner' \
  > "$work/claim2car.dump"
"${compose[@]}" exec --no-TTY postgres sh -ec \
  'PGPASSWORD="$(cat /run/secrets/postgres_password)" pg_dumpall --username=postgres --globals-only' \
  > "$work/postgres-globals.sql"
tar --numeric-owner -C "$DATA" -czf "$work/evidence.tar.gz" evidence
sed -n 's/^C2C_IMAGE=//p' "$COMPOSE_ENV" > "$work/image-digest.txt"
grep -Eq '^[^[:space:]]+@sha256:[0-9a-f]{64}$' "$work/image-digest.txt" || {
  echo "C2C_IMAGE must be an immutable sha256 reference." >&2
  exit 6
}
date -u +'%Y-%m-%dT%H:%M:%SZ' > "$work/created-at-utc.txt"
sha256sum "$work/claim2car.dump" "$work/postgres-globals.sql" "$work/evidence.tar.gz" "$work/image-digest.txt" "$work/created-at-utc.txt" \
  > "$work/SHA256SUMS"
archive="$work/claim2car-$(date -u +'%Y%m%dT%H%M%SZ').tar.gz"
tar -C "$work" --exclude="$(basename "$archive")" -czf "$archive" .
checksum=$(sha256sum "$archive" | cut -d ' ' -f 1)
name="${C2C_BACKUP_PREFIX:-claim2car}/${checksum}.tar.gz"

oci os object put --auth instance_principal --bucket-name "$C2C_BACKUP_BUCKET" \
  --file "$archive" --name "$name" --force >/dev/null
oci os object head --auth instance_principal --bucket-name "$C2C_BACKUP_BUCKET" --name "$name" >/dev/null
echo "Claim2Car backup uploaded and object HEAD verified: $name sha256=$checksum"
