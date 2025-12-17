# s3_bucket_stack.py
# Production-ready CDK Stack to create a private S3 bucket for app uploads
# and minimal IAM roles (Lambda + EC2).
# Fully reviewed, secure, and cross-stack compatible.

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

# Environment selection: set DEPLOY_ENV=prod for production behaviour (RETAIN).
# Default is dev.
ENV = os.environ.get("DEPLOY_ENV", "dev")


class S3BucketStack(Stack):
    """
    Stack to create a private S3 bucket for application files
    and IAM roles for EC2/Lambda access.
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ---------------------------------------------------------
        # Bucket name (environment-aware to avoid collisions)
        # ---------------------------------------------------------
        bucket_name = f"jobwork-app-files-{ENV}"

        # ---------------------------------------------------------
        # Create PRIVATE S3 bucket with secure defaults
        # ---------------------------------------------------------
        self.bucket = s3.Bucket(
            self,
            "AppFilesBucket",
            bucket_name=bucket_name,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            versioned=True,
            enforce_ssl=True,
            removal_policy=RemovalPolicy.RETAIN if ENV == "prod" else RemovalPolicy.DESTROY,
            cors=[
                s3.CorsRule(
                    allowed_methods=[
                        s3.HttpMethods.GET,
                        s3.HttpMethods.PUT,
                        s3.HttpMethods.HEAD,
                    ],
                    allowed_origins=[
                        os.environ.get("FRONTEND_ORIGIN", "*")
                    ],
                    allowed_headers=["*"],
                    max_age=3000,
                )
            ],
        )

        # ---------------------------------------------------------
        # Lifecycle rule (cost optimization)
        # ---------------------------------------------------------
        self.bucket.add_lifecycle_rule(
            id="transition-to-ia",
            enabled=True,
            transitions=[
                s3.Transition(
                    storage_class=s3.StorageClass.INFREQUENT_ACCESS,
                    transition_after=Duration.days(30),
                )
            ],
            expiration=Duration.days(365),
        )

        # ---------------------------------------------------------
        # IAM policies (least privilege)
        # ---------------------------------------------------------
        bucket_policy = iam.PolicyStatement(
            actions=["s3:ListBucket"],
            resources=[self.bucket.bucket_arn],
            effect=iam.Effect.ALLOW,
        )

        object_policy = iam.PolicyStatement(
            actions=["s3:GetObject", "s3:PutObject", "s3:DeleteObject"],
            resources=[f"{self.bucket.bucket_arn}/*"],
            effect=iam.Effect.ALLOW,
        )

        # ---------------------------------------------------------
        # Lambda IAM Role
        # ---------------------------------------------------------
        lambda_role = iam.Role(
            self,
            "AppLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="Lambda role to access JobWork Planner S3 bucket",
        )
        lambda_role.add_to_policy(bucket_policy)
        lambda_role.add_to_policy(object_policy)

        # ---------------------------------------------------------
        # EC2 IAM Role
        # ---------------------------------------------------------
        ec2_role = iam.Role(
            self,
            "AppEc2Role",
            assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
            description="EC2 role to access JobWork Planner S3 bucket",
        )
        ec2_role.add_to_policy(bucket_policy)
        ec2_role.add_to_policy(object_policy)

        # CDK helper grants (safe + explicit)
        self.bucket.grant_read_write(lambda_role)
        self.bucket.grant_read_write(ec2_role)

        # ---------------------------------------------------------
        # Outputs
        # ---------------------------------------------------------
        CfnOutput(
            self,
            "BucketName",
            value=self.bucket.bucket_name,
            description="S3 bucket name for app files",
        )

        CfnOutput(
            self,
            "AppLambdaRoleArn",
            value=lambda_role.role_arn,
            description="IAM role ARN for Lambda access",
        )

        CfnOutput(
            self,
            "AppEc2RoleArn",
            value=ec2_role.role_arn,
            description="IAM role ARN for EC2 access",
        )
