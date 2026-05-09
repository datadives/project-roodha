# =============================================================================
# deploy_aws_rds.ps1
# Project Roodha v1.5 - AWS RDS PostgreSQL 15 Provisioner
# Provisions: Security Group (port 5432 / local IP) + RDS db.t3.micro instance
# =============================================================================

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# -----------------------------------------------------------------------------
# STEP 0: Configuration
# -----------------------------------------------------------------------------
$AWS_REGION      = "ap-south-1"
$DB_INSTANCE_ID  = "roodha-v15-db"
$DB_NAME         = "roodha"
$DB_USERNAME     = "postgres"
$DB_PORT         = 5432
$DB_ENGINE       = "postgres"
$DB_ENGINE_VER   = "15.7"
$DB_INSTANCE_CLS = "db.t3.micro"
$DB_STORAGE_GB   = 20
$SG_NAME         = "roodha-db-sg"
$SG_DESC         = "Project Roodha v1.5 - RDS PostgreSQL access (Alembic migrations)"

# Simplified charset to avoid potential encoding/parser issues in some environments
$CHARSET  = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
$DB_PASS  = -join (1..24 | ForEach-Object { $CHARSET[(Get-Random -Maximum $CHARSET.Length)] })

Write-Host ""
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host " Project Roodha v1.5 - RDS Provisioner     " -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "DB Instance ID : $DB_INSTANCE_ID"
Write-Host "DB Name        : $DB_NAME"
Write-Host "Instance Class : $DB_INSTANCE_CLS (Free Tier)"
Write-Host "Engine         : PostgreSQL $DB_ENGINE_VER"
Write-Host "Region         : $AWS_REGION"
Write-Host ""

# -----------------------------------------------------------------------------
# STEP 1: Resolve the caller's current public IP address
# -----------------------------------------------------------------------------
Write-Host "[1/6] Resolving your public IP address..." -ForegroundColor Yellow

$MY_IP = (Invoke-RestMethod -Uri "https://checkip.amazonaws.com").Trim()
$MY_CIDR = "$MY_IP/32"

Write-Host "      Your IP: $MY_CIDR" -ForegroundColor Green

# -----------------------------------------------------------------------------
# STEP 2: Resolve the default VPC ID for this region
# -----------------------------------------------------------------------------
Write-Host "[2/6] Resolving default VPC ID..." -ForegroundColor Yellow

$VPC_ID = aws ec2 describe-vpcs `
    --region $AWS_REGION `
    --filters "Name=isDefault,Values=true" `
    --query "Vpcs[0].VpcId" `
    --output text

if ($VPC_ID -eq "None" -or [string]::IsNullOrWhiteSpace($VPC_ID)) {
    Write-Error "No default VPC found in region $AWS_REGION."
}

Write-Host "      Default VPC: $VPC_ID" -ForegroundColor Green

# -----------------------------------------------------------------------------
# STEP 3: Create the Security Group for RDS
# -----------------------------------------------------------------------------
Write-Host "[3/6] Creating Security Group: $SG_NAME ..." -ForegroundColor Yellow

$EXISTING_SG = aws ec2 describe-security-groups `
    --region $AWS_REGION `
    --filters "Name=group-name,Values=$SG_NAME" "Name=vpc-id,Values=$VPC_ID" `
    --query "SecurityGroups[0].GroupId" `
    --output text

