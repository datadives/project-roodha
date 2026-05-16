# Roodha V1.5 Deployment Runbook

This runbook deploys the V1.5 planning automation, worklist, notifications, exports, custom fields, and integration hook changes on the existing Elastic Beanstalk + RDS stack.

Before deployment, confirm the active AWS credentials are valid:

```bash
aws sts get-caller-identity
```

If this returns `InvalidClientTokenId`, the local access key is invalid or disabled. Use AWS CloudShell or generate a fresh IAM access key. Current local credential status is documented in `LIVE_DEPLOYMENT_STATUS.md`.

## 1. Backend Database Migration

Run from the backend bundle or an environment that can reach RDS:

```bash
cd job_work_planner/task-4-backend-skeleton
python -m alembic upgrade head
```

The V1.5 migration is non-destructive. It adds planning and notification fields plus `events` and `integration_webhooks`.

## 2. Required Backend Environment Variables

Keep existing production values and add these if missing:

```bash
MAINTENANCE_SECRET="use-a-long-random-value"
INTEGRATION_WEBHOOK_TOKEN="use-a-different-long-random-value"
EXPORTS_S3_BUCKET="optional-s3-bucket-for-csv-exports"
EXPORT_PRESIGN_TTL_SECONDS="300"
```

If `EXPORTS_S3_BUCKET` is not configured, exports still return a CSV data URL so demos do not fail.

## 3. Nightly V1.5 Maintenance

The nightly task scans for:

- overdue jobs
- overloaded machines over 10 planned hours

It writes in-app notifications and events. Trigger endpoint:

```bash
curl -X POST "$BACKEND/api/maintenance/v15-nightly" \
  -H "x-roodha-maintenance-secret: $MAINTENANCE_SECRET"
```

## 4. Frontend Routes Added

- `/planning` for Owner/Supervisor auto-plan preview and apply
- `/worklist` for shopfloor queue management
- `/settings` for Owner custom fields

## 5. Smoke Test

```bash
curl "$BACKEND/api/ping"
curl "$BACKEND/api/ready"
curl "$BACKEND/api/debug/db-check"
```

Then in the app:

1. Create customer, machine, part, shift, worker.
2. Create a high-priority job.
3. Open Planning and run Preview.
4. Apply selected rows.
5. Open Work and start/complete the first operation.
6. Open Analytics and export Jobs, Machine Load, WIP, Costing, and Delivery reports.
