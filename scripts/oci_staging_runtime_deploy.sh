#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${C2C_STAGING_ROOT:-/var/lib/claim2car}"; CONFIG="${C2C_STAGING_RUNTIME_CONFIG:-/etc/claim2car/runtime}"
IMAGE_REF="${OCI_IMAGE_REF:-}"; REGISTRY="${OCI_REGISTRY:-}"; REGISTRY_USER="${OCI_REGISTRY_USERNAME:-}"; REGISTRY_TOKEN="${OCI_REGISTRY_TOKEN:-}"
APP_PORT="${C2C_STAGING_LOOPBACK_PORT:-8000}"; DB_IMAGE="${C2C_POSTGRES_IMAGE:-}"
APP_CONTAINER=claim2car-app; DB_CONTAINER=claim2car-db; NETWORK=claim2car-staging
fail(){ echo "FAIL: $*" >&2; exit 1; }
[[ $EUID -eq 0 ]] || fail "Run as root."
[[ "$IMAGE_REF" =~ :sha-[a-f0-9]{40}@sha256:[a-f0-9]{64}$ ]] || fail "OCI_IMAGE_REF must include commit tag and pinned digest."
[[ -n "$REGISTRY" && -n "$REGISTRY_USER" && -n "$REGISTRY_TOKEN" ]] || fail "Registry credentials missing."
[[ "$IMAGE_REF" == "$REGISTRY/"* ]] || fail "OCI_IMAGE_REF must use the authenticated OCI_REGISTRY host."
[[ "$DB_IMAGE" =~ @sha256:[a-f0-9]{64}$ ]] || fail "C2C_POSTGRES_IMAGE must be pinned by sha256 digest."
[[ "$APP_PORT" =~ ^[0-9]{1,5}$ ]] && (( APP_PORT>=1024 && APP_PORT<=65535 )) || fail "Invalid loopback port."
[[ -d "$CONFIG" && ! -L "$CONFIG" ]] || fail "Runtime config directory missing or symlinked."
for p in "$ROOT/postgres" "$ROOT/evidence"; do
 [[ -d "$p" && ! -L "$p" ]] || fail "Storage path missing or symlinked: $p"
 mountpoint -q "$p" || fail "Storage path not mounted: $p"
 [[ "$(stat -c %u:%g "$p")" == 10001:10001 ]] || fail "Storage mount root must be UID/GID 10001: $p"
 mode="$(stat -c %a "$p")"
 if [[ "$p" == "$ROOT/postgres" ]]; then
  [[ "$mode" == 750 ]] || fail "PostgreSQL storage mount root must be mode 0750: $p"
 else
  [[ "$mode" == 700 ]] || fail "Evidence storage mount root must be mode 0700: $p"
 fi