if ($EXISTING_SG -ne "None" -and -not [string]::IsNullOrWhiteSpace($EXISTING_SG)) {
    Write-Host "      Security Group already exists. Reusing: $EXISTING_SG" -ForegroundColor DarkYellow
    $SG_ID = $EXISTING_SG
} else {
    $SG_ID = aws ec2 create-security-group `
        --region $AWS_REGION `
        --group-name $SG_NAME `
        --description $SG_DESC `
        --vpc-id $VPC_ID `
        --query "GroupId" `
        --output text

    Write-Host "      Security Group created. ID: $SG_ID" -ForegroundColor Green

    aws ec2 authorize-security-group-ingress `
        --region $AWS_REGION `
        --group-id $SG_ID `
        --protocol tcp `
        --port $DB_PORT `
        --cidr $MY_CIDR | Out-Null

    Write-Host "      Inbound rule: TCP $DB_PORT from $MY_CIDR - added." -ForegroundColor Green
}

# -----------------------------------------------------------------------------
# STEP 4: Create the RDS PostgreSQL 15 instance
# -----------------------------------------------------------------------------
Write-Host "[4/6] Provisioning RDS instance: $DB_INSTANCE_ID ..." -ForegroundColor Yellow
Write-Host "      (This command returns immediately; creation takes 5-10 min)" -ForegroundColor DarkGray

aws rds create-db-instance `
    --region $AWS_REGION `
    --db-instance-identifier $DB_INSTANCE_ID `
    --db-instance-class $DB_INSTANCE_CLS `
    --engine $DB_ENGINE `
    --engine-version $DB_ENGINE_VER `
    --master-username $DB_USERNAME `
    --master-user-password $DB_PASS `
    --db-name $DB_NAME `
    --allocated-storage $DB_STORAGE_GB `
    --storage-type gp2 `
    --vpc-security-group-ids $SG_ID `
    --publicly-accessible `
    --no-multi-az `
    --no-storage-encrypted `
    --backup-retention-period 7 `
    --no-deletion-protection `
    --no-auto-minor-version-upgrade `
    --port $DB_PORT | Out-Null

Write-Host "      RDS creation request accepted." -ForegroundColor Green

# -----------------------------------------------------------------------------
# STEP 5: Print credentials
# -----------------------------------------------------------------------------
Write-Host ""
Write-Host "=============================================" -ForegroundColor Magenta
Write-Host " SAVE THESE CREDENTIALS NOW" -ForegroundColor Magenta
Write-Host "=============================================" -ForegroundColor Magenta
Write-Host "DB Instance ID : $DB_INSTANCE_ID"            -ForegroundColor White
Write-Host "DB Name        : $DB_NAME"                   -ForegroundColor White
Write-Host "Master Username: $DB_USERNAME"               -ForegroundColor White
Write-Host "Master Password: $DB_PASS"                   -ForegroundColor Yellow
Write-Host "Port           : $DB_PORT"                   -ForegroundColor White
Write-Host "=============================================" -ForegroundColor Magenta
Write-Host ""

# -----------------------------------------------------------------------------
# STEP 6: Wait for DB availability
# -----------------------------------------------------------------------------
Write-Host "[5/6] Waiting for RDS instance to become available..." -ForegroundColor Yellow
Write-Host "      Polling every 30s. Go get a coffee." -ForegroundColor DarkGray

aws rds wait db-instance-available `
    --region $AWS_REGION `
    --db-instance-identifier $DB_INSTANCE_ID

Write-Host "      RDS instance is AVAILABLE." -ForegroundColor Green

# -----------------------------------------------------------------------------
# STEP 7: Retrieve endpoint
# -----------------------------------------------------------------------------
Write-Host "[6/6] Retrieving database endpoint..." -ForegroundColor Yellow

$DB_ENDPOINT = aws rds describe-db-instances `
    --region $AWS_REGION `
    --db-instance-identifier $DB_INSTANCE_ID `
    --query "DBInstances[0].Endpoint.Address" `
    --output text

# -----------------------------------------------------------------------------
# OUTPUT
# -----------------------------------------------------------------------------
Write-Host ""
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host " RDS Instance Provisioned Successfully      " -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "DB Endpoint    : $DB_ENDPOINT"               -ForegroundColor Green
Write-Host "Port           : $DB_PORT"                   -ForegroundColor White
Write-Host "Database       : $DB_NAME"                   -ForegroundColor White
Write-Host "Username       : $DB_USERNAME"               -ForegroundColor White
Write-Host "Security Group : $SG_ID (allows $MY_CIDR)"  -ForegroundColor White
Write-Host ""
Write-Host "--- Copy the following into your backend .env file ---" -ForegroundColor Yellow
Write-Host ""
Write-Host "DATABASE_URL=postgresql://${DB_USERNAME}:${DB_PASS}@${DB_ENDPOINT}:${DB_PORT}/${DB_NAME}" -ForegroundColor Green
Write-Host ""
Write-Host "--- Next Steps ---" -ForegroundColor Yellow
Write-Host "  1. Run migrations : alembic upgrade head" -ForegroundColor White
Write-Host "  2. Security       : Revoke SG rule after use" -ForegroundColor Red
Write-Host ""
