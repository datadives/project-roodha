# Project Roodha AWS Infrastructure Map

Last updated: 2026-05-07

This document stores the validated non-secret AWS infrastructure values for Project Roodha.
Do not store live IAM secret keys or database passwords in this file.

## Frontend Environment

```dotenv
VITE_COGNITO_USER_POOL_ID=us-east-1_971juKyUp
VITE_COGNITO_CLIENT_ID=6i2gbi9ttmv034ebau874s4cd0
VITE_COGNITO_USER_POOL_CLIENT_ID=6i2gbi9ttmv034ebau874s4cd0
VITE_AWS_REGION=us-east-1
```

## Backend Environment

```dotenv
COGNITO_USER_POOL_ID=us-east-1_971juKyUp
COGNITO_CLIENT_ID=6i2gbi9ttmv034ebau874s4cd0
COGNITO_APP_CLIENT_ID=6i2gbi9ttmv034ebau874s4cd0
DATABASE_URL=postgresql://postgres:[YOUR_DB_PASSWORD]@roodha-v15-db.c21wwauc86cp.us-east-1.rds.amazonaws.com:5432/postgres
AWS_REGION=us-east-1
```

## AWS Resources

- Cognito User Pool ID: `us-east-1_971juKyUp`
- Active Cognito App Client ID: `6i2gbi9ttmv034ebau874s4cd0`
- AWS Region: `us-east-1`
- RDS endpoint: `roodha-v15-db.c21wwauc86cp.us-east-1.rds.amazonaws.com`
- S3 bucket name: `roodha-build-src-918172959197`
- CloudFront distribution ID: `None` at time of capture

## GitHub Secrets Inventory

Use GitHub repository secrets for all secret material.

```text
AWS_ACCESS_KEY_ID=[SET_IN_GITHUB_SECRETS]
AWS_SECRET_ACCESS_KEY=[SET_IN_GITHUB_SECRETS]
AWS_S3_BUCKET_NAME=roodha-build-src-918172959197
AWS_CLOUDFRONT_DIST_ID=[SET_WHEN_AVAILABLE]
VITE_API_BASE_URL=[SET_IN_GITHUB_SECRETS_IF_REQUIRED]
VITE_COGNITO_USER_POOL_ID=us-east-1_971juKyUp
VITE_COGNITO_CLIENT_ID=6i2gbi9ttmv034ebau874s4cd0
```

## Cognito Operational Notes

- The React app must prefer `VITE_COGNITO_CLIENT_ID`.
- OTP delivery depends on Cognito email configuration and possibly SES verification or sandbox state.
- If a user is stuck in `UNCONFIRMED`, delete that user in Cognito and re-register cleanly.
- If a user is `CONFIRMED`, use login or forgot-password instead of re-registering.
- If `AllowAdminCreateUserOnly` is enabled, self-service registration from the frontend will fail until the user pool configuration is changed.

## Security Notes

- A live AWS secret key was shared during troubleshooting. Rotate that secret in AWS IAM and update GitHub Secrets.
- Never commit IAM secret keys, database passwords, or CloudShell session output containing secrets.
