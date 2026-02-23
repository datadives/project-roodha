from aws_cdk import (
    Stack,
    aws_apigatewayv2 as apigw,
    aws_apigatewayv2_integrations as integrations,
    aws_apigatewayv2_authorizers as authorizers,
    aws_logs as logs,
    CfnOutput,
)
from constructs import Construct
 
 
class ApiGatewayStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, ec2_public_ip: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)
 
        # ---------------------------------------------------------
        # HTTP API
        # ---------------------------------------------------------
        http_api = apigw.HttpApi(
            self,
            "JobWorkHttpApi",
            api_name="jobwork-http-api",
            cors_preflight=apigw.CorsPreflightOptions(
                allow_headers=["Authorization", "Content-Type"],
                allow_methods=[apigw.CorsHttpMethod.ANY],
                allow_origins=["*"],  # tighten later for prod
            ),
        )
 
        # ---------------------------------------------------------
        # Cognito JWT Authorizer
        # ---------------------------------------------------------
        jwt_authorizer = authorizers.HttpJwtAuthorizer(
            "CognitoJwtAuthorizer",
            jwt_issuer=f"https://cognito-idp.ap-south-1.amazonaws.com/ap-south-1_M3xBYcen7",
            jwt_audience=["5592g38cjskmpd9ceid24osugm"],
        )
 
        # ---------------------------------------------------------
        # EC2 HTTP Integration
        # ---------------------------------------------------------
        ec2_integration = integrations.HttpUrlIntegration(
            "Ec2HttpIntegration",
            url=f"http://{ec2_public_ip}",
            method=apigw.HttpMethod.ANY,
        )
 
        # ---------------------------------------------------------
        # Public Route (NO AUTH)
        # ---------------------------------------------------------
        http_api.add_routes(
            path="/health",
            methods=[apigw.HttpMethod.GET],
            integration=ec2_integration,
        )
 
        # ---------------------------------------------------------
        # Protected Routes (JWT REQUIRED)
        # ---------------------------------------------------------
        protected_routes = [
            "/auth/{proxy+}",
            "/masters/{proxy+}",
            "/jobs/{proxy+}",
            "/attachments/{proxy+}",
            "/reports/{proxy+}",
        ]
 
        for route in protected_routes:
            http_api.add_routes(
                path=route,
                methods=[apigw.HttpMethod.ANY],
                integration=ec2_integration,
                authorizer=jwt_authorizer,
            )
 
        # ---------------------------------------------------------
        # Output
        # ---------------------------------------------------------
        CfnOutput(
            self,
            "HttpApiBaseUrl",
            value=http_api.api_endpoint,
        )
 