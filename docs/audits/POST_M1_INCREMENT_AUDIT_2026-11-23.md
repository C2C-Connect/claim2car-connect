# Post-M1 SQL Increment Audit — 2026-11-23

**Scope:** PR #180 merged to `C2C-Connect/claim2car-connect` main as `35f7339564cf8f8d15d9eb4e28e14cb13b1c3fef`. Exact tested PR head: `539cde24a5ed390b26a97e6cfd206f334a48ff6`.

## Verified

- Exact-head workflows: 13/13 green.
- Full suite: 1,050 passed, 31 warnings, 219 subtests passed.
- Isolated synthetic PostgreSQL authority acceptance: 386/386 counted tests; DB-01–DB-14 14/14 PASS; diagnostics successful; overall database acceptance ACCEPTED.
- Migration 0028 `persistent_event_hash_chain.sql` creates SHA-256 genesis/event commitment functions and `pgcrypto`, stores `previous_hash`, `entry_hash`, `hash_version`, backfills in sequence order without rewriting event payload bytes, and fails transactionally on gaps.
- Existing append function recomputes the full stored chain before duplicate/new event acceptance.
- Trigger validates direct-insert chain continuity and computed hashes; event UPDATE/DELETE are blocked.
- Unit and PostgreSQL tests cover known-answer parity, tenant/session binding, tamper detection, duplicate/conflict behavior, direct privileged insertion, mutation rejection, backfill hash parity, backfill-gap rollback, forced RLS and migration inventory.

## Remaining forensic M1 gaps

1. Persisted-chain verifier is not yet integrated into server-owned journal/readback.
2. Manifest root/seal does not bind verified chain tip, sequence, hash version, and capture context.
3. Registered-original/artifact relationships are not yet bound to verified chain and manifest.
4. Independent verifier agreement and caller-supplied-root replacement remain incomplete.
5. Restart/restore, concurrency, missing/deleted/reordered/fork, privileged bypass and full adversarial verification remain to be expanded for M1.
6. An in-database chain is not an external trust anchor. Signer, trusted timestamp, transparency checkpoint or other external anchor is a separate mechanism.
7. No field qualification, forensic accuracy, causation, hidden-damage assessment, deployment, participant evidence, payment or dispatch acceptance.

## Next executable increment

Implement server-owned readback recomputation from PostgreSQL, bind sealed manifest roots to the verified chain tip and capture context, bind registered original artifacts, then add independent/adversarial/recovery/restart/restore/concurrency/fork tests. Execute M1 acceptance only after evidence is complete. Continue from main; no planning-only work.
