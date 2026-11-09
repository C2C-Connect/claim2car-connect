# Railway restricted staging deployment

Target project: `463d410b-09a3-4117-a3b5-05e6646e7807`.
This deployment is a synthetic-only containment rehearsal, not a working claims
product, an integrated database deployment, or production acceptance.

## Safety and packaging

The existing `Dockerfile` and its authenticated, database-backed intake runtime
are unchanged. `Dockerfile.railway` packages `backend/` and `config/` into a
separate non-root container and starts `app.railway_staging` on Railway's `PORT`.
The Railway image intentionally mounts only:

- `GET /health/live` and `GET /health/ready`, with the packaged full commit SHA.
- `GET /api/v1/dispatch/health`, reporting disabled package construction.
- `POST /api/v1/dispatch/build`, always returning the existing fixed HTTP 503
  containment error without parsing request data or invoking the builder.

Capture, analysis, triage, verification, reports, payments, redaction, and API
documentation are not mounted. No database or persistent evidence storage is
used by this surface. Readiness covers this restricted process only, and its
response explicitly reports `business_ready: false`.

A prior note in this document stated that the broader backend could not be
imported because `P_BRITTLE_BETA` and `DEFAULT_TAX_RATE` were missing. That
statement is stale at the current baseline: both constants are present in
`config/forensic_constants.py`. Their presence does not establish that every
backend module imports successfully or that the business API is deployable.
The backend entrypoint and its complete import/runtime behavior still require
an explicit integration smoke test before any broader surface is enabled.

## Repository settings

In **Settings → Secrets and variables → Actions**, configure these repository
secrets. GitHub supports adding them with `gh secret set`, which prompts locally
for the value. ([GitHub secrets guide](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets))

| Setting | Type | Purpose |
|---|---|---|
| `RAILWAY_TOKEN` | Secret | Project token for the selected staging environment. |
| `RAILWAY_ENVIRONMENT_ID` | Secret | Exact intended staging environment ID. |
| `RAILWAY_SERVICE_ID` | Secret | Dedicated restricted-staging application service ID. |
| `RAILWAY_DEPLOY_ENABLED` | Variable | Set to literal `true` only after the target and secrets are checked. |
| `RAILWAY_STAGING_URL` | Variable | Required HTTPS origin for the restricted staging service and post-deploy HTTP checks. |

