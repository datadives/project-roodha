import boto3
import json
import logging
import uuid

logger = logging.getLogger()
logger.setLevel(logging.INFO)

cognito = boto3.client('cognito-idp')

def lambda_handler(event, context):
    logger.info(f"Received event: {json.dumps(event)}")
    
    user_pool_id = event['userPoolId']
    username = event['userName']
    user_attributes = event['request']['userAttributes']
    
    updates = []
    
    # Check for custom:user_role
    if 'custom:user_role' not in user_attributes:
        logger.info("Setting custom:user_role to USER")
        updates.append({'Name': 'custom:user_role', 'Value': 'USER'})
    
    # Check for custom:tenant_id
    if 'custom:tenant_id' not in user_attributes:
        tenant_id = f"tenant-{uuid.uuid4().hex[:8]}"
        logger.info(f"Setting custom:tenant_id to {tenant_id}")
        updates.append({'Name': 'custom:tenant_id', 'Value': tenant_id})
    
    if updates:
        try:
            cognito.admin_update_user_attributes(
                UserPoolId=user_pool_id,
                Username=username,
                UserAttributes=updates
            )
            logger.info("Successfully updated user attributes")
        except Exception as e:
            logger.error(f"Error updating user attributes: {str(e)}")
            # We don't want to fail the sign-up confirmation, so we just log the error
    
    return event
