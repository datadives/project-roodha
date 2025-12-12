#!/usr/bin/env python3
import os
import aws_cdk as cdk

from jobwork_s3_iac.s3_bucket_stack import S3BucketStack

app = cdk.App()

# Choose environment – CDK will use your current AWS CLI credentials
S3BucketStack(
    app,
    "S3BucketStack",
    env=cdk.Environment(
        account=os.getenv("CDK_DEFAULT_ACCOUNT"),
        region=os.getenv("CDK_DEFAULT_REGION", "ap-south-1")
    )
)

app.synth()
