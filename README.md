# Roodha Manufacturing Job Planner

Roodha is a multi-tenant SaaS manufacturing job planner for job-work factories. It supports factory owners, supervisors, and operators through job intake, master data, planning, work execution, analytics, notifications, and CSV exports.

## Live Links

- Frontend: http://roodha-v1-live-918172959197.s3-website.ap-south-1.amazonaws.com
- Backend: http://roodha-backend-env.eba-52xsapkh.ap-south-1.elasticbeanstalk.com
- Backend ping: http://roodha-backend-env.eba-52xsapkh.ap-south-1.elasticbeanstalk.com/api/ping
- Backend readiness: http://roodha-backend-env.eba-52xsapkh.ap-south-1.elasticbeanstalk.com/api/ready

Current deployment status and credential blockers are tracked in
`infrastructure-docs/LIVE_DEPLOYMENT_STATUS.md`.

## Repository Structure

- `job_work_planner/task-4-backend-skeleton/` - FastAPI backend, SQLAlchemy models, Alembic migrations, RDS integration, Cognito auth, and backend tests.
- `job_work_planner/task-5-react-frontend/` - React/Vite frontend, role-based UI, dashboard, planning, worklist, settings, and frontend tests.
- `infrastructure-docs/` - AWS runbooks, verification scripts, EventBridge setup, RDS/Cognito/EB notes, and live E2E smoke tooling.
- `ROODHA_DEMO_RUNBOOK.md` - demo script and fallback talking points for manager/client review.

## V1.5 Feature Summary

- Capacity-based Auto Scheduler with preview and bulk apply.
- Work-to-List queues by machine or worker.
- In-app notifications with unread count.
- CSV exports for jobs, machine load, WIP, costing, and delivery reports.
- Custom fields and job tags.
- Inbound integration webhook groundwork.
- Owner, Supervisor, and Operator role-based access control.
- Tenant-scoped backend queries and security regression tests.

## Local Backend

```powershell
cd job_work_planner\task-4-backend-skeleton
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:PYTHONPATH='.'
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Required local environment values are documented in `job_work_planner/task-4-backend-skeleton/README.md`. Do not commit `.env` files.

## Local Frontend

```powershell
cd job_work_planner\task-5-react-frontend
npm install
npm run dev
```

Required Vite environment values are documented in `job_work_planner/task-5-react-frontend/README.md`. Do not commit `.env.local`.

## Verification

Backend:

```powershell
cd job_work_planner\task-4-backend-skeleton
$env:PYTHONPATH='.'
pytest -q
Remove-Item Env:\PYTHONPATH
```

Frontend:

```powershell
cd job_work_planner\task-5-react-frontend
npm test -- --run
npm run build
```

## Manager Review Checklist

- Owner can log in, create master data, invite users, view analytics, and export CSV.
- Supervisor can create jobs, run Auto Plan, review the planning preview, and manage work execution.
- Operator sees only assigned work and can start/complete operations with quantities.
- Analytics updates after jobs and operations exist.
- Notification bell shows unread alerts and updates after marking read.
- CSV export downloads successfully.
- Restricted routes return access denied for unsupported roles.

## Deployment Notes

- Backend runs on Elastic Beanstalk and connects to AWS RDS PostgreSQL.
- Frontend is hosted from S3 website hosting.
- Cognito manages signup, login, recovery, and role groups.
- SES production readiness is still an AWS account/email deliverability item; in-app notifications do not depend on SES inbox delivery.
- Detailed deployment and verification steps are in `infrastructure-docs/ROODHA_V15_RUNBOOK.md`.
- If local AWS access-key CSV credentials fail with `InvalidClientTokenId`, deploy from AWS CloudShell or generate a fresh IAM access key before running any EB/S3 mutation commands.
