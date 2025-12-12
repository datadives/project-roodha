# s3_bucket_stack.py
# Production-ready CDK Stack to create a private S3 bucket for app uploads and two minimal IAM roles (Lambda + EC2).
# This file is fully commented line-by-line as required.

from aws_cdk import (
    Stack,
    RemovalPolicy,
    Duration,
    CfnOutput,
    aws_s3 as s3,
    aws_iam as iam,
)
from constructs import Construct
import os

# Environment selection: set DEPLOY_ENV=prod for production behaviour (RETAIN). Default is dev.
ENV = os.environ.get('DEPLOY_ENV', 'dev')

class S3BucketStack(Stack):
    """Stack to create private S3 bucket and IAM roles for app access."""
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Derive a safe bucket name using environment to avoid collisions
        bucket_name = f"jobwork-app-files-{ENV}"

        # Create the S3 bucket with secure defaults
        # - Block all public access
        # - Server-side encryption using AWS-managed keys
        # - Versioning enabled for safety
        # - Lifecycle rule example to transition to INFREQUENT_ACCESS after 30 days
        # - RemovalPolicy.RETAIN in production to avoid accidental data deletion
        bucket = s3.Bucket(
            self,
            "AppFilesBucket",
            bucket_name=bucket_name,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,  # block public ACLs and policies
            encryption=s3.BucketEncryption.S3_MANAGED,  # encryption at rest with AWS-managed keys
            versioned=True,  # keep object versions (enable for protection)
            enforce_ssl=True,  # require HTTPS for requests
            removal_policy=RemovalPolicy.RETAIN if ENV == 'prod' else RemovalPolicy.DESTROY,
            # CORS: allow PUT from browser (pre-signed PUT) and GET for downloads
            cors=[s3.CorsRule(
                allowed_methods=[s3.HttpMethods.GET, s3.HttpMethods.PUT, s3.HttpMethods.HEAD],
                allowed_origins=[os.environ.get('FRONTEND_ORIGIN', '*')],  # set FRONTEND_ORIGIN in env for prod
                allowed_headers=['*'],
                max_age=3000
            )]
        )

        # Lifecycle rule: transition objects to STANDARD_IA after 30 days and expire after 365 days
        # This reduces long-term storage cost for older files.
        bucket.add_lifecycle_rule(
            id="transition-to-ia",
            enabled=True,
            transitions=[s3.Transition(
                storage_class=s3.StorageClass.INFREQUENT_ACCESS,
                transition_after=Duration.days(30)
            )],
            expiration=Duration.days(365),
            prefix=""  # apply to all objects; change to 'tenant_id/module/' if needed
        )

        # Create a least-privilege IAM policy statement for bucket access
        # - Allow ListBucket on the bucket itself (for listing prefixes)
        # - Allow GetObject/PutObject/DeleteObject on objects in the bucket
        bucket_policy = iam.PolicyStatement(
            actions=[
                "s3:ListBucket"
            ],
            resources=[bucket.bucket_arn],
            effect=iam.Effect.ALLOW
        )

        object_policy = iam.PolicyStatement(
            actions=[
                "s3:GetObject",
                "s3:PutObject",
                "s3:DeleteObject"
            ],
            resources=[f"{bucket.bucket_arn}/*"],
            effect=iam.Effect.ALLOW
        )

        # Role for Lambda (if your backend is Lambda). Trusted by the Lambda service principal.
        lambda_role = iam.Role(
            self,
            "AppLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="Role for Lambda functions to access the jobwork app files S3 bucket."
        )
        # Attach the minimal policies to the Lambda role
        lambda_role.add_to_policy(bucket_policy)
        lambda_role.add_to_policy(object_policy)

        # Role for EC2 (if your backend runs on EC2). Trusted by the EC2 service principal.
        ec2_role = iam.Role(
            self,
            "AppEc2Role",
            assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
            description="Role for EC2 instances to access the jobwork app files S3 bucket."
        )
        # Attach the minimal policies to the EC2 role
        ec2_role.add_to_policy(bucket_policy)
        ec2_role.add_to_policy(object_policy)

        # Grant read/write to the roles using CDK helper (also sets resource policies if needed)
        bucket.grant_read_write(lambda_role)
        bucket.grant_read_write(ec2_role)

        # Outputs so other stacks or teams can reference the resources
        CfnOutput(self, "BucketName", value=bucket.bucket_name, description="S3 bucket name for app files")
        CfnOutput(self, "AppLambdaRoleArn", value=lambda_role.role_arn, description="IAM role ARN for Lambda to access bucket")
        CfnOutput(self, "AppEc2RoleArn", value=ec2_role.role_arn, description="IAM role ARN for EC2 to access bucket")

# End of file
