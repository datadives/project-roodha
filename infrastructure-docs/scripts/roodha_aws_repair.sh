#!/usr/bin/env bash
set -euo pipefail

REGION="${REGION:-ap-south-1}"
ACCOUNT_ID_EXPECTED="${ACCOUNT_ID_EXPECTED:-918172959197}"
EB_ROLE_NAME="${EB_ROLE_NAME:-AWSElasticBeanstalkWebTier}"
EB_APP_NAME="${EB_APP_NAME:-roodha-backend}"
EB_ENV_NAME="${EB_ENV_NAME:-Roodha-backend-env}"
BACKEND_URL="${BACKEND_URL:-http://roodha-backend-env.eba-52xsapkh.ap-south-1.elasticbeanstalk.com}"
USER_POOL_ID="${USER_POOL_ID:-ap-south-1_U3JeTevgw}"
USER_POOL_CLIENT_ID="${USER_POOL_CLIENT_ID:-3ab798pg0k2p8hp7v6bbtlh4mj}"
RDS_INSTANCE_ID="${RDS_INSTANCE_ID:-roodha-v1-postgres}"
DEFAULT_OWNER_GROUP="${DEFAULT_OWNER_GROUP:-OWNER}"
LAMBDA_ROLE_NAME="${LAMBDA_ROLE_NAME:-roodha-cognito-post-confirm-role}"
LAMBDA_NAME="${LAMBDA_NAME:-roodha-cognito-post-confirm-owner}"

# Optional SES production settings. Leave blank to keep Cognito default sender.
SES_SENDER_EMAIL="${SES_SENDER_EMAIL:-}"
SES_DOMAIN="${SES_DOMAIN:-}"
APP_URL="${APP_URL:-https://roodha.com}"
ADMIN_CONTACT_EMAIL="${ADMIN_CONTACT_EMAIL:-}"

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
    fail "Refusing to mutate account $ACCOUNT_ID. Expected $ACCOUNT_ID_EXPECTED."
  fi
  USER_POOL_ARN="arn:aws:cognito-idp:${REGION}:${ACCOUNT_ID}:userpool/${USER_POOL_ID}"
}

configure_cognito_pool() {
  log "Configuring Cognito public signup, OTP, recovery, and invites"
  aws cognito-idp update-user-pool \
    --region "$REGION" \
    --user-pool-id "$USER_POOL_ID" \
    --auto-verified-attributes email \
    --account-recovery-setting 'RecoveryMechanisms=[{Priority=1,Name=verified_email}]' \
    --verification-message-template 'DefaultEmailOption=CONFIRM_WITH_CODE,EmailSubject="Your Roodha verification code",EmailMessage="Your Roodha verification code is {####}. This code expires soon."' \
    --admin-create-user-config 'AllowAdminCreateUserOnly=false,InviteMessageTemplate={EmailSubject="You are invited to Roodha",EmailMessage="You have been invited to Roodha. Username: {username}. Temporary password: {####}"}' \
    --email-configuration EmailSendingAccount=COGNITO_DEFAULT >/dev/null

  aws cognito-idp update-user-pool-client \
    --region "$REGION" \
    --user-pool-id "$USER_POOL_ID" \
    --client-id "$USER_POOL_CLIENT_ID" \
    --explicit-auth-flows \
      ALLOW_USER_PASSWORD_AUTH \
      ALLOW_USER_SRP_AUTH \
      ALLOW_REFRESH_TOKEN_AUTH >/dev/null
}

create_groups() {
  log "Ensuring Cognito role groups exist"
  for group in OWNER SUPERVISOR OPERATOR; do
    aws cognito-idp create-group \
      --region "$REGION" \
      --user-pool-id "$USER_POOL_ID" \
      --group-name "$group" >/dev/null 2>&1 || true
  done
}

