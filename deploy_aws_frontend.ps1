# =============================================================================
# deploy_aws_frontend.ps1
# Project Roodha v1.5 - AWS Static Frontend Infrastructure Provisioner
# Provisions: S3 (private) + CloudFront OAC Distribution
# =============================================================================

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# -----------------------------------------------------------------------------
# STEP 0: Generate a random suffix and define resource names
# -----------------------------------------------------------------------------
$RANDOM_SUFFIX = -join ((97..122) | Get-Random -Count 8 | ForEach-Object { [char]$_ })
$BUCKET_NAME   = "roodha-v15-frontend-$RANDOM_SUFFIX"
$AWS_REGION    = "ap-south-1"   # Change to your target region if needed
$OAC_NAME      = "roodha-v15-oac-$RANDOM_SUFFIX"

Write-Host ""
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host " Project Roodha v1.5 — Frontend Provisioner" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "Bucket Name : $BUCKET_NAME"
Write-Host "OAC Name    : $OAC_NAME"
Write-Host "Region      : $AWS_REGION"
Write-Host ""

# -----------------------------------------------------------------------------
# STEP 1: Create a private S3 bucket
# Note: ap-south-1 and all non-us-east-1 regions require LocationConstraint
# -----------------------------------------------------------------------------
Write-Host "[1/6] Creating private S3 bucket: $BUCKET_NAME ..." -ForegroundColor Yellow

aws s3api create-bucket `
    --bucket $BUCKET_NAME `
    --region $AWS_REGION `
    --create-bucket-configuration LocationConstraint=$AWS_REGION

Write-Host "      Bucket created." -ForegroundColor Green

# -----------------------------------------------------------------------------
# STEP 2: Block ALL public access on the bucket (enforce private-only)
# -----------------------------------------------------------------------------
Write-Host "[2/6] Blocking all public access on bucket..." -ForegroundColor Yellow

aws s3api put-public-access-block `
    --bucket $BUCKET_NAME `
    --public-access-block-configuration `
        "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"

Write-Host "      Public access blocked." -ForegroundColor Green

# -----------------------------------------------------------------------------
# STEP 3: Create a CloudFront Origin Access Control (OAC)
# OAC is the modern replacement for OAI — grants CloudFront SigV4-signed
# access to the private S3 bucket without making the bucket public.
# -----------------------------------------------------------------------------
Write-Host "[3/6] Creating CloudFront Origin Access Control (OAC)..." -ForegroundColor Yellow

$OAC_CONFIG = @{
    Name                          = $OAC_NAME
    Description                   = "OAC for Project Roodha v1.5 frontend bucket"
    SigningProtocol               = "sigv4"
    SigningBehavior               = "always"
    OriginAccessControlOriginType = "s3"
} | ConvertTo-Json -Compress

$OAC_RESULT = aws cloudfront create-origin-access-control `
    --origin-access-control-config $OAC_CONFIG `
    | ConvertFrom-Json

$OAC_ID = $OAC_RESULT.OriginAccessControl.Id
Write-Host "      OAC created. ID: $OAC_ID" -ForegroundColor Green

# -----------------------------------------------------------------------------
# STEP 4: Attach a bucket policy that allows CloudFront (via OAC) to GetObject
# The policy uses the OAC ID in the condition to scope access precisely.
# -----------------------------------------------------------------------------
Write-Host "[4/6] Attaching S3 bucket policy for CloudFront OAC access..." -ForegroundColor Yellow

$ACCOUNT_ID = (aws sts get-caller-identity | ConvertFrom-Json).Account

$BUCKET_POLICY = @{
    Version   = "2012-10-17"
    Statement = @(
        @{
            Sid       = "AllowCloudFrontOACAccess"
            Effect    = "Allow"
            Principal = @{ Service = "cloudfront.amazonaws.com" }
            Action    = "s3:GetObject"
            Resource  = "arn:aws:s3:::$BUCKET_NAME/*"
            Condition = @{
                StringEquals = @{
                    "AWS:SourceArn" = "arn:aws:cloudfront::${ACCOUNT_ID}:distribution/*"
                }
            }
        }
    )
} | ConvertTo-Json -Depth 10 -Compress

aws s3api put-bucket-policy `
    --bucket $BUCKET_NAME `
    --policy $BUCKET_POLICY

Write-Host "      Bucket policy attached." -ForegroundColor Green

# -----------------------------------------------------------------------------
# STEP 5: Create the CloudFront Distribution
# - Default root object: index.html (serves the SPA on the root path)
# - Custom error response: HTTP 404 → index.html with 200 status
#   This is CRITICAL for React Router — all client-side routes must
#   return index.html so the JS router can handle path resolution.
# - HTTPS only (redirect HTTP → HTTPS)
# - OAC-backed S3 origin (no public bucket policy required)
# -----------------------------------------------------------------------------
Write-Host "[5/6] Creating CloudFront Distribution..." -ForegroundColor Yellow

