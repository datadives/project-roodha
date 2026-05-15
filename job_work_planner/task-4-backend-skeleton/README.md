# Roodha Backend

FastAPI backend for the Roodha multi-tenant manufacturing job planner.

## Local Setup

```powershell
cd job_work_planner\task-4-backend-skeleton
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Required `.env` values:

```text
ENV=local
DATABASE_URL=postgresql+asyncpg://postgres:<password>@<host>:5432/roodha_db
AWS_REGION=ap-south-1
COGNITO_REGION=ap-south-1
COGNITO_USER_POOL_ID=ap-south-1_U3JeTevgw
COGNITO_APP_CLIENT_ID=3ab798pg0k2p8hp7v6bbtlh4mj
ALLOW_DEV_PASS=true
DEV_PASS_TOKEN=roodha-dev-test-123
DEV_TENANT_ID=lalafactory
```

For production, use `ENV=production`, `ALLOW_DEV_PASS=false`, and store secrets in Elastic Beanstalk environment configuration.

## Health Checks

```bash
curl /api/ping
curl /api/ready
curl /api/debug/db-check
```

`/api/debug/db-check` verifies the configured host, database, schema, table presence, and SQLAlchemy pool pre-ping.

## Role Model

- `OWNER`: tenant, users, master data, jobs, analytics, costing, exports.
- `SUPERVISOR`: planning, kanban, job review, operation assignment.
- `OPERATOR`: assigned operation visibility and progress updates.

Supervisor and operator users are created through `/api/users/invite`; the route writes Cognito attributes/groups and mirrors the user in PostgreSQL.

## CSV Export

Jobs and machine-load exports return a downloadable URL. If `S3_BUCKET_NAME` is unset, the backend returns a `data:text/csv` URL so local/client demos continue to work. For production at larger scale, configure S3 and replace this with pre-signed object URLs.

## Tests

```powershell
$env:PYTHONPATH='.'
pytest -q
Remove-Item Env:\PYTHONPATH
```

Minimum client-ready checks:

- DB connection and table readiness.
- Cognito token parsing and runtime guard tests.
- `/api/users/me` role preservation.
- Job create -> kanban -> metrics -> analytics flow.
- Owner/Supervisor/Operator access restrictions.
