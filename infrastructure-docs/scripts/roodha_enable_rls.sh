#!/usr/bin/env bash
set -euo pipefail

REGION="${REGION:-ap-south-1}"
EB_ENV_NAME="${EB_ENV_NAME:-Roodha-backend-env}"

log() { echo -e "\n==> $*"; }
fail() { echo "ERROR: $*" >&2; exit 1; }

if ! aws sts get-caller-identity >/dev/null 2>&1; then
  fail "AWS credentials are not available. Restart CloudShell, then run: aws sts get-caller-identity"
fi

if ! command -v psql >/dev/null 2>&1; then
  log "Installing psql client"
  sudo dnf install -y postgresql15 >/dev/null 2>&1 || sudo yum install -y postgresql >/dev/null
fi

log "Reading DATABASE_URL from Elastic Beanstalk without printing the secret"
DATABASE_URL="$(
  aws elasticbeanstalk describe-configuration-settings \
    --region "$REGION" \
    --environment-name "$EB_ENV_NAME" \
    --query "ConfigurationSettings[0].OptionSettings[?Namespace=='aws:elasticbeanstalk:application:environment' && OptionName=='DATABASE_URL'].Value | [0]" \
    --output text
)"

if [[ -z "$DATABASE_URL" || "$DATABASE_URL" == "None" ]]; then
  fail "DATABASE_URL was not found on Elastic Beanstalk environment $EB_ENV_NAME"
fi

PSQL_URL="$(DATABASE_URL="$DATABASE_URL" python3 - <<'PY'
import os
url = os.environ["DATABASE_URL"]
print(url.replace("postgresql+asyncpg://", "postgresql://", 1))
PY
)"

TABLES=(
  tenants
  users
  customers
  parts
  machines
  shifts
  workers
  operations_master
  jobs
  job_operations
  notifications
  audit_logs
  custom_fields
  custom_field_values
  job_cost_summaries
)

log "Enabling and forcing tenant RLS policies"
for table in "${TABLES[@]}"; do
  PGPASSWORD="" psql "$PSQL_URL" -v ON_ERROR_STOP=1 -v table="$table" <<'SQL' >/dev/null
DO $$
DECLARE
  v_table text := :'table';
BEGIN
  IF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = v_table
      AND column_name = 'tenant_id'
  ) THEN
    EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', v_table);
    EXECUTE format('ALTER TABLE public.%I FORCE ROW LEVEL SECURITY', v_table);

    IF NOT EXISTS (
      SELECT 1
      FROM pg_policies
      WHERE schemaname = 'public'
        AND tablename = v_table
        AND policyname = 'tenant_isolation_policy'
    ) THEN
      EXECUTE format(
        'CREATE POLICY tenant_isolation_policy ON public.%I USING (tenant_id = current_setting(''app.current_tenant'', true)) WITH CHECK (tenant_id = current_setting(''app.current_tenant'', true))',
        v_table
      );
    END IF;
  END IF;
END $$;
SQL
done

log "RLS status"
psql "$PSQL_URL" -v ON_ERROR_STOP=1 <<'SQL'
SELECT c.relname AS table_name,
       c.relrowsecurity AS rls_enabled,
       c.relforcerowsecurity AS rls_forced,
       count(p.policyname) AS policies
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
LEFT JOIN pg_policies p ON p.schemaname = n.nspname AND p.tablename = c.relname
WHERE n.nspname = 'public'
  AND c.relkind = 'r'
  AND c.relname IN (
    'tenants','users','customers','parts','machines','shifts','workers',
    'operations_master','jobs','job_operations','notifications','audit_logs',
    'custom_fields','custom_field_values','job_cost_summaries'
  )
GROUP BY c.relname, c.relrowsecurity, c.relforcerowsecurity
ORDER BY c.relname;
SQL

log "Done. Redeploy/restart the backend after this if it was already running."
