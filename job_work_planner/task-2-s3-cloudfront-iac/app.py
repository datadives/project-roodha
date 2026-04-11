#!/usr/bin/env python3
import os
import aws_cdk as cdk

from jobwork_s3_iac.s3_bucket_stack import S3BucketStack
from jobwork_s3_iac.cloudfront_stack import CloudFrontStack

app = cdk.App()

# AWS environment (account + region)
env = cdk.Environment(
    account=os.getenv("CDK_DEFAULT_ACCOUNT"),
    region=os.getenv("CDK_DEFAULT_REGION", "ap-south-1"),
)

# ---------------------------------------------------------
# Stack 1: Public S3 website bucket for the production frontend
# ---------------------------------------------------------
s3_stack = S3BucketStack(
    app,
    "RoodhaProdBucketStackV1",
    env=env,
)

# ---------------------------------------------------------
# Stack 2: Optional CloudFront distribution in front of the frontend bucket
# ---------------------------------------------------------
CloudFrontStack(
    app,
    "RoodhaFrontendProdStackV1",
    bucket=s3_stack.bucket,
    env=env,
)

app.synth()
