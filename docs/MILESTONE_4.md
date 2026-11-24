# Milestone 4 — Itemized Estimate & Valuation (Layer 3)

**Status:** Calculation modules exist; production adjudication is disabled pending server-verified evidence

- Controlled-test seed catalog resolver; no verified external OEM/CAPA feed
- Internal-value blend and age-based fallback curve; not market-verified ACV
- 51 jurisdictions RTV
- Weighted geometric S_i
- Adjudicator orchestrator

API: `POST /api/v1/triage/adjudicate` is hard-disabled (503) until evidence integrity, manifest, vehicle identity, market, and jurisdiction inputs are server-derived.
