# Phase C/D capture notes

Source: `C2C-Connect/claim2car-faos-v1` `docs/phase-c-d-requirements.md` at `531935753a33fb10ebf2af32c71d34cac3e7ef80` (2026-10-11). Adapted onto this repository. Nothing here is implemented by being written down. PostgreSQL remains the store. MongoDB stays out.

Live personal data, consequential decisions, and money movement still need their own approval. M1 is the narrower cut in the product contract: authorized test operator, consent, VIN, photos, durable save/resume, human review.

## Requirements to keep

| ID | Requirement |
|---|---|
| C01 | Versioned records keep source, units, uncertainty, method, identity, and session lineage. A missing input stays unavailable or goes to human review. Tests must reject an invented substitute and a cross-session reference. |
| C02 | Events are attributed and replayable. Review appends. It does not rewrite source bytes. An integrity failure cannot be waived by review. |
| C03 | Completion needs scoped consent, an explicit vehicle outcome, the required artifacts, quality outcomes, a verified manifest, and a resolved review policy. Missing analytical inputs produce no invented result. |
| C04 | Retries with the same identity are idempotent. A conflicting payload fails. Restart recovery is tested against PostgreSQL. The capture branch already does this for VIN drafts only. |
| C05 | Physics and model output stay separate from the human decision. Any blend weight is an experiment with a version, not a pilot rule. An override is true, false, or unavailable. It is never inferred from a missing input. |
| C06 | Artifact digests are SHA-256. Manifest encoding, ordering, version, and the trusted root are explicit. Tamper, omission, and duplicate conflicts fail a boolean check. A weighted scene score is not proof. |
| C07 | A synthetic downstream loop may end at an obligation record. It must not call a payment, invoice, or transfer API. |
| D01 | `contracts/shot-list.json` version `claims2car-12-v1` is the only shot contract. Clients consume it. They do not keep a second copy. |
| D02 | Field and test paths share domain validation. Adapters are isolated. A client mode flag grants no production authority. |
| D03 | VIN validation and vPIC decoding keep raw fields and unavailable outcomes. Body class is versioned. A silhouette or PNG is not calibrated 3D geometry. |
| D04 | The intended capture device is an MDM-managed 11-inch M4 iPad Pro with LiDAR. Depth, intrinsics, pose, units, confidence, and timestamps are recorded, or the sensor is explicitly unavailable. This is not yet selected as the M1 test device. The product contract still says the M1 device is an open decision. |
| D05 | A background sharpness check may start from Laplacian variance 160. That threshold is unvalidated. Framing, latency, and frame rate need device measurements before they are gates. |
| D06 | An append-only outbox and resumable sync must preserve bytes, acknowledgements, and conflicts. Interrupted upload, storage exhaustion, and restart are test cases. Do not claim IndexedDB is tamper-proof. |

## Deferred on purpose

DARCI latency and cost targets, a structural-override hypothesis, and carrier-export mappings stay in `research-backlog.md`. They are not M1.

## Order

Domain records, replay, guards, and idempotent PostgreSQL writes come before the capture shell. Quality, physics, and commercial authority stay gated even after their interfaces exist.
