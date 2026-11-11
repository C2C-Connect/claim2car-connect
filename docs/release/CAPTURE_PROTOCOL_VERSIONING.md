# Capture Protocol Versioning and Session Identity

**Decision:** `claims2car-16-v1` is the default for newly created sessions. `claims2car-12-v1` remains an explicitly selectable, versioned alternative. Historical sessions are never silently relabelled.

## Implemented in the current PR #31 increment

- Authority migration `0018_capture_protocol_session_binding.sql` adds `faos.sessions.capture_protocol_version`.
- The migration backfills all existing sessions as `claims2car-12-v1`, then changes the database default for new rows to `claims2car-16-v1`.
- A database trigger rejects attempts to change the protocol version after session creation.
- The claim-case constructor accepts an explicit protocol ID; the default is 16-v1. Idempotent retries that attempt to change the protocol ID are rejected.
- Controlled capture-session creation accepts a protocol ID and defaults to 16-v1. A retry with a different version is rejected.
- Session and claim-case readback return the immutable protocol version.
- New `SESSION_CREATED` journal payloads also record the protocol version; readback verifies the journal value matches the immutable session column. Historical pre-0018 creation payloads remain readable only as 12-v1 after the migration backfill.
- Authenticated `GET /v1/capture-protocols` exposes the default and each protocol's status, slot contract, and capture-enabled state.
- The operator workbench fetches that registry and lets operators choose the protocol for a new session. Existing sessions retain their own stored version regardless of the selector's current value.
- Manifest construction requires an implemented protocol. The existing 12-v1 manifest remains supported without changing its slots or historical digest identity.
- Evidence registration, quality recording, and sealing fail closed for a 16-v1 session while its exact slot definition is pending.

## Source-document reconciliation findings

The architecture source files do not yet define one internally consistent 16-slot contract:

- The section titled **12-to-16 Angle Perspective Matrix** says 12 standard views plus up to four specialized details, but its own standard-view enumeration is 8 exterior + 2 undercarriage + 2 interior + 2 legal/document = **14 standard views**. Four additional details would make 18, not 16.
- The section titled **Breakdown of the Mandatory 16-Point Shot Protocol** enumerates 8 exterior + 2 interior + 1 license plate + 1 insurance/document + 3 damage close-ups = **15 items**, not 16.
- A separate **16-Point Perspective Matrix** repeats 8 exterior + 2 undercarriage + 2 interior + 2 legal/document = **14 items**.
- The three close-ups are described as primary impact, structural frame-rail buckling, glass stress fractures, and ADAS sensor clusters at 0°, 45°, and 90°; the text does not establish whether these are three required slots, four semantic targets, or a conditional multi-angle set.

These are source-level arithmetic and semantics conflicts, not merely inconsistent code identifiers. The implementation therefore keeps 16-v1 as the approved new-session default while refusing to fabricate a missing slot or reinterpret the historical 12-v1 list.
## Registry state

| Protocol | New-session default | Contract state | Evidence capture |
|---|---:|---|---|
| `claims2car-16-v1` | Yes | Definition pending | Disabled until exact 16 slots and ordering are approved |
| `claims2car-12-v1` | No | Existing contract retained | Enabled as explicit legacy alternative |

## Non-negotiable compatibility rules

1. Existing sessions are backfilled as 12-v1 and retain that identity.
2. The protocol version is immutable on the session row.
3. Manifest `shot_list_version` must match the session's protocol version.
4. A retry using a different protocol is an idempotency conflict, not an update.
5. The 16-v1 default must never silently fall through to the 12-v1 slot list.
6. No 16-v1 manifest may be constructed until the authoritative slot IDs, order, and capture semantics are approved.
7. The Slice 2 browser controller's separate 12-slot set must be reconciled explicitly; do not assume its identifiers are aliases for the API's 12-v1 slots.

## Remaining implementation work

- Reconcile the source architecture's inconsistent 14/15-item enumerations with the founder-approved 16-item contract.
- Record each of the 16 required slot IDs, order, semantic definition, required/conditional status, image framing guidance, safety constraints, and allowed skip/retake behavior.
- Obtain founder approval for the exact contract before changing the registry to `implemented`.
- Add the approved 16-v1 contract to the API, manifest builder, operator UI, browser controller, offline queue, and reviewer presentation.
- Add cross-layer contract-parity tests proving every layer uses the same exact ordered slots.
- Keep historical 12-v1 verification fixtures and manifests unchanged.

**Status interpretation:** the 16-v1 session identity and default are implemented; the 16-v1 capture contract is not. A newly created 16-v1 session is correctly versioned but cannot accept 12-v1 evidence. Select 12-v1 when a currently executable capture flow is required.
