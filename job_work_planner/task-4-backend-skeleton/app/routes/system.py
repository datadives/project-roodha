"""
system.py
 
This file contains system-level routes like:
- health check
- readiness check
- user identity
- tenant context
 
These routes are used by:
- Load balancers
- API Gateway
- Authentication layer
"""
 
from fastapi import APIRouter, Request, HTTPException
 
# Create a router object
router = APIRouter()
 
# -------------------------------------------------------
# PUBLIC ENDPOINT
# -------------------------------------------------------
 
@router.get("/health")
def health_check():
    """
    Health check endpoint.
    This is used by:
    - Load balancer
    - API Gateway
    - Monitoring tools
 
    No authentication required.
    """
    return {
        "status": "ok",
        "service": "jobwork-backend"
    }
 
 
@router.get("/ready")
def readiness_check():
    """
    Readiness endpoint.
 
    Used to check whether the application is ready
    to receive traffic.
 
    Dependencies are MOCKED for now.
    """
    return {
        "status": "ready",
        "dependencies": {
            "database": "not_checked",
            "s3": "not_checked"
        }
    }
 
 
# -------------------------------------------------------
# AUTH HELPER (MOCK JWT VALIDATION)
# -------------------------------------------------------
 
def get_user_from_jwt(request: Request):
    """
    MOCK JWT validation logic.
 
    In real life:
    - Token will be validated using Cognito
    - Signature + expiry will be checked
 
    For now:
    - We only check if Authorization header exists
    """
 
    auth_header = request.headers.get("Authorization")
 
    if not auth_header:
        raise HTTPException(
            status_code=401,
            detail="Authorization header missing"
        )
 
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Invalid Authorization header format"
        )
 
    # Mock user extracted from token
    return {
        "user_id": "mock-user-id",
        "email": "mock.user@jobwork.com"
    }
 
 
# -------------------------------------------------------
# PROTECTED ENDPOINTS
# -------------------------------------------------------
 
@router.get("/me")
def get_current_user(request: Request):
    """
    Returns logged-in user info.
 
    Requires JWT.
    """
    user = get_user_from_jwt(request)
 
    return {
        "message": "JWT received successfully",
        "user": user
    }
 
 
@router.get("/tenant/current")
def get_current_tenant(request: Request):
    """
    Returns current tenant context.
 
    This is IMPORTANT for multi-tenant SaaS systems.
 
    Requires JWT.
    """
    user = get_user_from_jwt(request)
 
    # Mock tenant info
    tenant = {
        "tenant_id": "tenant-123",
        "tenant_name": "Demo Company Pvt Ltd",
        "plan": "trial"
    }
 
    return {
        "user": user,
        "tenant": tenant
    }