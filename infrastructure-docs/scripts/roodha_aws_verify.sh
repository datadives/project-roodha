#!/usr/bin/env bash
set -euo pipefail

REGION="${REGION:-ap-south-1}"
ACCOUNT_ID_EXPECTED="${ACCOUNT_ID_EXPECTED:-918172959197}"
EB_APP_NAME="${EB_APP_NAME:-roodha-backend}"
EB_ENV_NAME="${EB_ENV_NAME:-Roodha-backend-env}"
BACKEND_URL="${BACKEND_URL:-http://roodha-backend-env.eba-52xsapkh.ap-south-1.elasticbeanstalk.com}"
USER_POOL_ID="${USER_POOL_ID:-ap-south-1_U3JeTevgw}"
USER_POOL_CLIENT_ID="${USER_POOL_CLIENT_ID:-3ab798pg0k2p8hp7v6bbtlh4mj}"
RDS_INSTANCE_ID="${RDS_INSTANCE_ID:-roodha-v1-postgres}"

log() { printf "\n\033[1;32m==> %s\033[0m\n" "$*"; }
warn() { printf "\n\033[1;33mWARNING: %s\033[0m\n" "$*"; }
fail() { printf "\n\033[1;31mERROR: %s\033[0m\n" "$*" >&2; exit 1; }

require_identity() {
  log "Checking CloudShell/AWS identity"
  if ! IDENTITY_JSON="$(aws sts get-caller-identity --output json 2>/tmp/roodha_sts_error.txt)"; then
    cat /tmp/roodha_sts_error.txt >&2 || true
    fail "AWS credentials are unavailable. Restart CloudShell, then run: aws sts get-caller-identity"
  fi

  ACCOUNT_ID="$(printf "%s" "$IDENTITY_JSON" | python3 -c 'import json,sys; print(json.load(sys.stdin)["Account"])')"
  echo "$IDENTITY_JSON"
  if [[ "$ACCOUNT_ID" != "$ACCOUNT_ID_EXPECTED" ]]; then
    warn "Expected account $ACCOUNT_ID_EXPECTED but current account is $ACCOUNT_ID"
  fi
}

curl_json() {
  local path="$1"
  local url="${BACKEND_URL}${path}"
  echo "GET $url"
  curl -fsS "$url" | python3 -m json.tool
}

require_identity

log "Checking Cognito user pool"
aws cognito-idp describe-user-pool \
  --region "$REGION" \
  --user-pool-id "$USER_POOL_ID" \
  --query 'UserPool.{AutoVerifiedAttributes:AutoVerifiedAttributes,EmailConfiguration:EmailConfiguration,AccountRecoverySetting:AccountRecoverySetting,LambdaConfig:LambdaConfig,AdminCreateUserConfig:AdminCreateUserConfig}' \
  --output json

log "Checking Cognito app client auth flows"
aws cognito-idp describe-user-pool-client \
  --region "$REGION" \
  --user-pool-id "$USER_POOL_ID" \
  --client-id "$USER_POOL_CLIENT_ID" \
  --query 'UserPoolClient.{ClientId:ClientId,ExplicitAuthFlows:ExplicitAuthFlows,PreventUserExistenceErrors:PreventUserExistenceErrors}' \
  --output json

log "Checking Cognito groups"
aws cognito-idp list-groups \
  --region "$REGION" \
  --user-pool-id "$USER_POOL_ID" \
  --query 'Groups[].GroupName' \
  --output table

log "Checking SES account and identities"
aws sesv2 get-account \
  --region "$REGION" \
  --query '{ProductionAccessEnabled:ProductionAccessEnabled,SendingEnabled:SendingEnabled,EnforcementStatus:EnforcementStatus}' \
  --output table || warn "SES v2 account check failed"
aws sesv2 list-email-identities \
  --region "$REGION" \
  --query 'EmailIdentities[].{Identity:IdentityName,Type:IdentityType,Verified:VerifiedForSendingStatus}' \
  --output table || warn "SES identity check failed"

log "Checking Elastic Beanstalk"
aws elasticbeanstalk describe-environments \
  --region "$REGION" \
  --application-name "$EB_APP_NAME" \
  --environment-names "$EB_ENV_NAME" \
  --query 'Environments[0].{Status:Status,Health:Health,HealthStatus:HealthStatus,CNAME:CNAME}' \
  --output table

log "Checking Elastic Beanstalk environment variables"
aws elasticbeanstalk describe-configuration-settings \
  --region "$REGION" \
  --application-name "$EB_APP_NAME" \
  --environment-name "$EB_ENV_NAME" \
  --query "ConfigurationSettings[0].OptionSettings[?Namespace=='aws:elasticbeanstalk:application:environment'].[OptionName,Value]" \
  --output table

log "Checking RDS"
aws rds describe-db-instances \
  --region "$REGION" \
  --db-instance-identifier "$RDS_INSTANCE_ID" \
  --query 'DBInstances[0].{Status:DBInstanceStatus,Engine:Engine,EngineVersion:EngineVersion,Endpoint:Endpoint.Address,PubliclyAccessible:PubliclyAccessible}' \
  --output table

log "Checking backend health"
curl_json "/api/ping"
curl_json "/api/ready"
curl_json "/api/debug/db-check"

log "Verification complete"
