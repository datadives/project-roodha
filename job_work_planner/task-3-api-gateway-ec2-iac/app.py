import os
import aws_cdk as cdk
from ec2_stack import Ec2Stack
from api_gateway_stack import ApiGatewayStack
 
app = cdk.App()
 
# ✅ HARD FIX: explicitly read account & region
env = cdk.Environment(
    account=os.environ["CDK_DEFAULT_ACCOUNT"],
    region=os.environ.get("CDK_DEFAULT_REGION", "ap-south-1"),
)
 
# EC2 backend
ec2_stack = Ec2Stack(
    app,
    "Ec2Stack",
    env=env,
)
 
# API Gateway
api_gateway_stack = ApiGatewayStack(
    app,
    "ApiGatewayStack",
    ec2_public_ip=ec2_stack.ec2_public_ip,
    env=env
)
 
api_gateway_stack.add_dependency(ec2_stack)
 
app.synth()