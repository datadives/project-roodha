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
# Stack 1: Private S3 bucket for app files
# ---------------------------------------------------------
s3_stack = S3BucketStack(
    app,
    "S3BucketStack",
    env=env,
)

# ---------------------------------------------------------
# Stack 2: CloudFront distribution in front of S3
# ---------------------------------------------------------
CloudFrontStack(
    app,
    "CloudFrontStack",
    bucket_name=s3_stack.bucket.bucket_name,
    env=env,
)

app.synth()
