#!/usr/bin/env bash
set -euo pipefail

REGION="${REGION:-ap-south-1}"
ACCOUNT_ID_EXPECTED="${ACCOUNT_ID_EXPECTED:-918172959197}"
EB_APP_NAME="${EB_APP_NAME:-roodha-backend}"
EB_ENV_NAME="${EB_ENV_NAME:-Roodha-backend-env}"
USER_POOL_ID="${USER_POOL_ID:-ap-south-1_U3JeTevgw}"
USER_POOL_CLIENT_ID="${USER_POOL_CLIENT_ID:-3ab798pg0k2p8hp7v6bbtlh4mj}"
BACKEND_URL="${BACKEND_URL:-http://roodha-backend-env.eba-52xsapkh.ap-south-1.elasticbeanstalk.com}"

log() { printf "\n\033[1;32m==> %s\033[0m\n" "$*"; }
warn() { printf "\n\033[1;33mWARNING: %s\033[0m\n" "$*"; }
fail() { printf "\n\033[1;31mERROR: %s\033[0m\n" "$*" >&2; exit 1; }

require_identity() {
  log "Checking CloudShell AWS identity"
  if ! identity_json="$(aws sts get-caller-identity --output json 2>/tmp/roodha_sts_error.txt)"; then
    cat /tmp/roodha_sts_error.txt >&2 || true
    fail "AWS credentials are unavailable. Restart CloudShell, then run: aws sts get-caller-identity"
  fi
  account_id="$(printf "%s" "$identity_json" | python3 -c 'import json,sys; print(json.load(sys.stdin)["Account"])')"
  arn="$(printf "%s" "$identity_json" | python3 -c 'import json,sys; print(json.load(sys.stdin)["Arn"])')"
  echo "Account: $account_id"
  echo "Caller:  $arn"
  [[ "$account_id" == "$ACCOUNT_ID_EXPECTED" ]] || fail "Refusing account $account_id. Expected $ACCOUNT_ID_EXPECTED."
  USER_POOL_ARN="arn:aws:cognito-idp:${REGION}:${account_id}:userpool/${USER_POOL_ID}"
}

diagnose_eb_logs() {
  log "Reading recent Elastic Beanstalk tail logs for invite errors"
  aws elasticbeanstalk request-environment-info \
    --region "$REGION" \
    --environment-name "$EB_ENV_NAME" \
    --info-type tail >/dev/null || warn "Could not request EB tail logs"
  sleep 15
  log_url="$(aws elasticbeanstalk retrieve-environment-info \
    --region "$REGION" \
    --environment-name "$EB_ENV_NAME" \
    --info-type tail \
    --query 'EnvironmentInfo[0].Message' \
    --output text 2>/dev/null || true)"

  if [[ "$log_url" == http* ]]; then
    curl -fsSL "$log_url" -o /tmp/roodha-eb-tail.txt || warn "Could not download EB tail log"
    grep -Ei "users/invite|Cognito invite|AccessDeniedException|InvalidParameterException|CodeDeliveryFailure|InvalidEmailRoleAccessPolicy|ResourceNotFoundException|AdminCreateUser|AdminAddUserToGroup" /tmp/roodha-eb-tail.txt | tail -80 || true
  else
    warn "No EB tail log URL returned."
  fi
}

find_eb_role() {
  log "Resolving Elastic Beanstalk instance profile role"
  instance_id="$(aws elasticbeanstalk describe-environment-resources \
    --region "$REGION" \
    --environment-name "$EB_ENV_NAME" \
    --query 'EnvironmentResources.Instances[0].Id' \
    --output text)"
  [[ -n "$instance_id" && "$instance_id" != "None" ]] || fail "No EB instance found."

  profile_arn="$(aws ec2 describe-instances \
    --region "$REGION" \
    --instance-ids "$instance_id" \
    --query 'Reservations[0].Instances[0].IamInstanceProfile.Arn' \
    --output text)"
  profile_name="${profile_arn##*/}"
  EB_ROLE_NAME="$(aws iam get-instance-profile \
    --instance-profile-name "$profile_name" \
    --query 'InstanceProfile.Roles[0].RoleName' \
    --output text)"
  [[ -n "$EB_ROLE_NAME" && "$EB_ROLE_NAME" != "None" ]] || fail "Could not resolve EB role from instance profile $profile_name."
  echo "EB instance: $instance_id"
  echo "EB role:     $EB_ROLE_NAME"
}

