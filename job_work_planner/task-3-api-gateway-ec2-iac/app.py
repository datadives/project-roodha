import os
from pathlib import Path

import aws_cdk as cdk

from api_gateway_stack import ApiGatewayStack
from ec2_stack import Ec2Stack
from cognito_stack import CognitoStack


app = cdk.App()

# 1. Environment Configuration
env = cdk.Environment(
    account=os.environ.get("CDK_DEFAULT_ACCOUNT", "000000000000"),
    region=os.environ.get("CDK_DEFAULT_REGION", "ap-south-1"),
)

# 2. Load Backend Environment
backend_env_path = Path(__file__).resolve().parents[1] / "task-4-backend-skeleton" / ".env"
backend_env = {}
if backend_env_path.exists():
    for line in backend_env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        backend_env[key.strip()] = value.strip()

# 3. Stack Provisioning (Priority 3: Observability Baseline)

# Modernized Cognito with X-Ray and Logs
cognito_stack = CognitoStack(
    app,
    "CognitoStack",
    env=env,
)

# Backend EC2 with CloudWatch/X-Ray Agents
ec2_stack = Ec2Stack(
    app,
    "Ec2Stack",
    backend_env=backend_env,
    env=env,
)

# API Gateway with Access Logs and Tracing
api_gateway_stack = ApiGatewayStack(
    app,
    "ApiGatewayStack",
    ec2_public_ip=os.environ.get("ROODHA_EC2_PUBLIC_IP", "65.0.185.145"),
    env=env,
)

app.synth()
