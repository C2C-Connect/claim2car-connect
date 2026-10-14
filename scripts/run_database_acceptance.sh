#!/usr/bin/env bash
set -Eeuo pipefail
python -m database.migrate
python scripts/run_counted_tests.py database --record "$FAOS_EVIDENCE_ROOT/database-evidence/counted-tests.json"