grant_eb_invite_permissions() {
  log "Granting Elastic Beanstalk least-privilege Cognito invite permissions"
  cat > /tmp/roodha-cognito-admin-policy.json <<JSON
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "RoodhaCognitoUserInvites",
      "Effect": "Allow",
      "Action": [
        "cognito-idp:AdminCreateUser",
        "cognito-idp:AdminGetUser",
        "cognito-idp:AdminUpdateUserAttributes",
        "cognito-idp:AdminAddUserToGroup",
        "cognito-idp:AdminSetUserPassword",
        "cognito-idp:AdminConfirmSignUp",
        "cognito-idp:AdminResetUserPassword",
        "cognito-idp:ListUsers"
      ],
      "Resource": "$USER_POOL_ARN"
    }
  ]
}
JSON

  aws iam put-role-policy \
    --role-name "$EB_ROLE_NAME" \
    --policy-name "RoodhaCognitoAdminUserInvites" \
    --policy-document file:///tmp/roodha-cognito-admin-policy.json
}

configure_post_confirm_lambda() {
  log "Creating/updating PostConfirmation Lambda for public owner signup"
  cat > /tmp/roodha-lambda-trust.json <<JSON
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {"Service": "lambda.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }
  ]
}
JSON

  aws iam create-role \
    --role-name "$LAMBDA_ROLE_NAME" \
    --assume-role-policy-document file:///tmp/roodha-lambda-trust.json >/dev/null 2>&1 || true

  aws iam attach-role-policy \
    --role-name "$LAMBDA_ROLE_NAME" \
    --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole >/dev/null 2>&1 || true

  cat > /tmp/roodha-lambda-policy.json <<JSON
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "cognito-idp:AdminAddUserToGroup",
        "cognito-idp:AdminUpdateUserAttributes"
      ],
      "Resource": "$USER_POOL_ARN"
    }
  ]
}
JSON

  aws iam put-role-policy \
    --role-name "$LAMBDA_ROLE_NAME" \
    --policy-name "RoodhaPostConfirmCognitoAccess" \
    --policy-document file:///tmp/roodha-lambda-policy.json

  sleep 10
  LAMBDA_ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${LAMBDA_ROLE_NAME}"
  WORKDIR="$(mktemp -d)"
  cat > "$WORKDIR/lambda_function.py" <<'PY'
import boto3
import os

cognito = boto3.client("cognito-idp")

def lambda_handler(event, context):
    user_pool_id = event["userPoolId"]
    username = event["userName"]
    group = os.environ.get("DEFAULT_GROUP", "OWNER")
    cognito.admin_add_user_to_group(UserPoolId=user_pool_id, Username=username, GroupName=group)
    cognito.admin_update_user_attributes(
        UserPoolId=user_pool_id,
        Username=username,
        UserAttributes=[{"Name": "email_verified", "Value": "true"}],
    )
    return event
PY
  (cd "$WORKDIR" && zip -q function.zip lambda_function.py)

  if aws lambda get-function --region "$REGION" --function-name "$LAMBDA_NAME" >/dev/null 2>&1; then
    aws lambda update-function-code \
      --region "$REGION" \
      --function-name "$LAMBDA_NAME" \
      --zip-file "fileb://${WORKDIR}/function.zip" >/dev/null
    aws lambda update-function-configuration \
      --region "$REGION" \
      --function-name "$LAMBDA_NAME" \
      --role "$LAMBDA_ROLE_ARN" \
      --handler lambda_function.lambda_handler \
      --runtime python3.12 \
      --environment "Variables={DEFAULT_GROUP=${DEFAULT_OWNER_GROUP}}" >/dev/null
  else
    aws lambda create-function \
      --region "$REGION" \
      --function-name "$LAMBDA_NAME" \
      --runtime python3.12 \
      --role "$LAMBDA_ROLE_ARN" \
      --handler lambda_function.lambda_handler \
      --zip-file "fileb://${WORKDIR}/function.zip" \
      --environment "Variables={DEFAULT_GROUP=${DEFAULT_OWNER_GROUP}}" >/dev/null
  fi

  LAMBDA_ARN="$(aws lambda get-function \
    --region "$REGION" \
    --function-name "$LAMBDA_NAME" \
    --query 'Configuration.FunctionArn' \
    --output text)"

  aws lambda add-permission \
    --region "$REGION" \
    --function-name "$LAMBDA_NAME" \
    --statement-id "AllowCognitoInvoke-${USER_POOL_ID}" \
    --action lambda:InvokeFunction \
    --principal cognito-idp.amazonaws.com \
    --source-arn "$USER_POOL_ARN" >/dev/null 2>&1 || true

  aws cognito-idp update-user-pool \
    --region "$REGION" \
    --user-pool-id "$USER_POOL_ID" \
    --lambda-config "PostConfirmation=${LAMBDA_ARN}" >/dev/null
}

