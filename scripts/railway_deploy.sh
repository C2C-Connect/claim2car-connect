#!/usr/bin/env bash
# Run only inside the serialized deployment job, after verification succeeds.
set -euo pipefail
unset RAILWAY_API_TOKEN

: "${GITHUB_OUTPUT:?GitHub Actions output file is required}"
: "${GITHUB_REPOSITORY:?GitHub repository is required}"
: "${GITHUB_SHA:?Verified commit SHA is required}"
: "${GH_TOKEN:?Read-only GitHub token is required}"
printf 'deployed=false\n' >> "$GITHUB_OUTPUT"

if [[ ! "$GITHUB_SHA" =~ ^[0-9a-f]{40}$ ]]; then
  printf '::error::GITHUB_SHA must be a full commit SHA.\n'
  exit 1
fi
for name in RAILWAY_PROJECT_ID RAILWAY_TOKEN RAILWAY_ENVIRONMENT_ID RAILWAY_SERVICE_ID RAILWAY_STAGING_URL; do
  if [[ -z "${!name:-}" || "${!name}" =~ [[:space:]] ]]; then
    printf '::error::Missing or malformed repository setting: %s\n' "$name"
    exit 1
  fi
done
if [[ "$RAILWAY_STAGING_URL" != https://* ]]; then
  printf '::error::RAILWAY_STAGING_URL must be an HTTPS origin.\n'
  exit 1
fi

# Verification jobs may finish out of order. Re-read main inside the deployment
# lock, immediately before stamping/uploading; API errors must fail closed.
head_sha=$(gh api --method GET "repos/${GITHUB_REPOSITORY}/git/ref/heads/main" --jq '.object.sha')
if [[ ! "$head_sha" =~ ^[0-9a-f]{40}$ ]]; then
  printf '::error::Could not determine the current main commit; refusing upload.\n'
  exit 1
fi
if [[ "$head_sha" != "$GITHUB_SHA" ]]; then
  printf '::notice::Skipping stale deployment %s; current main is %s.\n' "$GITHUB_SHA" "$head_sha"
  if [[ -n "${GITHUB_STEP_SUMMARY:-}" ]]; then
    printf 'Deployment skipped: verified commit `%s` is no longer main (`%s`). No Railway upload or live smoke test was run.\n' \
      "$GITHUB_SHA" "$head_sha" >> "$GITHUB_STEP_SUMMARY"
  fi
  exit 0
fi

printf '%s\n' "$GITHUB_SHA" > app/_build_revision.txt
railway up \
  --project "$RAILWAY_PROJECT_ID" \
  --environment "$RAILWAY_ENVIRONMENT_ID" \
  --service "$RAILWAY_SERVICE_ID" \
  --ci --message "Verified restricted staging commit ${GITHUB_SHA}"
printf 'deployed=true\n' >> "$GITHUB_OUTPUT"
