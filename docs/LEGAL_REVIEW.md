# LEGAL_REVIEW.md — Attorney Review Checklist

**Purpose:** Single list of every feature or claim the attorney must examine before any external publication. This list replaces prior legal/compliance gates.

**Status:** Features below are approved for development. They are **pending attorney review before publication**.

## Commercial & Payout

- [ ] Operator (tow) $110 payout trigger (e-signature verified + S_i ≥ 0.65 + dealer acceptance)
- [ ] Internal payout ledger and manual-settlement adapter
- [ ] Dealer acquisition fee range $375–$425, pay-on-close
- [ ] fee_factor active in dealer assignment scoring
- [ ] Shop auction floor $250 and two-stage Sovereign Repair Auction mechanics
- [ ] **Confirmed excluded:** any owner / vehicle-owner cash incentive or $80 consent payout

## Evidentiary & Integrity Claims

- [ ] SHA-256 sequential hash chaining and Merkle root sealing language
- [ ] Public verification endpoint (`/api/verify/`) claims and kill-switch behavior
- [ ] Forensic Integrity Score (S_i) thresholds and All-or-Nothing geometric form
- [ ] Chain-of-custody and “Forensic Notary” language
- [ ] Post-quantum signature claims (Dilithium / ML-DSA parameter set once chosen)
- [ ] Any FRE 901 / 902 or similar evidentiary framing in reports or portals

## Reports & Dispatch

- [ ] 7-page Forensic PDF Audit Dossier content and redaction matrix
- [ ] Role-gated packages (Owner Digital Compass, Dealer Deal Jacket, Shop Digital Twin, Carrier FNOL)
- [ ] ACORD 1 XML AutoLoss export and any carrier-facing claims language
- [ ] Public QR / exhibit verification flows

## Marketplace & Data

- [ ] Brand-matched dealer routing and capacity/fee scoring
- [ ] BFPI / Gold Lead identification language
- [ ] Shop auction anti-snipe and cryptographic bid chaining
- [ ] Internal ACV blend, P_s structural adjustment, Forensic RTV, and jurisdiction thresholds

## Capture & Consent

- [ ] Owner e-signature package (pressure-sensitive, GPS, NTP, device fingerprint) — **no cash incentive**
- [ ] Dual-plate VIN cross-check and ISO 3779 handling
- [ ] Offline WORM outbox and CrashBundle semantics

## Notes for counsel

- All legal/evidentiary/commercial features are built under the Full Build Directive.
- Publication is blocked until this checklist is reviewed and any required changes are made.
- Update this file when new claim surfaces are added.