report_ses_status() {
  log "Checking SES readiness"
  aws sesv2 get-account \
    --region "$REGION" \
    --query '{ProductionAccessEnabled:ProductionAccessEnabled,SendingEnabled:SendingEnabled,EnforcementStatus:EnforcementStatus}' \
    --output table || warn "SES account check failed"
  aws sesv2 list-email-identities \
    --region "$REGION" \
    --query 'EmailIdentities[].{Identity:IdentityName,Type:IdentityType,Verified:VerifiedForSendingStatus}' \
    --output table || warn "SES identity check failed"

  if [[ -n "$SES_SENDER_EMAIL" ]]; then
    log "Creating SES sender identity if missing: $SES_SENDER_EMAIL"
    aws sesv2 create-email-identity --region "$REGION" --email-identity "$SES_SENDER_EMAIL" >/dev/null 2>&1 || true
    warn "Open the sender inbox and click the AWS verification link before switching Cognito to SES."
  fi

  if [[ -n "$SES_DOMAIN" ]]; then
    log "Creating SES domain identity if missing: $SES_DOMAIN"
    aws sesv2 create-email-identity --region "$REGION" --email-identity "$SES_DOMAIN" >/dev/null 2>&1 || true
    warn "Add the DKIM DNS records printed by: aws sesv2 get-email-identity --region $REGION --email-identity $SES_DOMAIN"
  fi

  if [[ -n "$ADMIN_CONTACT_EMAIL" ]]; then
    log "Submitting SES production access request"
    aws sesv2 put-account-details \
      --region "$REGION" \
      --production-access-enabled \
      --mail-type TRANSACTIONAL \
      --website-url "$APP_URL" \
      --use-case-description "Roodha sends transactional OTP, password recovery, and user invitation emails for a multi-tenant manufacturing SaaS." \
      --additional-contact-email-addresses "$ADMIN_CONTACT_EMAIL" \
      --contact-language EN >/dev/null 2>&1 || true
  else
    warn "SES production request skipped. Set ADMIN_CONTACT_EMAIL plus SES_SENDER_EMAIL or SES_DOMAIN when ready."
  fi
}

verify_runtime() {
  log "Verifying EB, RDS, and backend after repair"
  aws elasticbeanstalk describe-environments \
    --region "$REGION" \
    --application-name "$EB_APP_NAME" \
    --environment-names "$EB_ENV_NAME" \
    --query 'Environments[0].{Status:Status,Health:Health,HealthStatus:HealthStatus,CNAME:CNAME}' \
    --output table
  aws rds describe-db-instances \
    --region "$REGION" \
    --db-instance-identifier "$RDS_INSTANCE_ID" \
    --query 'DBInstances[0].{Status:DBInstanceStatus,Endpoint:Endpoint.Address}' \
    --output table
  curl -fsS "${BACKEND_URL}/api/ping" | python3 -m json.tool
  curl -fsS "${BACKEND_URL}/api/debug/db-check" | python3 -m json.tool
}

require_identity
configure_cognito_pool
create_groups
grant_eb_invite_permissions
configure_post_confirm_lambda
report_ses_status
verify_runtime

log "Repair complete"
cat <<EOF

What this fixed automatically:
- Cognito public signup, email OTP, and email recovery settings.
- OWNER, SUPERVISOR, and OPERATOR groups.
- Public signup PostConfirmation Lambda that adds new signups to OWNER.
- Elastic Beanstalk invite permissions for supervisor/operator creation.

Manual production email step:
- Cognito default email is active for immediate testing.
- Production-grade OTP still requires SES verified sender/domain and SES production access approval.
EOF
