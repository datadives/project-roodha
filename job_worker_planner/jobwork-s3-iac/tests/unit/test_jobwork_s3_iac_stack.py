import aws_cdk as core
import aws_cdk.assertions as assertions

from jobwork_s3_iac.jobwork_s3_iac_stack import JobworkS3IacStack

# example tests. To run these tests, uncomment this file along with the example
# resource in jobwork_s3_iac/jobwork_s3_iac_stack.py
def test_sqs_queue_created():
    app = core.App()
    stack = JobworkS3IacStack(app, "jobwork-s3-iac")
    template = assertions.Template.from_stack(stack)

#     template.has_resource_properties("AWS::SQS::Queue", {
#         "VisibilityTimeout": 300
#     })
