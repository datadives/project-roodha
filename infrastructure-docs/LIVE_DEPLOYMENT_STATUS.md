# Roodha Live Deployment Status

Last updated: 2026-05-16

## Live URLs

- Frontend: http://roodha-v1-live-918172959197.s3-website.ap-south-1.amazonaws.com
- Backend: http://roodha-backend-env.eba-52xsapkh.ap-south-1.elasticbeanstalk.com
- Backend ping: http://roodha-backend-env.eba-52xsapkh.ap-south-1.elasticbeanstalk.com/api/ping
- Backend readiness: http://roodha-backend-env.eba-52xsapkh.ap-south-1.elasticbeanstalk.com/api/ready
- Backend DB check: http://roodha-backend-env.eba-52xsapkh.ap-south-1.elasticbeanstalk.com/api/debug/db-check

## Latest Verified Code

- Branch: `codex/saas-stabilization-live`
- Latest pushed commit: `6085b3a Harden auth routing and role sessions`
- GitHub remote: `origin`

## Local Verification

The latest branch passed local regression before deployment was attempted:

```powershell
cd job_work_planner\task-4-backend-skeleton
$env:PYTHONPATH='.'
pytest -q
# Result: 47 passed

cd ..\task-5-react-frontend
npm test -- --run
# Result: 25 passed

npm run build
# Result: production build passed
```

The build warning about `%VITE_BUILD_ID%` being undefined is non-blocking. It does not stop the frontend bundle from being generated.

## Deployment Blocker

Local AWS deployment from this machine is blocked because all tested local AWS access-key CSV files were rejected by AWS:

```text
InvalidClientTokenId: The security token included in the request is invalid.
```

Checked candidate files under `C:\Users\Dell\Downloads`:

- `roshan_accessKeys production rodhaaa(3).csv` - invalid for `aws sts get-caller-identity`
- `roshan_accessKeys (1).csv` - invalid for `aws sts get-caller-identity`
- `roshan_accessKeys (1) new 29 april.csv` - invalid for `aws sts get-caller-identity`
- `roshan_accessKeys.csv` - invalid for `aws sts get-caller-identity`

The `roshan_credentials*.csv` files contain AWS console username/password fields, not AWS CLI access keys, so they cannot be used directly for `aws elasticbeanstalk` or `aws s3` commands.

No secret values are stored in this repository.

## Required Next Action

Use one of these options before redeploying:

1. Open AWS CloudShell in account `918172959197`, where browser-authenticated AWS credentials are active.
2. Or create a fresh IAM access key with permission for Elastic Beanstalk, S3, CloudFront if used, Cognito verification, and IAM read/update for the EB instance role.

Verify credentials before mutation:

```bash
aws sts get-caller-identity
```

Expected account:

```text
918172959197
```

Do not run deployment commands until this succeeds.

## Backend Deploy Commands

Run from CloudShell or a terminal with valid credentials:

```bash
REGION="ap-south-1"
EB_APP_NAME="roodha-backend"
EB_ENV_NAME="Roodha-backend-env"
VERSION_LABEL="v-auth-stabilized-$(date +%Y%m%d-%H%M%S)"
SOURCE_BUCKET="elasticbeanstalk-ap-south-1-918172959197"

cd job_work_planner/task-4-backend-skeleton
python -m pytest -q

rm -f /tmp/roodha-backend.zip
zip -qr /tmp/roodha-backend.zip app alembic alembic.ini requirements.txt Procfile \
  -x "*.env*" "*/__pycache__/*" "*.pyc" "tests/*" "scripts/*" "*.log" "*.zip"

aws s3 cp /tmp/roodha-backend.zip "s3://${SOURCE_BUCKET}/${VERSION_LABEL}.zip" --region "$REGION"
aws elasticbeanstalk create-application-version \
  --region "$REGION" \
  --application-name "$EB_APP_NAME" \
  --version-label "$VERSION_LABEL" \
  --source-bundle S3Bucket="$SOURCE_BUCKET",S3Key="${VERSION_LABEL}.zip"

aws elasticbeanstalk update-environment \
  --region "$REGION" \
  --application-name "$EB_APP_NAME" \
  --environment-name "$EB_ENV_NAME" \
  --version-label "$VERSION_LABEL"

aws elasticbeanstalk wait environment-updated \
  --region "$REGION" \
  --application-name "$EB_APP_NAME" \
  --environment-names "$EB_ENV_NAME"
```

Verify after backend deploy:

```bash
BACKEND="http://roodha-backend-env.eba-52xsapkh.ap-south-1.elasticbeanstalk.com"
curl -fsS "$BACKEND/api/ping"
curl -fsS "$BACKEND/api/ready"
curl -fsS "$BACKEND/api/debug/db-check"
```

## Frontend Deploy Commands

Run from CloudShell or a terminal with valid credentials:

```bash
REGION="ap-south-1"
FRONTEND_BUCKET="roodha-v1-live-918172959197"

cd job_work_planner/task-5-react-frontend
npm ci
npm test -- --run
npm run build

aws s3 sync dist/ "s3://${FRONTEND_BUCKET}" --delete --region "$REGION"
```

If CloudFront is added later, invalidate `/*` after the S3 sync.

## Post-Deploy Product Smoke

1. Open the frontend live URL.
2. Log in as Owner and verify dashboard loads.
3. Invite Supervisor and Operator.
4. Invited users must use the temporary password flow and set a new password inline.
5. Confirm Supervisor can create a job and run Auto Plan.
6. Confirm Operator lands on `/operator` and sees Work-to-Do only.
7. Confirm Dashboard, Analytics, Notifications, and CSV exports still work.
