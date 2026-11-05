# Full tree push status

The complete Milestone 3–5 source tree lives in the companion zip:
`claim2car-connect-M3-M5-snapshot-20261103.zip`

This branch receives the tree incrementally via the GitHub connector.

## Modules to verify on branch after sync

- backend/app/physics/darci.py
- backend/app/analysis/{consensus,pipeline}.py
- backend/app/vision/adapters.py
- backend/app/catalog/parts_catalog.py
- backend/app/valuation/acv.py
- backend/app/jurisdiction/thresholds.py
- backend/app/integrity/s_i.py
- backend/app/triage/adjudicate.py
- backend/app/dispatch/{redaction,dispatcher}.py
- backend/app/reports/{forensic_pdf,acord_xml}.py
- backend/app/anchor/ledger.py
- backend/app/api/{analysis,triage,dispatch}.py
- tests/test_*.py
- config/forensic_constants.py

## Tests

46 passed locally (`pytest tests/ -q`)