done
postgres_source="$(findmnt -rn -o SOURCE --mountpoint "$ROOT/postgres")" || fail "Unable to resolve PostgreSQL mount source."
evidence_source="$(findmnt -rn -o SOURCE --mountpoint "$ROOT/evidence")" || fail "Unable to resolve evidence mount source."
[[ -n "$postgres_source" && -n "$evidence_source" && "$postgres_source" != "$evidence_source" ]] || fail "PostgreSQL and evidence storage must be distinct mounted volumes."
for f in runtime.env capture-runtime.json postgres-init.sql seed-tenant.sql; do [[ -s "$CONFIG/$f" && ! -L "$CONFIG/$f" ]] || fail "Missing or symlinked bootstrap file: $CONFIG/$f"; done
[[ "$(stat -c %u "$CONFIG/runtime.env")" == 0 && "$(stat -c %a "$CONFIG/runtime.env")" == 600 ]] || fail "runtime.env must be root-owned mode 0600."
[[ "$(stat -c %u "$CONFIG/capture-runtime.json")" == 0 && "$(stat -c %a "$CONFIG/capture-runtime.json")" == 640 ]] || fail "capture-runtime.json must be root-owned mode 0640."
source "$CONFIG/runtime.env"
authfile="$(mktemp /run/claim2car-ocir-auth.XXXXXX)" || fail "Unable to create ephemeral registry auth file."
cleanup_authfile() { rm -f "$authfile"; }
trap cleanup_authfile EXIT
chmod 0600 "$authfile"
printf '%s' "$REGISTRY_TOKEN" | podman login --authfile "$authfile" "$REGISTRY" --username "$REGISTRY_USER" --password-stdin
podman pull --authfile "$authfile" "$DB_IMAGE"
podman pull --authfile "$authfile" "$IMAGE_REF"
cleanup_authfile
trap - EXIT
unset REGISTRY_TOKEN
install -d -o 10001 -g 10001 "$ROOT/postgres/pgdata"
db_arch="$(podman image inspect "$DB_IMAGE" --format '{{.Os}}/{{.Architecture}}')"; [[ "$db_arch" == "linux/arm64" ]] || fail "Expected ARM64 PostgreSQL image; got $db_arch."
arch="$(podman image inspect "$IMAGE_REF" --format '{{.Os}}/{{.Architecture}}')"; [[ "$arch" == "linux/arm64" ]] || fail "Expected ARM64 app image; got $arch."
podman network exists "$NETWORK" || podman network create "$NETWORK"
if ! podman container exists "$DB_CONTAINER"; then
 podman run -d --name "$DB_CONTAINER" --restart=always --network "$NETWORK" --network-alias claim2car-db -e POSTGRES_PASSWORD="$PG_ADMIN_PASSWORD" -e POSTGRES_DB=postgres -e PGDATA=/var/lib/postgresql/data/pgdata -p 127.0.0.1:5432:5432 -v "$ROOT/postgres:/var/lib/postgresql/data:Z" -v "$CONFIG/postgres-init.sql:/docker-entrypoint-initdb.d/00-bootstrap.sql:ro,Z" "$DB_IMAGE"
else
 db_mount="$(podman inspect "$DB_CONTAINER" --format '{{range .Mounts}}{{if eq .Destination "/var/lib/postgresql/data"}}{{.Source}}{{end}}{{end}}')" || fail "Unable to inspect existing PostgreSQL container."
 [[ "$db_mount" == "$ROOT/postgres" ]] || fail "Existing PostgreSQL container is bound to unexpected storage: $db_mount"
 db_image_id="$(podman inspect "$DB_CONTAINER" --format '{{.Image}}')" || fail "Unable to inspect PostgreSQL image identity."
 expected_db_image_id="$(podman image inspect "$DB_IMAGE" --format '{{.Id}}')" || fail "Unable to inspect pinned PostgreSQL image."
 [[ "$db_image_id" == "$expected_db_image_id" ]] || fail "Existing PostgreSQL container image differs from requested digest; controlled DB image migration/recreation required."
 podman start "$DB_CONTAINER" >/dev/null || fail "Existing PostgreSQL container failed to start."
