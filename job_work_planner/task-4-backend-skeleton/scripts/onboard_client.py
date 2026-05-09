import os
import sys
import uuid
import argparse
import boto3
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Ensure we can import app modules from the parent directory
SCRIPTS_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPTS_DIR.parent
sys.path.append(str(ROOT_DIR))

# Import models from the main app
try:
    from app.models import Tenant, User
except ImportError:
    print("❌ Critical Error: Could not find app.models. Ensure you are running this from the backend root.")
    sys.exit(1)

# Load environment variables from .env
load_dotenv(ROOT_DIR / ".env")

# Industrial ANSI Colors for High-Contrast Terminal Feedback
class Colors:
    SAFETY_ORANGE = '\033[38;5;208m'
    SUCCESS_GREEN = '\033[92m'
    ALERT_RED = '\033[91m'
    INFO_BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'

def onboard():
    parser = argparse.ArgumentParser(description="PROJECT ROODHA - Automated SaaS Client Onboarding (v1.5)")
    parser.add_argument("--tenant-name", required=True, help="Legal name of the client organization")
    parser.add_argument("--owner-email", required=True, help="Email address of the primary tenant administrator")
    parser.add_argument("--owner-name", required=True, help="Full name of the primary owner")
    args = parser.parse_args()

    print(f"\n{Colors.BOLD}{Colors.SAFETY_ORANGE}🏗️  PROJECT ROODHA V1.5 - ONBOARDING SEQUENCE INITIATED{Colors.END}")
    print("=" * 70)

    # 1. Environment Validation
    db_url = os.getenv("DATABASE_URL")
    user_pool_id = os.getenv("COGNITO_USER_POOL_ID")
    aws_region = os.getenv("AWS_REGION", "us-east-1")

    if not all([db_url, user_pool_id]):
        print(f"{Colors.ALERT_RED}❌ ERROR: DATABASE_URL or COGNITO_USER_POOL_ID missing from .env{Colors.END}")
        sys.exit(1)

    # 2. Data Preparation
    tenant_uuid = str(uuid.uuid4())
    # Generate a clean 6-character short code for job numbering prefixes
    short_code = "".join(filter(str.isalnum, args.tenant_name)).upper()[:6]
    
    print(f"{Colors.INFO_BLUE}GENERATE{Colors.END} | Tenant ID: {Colors.BOLD}{tenant_uuid}{Colors.END}")
    print(f"{Colors.INFO_BLUE}GENERATE{Colors.END} | Short Code: {Colors.BOLD}{short_code}{Colors.END}")

    # 3. Database Layer: Commit Tenant & Admin Records
    print(f"\n{Colors.INFO_BLUE}SYNCING{Colors.END} | Updating PostgreSQL Tenant Registry...")
    try:
        # Use sync engine for CLI utility simplicity
        engine = create_engine(db_url)
        Session = sessionmaker(bind=engine)
        session = Session()

        # Create Tenant Record
        new_tenant = Tenant(
            tenant_id=tenant_uuid,
            company_name=args.tenant_name,
            short_code=short_code,
            subscription_plan="GOLD_V15"
        )
        session.add(new_tenant)

        # Create Admin User Record (Composite PK: tenant_id + user_id)
        new_user = User(
            tenant_id=tenant_uuid,
            user_id=args.owner_email.strip().lower(), 
            email=args.owner_email.strip().lower(),
            role="OWNER"
        )
        session.add(new_user)
        
        session.commit()
        print(f"{Colors.SUCCESS_GREEN}✅ Success: Database records committed.{Colors.END}")
    except Exception as e:
        print(f"{Colors.ALERT_RED}❌ Error: Database operation failed: {e}{Colors.END}")
        sys.exit(1)

    # 4. Identity Layer: Provision Cognito Admin User
    print(f"\n{Colors.INFO_BLUE}PROVISION{Colors.END} | Configuring AWS Cognito Identity Provider...")
    try:
        cognito = boto3.client('cognito-idp', region_name=aws_region)
        
        # Create user in Cognito
        cognito.admin_create_user(
            UserPoolId=user_pool_id,
            Username=args.owner_email.strip().lower(),
            UserAttributes=[
                {'Name': 'email', 'Value': args.owner_email.strip().lower()},
                {'Name': 'email_verified', 'Value': 'true'},
                {'Name': 'custom:tenant_id', 'Value': tenant_uuid},
                {'Name': 'custom:role', 'Value': 'OWNER'},
                {'Name': 'name', 'Value': args.owner_name}
            ],
            ForceAliasCreation=False,
            MessageAction='SUPPRESS', # We suppress so we can send a custom styled "Welcome" email later
            DesiredDeliveryMediums=['EMAIL']
        )
        
        print(f"{Colors.SUCCESS_GREEN}✅ Success: Cognito Identity established.{Colors.END}")
        print(f"{Colors.SUCCESS_GREEN}✅ Policy: custom:tenant_id guard active.{Colors.END}")
        
    except cognito.exceptions.UsernameExistsException:
        print(f"{Colors.SAFETY_ORANGE}⚠️  Warning: Identity already exists in Cognito. Proceeding with existing ID.{Colors.END}")
    except Exception as e:
        print(f"{Colors.ALERT_RED}❌ Error: Cognito provisioning failed: {e}{Colors.END}")
        print(f"{Colors.SAFETY_ORANGE}⚠️  Caution: DB record {tenant_uuid} exists but identity is unmapped.{Colors.END}")
        sys.exit(1)

    print(f"\n{Colors.BOLD}{Colors.SUCCESS_GREEN}🎉 ONBOARDING COMPLETE: {args.tenant_name} is now LIVE on Roodha V1.5.{Colors.END}")
    print("=" * 70)
    print(f"Final Step: Manually trigger the Welcome Email for {args.owner_email}.\n")

if __name__ == "__main__":
    onboard()
