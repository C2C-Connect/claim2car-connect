#!/usr/bin/env bash
set -Eeuo pipefail
root="$(python -c 'import uuid; print("output/database-runs/"+uuid.uuid4().hex)')"
mkdir -p "$root/database-guard" "$root/database-evidence"
root="$(cd "$root" && pwd)"
export FAOS_EVIDENCE_ROOT="$root"
finalize() {
  primary_rc=$?
  trap - EXIT
  set +e
  python scripts/candidate_manifest.py capture "$root/database-guard/after.json" > "$root/database-guard/after-capture.log" 2>&1
  capture_rc=$?
  python scripts/candidate_manifest.py compare "$root/database-guard/before.json" "$root/database-guard/after.json" > "$root/database-guard/compare.log" 2>&1
  compare_rc=$?
  (cd "$root" && sha256sum database-guard/before.json database-guard/after.json) > "$root/database-guard/manifests.sha256" 2>&1
  docker compose -p faos-active-run -f compose.database-tests.yml ps -a > "$root/database-evidence/container-state.log" 2>&1
  state_rc=$?
  docker compose -p faos-active-run -f compose.database-tests.yml logs --no-color > "$root/database-evidence/container.log" 2>&1
  logs_rc=$?
  docker image inspect postgis/postgis:16-3.4 --format '{{json .RepoDigests}} {{.Id}}' > "$root/database-evidence/image-digests.log" 2>&1
  image_rc=$?
  final_rc=$primary_rc
  for rc in "$capture_rc" "$compare_rc" "$state_rc" "$logs_rc" "$image_rc"; do
    if [ "$final_rc" -eq 0 ] && [ "$rc" -ne 0 ]; then final_rc=$rc; fi
  done
  printf 'classification=placeholder-scaffold-smoke-only\nacceptance_gates_verified=0/14\nprimary_exit_code=%s\nafter_capture_exit_code=%s\nmanifest_compare_exit_code=%s\ncontainer_state_exit_code=%s\ncontainer_logs_exit_code=%s\nimage_inspect_exit_code=%s\nfinal_exit_code=%s\n' "$primary_rc" "$capture_rc" "$compare_rc" "$state_rc" "$logs_rc" "$image_rc" "$final_rc" > "$root/database-evidence/status.txt"
  (cd "$root" && find database-guard database-evidence -type f -print0 | sort -z | xargs -0 sha256sum) > "$root/checksums.sha256"
  checksum_rc=$?
  if [ "$final_rc" -eq 0 ] && [ "$checksum_rc" -ne 0 ]; then final_rc=$checksum_rc; fi
  cat "$root/database-evidence/status.txt"
  echo "Evidence directory: $root"
  exit "$final_rc"
}
trap finalize EXIT
python scripts/candidate_manifest.py capture "$root/database-guard/before.json" > "$root/database-guard/before-capture.log" 2>&1
if bash scripts/run_database_acceptance.sh > "$root/database-evidence/harness.log" 2>&1; then
  harness_rc=0
else
  harness_rc=$?
fi
cat "$root/database-evidence/harness.log" || true
exit "$harness_rc"
