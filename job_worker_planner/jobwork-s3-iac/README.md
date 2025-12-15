JobWork Planner – S3 Application Storage (IaC)
Overview

This module provisions a secure, private Amazon S3 bucket using AWS CDK (Python) for the JobWork Planner SaaS application.

The bucket is designed to store application-owned files only, such as:

Purchase Orders (POs)

Part drawings

CSV exports and reports

The infrastructure is created using Infrastructure as Code (IaC) to ensure:

Consistency across environments

Security by default

Production readiness

Why Amazon S3?

Amazon S3 was chosen because it provides:

Highly durable and scalable object storage

Native support for private buckets

Tight integration with IAM roles

Support for pre-signed URLs (secure browser uploads)

Lifecycle policies for cost optimization

This makes it ideal for a multi-tenant SaaS application.

Key Design Principles
1. Private-by-Default Security

The S3 bucket is NOT public

All public access is blocked using:

Block Public ACLs

Block Public Policies

Restrict Public Buckets

HTTPS is enforced for all requests

Result:
Only the application can access the bucket.

2. IAM Role–Based Access (No Access Keys)

The bucket is accessed only via IAM roles

Two roles are created:

Lambda Role – for backend APIs

EC2 Role – for app servers

No access keys are stored anywhere

Result:
Follows AWS security best practices.

3. Multi-Tenant Object Key Strategy

Files are stored using the following prefix structure:

tenant_id/module/yyyy/mm/dd/filename


Example:

T001/uploads/2025/12/10/po_1234.pdf


This ensures:

Clear tenant isolation

Easy filtering and reporting

Scalability for future analytics

4. Browser Uploads Using Pre-Signed URLs

The bucket allows PUT operations via pre-signed URLs

CORS is configured to allow:

PUT, GET, HEAD

Files can be uploaded directly from the browser without exposing AWS credentials

Flow:

Backend generates a pre-signed URL

Browser uploads file directly to S3

Backend never handles raw file data

5. Versioning & Lifecycle Management

Versioning is enabled

Protects against accidental overwrites/deletes

Lifecycle rules

Transition files to cheaper storage after 30 days

Expire files after 365 days (configurable)

Result:
Cost-efficient long-term storage.

What This Stack Creates

✅ Private S3 bucket for app files

✅ CORS configuration for browser uploads

✅ IAM roles with least-privilege access

✅ Encryption at rest (AES-256)

✅ Versioning enabled

✅ Lifecycle policies

✅ CloudFormation outputs for integration

Project Structure
jobwork-s3-iac/
│
├── app.py                     # CDK app entry point
├── s3_bucket_stack.py          # S3 bucket + IAM roles definition
├── presign_upload_test.py      # Pre-signed URL upload test script
├── requirements.txt
├── cdk.json
├── README.md
└── jobwork_s3_iac/

Deployment Instructions
1. Install dependencies
pip install -r requirements.txt

2. Bootstrap CDK (one-time per account/region)
cdk bootstrap aws://<account-id>/<region>

3. Deploy the stack
cdk deploy S3BucketStack

Validation Performed

The following were verified after deployment:

Bucket exists in correct region

Public access is fully blocked

Encryption is enabled

Versioning is enabled

CORS rules are applied

IAM roles have correct permissions

Pre-signed URL upload works successfully

How This Fits Into the JobWork Planner System

Acts as the central file storage layer

Works with:

EC2 / Lambda backend

DynamoDB (metadata)

CloudFront (optional, future)

Designed for:

Multi-tenant SaaS

Secure browser uploads

Production workloads

Notes

No application data is public

No secrets or credentials are stored in code

Infrastructure is fully reproducible via CDK

Author

Roshan Sah
Intern – Data Engineering / Cloud
JobWork Planner Project
