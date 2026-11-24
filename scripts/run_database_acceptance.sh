#!/usr/bin/env bash
# This harness is the legacy comparison suite, not a deployment command.
set -Eeuo pipefail
if [ "${FAOS_MIGRATIONS_ALREADY_APPLIED:-0}" != "1" ]; then
  python -m database.migrate --legacy-baseline
fi
if [ "${FAOS_LEGACY_BASELINE_ALLOWED:-0}" = "1" ]; then
  python scripts/run_counted_tests.py database --legacy-baseline --record "$FAOS_EVIDENCE_ROOT/database-evidence/counted-tests.json"
else
  python scripts/run_counted_tests.py database --record "$FAOS_EVIDENCE_ROOT/database-evidence/counted-tests.json"
fi
