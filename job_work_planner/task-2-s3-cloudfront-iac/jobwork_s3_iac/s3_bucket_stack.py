# s3_bucket_stack.py
# Production-ready CDK stack for the Project Roodha frontend bucket.
# The live production bucket is configured as a public static website and
# this stack mirrors that behavior so future deploys do not drift it back
# to a private-only configuration.

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
    Stack to create the production frontend S3 bucket and IAM roles for
    EC2/Lambda access.
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ---------------------------------------------------------
        # Bucket names will be dynamically generated
        # ---------------------------------------------------------

        removal_policy = (
            RemovalPolicy.RETAIN if ENV == "prod" else RemovalPolicy.DESTROY
        )
        auto_delete_objects = ENV != "prod"

        # ---------------------------------------------------------
        # Create PUBLIC static website bucket aligned with production
        # ---------------------------------------------------------
        self.bucket = s3.Bucket(
            self,
            "RoodhaProdBucketV1",
            block_public_access=s3.BlockPublicAccess(
                block_public_acls=False,
                ignore_public_acls=False,
                block_public_policy=False,
                restrict_public_buckets=False,
            ),
            encryption=s3.BucketEncryption.S3_MANAGED,
            versioned=True,
            object_ownership=s3.ObjectOwnership.BUCKET_OWNER_ENFORCED,
            website_index_document="index.html",
            website_error_document="index.html",
            public_read_access=False,
            removal_policy=removal_policy,
            auto_delete_objects=auto_delete_objects,
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

        # Public website read access is granted through bucket policy because
        # Object Ownership is BucketOwnerEnforced and ACLs are disabled.
        self.bucket.add_to_resource_policy(
            iam.PolicyStatement(
                sid="PublicReadGetObject",
                actions=["s3:GetObject"],
                principals=[iam.AnyPrincipal()],
                resources=[self.bucket.arn_for_objects("*")],
                effect=iam.Effect.ALLOW,
            )
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
            "WebsiteUrl",
            value=f"http://{self.bucket.bucket_name}.s3-website.{Stack.of(self).region}.amazonaws.com",
            description="Public S3 static website URL for the frontend",
        )

        CfnOutput(
            self,
            "WebsiteDomainName",
            value=f"{self.bucket.bucket_name}.s3-website.{Stack.of(self).region}.amazonaws.com",
            description="Public S3 static website domain name for the frontend",
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
