# Dispatch build containment

Status: candidate implementation on `fix/unverified-triage-dispatch-containment-2026-11-24`; exact-head CI pending.
Current boundary: triage adjudication and dispatch package construction are both disabled until trusted evidence context is integrated.

## Scope

POST /api/v1/dispatch/build rejects validated requests with HTTP 503 and a non-cacheable, fixed error. Invalid requests may still receive framework validation errors. Caller-supplied synthetic or model provenance cannot bypass the block. Dispatch health advertises that package construction is disabled. The handler must not invoke the package builder or append to the anchor ledger.

This intentionally disables HTTP package construction until server-owned authorization and trusted provenance are integrated. It has no configuration switch or request override.

## Limits

The direct Python `build_dispatch` function now also raises `SERVER_VERIFIED_EVIDENCE_CONTEXT_REQUIRED`; a fabricated integrity dictionary and arbitrary photo-hash list cannot generate packages. This is still containment, not a complete provenance implementation: report builders, analysis modules, redaction, legacy public-verification module code, and the process-local ledger have separate audit findings. No tenant-bound verified-evidence context, durable recipient authorization, or external checkpoint is implied. No model loading, durable anchoring, tenant authorization, financial eligibility, consent enforcement or deployment readiness is established.

No commercial rules, migrations, runtime packaging, real-data collection, external dispatch, payments, merge or deployment are changed or authorized.

## Verification

Candidate regression coverage includes HTTP 503 when forged integrity/ACV inputs are submitted, direct builder rejection even with a fabricated passing integrity dictionary and arbitrary 64-character photo hashes, plus existing dispatch-route non-invocation checks. Exact-head GitHub Actions results are required before merge. These tests are not live HTTP against a deployed service, physical-device or deployment evidence.

Suggested focused commands:

    pytest tests/api/test_triage_integrity_contract.py tests/api/test_dispatch_build_containment.py -q
    pytest tests/test_dispatch.py -q

Inspect actual CI results on the exact candidate commit before review or merge.

## Follow-up before operational enablement

1. Propagate server-generated synthetic/model/unavailable provenance through analysis, adjudication and every report format.
2. Verify actor, tenant, session authority and current consent from trusted server state.
3. Retrieve observations and digests from trusted persistence, not request assertions.
4. Separate synthetic preview packaging from operational output and financial eligibility.
5. Test the integrated HTTP/database/artifact/journal/report path and crash recovery.
6. Reconcile commercial rules and milestone claims by explicit owner decision.
7. Require a separate reviewed change to replace this block; do not merely add a caller-controlled flag.
