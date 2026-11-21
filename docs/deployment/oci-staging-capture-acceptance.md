# Synthetic OCI staging capture acceptance

This acceptance harness is for an initialized **private synthetic staging** host only. It creates a synthetic collision/claim/session, grants owner capture-review consent, registers synthetic vehicle context, uploads all 16 protocol slots, records advisory quality, seals a manifest, and has the reviewer retrieve and SHA-256-verify every original byte.

It then records a NOTE_ONLY review, restarts the single application container, repeats reviewer manifest/original retrieval checks, intentionally modifies one **synthetic test artifact** to prove integrity failure is detected, and withdraws capture-review consent to verify the synthetic original is removed.

**Do not run against production or real claimant data.** The restart causes a short staging interruption. This is a backend/persistence acceptance test—not camera authenticity, device qualification, physical-scene validation, claim adjudication, or production readiness.

## Prerequisites

- Deployed integrated image with \`/health/ready\` and \`/health/build\` healthy.
- Persistent PostgreSQL and evidence volumes mounted and preflighted.
- Synthetic staging tenant initialized with owner/operator/reviewer credentials.
- Execute on the host as root; the harness targets loopback only and does not transmit bearer tokens to remote URLs.
- Run in a root shell with tracing disabled (\`set +x\`). Never put credentials in shared logs.

The one-time bootstrap creates \`operator-tokens.txt\`. Use the role-specific tokens to set these environment variables in the root shell, then securely delete the token file according to the bootstrap runbook:

\`\`\`bash
export C2C_ACCEPTANCE_OPERATOR_TOKEN='<synthetic operator token>'
export C2C_ACCEPTANCE_OWNER_TOKEN='<synthetic owner token>'
export C2C_ACCEPTANCE_REVIEWER_TOKEN='<synthetic reviewer token>'
\`\`\`

## Run

From the matching source checkout (must match the published image SHA):

\`\`\`bash
python3 scripts/oci_staging_capture_acceptance.py --confirm-synthetic
\`\`\`

The default target is \`http://127.0.0.1:8000\`. If accessing through an OCI Bastion/SSH port-forward, keep the tunnel local and use a loopback base URL. A successful report includes \`status=PASS\`, the capture session, revision, sealed manifest digest, 16-slot count, restart verification, reviewer retrieval, tamper rejection, and consent-withdrawal deletion.

The optional \`--skip-container-restart\` mode is diagnostic only and does **not** satisfy the restart-persistence acceptance gate.

If the script fails mid-run, the synthetic case may remain in staging. Inspect the reported session and revoke capture-review consent using the owner credential to remove registered original bytes before rerunning. Do not reuse identifiers; the harness generates new UUIDs on each attempt.
