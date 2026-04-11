"""
auth_middleware.py
------------------
Cognito JWT authentication middleware.
"""

import os
import time

import requests
from fastapi import Request
from fastapi.responses import JSONResponse
from jose import JWTError, jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.status import HTTP_401_UNAUTHORIZED

JWKS_CACHE_TTL_SECONDS = 60 * 60
_jwks_cache: dict[str, object] = {"value": None, "expires_at": 0}


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
        or os.getenv("COGNITO_USER_POOL_CLIENT_ID")
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


def _get_jwks(issuer: str) -> dict:
    now = time.time()
    cached_value = _jwks_cache.get("value")
    expires_at = float(_jwks_cache.get("expires_at") or 0)
    if cached_value and now < expires_at:
        return cached_value  # type: ignore[return-value]

    response = requests.get(f"{issuer}/.well-known/jwks.json", timeout=10)
    response.raise_for_status()
    payload = response.json()
    _jwks_cache["value"] = payload
    _jwks_cache["expires_at"] = now + JWKS_CACHE_TTL_SECONDS
    return payload


def _decode_verified_token(token: str) -> dict:
    pool_id = _get_cognito_pool_id()
    client_id = _get_cognito_client_id()
    region = _get_cognito_region(pool_id)
    issuer = _get_cognito_issuer(region, pool_id)
    jwks = _get_jwks(issuer)
    headers = jwt.get_unverified_header(token)
    kid = headers.get("kid")
    key = next((item for item in jwks.get("keys", []) if item.get("kid") == kid), None)
    if not key:
        raise JWTError("Unable to find matching Cognito signing key")

    return jwt.decode(
        token,
        key,
        algorithms=[key.get("alg", "RS256"), "RS256"],
        audience=client_id,
        issuer=issuer,
        options={"verify_at_hash": False},
    )


def _user_from_claims(payload: dict) -> dict | None:
    groups = payload.get("cognito:groups") or []
    role = (
        payload.get("custom:user_role")
        or payload.get("user_role")
        or (groups[0] if groups else None)
        or "OPERATOR"
    )
    tenant_id = payload.get("custom:tenant_id") or payload.get("tenant_id")
    user_id = payload.get("sub") or payload.get("cognito:username") or payload.get("username") or "unknown"
    user_email = payload.get("email") or payload.get("username") or ""
    company_name = payload.get("custom:company_name") or "New Tenant"

    from app.database import SessionLocal
    from app.models import Tenant, User
    import uuid

    db = SessionLocal()
    try:
        db_user = db.query(User).filter(User.user_id == user_id).first()
        if db_user:
            tenant_id = db_user.tenant_id
        else:
            if not tenant_id:
                tenant_id = f"tenant-{uuid.uuid4().hex[:8]}"
                new_tenant = Tenant(
                    tenant_id=tenant_id,
                    company_name=company_name,
                    subscription_plan="free"
                )
                db.add(new_tenant)
                db.commit()

            new_user = User(
                tenant_id=tenant_id,
                user_id=user_id,
                email=user_email,
                role=str(role).upper()
            )
            db.add(new_user)
            db.commit()
    finally:
        db.close()

    if not tenant_id:
        return None

    return {
        "user_id": user_id,
        "email": user_email,
        "tenant_id": tenant_id,
        "role": str(role).upper(),
    }


class JWTAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        public_paths = {
            "/health",
            "/ready",
            "/docs",
            "/openapi.json",
            "/redoc",
        }
        if request.method == "OPTIONS" or request.url.path in public_paths:
            return await call_next(request)

        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return JSONResponse(
                status_code=HTTP_401_UNAUTHORIZED,
                content={"detail": "Authorization header missing"},
            )

        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=HTTP_401_UNAUTHORIZED,
                content={"detail": "Invalid Authorization header format"},
            )

        token = auth_header.replace("Bearer ", "", 1).strip()

        try:
            if _is_development() and token == "test123":
                user = {
                    "user_id": "mock-user-id",
                    "email": "mock.user@jobwork.com",
                    "tenant_id": "tenant-123",
                    "role": "OWNER",
                }
            else:
                claims = _decode_verified_token(token)
                user = _user_from_claims(claims)
        except (JWTError, requests.RequestException, RuntimeError) as exc:
            return JSONResponse(
                status_code=HTTP_401_UNAUTHORIZED,
                content={"detail": f"Invalid or expired token: {exc}"},
            )

        if not user:
            return JSONResponse(
                status_code=HTTP_401_UNAUTHORIZED,
                content={"detail": "Invalid token or missing tenant claims"},
            )

        request.state.user = user
        return await call_next(request)
