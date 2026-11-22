# Capture Protocol Versioning and Session Identity

**Decision:** Founder-approved `claims2car-16-v1` is the default and enabled protocol for new capture sessions. `claims2car-12-v1` remains an explicitly selectable, versioned legacy alternative. Historical sessions and manifests are never silently relabelled.

**Approval and implementation:** The exact 16-slot contract was approved on 2026-11-11 and merged with PR #41 on 2026-11-12. The contract is defined in `contracts/shot-list-16-v1.json`; the registry reports 16-v1 as `implemented` with `capture_enabled: true`.

## Canonical 16-v1 contract

The following 16 slots are required in this exact order:

| Order | Slot ID | Evidence purpose |
|---:|---|---|
| 00 | `00_front_exterior` | Front-facing vehicle framing |
| 01 | `01_front_right_exterior` | Front-right 45° quarter view |
| 02 | `02_right_side_exterior` | Right-side profile |
| 03 | `03_rear_right_exterior` | Rear-right 45° quarter view |
| 04 | `04_rear_exterior` | Rear-facing vehicle framing |
| 05 | `05_rear_left_exterior` | Rear-left 45° quarter view |
| 06 | `06_left_side_exterior` | Left-side profile |
| 07 | `07_front_left_exterior` | Front-left 45° quarter view |
| 08 | `08_wheel_front_left` | Front-left wheel assembly |
| 09 | `09_wheel_front_right` | Front-right wheel assembly |
| 10 | `10_wheel_rear_right` | Rear-right wheel assembly |
| 11 | `11_wheel_rear_left` | Rear-left wheel assembly |
| 12 | `12_cabin_front_airbags` | Front cabin/dashboard and visible airbag indicators |
| 13 | `13_instrument_cluster_odometer` | Odometer and warning-light evidence |
| 14 | `14_physical_vin` | Readable physical VIN plate/sticker |
| 15 | `15_license_and_insurance_docs` | Driver's license and insurance-card documentation |

The machine-readable contract and exact descriptions are authoritative. Cross-layer implementations must preserve the same slot IDs and order.

## Interpretation and analysis boundary

- Slots **00–07** are the eight exterior perspectives and are the only 16-v1 slots eligible as inputs to crush-physics geometry.
- Slots **08–15** are wheel, cabin/airbag, odometer, VIN, and document evidence. They must not be treated as crush-physics geometry or used to infer impact-zone geometry.
- A slot's presence proves only that the corresponding evidence item was captured and recorded. It does not, by itself, prove damage, causation, vehicle identity, ownership, coverage, liability, or legal authenticity.
- Preserve original bytes, session/protocol binding, actor/tenant attribution, timestamps, ordered manifest identity, and retry/conflict semantics. A replacement is explicit supersession, not silent mutation.
- Roadside safety takes priority over completing the checklist. Pause, skip, or abort behavior must not delay emergency response, police, traffic control, stabilization, loading, or scene clearance.

## Legacy 12-v1 compatibility

The legacy contract remains selectable for new sessions when a currently deployed workflow requires it. Its historical slot IDs and interpretation remain unchanged:

`vin_ocr`, `doc_ocr`, `front`, `front_left`, `driver_side`, `rear_left`, `rear`, `rear_right`, `passenger_side`, `front_right`, `interior_front`, `undercarriage_engine`.

Do not translate, rename, or reinterpret historical 12-v1 evidence as 16-v1.

## Database identity and manifest binding

- Authority migration `0018_capture_protocol_session_binding.sql` adds `faos.sessions.capture_protocol_version`, backfills historical sessions as 12-v1, and defaults new sessions to 16-v1.
- The session protocol version is immutable after creation.
- New session-creation events record the protocol version; readback verifies that the event and immutable session column agree.
- Authority migration `0019_manifest_root_protocol_binding.sql` permits both version IDs and enforces that each registered manifest root matches the protocol version on its owning session.
- Root registration also verifies tenant context, the persisted seal event, manifest digest, schema version, and protocol version. A mismatch fails closed.
- The application, API registry, operator workbench, browser controller, manifest builder, and reviewer path must use the same version-specific contract.

## Registry state

| Protocol | New-session selection | Contract state | Capture |
|---|---|---|---|
| `claims2car-16-v1` | Default | Founder-approved and implemented | Enabled |
| `claims2car-12-v1` | Explicit legacy alternative | Existing contract retained | Enabled |

## Verification and remaining release boundaries

The contract has executable parity tests for its exact 16 ordered slots, 12-v1 compatibility, manifest digest binding, and the exclusion of slots 08–15 from crush-physics geometry. The current PR #47 additionally verifies database-level manifest-root/session protocol binding.

This does not establish persistent deployment or field acceptance. Real-participant use remains gated by owner identity proofing, legally reviewed disclosure for the full 16-slot collection (including license and insurance documentation), qualified-device testing, roadside field validation, persistent storage/backup/restore, operational ownership, and the applicable release approvals. The provider-neutral restricted health-only container is not an integrated product deployment.

## Non-negotiable compatibility rules

1. New sessions default to the founder-approved 16-v1 contract.
2. Existing sessions retain their immutable protocol version.
3. Every manifest root must match the protocol version of its owning session.
4. Historical 12-v1 manifests and digests remain unchanged.
5. No 12-v1 slot may be silently substituted for a missing 16-v1 slot.
6. Only slots 00–07 may feed crush-physics geometry; slots 08–15 are evidence-only for that analysis path.
7. Conflicting retries, supersession, consent withdrawal, and recovery remain explicit and auditable.


## FAOS 16-v2 additive protocol

The owner-supplied FAOS target is now represented by a separate `claims2car-16-v2` contract. It is implemented and selectable for controlled capture, but **does not replace the default 16-v1** until the corresponding disclosure, rollout, and field qualification are reviewed. The immutable 16-v1 and 12-v1 slot IDs remain supported.

The v2 contract maps the 16 positions as follows:

- 00–07: eight exterior perspectives, unchanged.
- 08–11: four accessible structural corner views (front-left, front-right, rear-right, rear-left). Operators must remain in safe standing positions; no crawling under or approaching an unsupported vehicle. If unsafe/unavailable, use the explicit exception workflow.
- 12–13: front and rear cabin/restraint perspectives.
- 14–15: instrument-cluster telemetry and physical VIN/vehicle-identity frame. VIN identity is not damage geometry.
- License/insurance documentation is supplemental and is not a mandatory v2 capture slot; obtain it only when separately necessary and consented.

The registry exposes v2 as a selectable version. New sessions remain defaulted to v1 in this increment. Authority migration 0027 permits v2 while preserving the existing default and historical session protocol identity. V2 non-exterior slots are excluded from damage-zone localization/physics input.
