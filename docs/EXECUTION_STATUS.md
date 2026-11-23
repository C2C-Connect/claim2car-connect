# Active focus — forensic substantiation (2026-11-23)

## Current verified checkpoint (2026-11-23 — PR #180 merged)

- PR #180 squash-merged to main: `35f7339564cf8f8d15d9eb4e28e14cb13b1c3fef`; PR #176 superseded and closed.
- Exact tested head `539cde24a5ed390b26a97e6cfd206f334a48ff6`: **13/13 workflows passed**.
- Full suite: **1,050 passed, 31 warnings, 219 subtests passed**.
- PostgreSQL authority acceptance on isolated synthetic DB: **386/386 counted tests**, DB-01–DB-14 **14/14 PASS**, 14 formal gate passes, diagnostics successful, overall DB acceptance ACCEPTED. This is not forensic M1 acceptance or field qualification.
- Migration 0028 persists SHA-256 genesis/event hashes, transactional historical backfill, append-time chain recomputation, direct-insert validation and immutable event mutation guards; Python/SQL parity and adversarial/migration tests are integrated.
- M1 still needs server-owned readback verification, chain-tip/context binding in sealed manifest roots, artifact/registered-original binding, independent verifier agreement, and restart/restore/concurrency/fork/independent-checkpoint validation.
- No deployment, real participant evidence, live payment or dispatch. OCI staging remains unverified/undeployed.


