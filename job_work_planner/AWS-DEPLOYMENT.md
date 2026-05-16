# Roodha AWS Production Runbook

This runbook keeps the Roodha V1 manufacturing planner repeatable on AWS: Cognito auth, Elastic Beanstalk API, RDS PostgreSQL, SES email readiness, and frontend/backend environment alignment.

## 1. CloudShell First Aid

Before running any AWS repair command:

```bash
export AWS_REGION=ap-south-1
export AWS_DEFAULT_REGION=ap-south-1
aws sts get-caller-identity
```

If this fails with `NoCredentials` or container metadata errors, restart CloudShell from the AWS console. Do not run mutating scripts until identity succeeds.

## 2. Safe AWS Scripts

From the repository root, upload or paste these scripts into CloudShell:

```bash
infrastructure-docs/scripts/roodha_aws_verify.sh
infrastructure-docs/scripts/roodha_aws_repair.sh
```

Use verification first:

```bash
chmod +x roodha_aws_verify.sh roodha_aws_repair.sh
./roodha_aws_verify.sh
```

Run repair only after verification confirms CloudShell identity:

```bash
./roodha_aws_repair.sh
./roodha_aws_verify.sh
```

The repair script is idempotent and non-destructive. It does not drop RDS data.

## 3. Required AWS Resources

Current production target:

```text
Region: ap-south-1
Account: 918172959197
Backend EB app: roodha-backend
Backend EB env: Roodha-backend-env
Backend URL: http://roodha-backend-env.eba-52xsapkh.ap-south-1.elasticbeanstalk.com
Cognito user pool: ap-south-1_U3JeTevgw
Cognito app client: 3ab798pg0k2p8hp7v6bbtlh4mj
RDS instance: roodha-v1-postgres
RDS database: roodha_db
EB instance role: AWSElasticBeanstalkWebTier
```

## 4. Backend Environment

Set these in Elastic Beanstalk environment properties:

```text
DATABASE_URL=postgresql+asyncpg://postgres:<password>@roodha-v1-postgres.c3kkegyu4x8q.ap-south-1.rds.amazonaws.com:5432/roodha_db
AWS_REGION=ap-south-1
COGNITO_REGION=ap-south-1
COGNITO_USER_POOL_ID=ap-south-1_U3JeTevgw
COGNITO_APP_CLIENT_ID=3ab798pg0k2p8hp7v6bbtlh4mj
ALLOWED_ORIGINS=*
ENV=production
ALLOW_DEV_PASS=false
ENABLE_DEMO_API_STUBS=false
```

For local-only demo testing, use `ENV=local` and `ALLOW_DEV_PASS=true`. Never use that pair for a production client demo unless the demo is explicitly isolated.

## 5. Frontend Environment

Set frontend Vite variables:

```text
VITE_API_BASE_URL=http://roodha-backend-env.eba-52xsapkh.ap-south-1.elasticbeanstalk.com/api
VITE_COGNITO_REGION=ap-south-1
VITE_COGNITO_USER_POOL_ID=ap-south-1_U3JeTevgw
VITE_COGNITO_CLIENT_ID=3ab798pg0k2p8hp7v6bbtlh4mj
VITE_ENABLE_SELF_SIGNUP=true
VITE_ALLOW_DEV_PASS=false
```

Local development may use `VITE_ALLOW_DEV_PASS=true`; production builds should not.

## 6. Cognito and Role Model

Roodha uses three Cognito groups:

- `OWNER`: tenant setup, users, master data, jobs, costing, analytics, exports.
- `SUPERVISOR`: planning, job review, kanban, assigned factory execution.
- `OPERATOR`: assigned operations only; can view and update work progress.

Public signup creates a tenant owner. Supervisor and operator accounts should be created through the Owner invite console.

## 7. OTP and SES Reality

Cognito default email is the fastest working OTP path for testing. Production email delivery requires:

1. Verify a real SES sender email or domain.
2. Add SES domain DKIM DNS records if using a domain.
3. Request SES production access for transactional email.
4. Only after approval, switch Cognito to SES `DEVELOPER` email mode.

Until SES is verified and out of sandbox, OTP to arbitrary customer emails may be unreliable or blocked by AWS.

## 8. RDS and Migrations

Production uses RDS PostgreSQL. Verify connectivity:

```bash
curl -fsS http://roodha-backend-env.eba-52xsapkh.ap-south-1.elasticbeanstalk.com/api/debug/db-check | python3 -m json.tool
```

Expected core tables:

```text
tenants users customers parts machines shifts workers operations_master jobs job_operations notifications
```

Do not drop data during repair. Use Alembic migrations for schema changes. Metadata-based table creation is acceptable only for initial empty V1 recovery.

## 9. Deployment Verification

Backend:

```bash
curl -i http://roodha-backend-env.eba-52xsapkh.ap-south-1.elasticbeanstalk.com/api/ping
curl -i http://roodha-backend-env.eba-52xsapkh.ap-south-1.elasticbeanstalk.com/api/ready
curl -i http://roodha-backend-env.eba-52xsapkh.ap-south-1.elasticbeanstalk.com/api/debug/db-check
```

Frontend:

```bash
npm test -- --run src/pages/LoginPage.test.js src/lib/auth.test.js src/config.test.js
npm run build
```

Backend:

```bash
pytest -q
```

## 10. Client Demo Checklist

- Owner signs up or logs in.
- Owner provisions workspace.
- Owner creates customer, part, machine, shift, worker.
- Owner invites supervisor and operator.
- Supervisor creates/reviews job.
- Operator starts/completes assigned operation.
- Dashboard and kanban update.
- Analytics WIP/costing update.
- Jobs CSV and machine-load CSV export.

## 11. Rollback

If a deployment regresses:

1. Revert only the latest EB application version.
2. Restore previous EB environment variables from the AWS console change history or exported config.
3. Run `roodha_aws_verify.sh`.
4. Re-test `/api/ping`, `/api/debug/db-check`, login, job creation, analytics, and exports.
