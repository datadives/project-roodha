import aws_cdk as cdk
from dynamodb_stack import MyTwoTables

app = cdk.App()
MyTwoTables(app, "MyTwoTablesStack")
app.synth()