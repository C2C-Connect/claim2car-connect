# Carrier Integration — CIECA-Aligned Message Model

**Status:** Slice 7 (2026-11-07) · **Owner decision:** D-11 (7-page carrier document: requirement, spec open)

## What this is

`contracts/carrier-message-model.json` (model version `carrier-message-v1`) defines the outbound message envelope and types for carrier-facing integration. The message types mirror the CIECA message categories — Claim/Status, FNOL, Assignment, Estimate, Attachment, Disposition — which is how the collision industry already exchanges this information (CIECA BMS XML and the emerging JSON API share one data dictionary).

## What is and is not claimed

- **Claimed:** a versioned, validated message contract with CIECA-aligned categories; messages are built only from sealed, integrity-verified, attributed decisions; the builder structurally refuses to emit compensation or incentive language (eradication alignment); delivery is outbox-only (Slice 6), nothing is sent live.
- **NOT claimed:** CIECA compliance. Field-level mapping to the CIECA schema requires CIECA membership access to the standard. When the owner obtains access, the mapping is a translation of `carrier-message-v1` payloads into CIECA messages — the categories, envelope, and validation are designed so that no architectural change is needed.

## Message types

| Type | Built from | Required payload |
|---|---|---|
| `CLAIM_STATUS` | frozen machine state | `status`, `session_id` (+ optional `vin`) |
| `ASSIGNMENT` | recorded acceptance + dispatch plan | `party_type`, `party_id`, `accepted_at`, `location_label`, `dispatch_total_minutes` |
| `ATTACHMENT` | sealed manifest | `manifest_digest`, `shot_list_version`, `artifact_count` |
| `DISPOSITION` | attributed reviewer decision | `disposition`, `actor`, `occurred_at`, `reason`, `artifact_ids` |
| `ESTIMATE` | reserved for M5 analysis output | (not built in this version) |

## Ordering guarantees

- `ATTACHMENT` requires a sealed (or reviewed) session — evidence references cannot precede the seal.
- `DISPOSITION` and `ASSIGNMENT` require the terminal `reviewed` state — the carrier never hears a verdict before the attributed reviewer decision is terminal.
- `ASSIGNMENT` requires the acceptance-gated `DispatchPlan` (product contract §7: acceptance precedes tow dispatch).

## Relationship to the 7-page carrier document (D-11)

The plan requires a seven-page carrier document whose specification is open. This message model is the candidate specification's data layer: a rendering step (PDF/HTML from `DISPOSITION` + `ATTACHMENT` payloads) can produce the document without re-deriving any facts. Rendering, like all live distribution, remains counsel-gated (Gates A–D).

## Sources

- CIECA standards overview: https://www.cieca.com/standardsoverview
- CTO Technology Recalibration Brief (2026-11-06), Tier 2 item 6.
