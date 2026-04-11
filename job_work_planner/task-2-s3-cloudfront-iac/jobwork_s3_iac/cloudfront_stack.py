# CloudFront stack for serving private S3 app files securely
# Uses Origin Access Control (OAC) — NO OAI

from aws_cdk import (
    Stack,
    CfnOutput,
    aws_cloudfront as cloudfront,
    aws_cloudfront_origins as origins,
    aws_s3 as s3,
)
from constructs import Construct


class CloudFrontStack(Stack):
    """
    Creates a CloudFront distribution in front of a PRIVATE S3 bucket
    using Origin Access Control (OAC).
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        bucket: s3.Bucket,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        app_files_bucket = bucket

        # Create Origin Access Control (OAC)
        oac = cloudfront.CfnOriginAccessControl(
            self,
            "AppFilesOAC",
            origin_access_control_config=cloudfront.CfnOriginAccessControl.OriginAccessControlConfigProperty(
                name="jobwork-app-files-oac",
                description="OAC for CloudFront to access private S3 bucket",
                origin_access_control_origin_type="s3",
                signing_behavior="always",
                signing_protocol="sigv4",
            ),
        )

        # Create CloudFront Distribution (NO OAI)
        distribution = cloudfront.Distribution(
            self,
            "RoodhaProdDistributionV1",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3BucketOrigin(app_files_bucket),
                allowed_methods=cloudfront.AllowedMethods.ALLOW_GET_HEAD,
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED,
            ),
            error_responses=[
                cloudfront.ErrorResponse(
                    http_status=403,
                    response_http_status=200,
                    response_page_path="/index.html"
                ),
                cloudfront.ErrorResponse(
                    http_status=404,
                    response_http_status=200,
                    response_page_path="/index.html"
                )
            ],
            comment="Project Roodha Production - Deployed April 2026",
        )

        import aws_cdk.aws_iam as iam
        app_files_bucket.add_to_resource_policy(
            iam.PolicyStatement(
                actions=["s3:GetObject"],
                resources=[app_files_bucket.arn_for_objects("*")],
                principals=[iam.ServicePrincipal("cloudfront.amazonaws.com")],
                conditions={
                    "StringLike": {
                        "AWS:SourceArn": f"arn:aws:cloudfront::{Stack.of(self).account}:distribution/*"
                    }
                }
            )
        )

        # Attach OAC to the CloudFront origin
        cfn_distribution = distribution.node.default_child
        cfn_distribution.add_property_override(
            "DistributionConfig.Origins.0.OriginAccessControlId",
            oac.attr_id,
        )

        # Outputs
        CfnOutput(
            self,
            "CloudFrontDistributionId",
            value=distribution.distribution_id,
        )

        CfnOutput(
            self,
            "CloudFrontDomainName",
            value=distribution.domain_name,
        )
