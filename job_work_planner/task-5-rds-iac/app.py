import os
import aws_cdk as cdk
from task_5_rds_iac.task_5_rds_iac_stack import Task5RdsIacStack

app = cdk.App()
Task5RdsIacStack(app, "RdsMasterStack",
    env=cdk.Environment(
        account=os.getenv('CDK_DEFAULT_ACCOUNT'), 
        region=os.getenv('CDK_DEFAULT_REGION')
    )
)

app.synth()