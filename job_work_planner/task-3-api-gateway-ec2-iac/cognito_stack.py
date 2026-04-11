from aws_cdk import (
    Duration,
    RemovalPolicy,
    Stack,
    aws_cognito as cognito,
    aws_lambda as _lambda,
    aws_iam as iam,
    aws_logs as logs,
)
from constructs import Construct


class CognitoStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # 1. Post-Confirmation Lambda Trigger with Observability
        # We define this first so we can reference it in the UserPool
        post_confirmation_lambda = _lambda.Function(
            self,
            "PostConfirmationFunction",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="cognito_post_confirmation.lambda_handler",
            code=_lambda.Code.from_asset("../"), # Points to job_work_planner directory
            memory_size=128,
            timeout=Duration.seconds(10),
            tracing=_lambda.Tracing.ACTIVE,  # Priority 3: X-Ray Tracing
            log_retention=logs.RetentionDays.ONE_WEEK, # Priority 3: Log Retention
        )

        # 2. Cognito User Pool
        user_pool = cognito.UserPool(
            self,
            "RoodhaUserPool",
            user_pool_name="roodha-user-pool",
            self_sign_up_enabled=True,
            sign_in_aliases=cognito.SignInAliases(username=False, email=True),
            auto_verify=cognito.AutoVerifiedAttrs(email=True),
            password_policy=cognito.PasswordPolicy(
                min_length=8,
                require_lowercase=True,
                require_uppercase=True,
                require_digits=True,
                require_symbols=False,
            ),
            custom_attributes={
                "tenant_id": cognito.StringAttribute(mutable=True),
                "user_role": cognito.StringAttribute(mutable=True),
            },
            lambda_triggers=cognito.UserPoolTriggers(
                post_confirmation=post_confirmation_lambda
            ),
            removal_policy=RemovalPolicy.DESTROY, # Hardened for dev/testing, use RETAIN for prod
        )

        # 3. App Client
        user_pool_client = user_pool.add_client(
            "RoodhaAppClient",
            auth_flows=cognito.AuthFlow(
                user_srp=True,
                admin_user_password=True,
                custom=True,
            ),
        )

        # 4. IAM Permissions for Lambda (Security First)
        # Lambda needs to update user attributes in Cognito
        post_confirmation_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=["cognito-idp:AdminUpdateUserAttributes"],
                resources=[user_pool.user_pool_arn],
            )
        )

        # Outputs
        self.user_pool_id = user_pool.user_pool_id
        self.user_pool_client_id = user_pool_client.user_pool_client_id
