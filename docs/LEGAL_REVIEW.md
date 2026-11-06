# LEGAL_REVIEW.md — Attorney Review Checklist

**Purpose:** Single list of every feature or claim the attorney must examine before any external publication. This list replaces prior legal/compliance gates.

**Status:** Features below are approved for development. They are **pending attorney review before publication**.

## Commercial & Payout

- [ ] Operator (tow) $110 payout — amount carried forward; trigger, eligibility, reversals, and ledger treatment remain open (plan v1.3, D-04)
- [ ] Internal payout ledger and manual-settlement adapter
- [ ] Flat $375 dealer acquisition fee, due on qualified-acquisition close (plan v1.3, D-01)
- [ ] fee_factor active in dealer assignment scoring
- [ ] Flat $275 repair-shop fee, due on recorded shop acceptance of the vehicle (plan v1.3, D-02); payment collection vs settlement and dispatch gating on payment failure (v1.3, D-12)
- [ ] **Confirmed excluded:** any owner / vehicle-owner cash incentive or consent payout (all amounts, all surfaces)

## Distribution & Navigation (new — owner decision 2026-11-06)

- [ ] Automatic distribution of the dealer packet dossier, shop repair packet, owner PDF, and carrier 7-page document to relevant parties on workflow completion (consent, TCPA/SMS, and privacy review of every recipient channel)
- [ ] Recipient authorization and verification before any document send
- [ ] Guided navigation / location sharing with receiving parties (dealer, shop) and tow driver (destination sharing via a Google Maps-class adapter; location-data privacy and retention review)

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
