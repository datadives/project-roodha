"""
/**
 * PROJECT ROODHA - v1.5.7 "Gold Baseline"
 * File: auth.py
 * 
 * 1) Purpose: Defines API endpoints for auth.
 * 2) Roadmap Connection: This file is a critical component of the Stage 2 (v1.5) Industrial 
 *    Hardening phase. It enforces multi-tenancy, security (RBAC), and transactional 
 *    resilience as defined in the formal Roadmap.
 */
"""
import os
import secrets
import string
import boto3
from fastapi import APIRouter, Request, HTTPException, status
from fastapi import Depends
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_middleware import _ensure_tenant_exists, require_roles
from app.core.tenant_context import tenant_id_context
from app.database import get_async_db
from app.models import Tenant, User
from app.routes.response_utils import api_success

router = APIRouter()

class DevConfirmSignUp(BaseModel):
    email: EmailStr


class TenantProvisionResponse(BaseModel):
    tenant_id: str
    company_name: str
    short_code: str | None = None
    role: str
    email: EmailStr | str
    created: bool


class UserInviteRequest(BaseModel):
    email: EmailStr
    role: str = Field(pattern="^(SUPERVISOR|OPERATOR)$")
    machine_id: str | None = None


class UserInviteResponse(BaseModel):
    email: EmailStr
    role: str
    tenant_id: str
    machine_id: str | None = None
    cognito_username: str
    delivery_medium: str = "EMAIL"


def _get_cognito_region() -> str:
    return (
        os.getenv("COGNITO_REGION")
        or os.getenv("AWS_REGION")
        or os.getenv("AWS_DEFAULT_REGION")
        or "us-east-1"
    )


def _generate_temporary_password(length: int = 18) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    while True:
        password = "".join(secrets.choice(alphabet) for _ in range(length))
        if (
            any(char.islower() for char in password)
            and any(char.isupper() for char in password)
            and any(char.isdigit() for char in password)
            and any(char in "!@#$%^&*" for char in password)
        ):
            return password

@router.post("/auth/dev-confirm-signup")
async def dev_confirm_signup(payload: DevConfirmSignUp, request: Request):
    """
    Bypass OTP/Verification in development environments only.
    Requires ALLOW_DEV_PASS=true in environment.
    """
    allow_dev_pass = os.getenv("ALLOW_DEV_PASS", "false").lower() == "true"
    if not allow_dev_pass:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Development bypass restricted in production"
        )

    pool_id = os.getenv("COGNITO_USER_POOL_ID")
    region = os.getenv("COGNITO_REGION", "ap-south-1")

    if not pool_id:
        raise HTTPException(status_code=500, detail="COGNITO_USER_POOL_ID not configured")

    client = boto3.client("cognito-idp", region_name=region)
    try:
        client.admin_confirm_sign_up(
            UserPoolId=pool_id,
            Username=payload.email
        )
        return api_success(None, message=f"User {payload.email} verified successfully (Admin Bypass)")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/users/me")
def get_user_profile(current_user: dict = Depends(require_roles(["OWNER", "SUPERVISOR", "OPERATOR"]))):
    """Standardized frontend session handshake endpoint."""
    return api_success({"user": current_user}, message="User profile retrieved")


@router.post("/tenants/create")
async def create_tenant_workspace(request: Request, db: AsyncSession = Depends(get_async_db)):
    user = getattr(request.state, "user", None)
    if not user or not user.get("tenant_id") or not user.get("user_id"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    tenant_id = user["tenant_id"]
    company_name = user.get("company_name") or user.get("email") or tenant_id
    token_role = str(user.get("role") or "OPERATOR").upper()
    user_id = user["user_id"]
    user_email = user.get("email") or ""

    tenant_id_context.set(tenant_id)
    existing_tenant = await db.scalar(select(Tenant.tenant_id).where(Tenant.tenant_id == tenant_id))
    short_code = await _ensure_tenant_exists(db, tenant_id, company_name)

    existing_user = await db.scalar(
        select(User).where(
            User.tenant_id == tenant_id,
            User.user_id == user_id,
        )
    )

    tenant_users = (
        await db.execute(select(User).where(User.tenant_id == tenant_id))
    ).scalars().all()

    provisioned_role = str(existing_user.role).upper() if existing_user else token_role
    if (not tenant_users or (len(tenant_users) == 1 and existing_user)) and provisioned_role == "OPERATOR":
        provisioned_role = "OWNER"

    if not existing_user:
        db.add(
            User(
                tenant_id=tenant_id,
                user_id=user_id,
                email=user_email,
                role=provisioned_role,
            )
        )
        await db.commit()
    elif str(existing_user.role).upper() != provisioned_role:
        existing_user.role = provisioned_role
        await db.commit()

    tenant = await db.scalar(select(Tenant).where(Tenant.tenant_id == tenant_id))
    response = TenantProvisionResponse(
        tenant_id=tenant_id,
        company_name=tenant.company_name if tenant else company_name,
        short_code=tenant.short_code if tenant else short_code,
        role=provisioned_role,
        email=user_email,
        created=existing_tenant is None,
    )
    return api_success(response.model_dump(), message="Tenant workspace provisioned")


@router.post("/users/invite")
async def invite_user(
    payload: UserInviteRequest,
    owner: dict = Depends(require_roles(["OWNER"])),
    db: AsyncSession = Depends(get_async_db),
):
    tenant_id = owner["tenant_id"]
    role = payload.role.upper()
    machine_id = payload.machine_id if role == "OPERATOR" and payload.machine_id else None

    pool_id = os.getenv("COGNITO_USER_POOL_ID")
    if not pool_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="COGNITO_USER_POOL_ID not configured",
        )

    user_attributes = [
        {"Name": "email", "Value": str(payload.email)},
        {"Name": "email_verified", "Value": "true"},
        {"Name": "custom:tenant_id", "Value": tenant_id},
        {"Name": "custom:role", "Value": role},
    ]
    if machine_id:
        user_attributes.append({"Name": "custom:machine_id", "Value": machine_id})

    client = boto3.client("cognito-idp", region_name=_get_cognito_region())
    try:
        result = client.admin_create_user(
            UserPoolId=pool_id,
            Username=str(payload.email),
            UserAttributes=user_attributes,
            TemporaryPassword=_generate_temporary_password(),
            DesiredDeliveryMediums=["EMAIL"],
        )
    except client.exceptions.UsernameExistsException:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A Cognito user already exists for this email.",
        )
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    cognito_username = result.get("User", {}).get("Username") or str(payload.email)
    existing_user = await db.scalar(
        select(User).where(
            User.tenant_id == tenant_id,
            User.email == str(payload.email),
        )
    )
    if existing_user:
        existing_user.role = role
    else:
        db.add(
            User(
                tenant_id=tenant_id,
                user_id=cognito_username,
                email=str(payload.email),
                role=role,
            )
        )
    await db.commit()

    response = UserInviteResponse(
        email=payload.email,
        role=role,
        tenant_id=tenant_id,
        machine_id=machine_id,
        cognito_username=cognito_username,
    )
    return api_success(response.model_dump(), message="Employee invite sent")
