#!/usr/bin/env bash
set -Eeuo pipefail
root="$(python -c 'import uuid; print("output/database-runs/"+uuid.uuid4().hex)')"
mkdir -p "$root/database-guard" "$root/database-evidence"
root="$(cd "$root" && pwd)"
export FAOS_EVIDENCE_ROOT="$root"
gate_verification_rc=not_run
gate_verification_exit_code=0
finalize() {
  primary_rc=$?
  trap - EXIT
  set +e
  python scripts/candidate_manifest.py capture "$root/database-guard/after.json" > "$root/database-guard/after-capture.log" 2>&1
  capture_rc=$?
  python scripts/candidate_manifest.py compare "$root/database-guard/before.json" "$root/database-guard/after.json" > "$root/database-guard/compare.log" 2>&1
  compare_rc=$?
  (cd "$root" && sha256sum database-guard/before.json database-guard/after.json) > "$root/database-guard/manifests.sha256" 2>&1
  manifests_rc=$?
  docker compose -p faos-active-run -f compose.database-tests.yml ps -a > "$root/database-evidence/container-state.log" 2>&1
  state_rc=$?
  docker compose -p faos-active-run -f compose.database-tests.yml logs --no-color > "$root/database-evidence/container.log" 2>&1
  logs_rc=$?
  docker image inspect postgis/postgis:16-3.4 --format '{{json .RepoDigests}} {{.Id}}' > "$root/database-evidence/image-digests.log" 2>&1
  image_rc=$?
  final_rc=$primary_rc
  for rc in "$capture_rc" "$compare_rc" "$manifests_rc" "$state_rc" "$logs_rc" "$image_rc"; do
    if [ "$final_rc" -eq 0 ] && [ "$rc" -ne 0 ]; then final_rc=$rc; fi
  done
  printf 'classification=counted-database-test-evidence\nacceptance_gates_verified=0/14\nprimary_exit_code=%s\ngate_verification_exit_code=%s\nafter_capture_exit_code=%s\nmanifest_compare_exit_code=%s\nmanifest_hash_exit_code=%s\ncontainer_state_exit_code=%s\ncontainer_logs_exit_code=%s\nimage_inspect_exit_code=%s\npre_checksum_exit_code=%s\n' "$primary_rc" "$gate_verification_rc" "$capture_rc" "$compare_rc" "$manifests_rc" "$state_rc" "$logs_rc" "$image_rc" "$final_rc" > "$root/database-evidence/status.txt"
  status_rc=$?
  if [ "$final_rc" -eq 0 ] && [ "$status_rc" -ne 0 ]; then final_rc=$status_rc; fi
  (cd "$root" && find database-guard database-evidence -type f -print0 | sort -z | xargs -0 sha256sum) > "$root/checksums.sha256"
  checksum_rc=$?
  verify_rc=not_run
  if [ "$checksum_rc" -eq 0 ]; then
    (cd "$root" && sha256sum --check checksums.sha256) > "$root/checksum-verification.log" 2>&1
    verify_rc=$?
  fi
  if [ "$final_rc" -eq 0 ] && [ "$checksum_rc" -ne 0 ]; then final_rc=$checksum_rc; fi
  if [ "$final_rc" -eq 0 ] && [ "$verify_rc" != not_run ] && [ "$verify_rc" -ne 0 ]; then final_rc=$verify_rc; fi
  # Root-level footer and checksum files are outside the checksummed payload.
  printf 'classification=counted-database-test-evidence\nacceptance_gates_verified=0/14\nchecksum_scope=database-guard/,database-evidence/\nstatus_write_exit_code=%s\nchecksum_generation_exit_code=%s\nchecksum_verification_exit_code=%s\nfinal_exit_code=%s\n' "$status_rc" "$checksum_rc" "$verify_rc" "$final_rc" > "$root/final-status.txt"
  summary_rc=$?
  if [ "$final_rc" -eq 0 ] && [ "$summary_rc" -ne 0 ]; then final_rc=$summary_rc; fi
  cat "$root/database-evidence/status.txt"
  cat "$root/final-status.txt"
  printf 'summary_write_exit_code=%s\nprocess_exit_code=%s\n' "$summary_rc" "$final_rc"
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
if [ "${FAOS_LEGACY_BASELINE_ALLOWED:-0}" = "1" ]; then
  # This workflow is intentionally pre-cutover. It validates only the legacy
  # component comparison suite; DB-01..DB-14 acceptance is evaluated by the
  # separate full-authority workflow after all 31 migrations are applied.
  gate_verification_rc=not_applicable
  printf 'classification=legacy-precutover-component-smoke\\nacceptance_gates=NOT_APPLICABLE\\nreason=authority_schema_not_installed\\n' > "$root/database-evidence/gate-verification.log"
else
  if python tests/database/verify_gates.py --preflight --report "$root/database-evidence/counted-tests.json" > "$root/database-evidence/gate-verification.log" 2>&1; then
    gate_verification_rc=0
  else
    gate_verification_rc=$?
  fi
  gate_verification_exit_code=$gate_verification_rc
fi
cat "$root/database-evidence/gate-verification.log" || true
if [ "$harness_rc" -ne 0 ]; then
  exit "$harness_rc"
fi
exit "$gate_verification_exit_code"
