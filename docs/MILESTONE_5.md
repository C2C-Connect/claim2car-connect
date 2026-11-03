# Milestone 5 — Reports & Dispatch (Layers 6/7)

**Status:** Complete  
**Constants version:** 2026.11.03.6

## Built

| Component | Path |
|-----------|------|
| Role-gated redaction matrix | `backend/app/dispatch/redaction.py` |
| Multi-recipient dispatcher (prism) | `backend/app/dispatch/dispatcher.py` |
| 7-page Forensic Dossier (structured + HTML) | `backend/app/reports/forensic_pdf.py` |
| ACORD XML + gavel / forensic extensions | `backend/app/reports/acord_xml.py` |
| Internal append-only anchor ledger | `backend/app/anchor/ledger.py` |
| Public verify API | `POST /api/v1/verify/`, `GET /api/v1/verify/{session_id}` |
| Dispatch build API | `POST /api/v1/dispatch/build` |
| Health + constants surfaces | `GET /health/*`, `GET /api/v1/config/constants` |

## Packages (role-gated)

| Role | Label | Key contents |
|------|-------|--------------|
| owner | Digital Compass | Plain-English summary, last-4 VIN, verdict, public_verify block |
| dealer | Forensic Deal Jacket | Full VIN, ACV/RTV, estimate lines, physics summary, Gold Lead hooks |
| shop | Digital Twin | Masked VIN, detections, depths, estimate lines, no owner PII |
| carrier | Trojan Horse FNOL Packet | Full payload + ACORD XML with forensic extensions |

Every package carries a **public_verify** block (session_id, merkle_root, master_hash, endpoint) so the dossier attestation page and independent verification work for all recipients.

## Design decisions (M5)

- Structured 7-page dossier is the primary deliverable. HTML + plain-text always generated; binary PDF via reportlab is an optional adapter (slot reserved).
- Redaction is allow-list based. Anchor / public_verify fields are intentionally preserved on every role.
- ACORD generation is carrier-only; other roles receive the dossier only.
- Internal ledger is the current anchoring backend. External Hyperledger / post-quantum signature adapters are reserved for later hardening.
- Owner cash incentive remains permanently excluded.

## How to run

```bash
export PYTHONPATH=.
pytest tests/test_dispatch.py -v
# Full suite
pytest tests/ -q
```

## Remaining (non-blocking for M5 close)

- Optional reportlab binary PDF renderer
- Post-quantum signature adapter
- Full React portals (payloads are ready)
- SFTP / carrier push adapters

These are explicitly deferred; the Layer 6/7 functional surface required by the architecture is complete and tested.
