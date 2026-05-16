# Roodha Job Work Planner

This folder contains the deployable Roodha application:

- `task-4-backend-skeleton/` - FastAPI backend, Alembic migrations, RDS data model, Cognito auth, V1.5 planning/notification/export APIs, and pytest coverage.
- `task-5-react-frontend/` - React/Vite frontend for Owner, Supervisor, and Operator workflows.
- `AWS-DEPLOYMENT.md` - AWS deployment guide for the current Elastic Beanstalk/S3/RDS stack.
- `setup_local_dev.py` - local setup helper.

## Live System

- Frontend: http://roodha-v1-live-918172959197.s3-website.ap-south-1.amazonaws.com
- Backend: http://roodha-backend-env.eba-52xsapkh.ap-south-1.elasticbeanstalk.com
- Health: http://roodha-backend-env.eba-52xsapkh.ap-south-1.elasticbeanstalk.com/api/ping

## Local Start

Backend:

```powershell
cd task-4-backend-skeleton
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:PYTHONPATH='.'
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Frontend:

```powershell
cd task-5-react-frontend
npm install
npm run dev
```

## Verification

```powershell
cd task-4-backend-skeleton
$env:PYTHONPATH='.'
pytest -q
Remove-Item Env:\PYTHONPATH

cd ..\task-5-react-frontend
npm test -- --run
npm run build
```

Do not commit `.env`, `.env.local`, AWS credential CSV files, `node_modules`, `dist`, caches, logs, or EB bundles.
