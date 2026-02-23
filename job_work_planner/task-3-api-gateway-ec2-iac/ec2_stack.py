from aws_cdk import (
    Stack,
    CfnOutput,
    aws_ec2 as ec2,
)
from constructs import Construct
 
 
class Ec2Stack(Stack):
    """
    EC2 stack hosting backend application.
    This EC2 acts as the backend for API Gateway (early-stage, no ALB yet).
    """
 
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
 
        # Use default VPC (simple & safe for early stage)
        vpc = ec2.Vpc.from_lookup(
            self,
            "DefaultVpc",
            is_default=True,
        )
 
        # Security Group: allow HTTP traffic
        sg = ec2.SecurityGroup(
            self,
            "BackendSecurityGroup",
            vpc=vpc,
            description="Allow HTTP traffic to backend EC2",
            allow_all_outbound=True,
        )
 
        sg.add_ingress_rule(
            ec2.Peer.any_ipv4(),
            ec2.Port.tcp(80),
            "Allow HTTP access",
        )
 
        # EC2 instance
        instance = ec2.Instance(
            self,
            "BackendInstance",
            vpc=vpc,
            instance_type=ec2.InstanceType("t3.micro"),
            machine_image=ec2.MachineImage.latest_amazon_linux2(),
            security_group=sg,
        )
 
        # Simple backend response
        instance.add_user_data(
            "#!/bin/bash",
            "yum install -y httpd",
            "systemctl start httpd",
            "systemctl enable httpd",
            "echo 'Hello from EC2 backend' > /var/www/html/index.html",
        )
 
        # Export public IP for API Gateway
        self.ec2_public_ip = instance.instance_public_ip
 
        CfnOutput(
            self,
            "Ec2PublicIp",
            value=self.ec2_public_ip,
            description="Public IP of backend EC2",
        )