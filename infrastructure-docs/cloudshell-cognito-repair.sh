#!/usr/bin/env bash
set -euo pipefail
export AWS_PAGER=""

POOL_ID="us-east-1_971juKyUp"
CLIENT_ID="6i2gbi9ttmv034ebau874s4cd0"
REGION="us-east-1"

if [ $# -lt 1 ]; then
  echo "Usage: ./cloudshell-cognito-repair.sh <email>"
  exit 1
fi

EMAIL="$1"

echo "=============================================="
echo "PROJECT ROODHA COGNITO ACCOUNT REPAIR"
echo "=============================================="
echo "Email: $EMAIL"
echo "Pool:  $POOL_ID"
echo "Client:$CLIENT_ID"
echo

echo "[1/6] Inspecting user pool configuration..."
aws cognito-idp describe-user-pool \
  --region "$REGION" \
  --user-pool-id "$POOL_ID" \
  --query 'UserPool.{Name:Name,AutoVerified:AutoVerifiedAttributes,AdminCreateOnly:AdminCreateUserConfig.AllowAdminCreateUserOnly,EmailSendingAccount:EmailConfiguration.EmailSendingAccount,From:EmailConfiguration.From,ReplyTo:EmailConfiguration.ReplyToEmailAddress}' \
  --output table \
  --no-cli-pager

echo
echo "[2/6] Checking Cognito user state..."
USER_STATUS="$(aws cognito-idp admin-get-user \
  --region "$REGION" \
  --user-pool-id "$POOL_ID" \
  --username "$EMAIL" \
  --query 'UserStatus' \
  --output text 2>/dev/null || true)"

if [ -z "${USER_STATUS:-}" ] || [ "$USER_STATUS" = "None" ]; then
  echo "No Cognito user exists yet for $EMAIL"
  USER_STATUS=""
else
  echo "Current user status: $USER_STATUS"
fi

echo
echo "[3/6] If user is UNCONFIRMED, delete and reset cleanly..."
if [ "${USER_STATUS:-}" = "UNCONFIRMED" ]; then
  aws cognito-idp admin-delete-user \
    --region "$REGION" \
    --user-pool-id "$POOL_ID" \
    --username "$EMAIL"
  echo "Deleted stuck UNCONFIRMED user."
  echo "Next step: go back to the app and register again with the same email."
  exit 0
fi

echo
echo "[4/6] If user is CONFIRMED, trigger forgot-password instead of sign-up..."
if [ "${USER_STATUS:-}" = "CONFIRMED" ]; then
  aws cognito-idp forgot-password \
    --region "$REGION" \
    --client-id "$CLIENT_ID" \
    --username "$EMAIL" \
    --output json \
    --no-cli-pager
  echo "Password reset flow requested for confirmed user."
  exit 0
fi

echo
echo "[5/6] If user exists but is not confirmed, request a fresh OTP..."
if [ -n "${USER_STATUS:-}" ]; then
  aws cognito-idp resend-confirmation-code \
    --region "$REGION" \
    --client-id "$CLIENT_ID" \
    --username "$EMAIL" \
    --output json \
    --no-cli-pager
  echo "Confirmation OTP resend requested."
  exit 0
fi

echo
echo "[6/6] No user exists yet. Frontend sign-up should create the user and trigger OTP."
echo "If OTP still does not arrive, check Cognito email delivery and SES configuration."
