# =============================================================================
# deploy_aws_cognito.ps1
# Project Roodha v1.5 - AWS Cognito Production Auth Layer Provisioner
# Provisions: User Pool + Custom Attributes + React SPA App Client
# =============================================================================

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# -----------------------------------------------------------------------------
# STEP 0: Configuration — adjust region if needed
# -----------------------------------------------------------------------------
$AWS_REGION     = "ap-south-1"
$POOL_NAME      = "RoodhaProductionPool"
$APP_CLIENT_NAME = "RoodhaReactFrontend"

Write-Host ""
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host " Project Roodha v1.5 — Cognito Provisioner " -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "User Pool Name : $POOL_NAME"
Write-Host "App Client     : $APP_CLIENT_NAME"
Write-Host "Region         : $AWS_REGION"
Write-Host ""

# -----------------------------------------------------------------------------
# STEP 1: Create the Cognito User Pool
# - PasswordPolicy: enforces strong passwords for production
# - AliasAttributes: allows users to sign in with their email address
# - AutoVerifiedAttributes: Cognito auto-sends email verification codes
# - MfaConfiguration: OFF — can be enabled later without schema changes
# -----------------------------------------------------------------------------
Write-Host "[1/3] Creating Cognito User Pool: $POOL_NAME ..." -ForegroundColor Yellow

$POOL_RESULT = aws cognito-idp create-user-pool `
    --pool-name $POOL_NAME `
    --region $AWS_REGION `
    --policies '{
        "PasswordPolicy": {
            "MinimumLength": 8,
            "RequireUppercase": true,
            "RequireLowercase": true,
            "RequireNumbers": true,
            "RequireSymbols": false,
            "TemporaryPasswordValidityDays": 7
        }
    }' `
    --alias-attributes "email" `
    --auto-verified-attributes "email" `
    --mfa-configuration "OFF" `
    --email-configuration '{
        "EmailSendingAccount": "COGNITO_DEFAULT"
    }' `
    --admin-create-user-config '{
        "AllowAdminCreateUserOnly": false
    }' `
    --schema '[
        {
            "Name": "email",
            "AttributeDataType": "String",
            "Required": true,
            "Mutable": true
        }
    ]' `
    | ConvertFrom-Json

$USER_POOL_ID = $POOL_RESULT.UserPool.Id
Write-Host "      User Pool created. ID: $USER_POOL_ID" -ForegroundColor Green

# -----------------------------------------------------------------------------
# STEP 2: Add custom attributes matching the V1.0 schema
#
# custom:tenant_id — isolates each factory/business tenant's data
# custom:role      — drives RBAC; valid values: "Owner" | "Supervisor"
#
# IMPORTANT:
# - Cognito custom attributes are IMMUTABLE by definition once created on
#   the pool schema. The Mutable flag here refers to whether a user's
#   VALUE for the attribute can be changed post-sign-up (set to true).
# - AttributeDataType must be "String" for both.
# - MinLength/MaxLength enforce data integrity at the Cognito layer.
# -----------------------------------------------------------------------------
Write-Host "[2/3] Adding custom schema attributes (tenant_id, role)..." -ForegroundColor Yellow

aws cognito-idp add-custom-attributes `
    --user-pool-id $USER_POOL_ID `
    --region $AWS_REGION `
    --custom-attributes '[
        {
            "Name": "tenant_id",
            "AttributeDataType": "String",
            "Mutable": true,
            "StringAttributeConstraints": {
                "MinLength": "1",
                "MaxLength": "128"
            }
        },
        {
            "Name": "role",
            "AttributeDataType": "String",
            "Mutable": true,
            "StringAttributeConstraints": {
                "MinLength": "1",
                "MaxLength": "64"
            }
        }
    ]' | Out-Null

Write-Host "      custom:tenant_id — added." -ForegroundColor Green
Write-Host "      custom:role      — added. (valid values: Owner | Supervisor)" -ForegroundColor Green

# -----------------------------------------------------------------------------
# STEP 3: Create the React SPA App Client
#
# - GenerateSecret: false — MANDATORY for browser-based SPAs. A client
#   secret cannot be safely stored in a React app (it would be exposed
#   in the browser bundle).
# - ExplicitAuthFlows:
#     ALLOW_USER_PASSWORD_AUTH   — standard username/password sign-in
#     ALLOW_REFRESH_TOKEN_AUTH   — enables silent token refresh (session)
#     ALLOW_USER_SRP_AUTH        — Secure Remote Password; recommended
#                                  for production (passwords never sent
#                                  in plaintext over the wire)
# - ReadAttributes / WriteAttributes: explicitly grants the client
#   permission to read and write custom:tenant_id and custom:role.
#   Without this, Cognito will silently ignore writes to custom attrs.
# -----------------------------------------------------------------------------
Write-Host "[3/3] Creating App Client: $APP_CLIENT_NAME ..." -ForegroundColor Yellow

$CLIENT_RESULT = aws cognito-idp create-user-pool-client `
    --user-pool-id $USER_POOL_ID `
    --region $AWS_REGION `
    --client-name $APP_CLIENT_NAME `
    --no-generate-secret `
    --explicit-auth-flows `
        "ALLOW_USER_PASSWORD_AUTH" `
        "ALLOW_REFRESH_TOKEN_AUTH" `
        "ALLOW_USER_SRP_AUTH" `
    --read-attributes `
        "email" `
        "email_verified" `
        "custom:tenant_id" `
        "custom:role" `
    --write-attributes `
        "email" `
        "custom:tenant_id" `
        "custom:role" `
    --token-validity-units '{
        "AccessToken":  "hours",
        "IdToken":      "hours",
        "RefreshToken": "days"
    }' `
    --access-token-validity  1 `
    --id-token-validity      1 `
    --refresh-token-validity 30 `
    --prevent-user-existence-errors "ENABLED" `
    | ConvertFrom-Json

$CLIENT_ID = $CLIENT_RESULT.UserPoolClient.ClientId
Write-Host "      App Client created. ID: $CLIENT_ID" -ForegroundColor Green

# -----------------------------------------------------------------------------
# OUTPUT: Print all values needed for the React .env file
# -----------------------------------------------------------------------------
Write-Host ""
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host " Cognito Infrastructure Provisioned" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "User Pool ID   : $USER_POOL_ID" -ForegroundColor White
Write-Host "App Client ID  : $CLIENT_ID" -ForegroundColor White
Write-Host "Region         : $AWS_REGION" -ForegroundColor White
Write-Host ""
Write-Host "--- Copy the following into your .env file ---" -ForegroundColor Yellow
Write-Host ""
Write-Host "VITE_AWS_REGION=$AWS_REGION"                          -ForegroundColor Green
Write-Host "VITE_COGNITO_USER_POOL_ID=$USER_POOL_ID"             -ForegroundColor Green
Write-Host "VITE_COGNITO_CLIENT_ID=$CLIENT_ID"                   -ForegroundColor Green
Write-Host ""
Write-Host "--- Custom Attributes (reference) ---" -ForegroundColor Yellow
Write-Host "  custom:tenant_id  — set at user creation, used for multi-tenant isolation" -ForegroundColor White
Write-Host "  custom:role       — Owner | Supervisor, drives RBAC in FastAPI backend"    -ForegroundColor White
Write-Host ""
