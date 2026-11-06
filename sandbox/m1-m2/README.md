# Claim2Car Connect (FAOS)

**Canonical product repository**

## Status

| Milestone | Status |
|-----------|--------|
| 1 – Foundation | **COMPLETE** |
| 2 – Intake (Layer 1) | **NEAR COMPLETE** |
| 3 – Analysis | Not started |
| 4–7 | Not started |

**Commercial rule:** Operator payout $110 only. **No owner cash incentive.**

## Quick start – API

```bash
export PYTHONPATH=.
python -m pip install -r backend/requirements.txt
python -m uvicorn backend.app.main:app --reload --port 8000
```

## Tests

```bash
PYTHONPATH=. python -m pytest tests/ -v
# 14 passed at M2 snapshot
```

## Docs

- `docs/GOVERNANCE.md`
- `docs/LEGAL_REVIEW.md`
- `docs/SPEC_DECISIONS.md`
- `docs/MILESTONE_1.md`
- `docs/MILESTONE_2.md`

This branch (`sandbox/m1-m2`) contains the Grok sandbox M1+M2 scaffold parallel to the validated `main` foundation. Merge carefully; do not overwrite validated paths without review.
