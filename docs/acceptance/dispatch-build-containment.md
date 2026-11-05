# Dispatch build containment

Status: proposed implementation on safety/synthetic-provenance-integration.
Baseline: f16be7405ebf88ea7fab95394e6b482f2e506b6d.

## Scope

POST /api/v1/dispatch/build rejects validated requests with HTTP 503 and a non-cacheable, fixed error. Invalid requests may still receive framework validation errors. Caller-supplied synthetic or model provenance cannot bypass the block. Dispatch health advertises that package construction is disabled. The handler must not invoke the package builder or append to the anchor ledger.

This intentionally disables HTTP package construction until server-owned authorization and trusted provenance are integrated. It has no configuration switch or request override.

## Limits

This is containment of one HTTP handler, not a complete provenance implementation. Internal build_dispatch calls, report builders, analysis and triage routes, redaction, public verification and the process-local ledger remain unchanged. Internal synthetic previews are not made operationally safe by this change. No model loading, durable anchoring, tenant authorization, financial eligibility, consent enforcement or deployment readiness is established.

No commercial rules, migrations, runtime packaging, real-data collection, external dispatch, payments, merge or deployment are changed or authorized.

## Verification

Two direct-handler unittest methods cover three provenance cases, builder/append non-invocation, fixed non-cacheable errors and disabled health reporting. These tests have not been executed in the authoring session. They are not live HTTP, PostgreSQL, browser, physical-device or deployment evidence.

Suggested focused command:

    python -m unittest discover -s tests/api -p test_dispatch_build_containment.py -v

Inspect actual CI results on the exact candidate commit before review or merge.

## Follow-up before operational enablement

1. Propagate server-generated synthetic/model/unavailable provenance through analysis, adjudication and every report format.
2. Verify actor, tenant, session authority and current consent from trusted server state.
3. Retrieve observations and digests from trusted persistence, not request assertions.
4. Separate synthetic preview packaging from operational output and financial eligibility.
5. Test the integrated HTTP/database/artifact/journal/report path and crash recovery.
6. Reconcile commercial rules and milestone claims by explicit owner decision.
7. Require a separate reviewed change to replace this block; do not merely add a caller-controlled flag.
