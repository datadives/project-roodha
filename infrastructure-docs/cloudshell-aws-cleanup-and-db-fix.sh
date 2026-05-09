#!/usr/bin/env bash
set -euo pipefail
export AWS_PAGER=""

REGION="us-east-1"
POOL_ID="us-east-1_971juKyUp"
FINAL_CLIENT_ID="6i2gbi9ttmv034ebau874s4cd0"
CLIENT_NAME="RoodhaSaaS_WebClient"
DB_ID="roodha-v15-db"
NEW_DB_PASSWORD="${1:-}"

echo "=============================================="
echo "PROJECT ROODHA AWS CLEANUP AND DB FIX"
echo "=============================================="

echo
echo "[1/7] Confirming AWS identity..."
aws sts get-caller-identity --output table --no-cli-pager

echo
echo "[2/7] Cleaning duplicate Cognito app clients for $CLIENT_NAME..."
CLIENTS=$(aws cognito-idp list-user-pool-clients \
  --region "$REGION" \
  --user-pool-id "$POOL_ID" \
  --query "UserPoolClients[?ClientName=='$CLIENT_NAME'].ClientId" \
  --output text \
  --no-cli-pager)

for client_id in $CLIENTS; do
  if [ "$client_id" != "$FINAL_CLIENT_ID" ]; then
    echo "Deleting duplicate Cognito app client: $client_id"
    aws cognito-idp delete-user-pool-client \
      --region "$REGION" \
      --user-pool-id "$POOL_ID" \
      --client-id "$client_id" \
      --no-cli-pager
  fi
done

echo
echo "[3/7] Hardening active Cognito app client..."
aws cognito-idp update-user-pool \
  --region "$REGION" \
  --user-pool-id "$POOL_ID" \
  --auto-verified-attributes email \
  --admin-create-user-config AllowAdminCreateUserOnly=false \
  --no-cli-pager

aws cognito-idp update-user-pool-client \
  --region "$REGION" \
  --user-pool-id "$POOL_ID" \
  --client-id "$FINAL_CLIENT_ID" \
  --explicit-auth-flows ALLOW_USER_PASSWORD_AUTH ALLOW_USER_SRP_AUTH ALLOW_REFRESH_TOKEN_AUTH \
  --prevent-user-existence-errors ENABLED \
  --supported-identity-providers COGNITO \
  --no-cli-pager

echo
echo "[4/7] Checking active app client has no client secret..."
CLIENT_SECRET=$(aws cognito-idp describe-user-pool-client \
  --region "$REGION" \
  --user-pool-id "$POOL_ID" \
  --client-id "$FINAL_CLIENT_ID" \
  --query "UserPoolClient.ClientSecret" \
  --output text \
  --no-cli-pager 2>/dev/null || true)

if [ "$CLIENT_SECRET" != "None" ] && [ -n "$CLIENT_SECRET" ]; then
  echo "ERROR: Active client still has a secret. Browser login cannot use this client."
  exit 1
fi
echo "OK: Active Cognito app client has no secret."

echo
echo "[5/7] Optionally resetting RDS master password..."
if [ -n "$NEW_DB_PASSWORD" ]; then
  aws rds modify-db-instance \
    --region "$REGION" \
    --db-instance-identifier "$DB_ID" \
    --master-user-password "$NEW_DB_PASSWORD" \
    --apply-immediately \
    --no-cli-pager
  echo "Password reset requested. Waiting for DB to become available..."
  aws rds wait db-instance-available \
    --region "$REGION" \
    --db-instance-identifier "$DB_ID"
else
  echo "No DB password argument supplied. Skipping password reset."
  echo "Usage to reset: ./cloudshell-aws-cleanup-and-db-fix.sh 'your-new-password'"
fi

echo
echo "[6/7] Reporting Roodha AWS resources without deleting broad infrastructure..."
echo "RDS:"
aws rds describe-db-instances \
  --region "$REGION" \
  --query "DBInstances[?contains(DBInstanceIdentifier, 'roodha')].[DBInstanceIdentifier,DBInstanceStatus,Endpoint.Address,PubliclyAccessible]" \
  --output table \
  --no-cli-pager

echo "S3 buckets containing roodha:"
aws s3api list-buckets \
  --query "Buckets[?contains(Name, 'roodha')].Name" \
  --output table \
  --no-cli-pager

echo "CloudFront distributions:"
aws cloudfront list-distributions \
  --query "DistributionList.Items[*].[Id,DomainName,Enabled,Comment]" \
  --output table \
  --no-cli-pager || true

echo
echo "[7/7] Writing non-secret cleanup summary..."
cat > roodha-aws-cleanup-summary.txt <<SUMMARY
Project Roodha AWS Cleanup Summary
Region=$REGION
CognitoUserPoolId=$POOL_ID
ActiveCognitoClientId=$FINAL_CLIENT_ID
RdsInstanceId=$DB_ID
RdsDatabaseUrl=postgresql://postgres:[YOUR_DB_PASSWORD]@roodha-v15-db.c21wwauc86cp.us-east-1.rds.amazonaws.com:5432/postgres
Notes:
- Duplicate Cognito app clients named $CLIENT_NAME were removed except $FINAL_CLIENT_ID.
- Cognito self-service signup and email auto-verification were enforced.
- Broad S3/CloudFront/RDS deletion is intentionally not automatic.
- Rotate any IAM access key pasted into chat or logs.
SUMMARY

echo
echo "DONE. Summary saved to $(pwd)/roodha-aws-cleanup-summary.txt"
