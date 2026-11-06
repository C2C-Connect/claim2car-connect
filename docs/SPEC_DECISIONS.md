# SPEC_DECISIONS.md — Conflict Resolution Log

**Rules (from Full Build Directive):**
1. Prefer the most detailed and most recent version of each formula or threshold.
2. Every constant, weight, and threshold lives in `config/forensic_constants.*` (versioned).
3. Log every conflict and the choice made here.

## Resolved

| Topic | Options | Decision | Date | Notes |
|-------|---------|----------|------|-------|
| Owner / vehicle-owner cash incentive | Owner cash payout vs none | **Permanently excluded** | 2026-11-02 | Legal counsel: liability exposure. No residual fields in data model, UI, or reports. All references to the historical payout amount eradicated from repositories and documents (2026-11-06). |
| Dealer acquisition fee (v1.3 D-01) | $175 vs $375–$425 range vs flat | **Flat $375, due on qualified-acquisition close** | 2026-11-06 | Plan v1.3. Single value in `config/forensic_constants.py` (`DEALER_ACQUISITION_FEE_USD`). |
| Repair-shop fee (v1.3 D-02) | $250 auction floor vs flat | **Flat $275, due on recorded shop acceptance of the vehicle** | 2026-11-06 | Plan v1.3. Acceptance precedes tow dispatch to that shop. `SHOP_FEE_USD`. |
| Operator payout trigger (v1.3 D-04) | Seal + acceptance vs acceptance-only vs shop vehicle acceptance | **Open — amount ($110) carried forward only** | 2026-11-06 | Plan v1.3: eligibility, trigger, split, reversals, disputes, and ledger treatment remain an open decision; no payout logic until approved. Shop acceptance authorizes dispatch/routing (confirmed separately). |
| Post-adjudication distribution (v1.3 §3.2, workstream M) | Manual vs automatic | **Automatic on workflow completion** | 2026-11-06 | Dealer dossier, shop repair packet, owner PDF, carrier 7-page document go to authorized parties. Full delivery state machine (generated/queued/sent/delivered/failed/accessed), idempotent retries, recipient verification per plan v1.3. Consent-gated; live sends pending attorney review. |
| Acceptance & guided navigation (v1.3 §4, D-13) | None vs Google Maps-class | **Guided navigation on acceptance** | 2026-11-06 | Receiving party gets step-by-step navigation to destination; tow driver routed to accepting shop. Provider behind an adapter (selection open, D-13); destination from the authorized acceptance record; tow-appropriate routing constraints; navigation handoff recorded separately from arrival/handoff. |
| Capture protocol | 12-point vs 16-point | **16-v1 default**; 12-v1 selectable and versioned | 2026-11-02 | Both recorded on every session. |
| S_i form | Weighted geometric vs cube-root vs arithmetic | **Geometric form required** (All-or-Nothing Trap) | 2026-11-02 | Prefer C_gps^0.30 × C_hash^0.45 × C_meta^0.25 (or equivalent multiplicative form). |
| RTV review band | 0.70 < RTV < 1.0 vs 0.70 ≤ RTV < 1.0 | **Inclusive lower bound** 0.70 ≤ RTV < 1.0 | 2026-11-02 | Unless a later more detailed version dictates otherwise. |
| Low-impact guard | E_k < 20 vs < 25 kJ | **E_k < 20 kJ** (stricter) | 2026-11-02 | |
| Photo link chain | Content-hash sequential linking | `link_k = SHA-256(content_k ‖ prev)` | 2026-11-03 | Used for notary and sealing. |
| NHTSA | Only external VIN/recall source | Affirmed | 2026-11-03 | All other third-party services self-hosted or internal behind adapters. |

## Pending (to be locked with unit tests in Layer 2/3)

| Topic | Options | Status |
|-------|---------|--------|
| R_struct weights | (0.45/0.30/0.15/0.10, r_y/2) vs (0.48/0.28/0.14/0.10, r_y/2.2, min(H,1.0)) | Deferred to Layer 2/3; will choose most detailed and lock with tests |
| P_struct | max(0,(r_y−0.55)·0.52)+0.38·P_brittle vs max(0,(r_y−0.6)·0.45)+0.4·P_brittle × w_zone | Deferred; same process |
| Dilithium-2 vs ML-DSA-65 | Different parameter sets | Pick one library/parameter set when post-quantum signing is implemented; document here |

## Performance targets (design targets, not gates)

- Sub-500 ms VIN path
- 180 ms / 30–50 ms class latency figures where cited
- $0.008 unit economics figure
- 99.98 % class availability figure

Measure and report actuals in benchmark files; do not block implementation on unvalidated targets.
