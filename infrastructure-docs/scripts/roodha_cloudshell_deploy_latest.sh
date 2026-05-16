#!/usr/bin/env bash
set -euo pipefail

REGION="${REGION:-ap-south-1}"
EXPECTED_ACCOUNT="${EXPECTED_ACCOUNT:-918172959197}"
REPO_URL="${REPO_URL:-https://github.com/roshandatadive/project-roodha.git}"
BRANCH="${BRANCH:-codex/saas-stabilization-live}"

EB_APP_NAME="${EB_APP_NAME:-roodha-backend}"
EB_ENV_NAME="${EB_ENV_NAME:-Roodha-backend-env}"
SOURCE_BUCKET="${SOURCE_BUCKET:-elasticbeanstalk-ap-south-1-918172959197}"
FRONTEND_BUCKET="${FRONTEND_BUCKET:-roodha-v1-live-918172959197}"

BACKEND_URL="${BACKEND_URL:-http://roodha-backend-env.eba-52xsapkh.ap-south-1.elasticbeanstalk.com}"
FRONTEND_URL="${FRONTEND_URL:-http://roodha-v1-live-918172959197.s3-website.ap-south-1.amazonaws.com}"
COGNITO_USER_POOL_ID="${COGNITO_USER_POOL_ID:-ap-south-1_U3JeTevgw}"
COGNITO_APP_CLIENT_ID="${COGNITO_APP_CLIENT_ID:-3ab798pg0k2p8hp7v6bbtlh4mj}"

DEPLOY_ROOT="${DEPLOY_ROOT:-$HOME/roodha-cloudshell-deploy}"
RUN_ID="$(date -u +%Y%m%d-%H%M%S)"
WORKDIR="${DEPLOY_ROOT}/${RUN_ID}"
VERSION_LABEL="${VERSION_LABEL:-v-auth-stabilized-${RUN_ID}}"
BACKEND_ZIP="/tmp/roodha-backend-${RUN_ID}.zip"
SOURCE_KEY="roodha-backend-${VERSION_LABEL}.zip"

log() {
  printf '\n==> %s\n' "$*"
}

fail() {
  printf '\nERROR: %s\n' "$*" >&2
  exit 1
}

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "Missing required command: $1"
}

need_cmd aws
need_cmd git
need_cmd python3
need_cmd zip
need_cmd zipinfo
need_cmd curl
need_cmd npm

log "Verifying AWS identity"
IDENTITY_JSON="$(aws sts get-caller-identity --region "$REGION" --output json)"
ACCOUNT_ID="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["Account"])' <<<"$IDENTITY_JSON")"
if [[ "$ACCOUNT_ID" != "$EXPECTED_ACCOUNT" ]]; then
  fail "Wrong AWS account: got ${ACCOUNT_ID}, expected ${EXPECTED_ACCOUNT}"
fi
printf 'AWS account: %s\n' "$ACCOUNT_ID"

log "Cloning latest code"
mkdir -p "$DEPLOY_ROOT"
git clone --depth 1 --branch "$BRANCH" "$REPO_URL" "$WORKDIR"
cd "$WORKDIR"
GIT_SHA="$(git rev-parse --short HEAD)"
printf 'Branch: %s\nCommit: %s\n' "$BRANCH" "$GIT_SHA"

log "Running backend tests"
cd "$WORKDIR/job_work_planner/task-4-backend-skeleton"
python3 -m venv .venv-deploy
source .venv-deploy/bin/activate
python -m pip install --upgrade pip >/dev/null
python -m pip install -r requirements.txt >/dev/null
python -m pip install pytest >/dev/null
PYTHONPATH=. python -m pytest -q
deactivate

log "Packaging backend for Elastic Beanstalk"
rm -f "$BACKEND_ZIP"
zip -qr "$BACKEND_ZIP" app alembic alembic.ini requirements.txt Procfile \
  -x "*.env*" "*/__pycache__/*" "*.pyc" "tests/*" "scripts/*" "*.log" "*.zip" "*.csv"

if zipinfo -1 "$BACKEND_ZIP" | grep -E '(^|/)(\.env|__pycache__|tests|scripts|node_modules|dist)(/|$)|\.(csv|log|zip)$' >/dev/null; then
  zipinfo -1 "$BACKEND_ZIP" | grep -E '(^|/)(\.env|__pycache__|tests|scripts|node_modules|dist)(/|$)|\.(csv|log|zip)$' >&2
  fail "Backend zip contains blocked local/generated/secret-like files"
