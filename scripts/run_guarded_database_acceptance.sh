#!/usr/bin/env bash
set -Eeuo pipefail
root="$(python -c 'import uuid; print("output/database-runs/"+uuid.uuid4().hex)')"
mkdir -p "$root/database-guard" "$root/database-evidence"
root="$(cd "$root" && pwd)"
export FAOS_EVIDENCE_ROOT="$root"
python scripts/candidate_manifest.py capture "$root/database-guard/before.json"
bash scripts/run_database_acceptance.sh
python scripts/candidate_manifest.py capture "$root/database-guard/after.json"
python scripts/candidate_manifest.py compare "$root/database-guard/before.json" "$root/database-guard/after.json"
echo "Guard checks passed successfully."
