#!/usr/bin/env bash
set -euo pipefail

REGION="${REGION:-ap-south-1}"
RULE_NAME="${RULE_NAME:-roodha-v15-nightly-maintenance}"
BACKEND_URL="${BACKEND_URL:-http://roodha-backend-env.eba-52xsapkh.ap-south-1.elasticbeanstalk.com}"
MAINTENANCE_SECRET="${MAINTENANCE_SECRET:-}"

if [[ -z "$MAINTENANCE_SECRET" ]]; then
  echo "Set MAINTENANCE_SECRET before running this script."
  exit 1
fi

aws sts get-caller-identity --region "$REGION" >/dev/null

echo "Creating EventBridge rule: $RULE_NAME"
aws events put-rule \
  --region "$REGION" \
  --name "$RULE_NAME" \
  --schedule-expression "cron(30 18 * * ? *)" \
  --state ENABLED \
  --description "Runs Roodha V1.5 nightly delay and overload checks" >/dev/null

echo
echo "Rule created. Add a target that calls:"
echo "POST ${BACKEND_URL%/}/api/maintenance/v15-nightly"
echo
echo "For a production setup, use EventBridge API Destination or a tiny Lambda target"
echo "that sends x-roodha-maintenance-secret from Secrets Manager."
