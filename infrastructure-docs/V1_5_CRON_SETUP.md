# V1.5 Cron Setup: Proactive Delay Guard

This document describes how to run the V1.5 Delay Guard every night at 11:00 PM so overdue and near-due jobs generate tenant-wide delay notifications.

## Target Endpoint

Trigger this backend route:

```text
POST https://<YOUR-API-URL>/api/system/delay-guard/evaluate
```

The endpoint evaluates jobs for the authenticated tenant and creates `DELAY` notifications for jobs that are overdue or due within 24 hours.

## Schedule

Use AWS EventBridge Scheduler with a daily cron expression.

For 11:00 PM UTC:

```text
cron(0 23 * * ? *)
```

For local India time, set the Scheduler timezone to `Asia/Kolkata` and keep the same wall-clock expression:

```text
cron(0 23 * * ? *)
```

## Recommended Production Pattern: Tiny Lambda Trigger

Use this pattern when the backend requires an Owner token or a secure machine-to-machine credential.

1. Create a Lambda function named `roodha-v15-delay-guard-trigger`.
2. Store the API URL and auth secret in environment variables or AWS Secrets Manager:
   - `ROODHA_API_URL=https://<YOUR-API-URL>`
   - `ROODHA_CRON_API_KEY=<secure-machine-key>` or a short-lived Owner token retrieval secret.
   - `ROODHA_TENANT_ID=<tenant-id>`
3. Configure the Lambda to call:

```http
POST /api/system/delay-guard/evaluate
Authorization: Bearer <Owner JWT or machine token>
X-Tenant-ID: <tenant-id>
Content-Type: application/json
```

4. Create an EventBridge Scheduler schedule:
   - Schedule pattern: `cron(0 23 * * ? *)`
   - Flexible time window: Off
   - Target: the Lambda function
   - Retry policy: 2-3 retries with a dead-letter queue for failures

This keeps credentials out of EventBridge API Destination headers and lets the Lambda refresh a Cognito token or sign a machine-to-machine request safely.

## Alternative: EventBridge API Destination

Use API Destination only if you can provide a stable secure auth header.

1. Open AWS EventBridge > Scheduler > Create schedule.
2. Set schedule pattern to `cron(0 23 * * ? *)`.
3. Choose target type: EventBridge API Destination.
4. Create a Connection with one of these auth strategies:
   - API key header, for example `X-Cron-Api-Key: <secret>`, if the backend supports it.
   - OAuth client credentials, if the backend exposes a machine-to-machine auth flow.
   - Static `Authorization: Bearer <token>` only for short-lived testing, not production.
5. Set the API Destination target:

```text
Method: POST
Endpoint: https://<YOUR-API-URL>/api/system/delay-guard/evaluate
Headers:
  Content-Type: application/json
  X-Tenant-ID: <tenant-id>
```

## Auth Note

The current endpoint is protected by `require_roles(["OWNER"])`, so a normal unsigned EventBridge request will be rejected. For production, prefer one of these:

- Add a dedicated machine-to-machine API key path for `/api/system/delay-guard/evaluate`, stored in AWS Secrets Manager and rotated regularly.
- Use Lambda to obtain a Cognito token for a service account with `OWNER` role before calling the endpoint.
- Use API Gateway IAM authorization for a separate maintenance endpoint that calls `evaluate_tenant_delays(db, tenant_id)` internally.

## Validation

After setup, run the trigger manually once and confirm:

1. The API returns `Delay guard evaluation completed`.
2. The response includes `jobs_evaluated`, `notifications_created`, and `notifications_skipped_existing`.
3. New delay notifications appear in the app notification panel.
4. CloudWatch Logs show no `401`, `403`, or tenant header errors.
