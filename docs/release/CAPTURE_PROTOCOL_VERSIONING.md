# Capture Protocol Versioning and Session Identity

**Decision:** `claims2car-16-v1` is the default for newly created sessions. `claims2car-12-v1` remains an explicitly selectable, versioned alternative. Historical sessions are never silently relabelled.

## Implemented in the current PR #31 increment

- Authority migration `0018_capture_protocol_session_binding.sql` adds `faos.sessions.capture_protocol_version`.
- The migration backfills all existing sessions as `claims2car-12-v1`, then changes the database default for new rows to `claims2car-16-v1`.
- A database trigger rejects attempts to change the protocol version after session creation.
- The claim-case constructor accepts an explicit protocol ID; the default is 16-v1. Idempotent retries that attempt to change the protocol ID are rejected.
- Controlled capture-session creation accepts a protocol ID and defaults to 16-v1. A retry with a different version is rejected.
- Session and claim-case readback return the immutable protocol version.
- Authenticated `GET /v1/capture-protocols` exposes the default and each protocol's status, slot contract, and capture-enabled state.
- The operator workbench fetches that registry and lets operators choose the protocol for a new session. Existing sessions retain their own stored version regardless of the selector's current value.
- Manifest construction requires an implemented protocol. The existing 12-v1 manifest remains supported without changing its slots or historical digest identity.
- Evidence registration, quality recording, and sealing fail closed for a 16-v1 session while its exact slot definition is pending.

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
