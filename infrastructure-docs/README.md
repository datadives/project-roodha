# Roodha Infrastructure Docs

This folder contains non-secret AWS documentation and operational scripts for the Roodha V1.5 deployment.

## Main Documents

- `ROODHA_V15_RUNBOOK.md` - production runbook for backend, frontend, RDS, Cognito, SES readiness, deployment, verification, and rollback.
- `LIVE_DEPLOYMENT_STATUS.md` - current live URLs, latest verified commit, local credential status, and next deploy action.
- `aws-infrastructure-map.md` - current non-secret AWS topology and app wiring.
- `V1_5_CRON_SETUP.md` - scheduled maintenance/EventBridge notes.

## Scripts

- `scripts/roodha_aws_verify.sh` - read-only AWS verification.
- `scripts/roodha_aws_repair.sh` - guarded AWS repair for Cognito, groups, EB permissions, and readiness.
- `scripts/roodha_v15_eventbridge_setup.sh` - EventBridge trigger setup for protected maintenance endpoint.
- `scripts/roodha_v15_live_e2e_smoke.py` - live smoke runner for V1.5 flows.
- `scripts/roodha_enable_rls.sh` - RLS setup helper.
- `cloudshell-cognito-repair.sh` and `cloudshell-aws-cleanup-and-db-fix.sh` - older CloudShell helpers retained for historical recovery scenarios.

## Safety Rules

- Do not commit AWS access-key CSV files, `.env` files, generated EB bundles, or command output containing secrets.
- Prefer `roodha_aws_verify.sh` before any repair script.
- SES production access and verified sender/domain setup are AWS account readiness items; do not claim email delivery is fully production-ready until AWS confirms them.
