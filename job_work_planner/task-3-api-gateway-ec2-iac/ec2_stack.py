from pathlib import Path

from aws_cdk import (
    CfnOutput,
    Stack,
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_s3_assets as s3_assets,
)
from constructs import Construct


class Ec2Stack(Stack):
    """
    EC2 stack hosting the production FastAPI backend.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        backend_env: dict[str, str],
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        vpc = ec2.Vpc.from_lookup(
            self,
            "DefaultVpc",
            is_default=True,
        )

        sg = ec2.SecurityGroup(
            self,
            "BackendSecurityGroup",
            vpc=vpc,
            description="Allow HTTP traffic to backend EC2",
            allow_all_outbound=True,
        )
        sg.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(80), "Allow HTTP access")

        backend_dir = Path(__file__).resolve().parents[1] / "task-4-backend-skeleton"
        backend_asset = s3_assets.Asset(
            self,
            "RoodhaBackendAsset",
            path=str(backend_dir),
            exclude=[".venv", "__pycache__", "tests", "*.pyc", ".env"],
        )

        instance = ec2.Instance(
            self,
            "BackendInstance",
            vpc=vpc,
            instance_type=ec2.InstanceType("t3.micro"),
            machine_image=ec2.MachineImage.latest_amazon_linux2023(),
            security_group=sg,
        )

        instance.role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSSMManagedInstanceCore")
        )
        # Priority 3: Add Observability Policies
        instance.role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("CloudWatchAgentServerPolicy")
        )
        instance.role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("AWSXRayDaemonWriteAccess")
        )

        backend_asset.grant_read(instance.role)

        backend_env_lines = [
            "ENV=production",
            f"DATABASE_URL={backend_env['DATABASE_URL']}",
            f"CORS_ALLOW_ORIGINS={backend_env['CORS_ALLOW_ORIGINS']}",
            f"AWS_REGION={backend_env['AWS_REGION']}",
            f"COGNITO_REGION={backend_env['AWS_REGION']}",
            f"COGNITO_USER_POOL_ID={backend_env['COGNITO_USER_POOL_ID']}",
            f"COGNITO_APP_CLIENT_ID={backend_env['COGNITO_APP_CLIENT_ID']}",
        ]
        backend_env_payload = "\n".join(backend_env_lines)

        instance.user_data.add_commands(
            "#!/bin/bash",
            "set -euxo pipefail",
            "dnf update -y",
            # Priority 3: Install Agents
            "dnf install -y python3.11 python3.11-pip nginx unzip amazon-cloudwatch-agent",
            "mkdir -p /opt/roodha",
            "mkdir -p /etc/nginx/conf.d",
            
            # Setup X-Ray Daemon
            'curl https://s3.ap-south-1.amazonaws.com/aws-xray-assets.ap-south-1/xray-daemon/aws-xray-daemon-3.x.rpm -o /tmp/xray.rpm',
            "dnf install -y /tmp/xray.rpm",

            "aws s3 cp s3://%s/%s /tmp/roodha-backend.zip --region %s"
            % (backend_asset.s3_bucket_name, backend_asset.s3_object_key, Stack.of(self).region),
            "rm -rf /opt/roodha/app",
            "unzip -o /tmp/roodha-backend.zip -d /opt/roodha/app",
            "PYTHON_BIN=$(command -v python3.11 || command -v python3)",
            "$PYTHON_BIN -m venv /opt/roodha/venv",
            "/opt/roodha/venv/bin/pip install --upgrade pip",
            "/opt/roodha/venv/bin/pip install -r /opt/roodha/app/requirements.txt",
            
            # Configure CloudWatch Agent (Basic)
            "cat > /opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json <<'EOF'",
            '{"logs":{"logs_collected":{"files":{"collect_list":[{"file_path":"/var/log/nginx/access.log","log_group_name":"roodha-access-logs","log_stream_name":"{instance_id}"}]}}}}',
            "EOF",

            "cat > /opt/roodha/app/.env <<'EOF'",
            backend_env_payload,
            "EOF",
            
            # Start Services
            "systemctl enable amazon-cloudwatch-agent xray",
            "systemctl start amazon-cloudwatch-agent xray",
            
            "cat > /etc/systemd/system/roodha-backend.service <<'EOF'",
            "[Unit]",
            "Description=Project Roodha FastAPI backend",
            "After=network.target",
            "",
            "[Service]",
            "User=root",
            "WorkingDirectory=/opt/roodha/app",
            "Environment=PYTHONPATH=/opt/roodha/app",
            "ExecStart=/opt/roodha/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000",
            "Restart=always",
            "RestartSec=5",
            "",
            "[Install]",
            "WantedBy=multi-user.target",
            "EOF",
            "cat > /etc/nginx/conf.d/roodha.conf <<'EOF'",
            "server {",
            "    listen 80 default_server;",
            "    server_name _;",
            "",
            "    location / {",
            "        proxy_pass http://127.0.0.1:8000;",
            "        proxy_http_version 1.1;",
            "        proxy_set_header Host $host;",
            "        proxy_set_header X-Real-IP $remote_addr;",
            "        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;",
            "        proxy_set_header X-Forwarded-Proto $scheme;",
            "    }",
            "}",
            "EOF",
            "rm -f /etc/nginx/conf.d/default.conf",
            "systemctl daemon-reload",
            "systemctl enable roodha-backend nginx",
            "systemctl restart roodha-backend",
            "systemctl restart nginx",
        )

        self.ec2_public_ip = instance.instance_public_ip

        CfnOutput(
            self,
            "Ec2PublicIp",
            value=self.ec2_public_ip,
            description="Public IP of backend EC2",
        )
