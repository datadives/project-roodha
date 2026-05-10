"""
PROJECT ROODHA - SECURITY & AUTHENTICATION
FILE: auth_middleware.py
PURPOSE: Implements JWT verification for AWS Cognito and multi-tenant context enforcement.
         Ensures data isolation by validating tenant-id headers against JWT claims.
"""

import os
import re
import time
from functools import wraps
from typing import List, Callable

import httpx
from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from jose import JWTError, jwt
from sqlalchemy import select
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.status import HTTP_401_UNAUTHORIZED, HTTP_403_FORBIDDEN

from app.core.tenant_context import (
    tenant_id_context, 
    user_id_context, 
    tenant_short_code_context
)
from app.database import AsyncSessionLocal
from app.models import Tenant, User

# --- SECURITY CONSTANTS ---
JWKS_CACHE_TTL_SECONDS = 60 * 60
_jwks_cache: dict[str, object] = {"value": None, "expires_at": 0}

# ---------------------------------------------------------
# --- COGNITO INTEGRATION UTILITIES ---
# ---------------------------------------------------------

def _is_development() -> bool:
    return os.getenv("ENV", "development").lower() == "development"

def _get_cognito_pool_id() -> str:
    pool_id = os.getenv("COGNITO_USER_POOL_ID") or os.getenv("VITE_COGNITO_USER_POOL_ID")
    if not pool_id:
        raise RuntimeError("COGNITO_USER_POOL_ID is not configured")
    return pool_id

def _get_cognito_client_id() -> str:
    client_id = (
        os.getenv("COGNITO_APP_CLIENT_ID")
        or os.getenv("COGNITO_CLIENT_ID")
        or os.getenv("COGNITO_USER_POOL_CLIENT_ID")
        or os.getenv("VITE_COGNITO_CLIENT_ID")
        or os.getenv("VITE_COGNITO_USER_POOL_CLIENT_ID")
    )
    if not client_id:
        raise RuntimeError("COGNITO_APP_CLIENT_ID is not configured")
    return client_id

def _get_cognito_region(pool_id: str) -> str:
    configured_region = os.getenv("COGNITO_REGION") or os.getenv("AWS_REGION")
    if configured_region:
        return configured_region
    if "_" not in pool_id:
        raise RuntimeError("COGNITO_REGION is not configured and could not be derived from pool id")
    return pool_id.split("_", 1)[0]

def _get_cognito_issuer(region: str, pool_id: str) -> str:
    return f"https://cognito-idp.{region}.amazonaws.com/{pool_id}"

async def _get_jwks(issuer: str) -> dict:
    """Retrieves and caches the JSON Web Key Set from Cognito for token validation."""
    now = time.time()
    cached_value = _jwks_cache.get("value")
    expires_at = float(_jwks_cache.get("expires_at") or 0)
    if cached_value and now < expires_at:
        return cached_value  # type: ignore[return-value]

    async with httpx.AsyncClient() as client:
        response = await client.get(f"{issuer}/.well-known/jwks.json", timeout=10)
        response.raise_for_status()
        payload = response.json()
        _jwks_cache["value"] = payload
        _jwks_cache["expires_at"] = now + JWKS_CACHE_TTL_SECONDS
        return payload

# ---------------------------------------------------------
# --- TOKEN DECODING & VALIDATION ---
# ---------------------------------------------------------

async def _decode_verified_token(token: str) -> dict:
    """Verifies signature, issuer, and claims of a Cognito ID token."""
    pool_id = _get_cognito_pool_id()
    client_id = _get_cognito_client_id()
    region = _get_cognito_region(pool_id)
    issuer = _get_cognito_issuer(region, pool_id)
    jwks = await _get_jwks(issuer)
    headers = jwt.get_unverified_header(token)
    kid = headers.get("kid")
    key = next((item for item in jwks.get("keys", []) if item.get("kid") == kid), None)
    if not key:
        raise JWTError("Unable to find matching Cognito signing key")

    payload = jwt.decode(
        token,
        key,
        algorithms=[key.get("alg", "RS256"), "RS256"],
        audience=client_id,
        issuer=issuer,
        options={"verify_at_hash": False},
    )
    token_use = payload.get("token_use")
    if token_use != "id":
        raise JWTError(f"Expected Cognito ID token in Authorization header, got token_use={token_use!r}")
    tenant_id = payload.get("custom:tenant_id") or payload.get("tenant_id")
    if not tenant_id:
        # Some live Cognito pools do not allow custom attributes during self-signup.
        # In that case, use a deterministic tenant derived from the verified email.
        email_seed = payload.get("email") or payload.get("cognito:username") or payload.get("username")
        if not email_seed:
            raise JWTError('Token missing required claim "custom:tenant_id"')
        tenant_id = re.sub(r"[^A-Za-z0-9]", "", email_seed.split("@", 1)[0]).lower() or "default"
        payload["tenant_id"] = tenant_id
    return payload

