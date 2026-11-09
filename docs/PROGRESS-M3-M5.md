# Progress Marker — Batch M3 + M4 + M5 (2026-11-03)

> **Historical snapshot — 2026-11-03.** Status labels below describe the scope and branch/sandbox context recorded on that date. They are not current canonical release status, integrated-product acceptance, field validation, or deployment evidence. The Founder-approved five-slice execution plan and current Slice 1/architecture evidence supersede any broader interpretation of these milestone labels.


**Branch target:** `sandbox/m3-m4-m5-snapshot`  
**Canonical repo:** `C2C-Connect/claim2car-connect`  
**Constants:** `2026.11.03.6`

## Milestone status

| Milestone | Status |
|-----------|--------|
| 1 Foundation | Complete |
| 2 Intake (Layer 1) | Near complete (camera/gates/Notary path) |
| **3 Analysis (Layer 2)** | **Complete** — DARCI, 55/45, vision adapters, guards |
| **4 Itemized estimate & valuation (Layer 3)** | **Complete** — catalog, ACV, 51 jurisdictions, S_i, adjudicator |
| **5 Reports & dispatch (Layers 6/7)** | **Complete** — redaction prism, 7-page dossier, ACORD, anchor ledger, public verify |
| 6 Marketplace (Layer 4) | Next |
| 7 Self-audit (Layer 5) | Not started |

## Test status

- Slice 1 correction (2026-11-06): the earlier "46 passed" claim was not reproducible from any
  committed branch — the forensic constants file was never committed with the values the M3–M5 code
  referenced (28+ missing names). The constants have been reconstructed (test-pinned, docstring-pinned,
  or explicitly provisional) and the full non-database suite now passes: **136 passed + 93 subtests**.
  The full suite (including database/integration tests) runs in CI via `.github/workflows/full-suite.yml`.
- Coverage of core formulas (physics, consensus, S_i, ACV, RTV, jurisdiction, redaction, anchor, ACORD, dispatch)

## Key artifacts solidified in this batch

### Layer 2
- `backend/app/physics/darci.py`
- `backend/app/analysis/consensus.py` + `pipeline.py`
- `backend/app/vision/adapters.py`

### Layer 3
- `backend/app/catalog/parts_catalog.py`
- `backend/app/valuation/acv.py`
- `backend/app/jurisdiction/thresholds.py`
- `backend/app/integrity/s_i.py`
- `backend/app/triage/adjudicate.py`

### Layers 6/7
- `backend/app/dispatch/redaction.py` (allow-list + public_verify block)
- `backend/app/dispatch/dispatcher.py` (4-role prism)
- `backend/app/reports/forensic_pdf.py` (7-page structured dossier)
- `backend/app/reports/acord_xml.py`
- `backend/app/anchor/ledger.py`
- `backend/app/api/analysis.py`, `api/triage.py`, `api/dispatch.py`

## Decisions enforced

- Owner cash incentive permanently removed (legal counsel).
- Internal valuation/catalog only at runtime (no Black Book / Manheim dependency).
- Weighted geometric S_i with All-or-Nothing Trap.
- Physics primacy 55/45 + hard guards (low-impact, severe-impact, structural collapse).
- Every dispatch package carries a public-safe verification block.
- All commercial / legal-claim features built and flagged “pending attorney review before publication” (see LEGAL_REVIEW.md).

## How to demonstrate

```bash
export PYTHONPATH=.
pytest tests/ -q
# Smoke dispatch
python -c "
from backend.app.dispatch.dispatcher import build_dispatch
from tests.test_dispatch import _sample_adj
r = build_dispatch(_sample_adj(), vin='1HGCM82633A004352', photo_hashes=['a','b'])
print([p.role for p in r.packages], 'pages=', len(r.packages[0].dossier.pages))
"
```

## Next

Milestone 6 — Marketplace (Layer 4):
- XGBoost assignment engine (62-feature style)
- BFPI / Gold Leads
- F&I Buddy hooks
- Dealer command center payloads
- Two-stage auction with anti-snipe
- Parts RFP
- Payout ledger

After M5 is pushed and confirmed on GitHub, proceed directly to M6.
