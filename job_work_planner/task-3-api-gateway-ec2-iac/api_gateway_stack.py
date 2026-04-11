from aws_cdk import CfnOutput, Stack, aws_apigatewayv2 as apigw, aws_apigatewayv2_integrations as integrations
from constructs import Construct


class ApiGatewayStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, ec2_public_ip: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        http_api = apigw.HttpApi(
            self,
            "JobWorkHttpApi",
            api_name="jobwork-http-api",
            cors_preflight=apigw.CorsPreflightOptions(
                allow_headers=[
                    "Content-Type",
                    "X-Amz-Date",
                    "Authorization",
                    "X-Api-Key",
                    "X-Amz-Security-Token",
                    "tenant-id",
                    "user-role",
                ],
                allow_methods=[apigw.CorsHttpMethod.ANY],
                allow_origins=["*"],
            ),
        )

        ec2_integration = integrations.HttpUrlIntegration(
            "Ec2HttpIntegration",
            url=f"http://{ec2_public_ip}",
            method=apigw.HttpMethod.ANY,
            # Preserve the original request path so API Gateway forwards
            # /health and tenant routes to FastAPI instead of collapsing to /.
            parameter_mapping=apigw.ParameterMapping().overwrite_path(
                apigw.MappingValue.request_path()
            ),
        )

        http_api.add_routes(
            path="/health",
            methods=[apigw.HttpMethod.GET],
            integration=ec2_integration,
        )

        http_api.add_routes(
            path="/{proxy+}",
            methods=[apigw.HttpMethod.ANY],
            integration=ec2_integration,
        )

        CfnOutput(
            self,
            "HttpApiBaseUrl",
            value=http_api.api_endpoint,
        )