Use Railway project **Settings → Tokens** to create an environment-scoped project
token, and store it as `RAILWAY_TOKEN`, not `RAILWAY_API_TOKEN`. ([Railway GitHub Actions guide](https://railway.com/guides/github-actions))
Never paste the token into chat, source files, commands recorded in shell
history, or workflow logs.

The project ID is embedded in the workflow and is not a credential. Use the
Railway command palette, **Cmd/Ctrl + K**, to copy the service and environment
IDs from the intended context. ([Railway API cookbook](https://docs.railway.com/integrations/api/api-cookbook))

```bash
REPO="C2C-Connect/claim2car-connect"
gh secret set RAILWAY_TOKEN --repo "$REPO"
gh secret set RAILWAY_ENVIRONMENT_ID --repo "$REPO"
gh secret set RAILWAY_SERVICE_ID --repo "$REPO"
gh variable set RAILWAY_STAGING_URL --repo "$REPO" --body "https://YOUR-STAGING-HOST"
# Enable only after verification of the target and all three secrets.
gh variable set RAILWAY_DEPLOY_ENABLED --repo "$REPO" --body true
gh workflow run railway-deploy.yml --repo "$REPO" --ref main
```

## Verification and deployment

The workflow runs the API and dispatch regression tests, builds the dedicated
image, verifies its non-root identity, and tests its actual HTTP behavior on an
overridden port with a read-only filesystem. PR runs use no Railway secrets.
Deployment is allowed only on `main`, after that verification succeeds and the
repository deployment flag is enabled. Until enabled, a green verification run
does not mean anything has been deployed.

Inside the serialized deployment job, `scripts/railway_deploy.sh` reads the
current `main` ref using the read-only GitHub Actions token immediately before
stamping and uploading. An outdated verified commit is skipped without touching
Railway, and its public smoke step is also skipped. GitHub lookup failures or
invalid ref responses fail closed instead of uploading an unchecked revision.
This prevents an older verification run that finishes late from overwriting a
newer deployed commit; it does not cancel an upload already in progress if
`main` advances after the check.

The smoke script polls both `/health/live` and `/health/ready` using one shared
readiness deadline. Transient HTTP failures, network errors, malformed JSON, and
old revisions are retried within that budget, with each health request bounded
by the time remaining. Incorrect scope, cache policy, or enabled business
capabilities in a successful health response fail immediately; dispatch and
route-containment checks also remain fail-fast.

The workflow stamps `app/_build_revision.txt` with the exact checked-out commit.
`UNSTAMPED` is deliberately invalid and makes the staging process fail startup.
Do not commit a generated stamp or edit source files after stamping and then
claim the resulting image represents the unchanged commit.

Create or choose a dedicated staging application service, then set its custom
Railway Config File path to `/deployment/railway-staging.toml` in that service's
settings. Railway requires the absolute repository path when selecting a custom
config file. ([Railway config reference](https://docs.railway.com/reference/config-as-code))
The file selects `Dockerfile.railway`, `/health/ready`, a 120-second health check
timeout, and bounded on-failure restarts; review service settings for overrides
before enabling deployment. There is deliberately no root `railway.toml`, so
other services are not opted in by this repository change.

If native GitHub autodeploy is configured on that service, do not also let it
deploy every push alongside this workflow. Railway's native GitHub triggers and
CLI-driven Actions are alternative automation paths. ([Railway GitHub Actions guide](https://railway.com/guides/github-actions))

## Direct deployment and connection workarounds

Use an environment-scoped project token in `RAILWAY_TOKEN`. Explicit `--project`
and `--environment` avoid a local link; `--environment` is required when using
`--project`. ([Railway deployment guide](https://docs.railway.com/cli/deploying))
Use the intended existing application service, never a database service.
That service must first select `/deployment/railway-staging.toml` as described
above; the CLI upload alone does not configure that service setting.

```bash
# Run from a clean checkout of the reviewed commit, before generating the stamp.
git diff --quiet && git diff --cached --quiet || exit 1
git rev-parse HEAD > app/_build_revision.txt
unset RAILWAY_API_TOKEN
read -r -s -p "Railway staging project token: " RAILWAY_TOKEN
printf '\n'
export RAILWAY_TOKEN
read -r -p "Railway staging environment ID: " RAILWAY_ENVIRONMENT_ID
read -r -p "Restricted staging service ID: " RAILWAY_SERVICE_ID
: "${RAILWAY_TOKEN:?required}"
: "${RAILWAY_ENVIRONMENT_ID:?required}"
: "${RAILWAY_SERVICE_ID:?required}"
npx --yes --package=@railway/cli@5.71.0 railway up \
  --project 463d410b-09a3-4117-a3b5-05e6646e7807 \
  --environment "$RAILWAY_ENVIRONMENT_ID" \
  --service "$RAILWAY_SERVICE_ID" --ci
unset RAILWAY_TOKEN
```

For local interactive account work, `railway login --browserless` avoids a local
browser callback. It is not needed in Actions and does not replace the project
token. ([Railway login reference](https://docs.railway.com/cli/login))
If streaming is blocked, `railway up --detach` queues deployment without waiting
for success; inspect the resulting deployment before retrying. ([Railway up reference](https://docs.railway.com/cli/up))
None of these routes bypasses authorization, a Railway-wide outage, or an
incorrect environment/service target.

```bash
# For logs, securely re-export RAILWAY_TOKEN if it was unset above.
railway logs --project 463d410b-09a3-4117-a3b5-05e6646e7807 \
  --environment "$RAILWAY_ENVIRONMENT_ID" --service "$RAILWAY_SERVICE_ID" \
  --build --lines 100

python scripts/railway_smoke.py --base-url https://YOUR-STAGING-HOST \
  --expected-revision "$(git rev-parse HEAD)"

# Restore the generated local stamp after deployment.
git restore app/_build_revision.txt
unset RAILWAY_TOKEN
```

`--lines 100` requests finite historical logs instead of a live stream. ([Railway logs reference](https://docs.railway.com/cli/logs))
Do not disable TLS verification; inspect logs and deployment status before
rerunning an upload with an uncertain result.

## Operational limits

No database provisioning/migration, real-data collection, model enablement,
durable evidence storage, live payments, external dispatch, or production
rollout is performed by this workflow. Enabling those capabilities requires
separate integration, authorization, and acceptance work.
