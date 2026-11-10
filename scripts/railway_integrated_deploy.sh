#!/usr/bin/env bash
# Manually gated integrated staging deploy. Never targets the restricted health-only service.
set -euo pipefail
unset RAILWAY_API_TOKEN

: "${GITHUB_OUTPUT:?GitHub Actions output file is required}"
: "${GITHUB_REPOSITORY:?GitHub repository is required}"
: "${GITHUB_SHA:?Verified main SHA is required}"
: "${GH_TOKEN:?Read-only GitHub token is required}"
printf 'deployed=false\n' >> "$GITHUB_OUTPUT"

for name in RAILWAY_PROJECT_ID RAILWAY_TOKEN RAILWAY_ENVIRONMENT_ID RAILWAY_SERVICE_ID RAILWAY_STAGING_URL MIGRATION_DATABASE_URL; do
  if [[ -z "${!name:-}" || "${!name}" =~ [[:space:]] ]]; then
    printf '::error::Missing or malformed integrated staging setting: %s\n' "$name"
    exit 1
  fi
done
if [[ "$GITHUB_REF" != "refs/heads/main" || ! "$GITHUB_SHA" =~ ^[0-9a-f]{40}$ ]]; then
  printf '::error::Integrated staging deploys are allowed only from a full main-branch commit SHA.\n'
  exit 1
fi
if [[ "$RAILWAY_STAGING_URL" != https://* ]]; then
  printf '::error::RAILWAY_STAGING_URL must be an HTTPS origin.\n'
  exit 1
fi

head_sha=$(gh api --method GET "repos/${GITHUB_REPOSITORY}/git/ref/heads/main" --jq '.object.sha')
if [[ "$head_sha" != "$GITHUB_SHA" ]]; then
  printf '::notice::Skipping stale integrated deploy %s; main is now %s.\n' "$GITHUB_SHA" "$head_sha"
  exit 0
fi

# Apply the PostgreSQL authority plan before uploading the matching application.
# This DSN is a GitHub secret and is never printed.
python -m database.migrate
if [[ -n "${ROUTING_MIGRATION_DATABASE_URL:-}" ]]; then
  python -m database.migrate --routing
fi

head_sha=$(gh api --method GET "repos/${GITHUB_REPOSITORY}/git/ref/heads/main" --jq '.object.sha')
if [[ "$head_sha" != "$GITHUB_SHA" ]]; then
  printf '::notice::Main advanced during migration; schema is forward-compatible, but this stale app revision will not deploy.\n'
  exit 0
fi

printf '%s\n' "$GITHUB_SHA" > app/_build_revision.txt
railway up \
  --project "$RAILWAY_PROJECT_ID" \
  --environment "$RAILWAY_ENVIRONMENT_ID" \
  --service "$RAILWAY_SERVICE_ID" \
  --ci --message "Claim2Car integrated staging ${GITHUB_SHA}"
printf 'deployed=true\n' >> "$GITHUB_OUTPUT"
