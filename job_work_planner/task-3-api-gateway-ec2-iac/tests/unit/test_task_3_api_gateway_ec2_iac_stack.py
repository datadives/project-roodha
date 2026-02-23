import aws_cdk as core
import aws_cdk.assertions as assertions

from task_3_api_gateway_ec2_iac.task_3_api_gateway_ec2_iac_stack import Task3ApiGatewayEc2IacStack

# example tests. To run these tests, uncomment this file along with the example
# resource in task_3_api_gateway_ec2_iac/task_3_api_gateway_ec2_iac_stack.py
def test_sqs_queue_created():
    app = core.App()
    stack = Task3ApiGatewayEc2IacStack(app, "task-3-api-gateway-ec2-iac")
    template = assertions.Template.from_stack(stack)

#     template.has_resource_properties("AWS::SQS::Queue", {
#         "VisibilityTimeout": 300
#     })
