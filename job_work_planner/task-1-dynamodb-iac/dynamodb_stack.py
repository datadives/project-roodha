from aws_cdk import (
    Stack,
    RemovalPolicy,
    aws_dynamodb as dynamodb,
)
from constructs import Construct

class MyTwoTables(Stack):
    """ 
    This is our CDK stack.
    Think of it as our list of instructions for AWS.
    When we deploy, AWS reads this and creates the tables.
    """

    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        # ----------------------
        # TENANT TABLE (simple notebook)
        # PK = tenant_id (unique ID for each tenant)
        # ----------------------
        tenant_table = dynamodb.Table(
            self, "TenantTable",
            table_name="tenant",
            partition_key=dynamodb.Attribute(name="tenant_id", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # ----------------------
        # USERS TABLE (students inside each tenant)
        # PK = tenant_id  → groups users by tenant
        # SK = user_id    → unique per user
        # ----------------------
        users_table = dynamodb.Table(
            self, "UsersTable",
            table_name="users",
            partition_key=dynamodb.Attribute(name="tenant_id", type=dynamodb.AttributeType.STRING),
            sort_key=dynamodb.Attribute(name="user_id", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
        )