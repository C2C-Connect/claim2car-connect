# PR #2 gap list

**Reviewed:** `acceptance/capture-core` at `2edc6e508ceefc7215b2870e836a1a34f3b2e3d8`
**Against:** product gates PRODUCT-01 through PRODUCT-04 in `docs/acceptance/product-contract.md`
**Date:** 2026-11-01
**This document does not merge, rebase, or award a gate.**

`main` moved after the PR was opened, and only by documentation (`0f89d675`, PR #3). The capture branch was left at the pinned SHA. Required status checks on `main` were not changed.

## What the branch actually contains

Controlled-test session create/get and a VIN draft on the existing event journal.

- Auth is a server-owned opaque bearer token. The database role must match the credential, must be a non-superuser `faos_app` member, and must see only its own tenant.
- `POST /v1/capture-sessions` and `GET /v1/capture-sessions/{id}` store and return session metadata. The first event must remain `SESSION_CREATED` / `capture-created` / `{"synthetic":true}` / schema `0.1`. Any other first event is `UNMANAGED_CAPTURE_SESSION`.
- `PUT` and `GET` `/v1/capture-sessions/{id}/draft` append and read a VIN. The VIN must already be 17 characters in `A-HJ-NPR-Z0-9` and must pass the ISO 3779 check digit. Idempotent replay of the same `request_id` returns the original draft. A conflicting body or a stale `expected_revision` returns 409. A different actor gets 403.
- `faos.lock_session_for_completion` is a `SELECT … FOR UPDATE`. It does not mark the session complete.
- The frontend modules validate a VIN, parse one vPIC payload, and refuse a suggested VIN, a VIN mismatch, an unresolved decode, and an incomplete make/model/year/body class. They do not invent a vehicle. Curb weight is `reported`, `unavailable`, or `invalid`. `physicsReady` stays false.
- The intake workflow file says it requires 9 PostgreSQL draft tests and 7 loopback HTTP/PostgreSQL tests. This review did not re-run them. Offline VIN tests are not browser, camera, or deployment proof. The live vPIC workflow runs only for that branch when its own file changes, or on manual dispatch. It is one test VIN.

## Gate gaps

### PRODUCT-01 — Identity, authorization, consent

Partial. Tenant and actor boundaries are enforced for these routes. There is no operator sign-in, and there is no consent record. Nothing checks consent version, an explicit act, a timestamp, or session linkage before a draft is saved.

### PRODUCT-02 — Capture session and lifecycle

Partial. Create, idempotent replay, and readback exist. Resume of anything beyond the VIN draft does not. There is no complete or abort transition, and no frontend session client.

The in-memory Gavel prototype (`CREATED → ACTIVE → CAPTURE_COMPLETE → PROCESSING → COMPLETED`, plus `ABORTED`) is not implemented on this branch. Do not treat a later copy of that prototype as this session service. This service will not accept a non-synthetic first event, so a real capture cannot grow on the same row without a deliberate contract change.

### PRODUCT-03 — Vehicle identity / VIN

Partial, and the strongest slice on the branch. Check digit and charset are enforced on the server and in the client. The persisted draft stores the VIN string only. It does not store make, model, year, body class, trim, engine, drive, transmission, fuel, manufacturer, or plant. The vPIC parser is not called by the draft API. There is no OCR. There is no silent character substitution.

### PRODUCT-04 — Evidence collection

Not started. No image bytes, no object storage, no shot-list check, no artifact hash, no retrieval.

## Hardening still open

The ledger item for this PR asked for request-size limits, rate controls, and broader failure paths.

- Config files are capped at 64 KiB. Draft bodies are small and reject unknown fields. There is no general HTTP body cap beyond the framework default.
- There is no application rate limit. Database statement timeout is 5 seconds and lock timeout is 3 seconds.
- Mapped failures are 401, 403, 404, 409, 422, 500, and 503. 500 is a catch-all and does not echo the VIN or the token.

## Decision

Not promoted. A merge remains a separate decision after a fresh run of the intake and VIN checks against `2edc6e50`. Merging `main` into the branch later, if wanted, should be a merge commit so this SHA stays in the history. Do not rebase it.
