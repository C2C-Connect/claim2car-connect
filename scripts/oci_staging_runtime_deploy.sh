#!/usr/bin/env bash
set -Eeuo pipefail
ROOT=/var/lib/claim2car; CONFIG=/etc/claim2car/runtime
IMAGE_REF="${OCI_IMAGE_REF:-}"; REGISTRY="${OCI_REGISTRY:-}"; REGISTRY_USER="${OCI_REGISTRY_USERNAME:-}"; REGISTRY_TOKEN="${OCI_REGISTRY_TOKEN:-}"
APP_PORT="${C2C_STAGING_LOOPBACK_PORT:-8000}"; DB_IMAGE="${C2C_POSTGRES_IMAGE:-postgis/postgis:16-3.4}"
APP_CONTAINER=claim2car-app; DB_CONTAINER=claim2car-db; NETWORK=claim2car-staging
fail(){ echo "FAIL: $*" >&2; exit 1; }
[[ $EUID -eq 0 ]] || fail "Run as root."
[[ "$IMAGE_REF" =~ :sha-[a-f0-9]{40}@sha256:[a-f0-9]{64}$ ]] || fail "OCI_IMAGE_REF must include commit tag and pinned digest."
[[ -n "$REGISTRY" && -n "$REGISTRY_USER" && -n "$REGISTRY_TOKEN" ]] || fail "Registry credentials missing."
[[ "$APP_PORT" =~ ^[0-9]{1,5}$ ]] && (( APP_PORT>=1024 && APP_PORT<=65535 )) || fail "Invalid loopback port."
for p in "$ROOT/postgres" "$ROOT/evidence"; do [[ -d "$p" ]] || fail "Storage path missing: $p"; mountpoint -q "$p" || fail "Storage path not mounted: $p"; if [[ "$p" == "$ROOT/evidence" ]]; then [[ "$(stat -c %u "$p")" == 10001 ]] || fail "Evidence storage must be UID 10001."; fi; done
for f in runtime.env capture-runtime.json postgres-init.sql seed-tenant.sql; do [[ -s "$CONFIG/$f" ]] || fail "Missing secret bootstrap file: $f"; done
chmod 0600 "$CONFIG/runtime.env"; source "$CONFIG/runtime.env"
printf '%s' "$REGISTRY_TOKEN" | podman login "$REGISTRY" --username "$REGISTRY_USER" --password-stdin
podman pull "$DB_IMAGE"; podman pull "$IMAGE_REF"; install -d -o 10001 -g 10001 "$ROOT/postgres/pgdata"
arch="$(podman image inspect "$IMAGE_REF" --format '{{.Os}}/{{.Architecture}}')"; [[ "$arch" == "linux/arm64" ]] || fail "Expected ARM64 app image; got $arch."
podman network exists "$NETWORK" || podman network create "$NETWORK"
if ! podman container exists "$DB_CONTAINER"; then
 podman run -d --name "$DB_CONTAINER" --restart=always --network "$NETWORK" --network-alias claim2car-db -e POSTGRES_PASSWORD="$PG_ADMIN_PASSWORD" -e POSTGRES_DB=postgres -e PGDATA=/var/lib/postgresql/data/pgdata -p 127.0.0.1:5432:5432 -v "$ROOT/postgres:/var/lib/postgresql/data:Z" -v "$CONFIG/postgres-init.sql:/docker-entrypoint-initdb.d/00-bootstrap.sql:ro,Z" "$DB_IMAGE"
else podman start "$DB_CONTAINER" >/dev/null || true; fi
ready=0; for i in $(seq 1 90); do if podman exec "$DB_CONTAINER" pg_isready -U postgres -d postgres >/dev/null 2>&1; then ready=1; break; fi; sleep 2; done
[[ "$ready" == 1 ]] || fail "PostgreSQL not ready."
podman run --rm --network "$NETWORK" -e MIGRATION_DATABASE_URL="$MIGRATION_DATABASE_URL" "$IMAGE_REF" python -m database.migrate
podman exec -i "$DB_CONTAINER" psql -U postgres -d claim2car -v ON_ERROR_STOP=1 < "$CONFIG/seed-tenant.sql"
previous=""; [[ -f "$CONFIG/last-image-ref" ]] && previous="$(cat "$CONFIG/last-image-ref")"
podman stop "$APP_CONTAINER" >/dev/null 2>&1 || true; podman rm "$APP_CONTAINER" >/dev/null 2>&1 || true
run_app(){ local ref="$1"; podman run -d --name "$APP_CONTAINER" --restart=always --network "$NETWORK" -p "127.0.0.1:$APP_PORT:8000" -e C2C_RUNTIME_MODE=integrated -e APP_DATABASE_URL="$APP_DATABASE_URL" -e C2C_INTERNAL_SERVICE_TOKEN="$C2C_INTERNAL_SERVICE_TOKEN" -e C2C_VIN_HMAC_PEPPER="$C2C_VIN_HMAC_PEPPER" -e C2C_CAPTURE_CONFIG_FILE=/run/secrets/capture-runtime.json -e C2C_ARTIFACT_STORAGE_ROOT=/var/lib/claim2car/evidence -e C2C_REQUIRE_PERSISTENT_EVIDENCE_MOUNT=true -v "$ROOT/evidence:/var/lib/claim2car/evidence:Z" -v "$CONFIG/capture-runtime.json:/run/secrets/capture-runtime.json:ro,Z" "$ref"; }
run_app "$IMAGE_REF"; revision="$(echo "$IMAGE_REF" | sed -E 's/.*sha-([0-9a-f]{40}).*/\1/')"; ok=0
for i in $(seq 1 60); do if curl --fail --silent "http://127.0.0.1:$APP_PORT/health/ready" >/dev/null 2>&1 && curl --fail --silent "http://127.0.0.1:$APP_PORT/health/build" | grep -q "$revision"; then ok=1; break; fi; sleep 3; done
if [[ "$ok" != 1 ]]; then podman logs "$APP_CONTAINER" >&2 || true; podman stop "$APP_CONTAINER" >/dev/null 2>&1 || true; podman rm "$APP_CONTAINER" >/dev/null 2>&1 || true; [[ -n "$previous" ]] && run_app "$previous"; fail "New deployment failed; rollback attempted."; fi
printf '%s\n' "$IMAGE_REF" > "$CONFIG/last-image-ref"; chmod 0600 "$CONFIG/last-image-ref"
systemctl enable --now podman-restart.service >/dev/null 2>&1 || fail "Podman restart service unavailable; reboot persistence cannot be guaranteed."
echo "PASS: image deployed, readiness and revision checked. Loopback HTTP only; TLS/private access remains separate."
