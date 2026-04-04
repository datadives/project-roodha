from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
    aws_rds as rds,
    CfnOutput,
    RemovalPolicy
)
from constructs import Construct

class Task5RdsIacStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        # 1. Look up your default AWS network (VPC)
        vpc = ec2.Vpc.from_lookup(self, "DefaultVpc", is_default=True)

        # 2. Create a Security Group to allow your local PC to connect
        rds_sg = ec2.SecurityGroup(
            self, "RdsSecurityGroup",
            vpc=vpc,
            description="Allow inbound traffic to RDS for local testing",
            allow_all_outbound=True
        )
        rds_sg.add_ingress_rule(
            ec2.Peer.any_ipv4(), 
            ec2.Port.tcp(5432), 
            "Allow PostgreSQL access from anywhere"
        )

        # 3. Create the PostgreSQL Database
        db_instance = rds.DatabaseInstance(
            self, "MasterDbInstance",
            engine=rds.DatabaseInstanceEngine.postgres(
                version=rds.PostgresEngineVersion.VER_15
            ),
            instance_type=ec2.InstanceType.of(
                ec2.InstanceClass.T3, ec2.InstanceSize.MICRO
            ),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PUBLIC
            ),
            security_groups=[rds_sg],
            database_name="roodhamaster",
            publicly_accessible=True, # Allows local testing
            removal_policy=RemovalPolicy.DESTROY, 
            deletion_protection=False
        )

        # 4. Output the connection details
        CfnOutput(self, "RdsEndpoint", value=db_instance.db_instance_endpoint_address)
        CfnOutput(self, "RdsSecretArn", value=db_instance.secret.secret_arn)