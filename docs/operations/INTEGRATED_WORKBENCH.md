# Integrated operator and reviewer workbench

This guide describes the first connected browser workbench shipped with the Slice 2 candidate. It is an operator/reviewer interface over the existing integrated FastAPI APIs, not a self-service identity provider or a production deployment.

## Runtime requirements

The integrated runtime must be started with:

- `C2C_RUNTIME_MODE=integrated`
- `C2C_CAPTURE_CONFIG_FILE` pointing to a private runtime JSON file mounted read-only
- `C2C_ARTIFACT_STORAGE_ROOT` pointing to persistent, writable evidence storage
- `C2C_VIN_HMAC_PEPPER` containing at least 32 ASCII characters
- `C2C_INTERNAL_SERVICE_TOKEN` containing 43–128 URL-safe characters

The evidence directory must be an absolute path and writable by the container's non-root UID (10001). Do not place the runtime JSON, raw access tokens, database passwords, VIN pepper, or internal service token in the repository or image.

The integrated image includes `frontend/app` and the VIN validation module under `frontend/src`. The workbench is served at `/` only when integrated runtime mode is selected. The root page and source modules contain no credentials; protected API actions still require bearer authentication.

## Provisioning actor credentials

There is no HTTP sign-in, password reset, invitation, or account-creation endpoint in this increment. An authorized administrator provisions high-entropy tokens out of band and stores only each token's SHA-256 digest in the private runtime file.

Generate one token per actor using a trusted administration environment:

```python
import hashlib
import secrets
import time

for actor_role in ("operator", "owner", "reviewer"):
    token = secrets.token_urlsafe(32)  # 43 URL-safe characters
    print({
        "actor_role": actor_role,
        "token": token,  # distribute securely; do not put this in the runtime file
        "token_sha256": hashlib.sha256(token.encode("ascii")).hexdigest(),
        "expires_at": int(time.time()) + 8 * 60 * 60,
    })
```

The raw token is shown once by the provisioning process. Deliver it to its intended person through an approved secure channel. Never paste it into an issue, pull request, source file, chat transcript, or ordinary log.

Each credential entry in the private runtime JSON has this shape:

```json
{
  "actor_id": "unique-operator-actor",
  "tenant_id": "00000000-0000-0000-0000-000000000001",
  "database_role": "tenant_login_operator",
  "token_sha256": "<64-character-lowercase-sha256-digest>",
  "expires_at": 1800000000,
  "enabled": true,
  "actor_role": "operator"
}
```

Use a unique `actor_id` for each person/credential. `actor_role` must be one of `owner`, `operator`, `reviewer`, or `supervisor`. `database_role` must match a key in `dsn_by_role`, and the configured DSN's PostgreSQL user must match that role. All DSNs in the runtime configuration must point to the same explicit database target. The runtime rejects ambiguous identities and privileged database roles.

The top-level runtime configuration also contains `health_database_url`, `dsn_by_role`, and `credentials`. Follow the existing private configuration schema in `app/capture_api.py`; do not commit a sample containing working credentials or database endpoints.

## Operator workflow

1. Open the integrated workbench over HTTPS.
2. Connect with the provisioned operator token.
3. Create a case. The server derives the operator and tenant from the credential.
4. Have the vehicle owner review the approved disclosure. Record consent using the owner's separate owner-role token. The owner token is cleared from the form after a successful request.
5. Enter the VIN. The browser validates its format/check digit; the server stores a keyed VIN reference, not the raw VIN.
6. Capture the 12 canonical evidence slots. The browser uploads the original image bytes without resizing or recompression and supplies a SHA-256 digest for server verification.
7. Complete the manual advisory image checks and seal the evidence manifest.

The browser keeps bearer tokens in memory only. Refreshing or closing the page clears the session token. The current UI does not implement offline drafts, resumable upload queues, or case resume after a page reload.

**Roadside safety takes precedence.** If a required angle is unsafe, stop and leave the case unsealed. The current browser UI does not yet submit server-recorded skip/abort events, and the server requires the complete canonical evidence set before sealing. Do not enter traffic or delay emergency response, police direction, stabilization, loading, or scene clearance to complete a capture.

## Reviewer workflow

1. Connect with a provisioned reviewer or supervisor token.
2. Refresh the tenant-scoped sealed evidence queue.
3. Retrieve and inspect the original evidence items.
4. Record one of the currently supported dispositions: `NOTE_ONLY` or `HUMAN_QC_REQUIRED`, with a non-empty rationale.

The server enforces tenant scope and independent-reviewer authorization. This increment does not provide assignment/locking, supervisor correction, retake routing, or a full adjudication state machine. Human review remains authoritative.

## Release boundaries

The workbench does not enable automated claim acceptance, financial settlement, dealer/shop dispatch, carrier delivery, external document distribution, or live participant-data publication. A passing CI workflow proves the tested code path only; it does not establish a persistent staging deployment, device qualification, field validation, legal approval, or production readiness.

Before a pilot, complete the applicable Slice 2 real-device acceptance and Slice 3 persistent database/evidence-storage, restore, TLS, monitoring, and deployment gates.