# ---------------------------------------------------------
# --- TENANT & USER PROVISIONING ---
# ---------------------------------------------------------

def _build_short_code_seed(tenant_id: str) -> str:
    seed = re.sub(r"[^A-Za-z0-9]", "", tenant_id or "").upper()
    return (seed or "TENANT")[:10]

async def _ensure_tenant_exists(db, tenant_id: str, company_name: str) -> str:
    """Ensures a Tenant record exists in the local database for RLS consistency."""
    tenant_short_code = await db.scalar(
        select(Tenant.short_code).where(Tenant.tenant_id == tenant_id)
    )
    if tenant_short_code:
        return tenant_short_code

    base_short_code = _build_short_code_seed(tenant_id)
    tenant_short_code = base_short_code

    for attempt in range(1, 100):
        existing_tenant = await db.scalar(
            select(Tenant.tenant_id).where(Tenant.short_code == tenant_short_code)
        )
        if not existing_tenant:
            db.add(
                Tenant(
                    tenant_id=tenant_id,
                    company_name=company_name,
                    short_code=tenant_short_code,
                    subscription_plan="free",
                )
            )
            await db.commit()
            return tenant_short_code

        suffix = str(attempt)
        tenant_short_code = f"{base_short_code[: 10 - len(suffix)]}{suffix}"

    raise RuntimeError(f"Unable to allocate a tenant short code for tenant '{tenant_id}'")

async def _user_from_claims(payload: dict) -> dict | None:
    """Maps Cognito claims to the internal application User model."""
    groups = payload.get("cognito:groups") or []
    role = (
        payload.get("custom:role")
        or payload.get("custom:user_role")
        or payload.get("role")
        or payload.get("user_role")
        or (groups[0] if groups else None)
        or "OPERATOR"
    )
    tenant_id = payload.get("custom:tenant_id") or payload.get("tenant_id")
    user_id = payload.get("sub") or payload.get("cognito:username") or payload.get("username")
    if not user_id:
        raise JWTError('Token missing required user identifier claim "sub"')
    user_email = payload.get("email") or payload.get("username") or ""
    company_name = payload.get("custom:company_name") or tenant_id
    machine_id = payload.get("custom:machine_id") or payload.get("machine_id")

    async with AsyncSessionLocal() as db:
        tenant_short_code = await _ensure_tenant_exists(db, tenant_id, company_name)

        db_role = await db.scalar(
            select(User.role).where(
                User.tenant_id == tenant_id,
                User.user_id == user_id,
            )
        )
        if db_role:
            role = db_role
        else:
            db.add(
                User(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    email=user_email,
                    role=str(role).upper(),
                )
            )
            await db.commit()

    return {
        "user_id": user_id,
        "email": user_email,
        "tenant_id": tenant_id,
        "tenant_short_code": tenant_short_code,
        "company_name": company_name,
        "machine_id": machine_id,
        "role": str(role).upper(),
    }

# ---------------------------------------------------------
# --- RBAC & ACCESS CONTROL ---
# ---------------------------------------------------------

