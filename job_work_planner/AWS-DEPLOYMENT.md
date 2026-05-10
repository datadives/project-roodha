# AWS Deployment Guide — Job Work Planner

## Overview
This guide explains how to deploy the Job Work Planner project to AWS using CodeBuild, Docker, and best practices.

## Structure
- `buildspec.yml` — AWS CodeBuild build instructions (in backend folder)
- `Dockerfile` — Docker image definition (in backend folder)
- `requirements.txt` — Python dependencies
- Frontend build handled by Vite (see frontend README)

## Backend Deployment (API)
1. **Build Docker Image**
   - Use the provided `Dockerfile` in `task-4-backend-skeleton/`.
2. **AWS CodeBuild**
   - Uses `buildspec.yml` for build and deployment steps.
   - Make sure environment variables are set in AWS (do not commit secrets).
3. **Database**
   - Use RDS or another managed database service.
   - Run Alembic migrations as part of deployment.

## Frontend Deployment
1. **Build**
   - Run `npm run build` in `task-5-react-frontend/`.
2. **Host**
   - Deploy the `dist/` folder to S3 (for static hosting) or use Amplify.

## Best Practices
- Never commit `.env` or secrets.
- Use IAM roles and least privilege.
- Monitor logs and set up alerts.

---

For more details, see the backend and frontend `README.md` files.