fi
ready=0; for i in $(seq 1 90); do if podman exec "$DB_CONTAINER" pg_isready -U postgres -d postgres >/dev/null 2>&1; then ready=1; break; fi; sleep 2; done
[[ "$ready" == 1 ]] || fail "PostgreSQL not ready."
podman run --rm --network "$NETWORK" -e MIGRATION_DATABASE_URL="$MIGRATION_DATABASE_URL" "$IMAGE_REF" python -m database.migrate
podman exec -i "$DB_CONTAINER" psql -U postgres -d claim2car -v ON_ERROR_STOP=1 < "$CONFIG/seed-tenant.sql"
previous=""; [[ -f "$CONFIG/last-image-ref" ]] && previous="$(cat "$CONFIG/last-image-ref")"
podman stop "$APP_CONTAINER" >/dev/null 2>&1 || true; podman rm "$APP_CONTAINER" >/dev/null 2>&1 || true
run_app(){ local ref="$1"; podman run -d --name "$APP_CONTAINER" --restart=always --network "$NETWORK" --user 10001:10001 --read-only --cap-drop=ALL --security-opt=no-new-privileges --tmpfs /tmp:rw,nosuid,nodev,noexec,size=64m,uid=10001,gid=10001 -p "127.0.0.1:$APP_PORT:8000" -e C2C_RUNTIME_MODE=integrated -e APP_DATABASE_URL="$APP_DATABASE_URL" -e C2C_INTERNAL_SERVICE_TOKEN="$C2C_INTERNAL_SERVICE_TOKEN" -e C2C_VIN_HMAC_PEPPER="$C2C_VIN_HMAC_PEPPER" -e C2C_CAPTURE_CONFIG_FILE=/run/secrets/capture-runtime.json -e C2C_ARTIFACT_STORAGE_ROOT=/var/lib/claim2car/evidence -e C2C_REQUIRE_PERSISTENT_EVIDENCE_MOUNT=true -e SQUARE_ENVIRONMENT="${SQUARE_ENVIRONMENT:-}" -e SQUARE_SANDBOX_ACCESS_TOKEN="${SQUARE_SANDBOX_ACCESS_TOKEN:-}" -e SQUARE_SANDBOX_LOCATION_ID="${SQUARE_SANDBOX_LOCATION_ID:-}" -e SQUARE_SANDBOX_WEBHOOK_SIGNATURE_KEY="${SQUARE_SANDBOX_WEBHOOK_SIGNATURE_KEY:-}" -e SQUARE_SANDBOX_WEBHOOK_URL="${SQUARE_SANDBOX_WEBHOOK_URL:-}" -v "$ROOT/evidence:/var/lib/claim2car/evidence:Z" -v "$CONFIG/capture-runtime.json:/run/secrets/capture-runtime.json:ro,Z" "$ref"; }
image_revision() {
 local ref="$1"
 [[ "$ref" =~ :sha-([a-f0-9]{40})@sha256:[a-f0-9]{64}$ ]] || return 1
 printf '%s' "${BASH_REMATCH[1]}"
}
wait_for_app() {
 local expected_revision="$1"
 for i in $(seq 1 60); do
  if curl --fail --silent "http://127.0.0.1:$APP_PORT/health/ready" >/dev/null 2>&1 && curl --fail --silent "http://127.0.0.1:$APP_PORT/health/build" | python3 -c 'import json,sys; data=json.load(sys.stdin); sys.exit(0 if data.get("revision")==sys.argv[1] else 1)' "$expected_revision"; then return 0; fi
  sleep 3
 done
 return 1
}
revision="$(image_revision "$IMAGE_REF")" || fail "Unable to extract exact revision from requested image ref."
if ! run_app "$IMAGE_REF" || ! wait_for_app "$revision"; then
 podman logs "$APP_CONTAINER" >&2 || true
 podman stop "$APP_CONTAINER" >/dev/null 2>&1 || true
 podman rm "$APP_CONTAINER" >/dev/null 2>&1 || true
 if [[ -n "$previous" ]]; then
  previous_revision="$(image_revision "$previous")" || fail "New image failed and recorded rollback reference is invalid; no rollback launched."
  if run_app "$previous" && wait_for_app "$previous_revision"; then
   echo "PASS: rollback image readiness and exact revision verified: $previous_revision" >&2
  else
   podman logs "$APP_CONTAINER" >&2 || true
   podman stop "$APP_CONTAINER" >/dev/null 2>&1 || true
   podman rm "$APP_CONTAINER" >/dev/null 2>&1 || true
   fail "New deployment failed; rollback image also failed readiness/revision verification."
  fi
 else
  fail "New deployment failed and no prior image is recorded; app remains stopped."
 fi
 fail "New deployment failed; previous image was restored and verified. Database migrations are not automatically reversed."
fi
systemctl enable --now podman-restart.service >/dev/null 2>&1 || fail "Podman restart service unavailable; reboot persistence cannot be guaranteed."
printf '%s\n' "$IMAGE_REF" > "$CONFIG/last-image-ref"; chmod 0600 "$CONFIG/last-image-ref"
echo "PASS: image deployed, readiness and exact revision checked. Loopback HTTP only; TLS/private access remains separate."
