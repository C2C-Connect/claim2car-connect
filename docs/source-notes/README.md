# Source notes

These notes preserve useful material from earlier Claim2Car lines. They are not acceptance contracts, not a shot list, and not economics.

Authoritative documents stay where they are:

- `docs/acceptance/product-contract.md`
- `docs/acceptance/database-contract.md`
- `docs/acceptance/baseline-and-milestone.md`
- `contracts/shot-list.json` (`claims2car-12-v1`)

| Note | What it is |
|---|---|
| `pr-2-gap-list.md` | Read of `acceptance/capture-core` at `2edc6e50` against PRODUCT-01–04. No merge. |
| `phase-c-d-capture.md` | Capture and evidence requirements carried from `claim2car-faos-v1` `docs/phase-c-d-requirements.md` (`53193575`). |
| `multi-dealer-invariants.md` | Routing rules carried from `docs/phase-c-multi-dealer-invariants.md` (`b1ea4e3f`). Post-M1. |
| `research-backlog.md` | Unvalidated research carried from `docs/research-backlog.md` (`38bae9d7`). |
| `base44-capture-residue.md` | Four non-binding notes from the 2026-10-05 Base44 export. |

`gavel_lifecycle.py` at the repository root is the un-wired session-transition prototype from `claim2car-faos-v1` (`2ed22b3e`), with `test_lifecycle.py`. `database/capture_sessions.py` on `acceptance/capture-core` does not call it. Do not connect the two without an explicit slice.