def role_required(allowed_roles: List[str]) -> Callable:
    """
    Decorator to enforce Role-Based Access Control on FastAPI routes.
    Must be used on routes where the Request object is available in kwargs.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            request: Request = kwargs.get("request")
            if not request:
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break
            
            if not request:
                raise RuntimeError("Request object missing from decorated route.")

            user = getattr(request.state, "user", None)
            if not user:
                return _unauthorized("Authentication required")

            user_role = str(user.get("role", "")).upper()
            if user_role not in [role.upper() for role in allowed_roles]:
                return _forbidden(f"Role '{user_role}' unauthorized for this action")

            return await func(*args, **kwargs)
        return wrapper
    return decorator


def require_roles(allowed_roles: List[str]) -> Callable:
    """
    FastAPI dependency factory for strict RBAC.

    Usage:
        user = Depends(require_roles(["OWNER", "SUPERVISOR"]))

    The JWT middleware must already have validated the Cognito ID token and
    populated request.state.user from the custom:role/custom:user_role claim.
    """
    normalized_allowed_roles = {str(role).upper() for role in allowed_roles}

    def dependency(request: Request) -> dict:
        user = getattr(request.state, "user", None)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
            )

        user_role = str(user.get("role") or "").upper()
        if user_role not in normalized_allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{user_role or 'UNKNOWN'}' unauthorized for this action",
            )

        return user

    return dependency

# ---------------------------------------------------------
# --- MIDDLEWARE IMPLEMENTATION ---
# ---------------------------------------------------------

def _unauthorized(detail: str):
    return JSONResponse(
        status_code=HTTP_401_UNAUTHORIZED,
        content={"detail": detail}
    )

def _forbidden(detail: str):
    return JSONResponse(
        status_code=HTTP_403_FORBIDDEN,
        content={"detail": detail}
    )

def _extract_bearer_token(request: Request) -> tuple[str | None, str | None]:
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return None, "Authorization header missing"

    parts = auth_header.strip().split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None, "Authorization header must be formatted as 'Bearer <token>'"

    token = parts[1].strip()
    if not token or token.lower() in {"undefined", "null"}:
        return None, "Bearer token missing"

    return token, None

class JWTAuthMiddleware(BaseHTTPMiddleware):
    """
    Primary multi-tenancy shield. Verifies identity and ensures tenant isolation.
    Populates Thread-Safe context variables for deep service layer access.
    """
    async def dispatch(self, request: Request, call_next):
        if request.method == "OPTIONS":
            return await call_next(request)

        public_paths = {
            "/health", "/ready", "/api/health", "/api/ready", "/api/debug/db-check",
            "/docs", "/openapi.json", "/redoc",
            "/maintenance/batch-costing",
        }
        if request.url.path in public_paths or request.url.path.startswith("/maintenance"):
            return await call_next(request)

        token, token_error = _extract_bearer_token(request)
        if token_error:
            return _unauthorized(token_error)

        # --- DEV BYPASS ---
        allow_dev_pass = os.getenv("ALLOW_DEV_PASS", "false").lower() == "true"
        dev_token = os.getenv("DEV_PASS_TOKEN", "roodha-dev-test-123")
        
        if allow_dev_pass and token == dev_token:
            # Inject a mock user for development
            tenant_id = (request.headers.get("X-Tenant-ID") or os.getenv("VITE_DEV_TENANT_ID") or "tenant-123").strip()
            user = {
                "user_id": "dev-user-id",
                "email": "dev@example.com",
                "tenant_id": tenant_id,
                "tenant_short_code": "DEV",
                "company_name": "Dev Company",
                "role": (request.headers.get("X-Dev-Role") or "OWNER").upper(),
            }
        else:
            if token.count(".") != 2:
                return _unauthorized("Bearer token is not a JWT")
            try:
                # --- MULTI-TENANCY SHIELD ---
                # Enforce X-Tenant-ID consistency check between Header and JWT Claim.
                claims = await _decode_verified_token(token)
                jwt_tenant_id = claims.get("custom:tenant_id") or claims.get("tenant_id")

                if request.url.path.startswith("/api/"):
                    header_tenant_id = (request.headers.get("X-Tenant-ID") or "").strip()
                    if not header_tenant_id:
                        return _unauthorized("Tenant ID header missing")
                    if header_tenant_id != jwt_tenant_id:
                        return _forbidden("Cross-tenant access attempt blocked")

                user = await _user_from_claims(claims)
            except Exception as exc:
                return _unauthorized(f"Security validation failed: {str(exc)}")

        if not user:
            return _unauthorized("Identity resolution failed")

        tenant_id = user.get("tenant_id")
        user_id = user.get("user_id")
        tenant_short_code = user.get("tenant_short_code")

        # Set Global Context for RLS and Auditing
        token_tid = tenant_id_context.set(tenant_id)
        token_uid = user_id_context.set(user_id)
        token_tsc = tenant_short_code_context.set(tenant_short_code)
        
        request.state.user = user
        
        try:
            response = await call_next(request)
        finally:
            # Prevent context leakage across async tasks
            tenant_id_context.reset(token_tid)
            user_id_context.reset(token_uid)
            tenant_short_code_context.reset(token_tsc)
            
        return response