ensure_groups() {
  log "Ensuring Cognito role groups exist"
  for group in OWNER SUPERVISOR OPERATOR; do
    aws cognito-idp create-group \
      --region "$REGION" \
      --user-pool-id "$USER_POOL_ID" \
      --group-name "$group" >/dev/null 2>&1 || true
  done
}

ensure_custom_attributes() {
  log "Ensuring Cognito custom attributes exist"
  schema_names="$(aws cognito-idp describe-user-pool \
    --region "$REGION" \
    --user-pool-id "$USER_POOL_ID" \
    --query 'UserPool.SchemaAttributes[].Name' \
    --output text)"

  missing=()
  for attr in tenant_id user_role machine_id; do
    if ! grep -qw "$attr" <<<"$schema_names"; then
      missing+=("$attr")
    fi
  done

  if (( ${#missing[@]} == 0 )); then
    echo "All required custom attributes exist."
    return
  fi

  args=()
  for attr in "${missing[@]}"; do
    args+=("Name=$attr,AttributeDataType=String,Mutable=true,Required=false,StringAttributeConstraints={MinLength=1,MaxLength=256}")
  done

  aws cognito-idp add-custom-attributes \
    --region "$REGION" \
    --user-pool-id "$USER_POOL_ID" \
    --custom-attributes "${args[@]}" >/dev/null
  echo "Added custom attributes: ${missing[*]}"
}

configure_cognito_invites() {
  log "Configuring Cognito invite, OTP, and recovery settings"
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

grant_eb_permissions() {
  log "Granting EB role Cognito invite permissions scoped to the user pool"
  cat > /tmp/roodha-cognito-invite-policy.json <<JSON
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
        "cognito-idp:AdminDeleteUser",
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
    --policy-document file:///tmp/roodha-cognito-invite-policy.json >/dev/null
}

verify() {
  log "Verifying repaired Cognito and EB invite state"
  aws elasticbeanstalk describe-environments \
    --region "$REGION" \
    --application-name "$EB_APP_NAME" \
    --environment-names "$EB_ENV_NAME" \
    --query 'Environments[0].{Status:Status,Health:Health,HealthStatus:HealthStatus,VersionLabel:VersionLabel}' \
    --output table

  aws cognito-idp list-groups \
    --region "$REGION" \
    --user-pool-id "$USER_POOL_ID" \
    --query 'Groups[].GroupName' \
    --output table

  aws cognito-idp describe-user-pool \
    --region "$REGION" \
    --user-pool-id "$USER_POOL_ID" \
    --query 'UserPool.{EmailConfiguration:EmailConfiguration,AdminCreateUserConfig:AdminCreateUserConfig,CustomAttributes:SchemaAttributes[?starts_with(Name, `tenant_id`) || starts_with(Name, `user_role`) || starts_with(Name, `machine_id`)].Name}' \
    --output json

  aws iam get-role-policy \
    --role-name "$EB_ROLE_NAME" \
    --policy-name "RoodhaCognitoAdminUserInvites" \
    --query 'PolicyDocument.Statement[0].Action' \
    --output table

  curl -fsS "${BACKEND_URL}/api/ping" | python3 -m json.tool
}

report_ses() {
  log "Reporting SES readiness"
  aws sesv2 get-account \
    --region "$REGION" \
    --query '{ProductionAccessEnabled:ProductionAccessEnabled,SendingEnabled:SendingEnabled,EnforcementStatus:EnforcementStatus}' \
    --output table || warn "SES account status unavailable"
  aws sesv2 list-email-identities \
    --region "$REGION" \
    --query 'EmailIdentities[].{Identity:IdentityName,Type:IdentityType,Verified:VerifiedForSendingStatus}' \
    --output table || warn "SES identity status unavailable"
}

require_identity
diagnose_eb_logs
find_eb_role
ensure_groups
ensure_custom_attributes
configure_cognito_invites
grant_eb_permissions
verify
report_ses

log "Done"
cat <<'EOF'

Next live test:
1. Log in as OWNER.
2. Open Users.
3. Invite a SUPERVISOR without machine assignment.
4. Invite an OPERATOR with a machine selected.

Expected UI result:
Employee invite sent

If invite succeeds but email does not arrive, the remaining blocker is AWS email deliverability:
- verify a real SES sender/domain
- request SES production access
EOF
