# Milestone 5 — Reports & Dispatch (Layers 6/7)

**Status:** Core implemented  
**Constants version:** 2026.11.03.5

## Built

| Component | Path |
|-----------|------|
| Redaction matrix | `backend/app/dispatch/redaction.py` |
| Multi-recipient dispatcher | `backend/app/dispatch/dispatcher.py` |
| 7-page Forensic Dossier | `backend/app/reports/forensic_pdf.py` |
| ACORD XML + gavel extension | `backend/app/reports/acord_xml.py` |
| Internal anchor ledger | `backend/app/anchor/ledger.py` |
| Public verify API | `POST /api/v1/verify/`, `GET /api/v1/verify/{session_id}` |
| Dispatch API | `POST /api/v1/dispatch/build` |

## Packages

| Role | Label |
|------|-------|
| owner | Digital Compass |
| dealer | Forensic Deal Jacket |
| shop | Digital Twin (PII stripped, masked VIN) |
| carrier | Trojan Horse FNOL + ACORD XML |

## Run

```bash
export PYTHONPATH=.
pytest tests/ -v
```
