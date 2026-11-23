# Post-M1 Readback Audit — 2026-11-23

**Scope:** PR #182 merged to `C2C-Connect/claim2car-connect` main as `f0c6fbfc7d0278e77964a45004e0e42ede7a8146`. Exact tested head: `668785ea465b807932e63fdb6a555ed419099b6b`.

## Verified

- Exact-head workflows: 13/13 green.
- Full repository: 1,054 passed, 31 warnings, 219 subtests.
- Isolated synthetic PostgreSQL authority acceptance: 390/390 counted tests; DB-01–DB-14 14/14 PASS; diagnostics successful; overall DB acceptance ACCEPTED.
- `database/readback.py` now derives tenant/session/event rows from PostgreSQL and recomputes the hash chain using the Python contract.
- `load_journal` fails closed when authority-schema history is invalid; locked consumers verify within the session lock before replay/eligibility.
- Legacy schema compatibility is explicit `LEGACY_UNHASHED`; a partial hash-column schema fails closed.
- Integration tests cover persisted-row verification, tampering, locked consumers, tenant visibility, legacy compatibility and partial schema.

## Remaining M1 gaps

1. Sealed manifest root does not yet bind the verified event-chain tip, seal sequence, hash version and deterministic capture-context commitment.
2. Registration must recompute/validate persisted chain and seal record before accepting root, and idempotent retries must compare all bound fields.
3. Readback/completion/receipt consumers must independently verify the stored root binding.
4. Registered originals/artifacts must be bound to tenant/session/manifest/chain and verify IDs, bytes/hash and provenance.
5. Independent verifier must derive DB records and registered originals, not accept caller-provided roots/hashes.
6. Restart/restore, concurrent append, missing/deleted/reordered/forked rows, privileged bypass and full adversarial tests remain.
7. A DB-resident chain is not an independent trust anchor. External signer/checkpoint/trusted timestamp remains separate.
8. No field qualification, forensic accuracy/cause claims, staging deployment, participant evidence, live payment or dispatch.

## Next executable increment

Implement migration 0029 for manifest-root chain-tip/context binding and verified registration/consumers; bind registered original/artifacts; add independent, recovery, restart/restore, concurrency, tamper, missing/reorder/fork tests. Continue from main; no planning-only work.