fi

log "Uploading backend bundle"
aws s3 cp "$BACKEND_ZIP" "s3://${SOURCE_BUCKET}/${SOURCE_KEY}" --region "$REGION" >/dev/null

log "Creating Elastic Beanstalk version ${VERSION_LABEL}"
aws elasticbeanstalk create-application-version \
  --region "$REGION" \
  --application-name "$EB_APP_NAME" \
  --version-label "$VERSION_LABEL" \
  --source-bundle S3Bucket="$SOURCE_BUCKET",S3Key="$SOURCE_KEY" >/dev/null

log "Updating Elastic Beanstalk environment"
aws elasticbeanstalk update-environment \
  --region "$REGION" \
  --application-name "$EB_APP_NAME" \
  --environment-name "$EB_ENV_NAME" \
  --version-label "$VERSION_LABEL" >/dev/null

log "Waiting for EB environment to become Ready and healthy"
READY="false"
for _attempt in $(seq 1 60); do
  ENV_STATE="$(aws elasticbeanstalk describe-environments \
    --region "$REGION" \
    --application-name "$EB_APP_NAME" \
    --environment-names "$EB_ENV_NAME" \
    --query 'Environments[0].[Status,Health,HealthStatus]' \
    --output text)"
  printf '%s\n' "$ENV_STATE"
  STATUS="$(awk '{print $1}' <<<"$ENV_STATE")"
  HEALTH="$(awk '{print $2}' <<<"$ENV_STATE")"
  HEALTH_STATUS="$(awk '{print $3}' <<<"$ENV_STATE")"
  if [[ "$STATUS" == "Ready" && ( "$HEALTH" == "Green" || "$HEALTH_STATUS" == "Ok" ) ]]; then
    READY="true"
    break
  fi
  sleep 20
done
[[ "$READY" == "true" ]] || fail "Elastic Beanstalk did not become Ready/healthy in time"

log "Verifying backend endpoints"
curl -fsS "${BACKEND_URL}/api/ping" >/dev/null
curl -fsS "${BACKEND_URL}/api/ready" >/dev/null
curl -fsS "${BACKEND_URL}/api/debug/db-check" >/dev/null
printf 'Backend smoke: PASS\n'

log "Running frontend tests and build"
cd "$WORKDIR/job_work_planner/task-5-react-frontend"
npm ci
export VITE_API_BASE_URL="${VITE_API_BASE_URL:-${BACKEND_URL}/api}"
export VITE_COGNITO_REGION="${VITE_COGNITO_REGION:-${REGION}}"
export VITE_COGNITO_USER_POOL_ID="${VITE_COGNITO_USER_POOL_ID:-${COGNITO_USER_POOL_ID}}"
export VITE_COGNITO_CLIENT_ID="${VITE_COGNITO_CLIENT_ID:-${COGNITO_APP_CLIENT_ID}}"
export VITE_ENABLE_SELF_SIGNUP="${VITE_ENABLE_SELF_SIGNUP:-true}"
export VITE_S3_WEBSITE_URL="${VITE_S3_WEBSITE_URL:-${FRONTEND_URL}}"
npm test -- --run
npm run build

log "Syncing frontend to S3"
aws s3 sync dist/ "s3://${FRONTEND_BUCKET}" --delete --region "$REGION"

if [[ -n "${CLOUDFRONT_DISTRIBUTION_ID:-}" ]]; then
  log "Invalidating CloudFront distribution ${CLOUDFRONT_DISTRIBUTION_ID}"
  aws cloudfront create-invalidation \
    --distribution-id "$CLOUDFRONT_DISTRIBUTION_ID" \
    --paths "/*" >/dev/null
fi

log "Deployment complete"
cat <<EOF
DEPLOY_PASS
Account: ${ACCOUNT_ID}
Branch: ${BRANCH}
Commit: ${GIT_SHA}
Backend version: ${VERSION_LABEL}
Frontend bucket: s3://${FRONTEND_BUCKET}
Frontend URL: ${FRONTEND_URL}
Backend URL: ${BACKEND_URL}

Manual smoke:
1. Open ${FRONTEND_URL}
2. Log in as Owner and confirm /dashboard.
3. Invite Operator and confirm Set New Password flow.
4. Confirm Operator lands on /operator.
EOF