$S3_DOMAIN = "$BUCKET_NAME.s3.$AWS_REGION.amazonaws.com"
$CALLER_REF = "roodha-v15-$(Get-Date -Format 'yyyyMMddHHmmss')"

$DISTRIBUTION_CONFIG = @{
    CallerReference = $CALLER_REF
    Comment         = "Project Roodha v1.5 Frontend Distribution"
    DefaultRootObject = "index.html"
    Origins = @{
        Quantity = 1
        Items    = @(
            @{
                Id                      = "S3-$BUCKET_NAME"
                DomainName              = $S3_DOMAIN
                S3OriginConfig          = @{ OriginAccessIdentity = "" }
                OriginAccessControlId   = $OAC_ID
            }
        )
    }
    DefaultCacheBehavior = @{
        TargetOriginId       = "S3-$BUCKET_NAME"
        ViewerProtocolPolicy = "redirect-to-https"
        AllowedMethods       = @{
            Quantity = 2
            Items    = @("GET", "HEAD")
        }
        CachedMethods = @{
            Quantity = 2
            Items    = @("GET", "HEAD")
        }
        ForwardedValues = @{
            QueryString = $false
            Cookies     = @{ Forward = "none" }
        }
        MinTTL     = 0
        DefaultTTL = 86400
        MaxTTL     = 31536000
        Compress   = $true
    }
    # React Router fix: map all 404s from S3 back to index.html
    # CloudFront returns 200 so the browser loads the SPA shell correctly
    CustomErrorResponses = @{
        Quantity = 1
        Items    = @(
            @{
                ErrorCode            = 404
                ResponsePagePath     = "/index.html"
                ResponseCode         = "200"
                ErrorCachingMinTTL   = 300
            }
        )
    }
    PriceClass = "PriceClass_All"
    Enabled    = $true
    HttpVersion = "http2"
    IsIPV6Enabled = $true
} | ConvertTo-Json -Depth 20 -Compress

$DIST_RESULT = aws cloudfront create-distribution `
    --distribution-config $DISTRIBUTION_CONFIG `
    | ConvertFrom-Json

$DIST_ID     = $DIST_RESULT.Distribution.Id
$DIST_DOMAIN = $DIST_RESULT.Distribution.DomainName

Write-Host "      Distribution created. ID: $DIST_ID" -ForegroundColor Green

# -----------------------------------------------------------------------------
# STEP 6: Update the bucket policy with the exact Distribution ARN
# The initial policy used a wildcard ARN (*). Now that we have the real
# Distribution ID, we tighten the policy to allow only this distribution.
# -----------------------------------------------------------------------------
Write-Host "[6/6] Tightening bucket policy to exact Distribution ARN..." -ForegroundColor Yellow

$DIST_ARN = "arn:aws:cloudfront::${ACCOUNT_ID}:distribution/$DIST_ID"

$TIGHT_POLICY = @{
    Version   = "2012-10-17"
    Statement = @(
        @{
            Sid       = "AllowCloudFrontOACAccess"
            Effect    = "Allow"
            Principal = @{ Service = "cloudfront.amazonaws.com" }
            Action    = "s3:GetObject"
            Resource  = "arn:aws:s3:::$BUCKET_NAME/*"
            Condition = @{
                StringEquals = @{
                    "AWS:SourceArn" = $DIST_ARN
                }
            }
        }
    )
} | ConvertTo-Json -Depth 10 -Compress

aws s3api put-bucket-policy `
    --bucket $BUCKET_NAME `
    --policy $TIGHT_POLICY

Write-Host "      Bucket policy tightened to distribution ARN." -ForegroundColor Green

# -----------------------------------------------------------------------------
# OUTPUT: Print all provisioned resource identifiers
# Note: CloudFront propagation takes 5–10 minutes after this script completes.
# -----------------------------------------------------------------------------
Write-Host ""
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host " Infrastructure Provisioned Successfully" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "S3 Bucket Name      : $BUCKET_NAME" -ForegroundColor White
Write-Host "OAC ID              : $OAC_ID" -ForegroundColor White
Write-Host "Distribution ID     : $DIST_ID" -ForegroundColor White
Write-Host ""
Write-Host "CloudFront Domain   : https://$DIST_DOMAIN" -ForegroundColor Green
Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Yellow
Write-Host "  1. Run: npm run build" -ForegroundColor White
Write-Host "  2. Run: aws s3 sync ./dist s3://$BUCKET_NAME --delete" -ForegroundColor White
Write-Host "  3. Run: aws cloudfront create-invalidation --distribution-id $DIST_ID --paths '/*'" -ForegroundColor White
Write-Host "  4. Wait ~5-10 min for CloudFront propagation, then open the domain above." -ForegroundColor White
Write-Host ""
