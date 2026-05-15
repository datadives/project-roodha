"""
PROJECT ROODHA - SECURITY & AUTHENTICATION
FILE: auth_middleware.py
PURPOSE: Implements JWT verification for AWS Cognito and multi-tenant context enforcement.
         Ensures data isolation by validating tenant-id headers against JWT claims.
"""

import os
import re
import time
import asyncio
import json
import logging
import uuid
import base64
from functools import wraps
from typing import List, Callable

import httpx
from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse, Response
from jose import JWTError, jwt
from sqlalchemy import func, or_, select, text
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
logger = logging.getLogger("jobwork-backend.auth")
_demo_store: dict[str, list[dict]] = {
    "customers": [
        {
            "customer_id": "11111111-1111-4111-8111-111111111111",
            "id": "11111111-1111-4111-8111-111111111111",
            "name": "Demo Customer",
            "contact_person": "Demo Buyer",
            "phone": "",
            "email": "buyer@example.com",
            "is_active": True,
        }
    ],
    "machines": [
        {
            "machine_id": "demo-machine-1",
            "id": "demo-machine-1",
            "name": "CNC-01",
            "code": "CNC-01",
            "is_active": True,
        }
    ],
    "shifts": [
        {
            "shift_id": "demo-shift-1",
            "id": "demo-shift-1",
            "name": "General Shift",
            "start_time": "09:00",
            "end_time": "18:00",
            "is_active": True,
        }
    ],
    "parts": [
        {
            "part_id": "22222222-2222-4222-8222-222222222222",
            "id": "22222222-2222-4222-8222-222222222222",
            "customer_id": "11111111-1111-4111-8111-111111111111",
            "part_number": "DEMO-PART-001",
            "name": "Demo Machined Part",
            "description": "Seeded demo part",
            "is_active": True,
            "default_operations_route": [],
        }
    ],
    "workers": [],
    "jobs": [],
    "job_operations": [],
}

# ---------------------------------------------------------
# --- COGNITO INTEGRATION UTILITIES ---
# ---------------------------------------------------------

def _runtime_env() -> str:
    return (os.getenv("ENV") or os.getenv("APP_ENV") or os.getenv("ENVIRONMENT") or "development").strip().lower()


def _is_local_runtime() -> bool:
    return _runtime_env() in {"local", "development", "dev", "test"}


def _is_production_runtime() -> bool:
    return _runtime_env() in {"production", "prod"}


def _allow_dev_pass() -> bool:
    if os.getenv("ALLOW_DEV_PASS", "false").lower() != "true":
        return False
    if not _is_local_runtime():
        logger.warning("ALLOW_DEV_PASS is ignored because ENV=%s is not a local runtime", _runtime_env())
        return False
    return True


def _allow_demo_api_stubs() -> bool:
    """Keep demo API stubs opt-in so dev auth still exercises the real database."""
    return _allow_dev_pass() and os.getenv("ENABLE_DEMO_API_STUBS", "false").lower() == "true"


def _allow_email_tenant_fallback() -> bool:
    return _is_local_runtime() and os.getenv("ALLOW_EMAIL_TENANT_FALLBACK", "false").lower() == "true"

def _get_cognito_pool_id() -> str:
    pool_id = (
        os.getenv("USER_POOL_ID")
        or os.getenv("COGNITO_USER_POOL_ID")
        or os.getenv("VITE_COGNITO_USER_POOL_ID")
    )
    if isinstance(pool_id, str):
        pool_id = pool_id.strip()
    if not pool_id:
        raise RuntimeError("USER_POOL_ID/COGNITO_USER_POOL_ID is not configured")
    return pool_id

def _get_cognito_client_id() -> str:
    client_id = (
        os.getenv("APP_CLIENT_ID")
        or os.getenv("COGNITO_APP_CLIENT_ID")
        or os.getenv("COGNITO_CLIENT_ID")
        or os.getenv("COGNITO_USER_POOL_CLIENT_ID")
        or os.getenv("VITE_COGNITO_CLIENT_ID")
        or os.getenv("VITE_COGNITO_USER_POOL_CLIENT_ID")
    )
    if isinstance(client_id, str):
        client_id = client_id.strip()
    if not client_id:
        raise RuntimeError("APP_CLIENT_ID/COGNITO_APP_CLIENT_ID is not configured")
    return client_id

def _get_cognito_region(pool_id: str) -> str:
    configured_region = os.getenv("REGION") or os.getenv("COGNITO_REGION") or os.getenv("AWS_REGION")
    if configured_region:
        return configured_region.strip()
    if "_" not in pool_id:
        raise RuntimeError("COGNITO_REGION is not configured and could not be derived from pool id")
    return pool_id.split("_", 1)[0].strip()

def _get_cognito_issuer(region: str, pool_id: str) -> str:
    return f"https://cognito-idp.{region}.amazonaws.com/{pool_id}"

def _load_jwks_from_env() -> dict | None:
    jwks_json = os.getenv("COGNITO_JWKS_JSON")
    if not jwks_json:
        return None

    try:
        parsed = json.loads(jwks_json)
        if isinstance(parsed, dict) and isinstance(parsed.get("keys"), list) and parsed["keys"]:
            _jwks_cache["value"] = parsed
            _jwks_cache["expires_at"] = time.time() + JWKS_CACHE_TTL_SECONDS
            return parsed
    except Exception as exc:  # noqa: BLE001
        logger.warning("COGNITO_JWKS_JSON is configured but invalid: %s", exc)
    return None

async def _get_jwks(issuer: str) -> dict:
    """Retrieves and caches the JSON Web Key Set from Cognito for token validation."""
    now = time.time()
    cached_value = _jwks_cache.get("value")
    expires_at = float(_jwks_cache.get("expires_at") or 0)
    if cached_value and now < expires_at:
        return cached_value  # type: ignore[return-value]

    env_jwks = _load_jwks_from_env()
    if env_jwks:
        return env_jwks

    last_error = None
    for attempt in range(3):
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{issuer}/.well-known/jwks.json", timeout=10)
                response.raise_for_status()
                payload = response.json()
                _jwks_cache["value"] = payload
                _jwks_cache["expires_at"] = time.time() + JWKS_CACHE_TTL_SECONDS
                return payload
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt < 2:
                await asyncio.sleep(0.6 * (attempt + 1))

    # Fallback to stale JWKS cache if available during transient DNS/network failures.
    if cached_value:
        return cached_value  # type: ignore[return-value]

    raise RuntimeError(f"Unable to fetch Cognito JWKS from issuer '{issuer}': {last_error}")

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
        if not _allow_email_tenant_fallback():
            raise JWTError('Token missing required claim "custom:tenant_id"')
        email_seed = payload.get("email") or payload.get("cognito:username") or payload.get("username")
        if not email_seed:
            raise JWTError('Token missing required claim "custom:tenant_id"')
        tenant_id = re.sub(r"[^A-Za-z0-9]", "", email_seed.split("@", 1)[0]).lower() or "default"
        payload["tenant_id"] = tenant_id
    return payload

# ---------------------------------------------------------
# --- TENANT & USER PROVISIONING ---
# ---------------------------------------------------------

def _identity_fields_from_claims(payload: dict) -> dict:
    groups = payload.get("cognito:groups") or []
    role = (
        payload.get("custom:user_role")
        or payload.get("custom:role")
        or payload.get("user_role")
        or payload.get("role")
        or (groups[0] if groups else None)
        or "OPERATOR"
    )
    tenant_id = payload.get("custom:tenant_id") or payload.get("tenant_id")
    user_id = payload.get("sub") or payload.get("cognito:username") or payload.get("username")
    if not user_id:
        raise JWTError('Token missing required user identifier claim "sub"')

    return {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "email": payload.get("email") or payload.get("username") or "",
        "company_name": payload.get("custom:company_name") or tenant_id,
        "machine_id": payload.get("custom:machine_id") or payload.get("machine_id"),
        "role": str(role).upper(),
    }

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
    identity = _identity_fields_from_claims(payload)
    role = identity["role"]
    tenant_id = identity["tenant_id"]
    user_id = identity["user_id"]
    user_email = identity["email"]
    company_name = identity["company_name"]
    machine_id = identity["machine_id"]

    async with AsyncSessionLocal() as db:
        if tenant_id:
            await db.execute(
                text("SELECT set_config('app.current_tenant', :tid, true)").bindparams(tid=tenant_id)
            )
        tenant_short_code = await _ensure_tenant_exists(db, tenant_id, company_name)

        db_user = await db.scalar(
            select(User).where(
                User.tenant_id == tenant_id,
                or_(
                    User.user_id == user_id,
                    func.lower(User.email) == str(user_email or "").strip().lower(),
                ),
            )
        )
        db_role = db_user.role if db_user else None
        if not db_role:
            db.add(
                User(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    email=user_email,
                    role=str(role).upper(),
                )
            )
            await db.commit()
            db_role = str(role).upper()
        elif db_user and db_user.user_id != user_id:
            db_user.user_id = user_id
            await db.commit()

    effective_role = str(db_role or role).upper()

    return {
        "user_id": user_id,
        "email": user_email,
        "tenant_id": tenant_id,
        "tenant_short_code": tenant_short_code,
        "company_name": company_name,
        "machine_id": machine_id,
        "role": effective_role,
        "db_role": effective_role,
        "user_role": effective_role,
        "userRole": effective_role,
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


def _api_success(data, message: str = "OK", status_code: int = 200) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"success": True, "data": data, "message": message},
    )


def _camel_or_snake(payload: dict, camel_key: str, snake_key: str, default=None):
    return payload.get(camel_key, payload.get(snake_key, default))


def _demo_job_card(job: dict) -> dict:
    return {
        "job_id": job["job_id"],
        "jobId": job["job_id"],
        "job_number": job["job_number"],
        "jobNumber": job["job_number"],
        "customer_id": job.get("customer_id"),
        "customerId": job.get("customer_id"),
        "customer_name": job.get("customer_name", "Demo Customer"),
        "customerName": job.get("customer_name", "Demo Customer"),
        "part_id": job.get("part_id"),
        "partId": job.get("part_id"),
        "part_number": job.get("part_number", "DEMO-PART-001"),
        "partNumber": job.get("part_number", "DEMO-PART-001"),
        "quantity": job.get("quantity", 1),
        "due_date": job.get("due_date"),
        "dueDate": job.get("due_date"),
        "priority": job.get("priority", "MEDIUM"),
        "status": job.get("status", "NOT_STARTED"),
        "current_stage": job.get("current_stage", "Cutting"),
        "currentStage": job.get("current_stage", "Cutting"),
        "alert_priority": job.get("alert_priority", "NORMAL"),
        "alertPriority": job.get("alert_priority", "NORMAL"),
        "delayed": False,
    }


def _demo_find_job(job_id: str) -> dict | None:
    return next((job for job in _demo_store["jobs"] if str(job.get("job_id")) == str(job_id)), None)


def _demo_find_operation(job_op_id: str) -> dict | None:
    return next(
        (operation for operation in _demo_store["job_operations"] if str(operation.get("job_op_id")) == str(job_op_id)),
        None,
    )


def _demo_metric_jobs() -> list[dict]:
    if _demo_store["jobs"]:
        return _demo_store["jobs"]

    return [
        {
            "job_id": "demo-metric-job-1",
            "jobId": "demo-metric-job-1",
            "tenant_id": "lalafactory",
            "job_number": "DEMO-0001",
            "jobNumber": "DEMO-0001",
            "customer_id": "11111111-1111-4111-8111-111111111111",
            "customerId": "11111111-1111-4111-8111-111111111111",
            "customer_name": "Demo Customer",
            "customerName": "Demo Customer",
            "part_id": "22222222-2222-4222-8222-222222222222",
            "partId": "22222222-2222-4222-8222-222222222222",
            "part_number": "DEMO-PART-001",
            "partNumber": "DEMO-PART-001",
            "quantity": 100,
            "due_date": time.strftime("%Y-%m-%d", time.gmtime(time.time() + 7 * 24 * 60 * 60)),
            "dueDate": time.strftime("%Y-%m-%d", time.gmtime(time.time() + 7 * 24 * 60 * 60)),
            "priority": "MEDIUM",
            "status": "NOT_STARTED",
            "alert_priority": "NORMAL",
            "alertPriority": "NORMAL",
            "operations": [
                {
                    "job_op_id": "demo-metric-op-1",
                    "jobOperationId": "demo-metric-op-1",
                    "machine_id": "demo-machine-1",
                    "machineId": "demo-machine-1",
                    "status": "NOT_STARTED",
                    "sequence_number": 1,
                    "sequenceNumber": 1,
                }
            ],
        }
    ]


def _demo_estimated_cost(job: dict) -> int:
    quantity = int(job.get("quantity") or 0)
    operation_count = max(len(job.get("operations") or []), 1)
    return quantity * operation_count * 125


def _demo_booked_hours(job: dict) -> float:
    quantity = max(int(job.get("quantity") or 0), 1)
    operation_count = max(len(job.get("operations") or []), 1)
    return round(operation_count * max(quantity / 50, 1), 2)


def _demo_stage_cards(jobs: list[dict]) -> dict[str, list[dict]]:
    cards = [_demo_job_card(job) for job in jobs]
    return {
        "not_started": [card for card in cards if card["status"] == "NOT_STARTED"],
        "in_progress": [card for card in cards if card["status"] == "IN_PROGRESS"],
        "waiting": [card for card in cards if card["status"] == "WAITING"],
        "completed": [card for card in cards if card["status"] == "COMPLETED"],
    }


def _demo_csv_download(filename: str, csv_text: str) -> dict:
    encoded = base64.b64encode(csv_text.encode("utf-8")).decode("ascii")
    download_url = f"data:text/csv;base64,{encoded}"
    return {
        "download_url": download_url,
        "downloadUrl": download_url,
        "filename": filename,
    }


async def _demo_response_for_request(request: Request, user: dict) -> JSONResponse | None:
    """Return lightweight demo data when the dev-pass session is active."""
    path = request.url.path
    method = request.method.upper()
    tenant_id = user.get("tenant_id") or "lalafactory"

    if path == "/api/users/me" and method == "GET":
        return _api_success({"user": user}, "User profile retrieved")

    if path == "/api/tenants/create" and method == "POST":
        return _api_success(
            {
                "tenant_id": tenant_id,
                "company_name": user.get("company_name") or "Demo Company",
                "short_code": "DEMO",
                "role": user.get("role") or "OWNER",
                "email": user.get("email") or "dev@example.com",
                "created": False,
            },
            "Tenant workspace provisioned",
        )

    if path == "/api/planning/machine-load" and method == "GET":
        metric_jobs = _demo_metric_jobs()
        booked_hours = round(sum(_demo_booked_hours(job) for job in metric_jobs if job.get("status") != "COMPLETED"), 2)
        return _api_success(
            {
                "machines": [
                    {
                        "machine_id": "demo-machine-1",
                        "machine_name": "CNC-01",
                        "booked_hours": booked_hours,
                        "available_hours": 8,
                        "utilization_percent": min(round((booked_hours / 8) * 100, 1), 999),
                        "pending_operations": sum(len(job.get("operations") or []) for job in metric_jobs),
                        "is_overloaded": booked_hours > 8,
                    }
                ]
            },
            "Machine load synchronized",
        )

    if path == "/api/kanban" and method == "GET":
        columns = _demo_stage_cards(_demo_metric_jobs())
        return _api_success(
            {
                "not_started": columns["not_started"],
                "in_progress": columns["in_progress"],
                "waiting": columns["waiting"],
                "completed": columns["completed"],
                "columns": columns,
            },
            "Kanban board synchronized successfully",
        )

    if path == "/api/jobs" and method == "GET":
        return _api_success(_demo_store["jobs"], f"{len(_demo_store['jobs'])} job(s) found")

    if path == "/api/jobs" and method == "POST":
        try:
            payload = await request.json()
        except Exception:  # noqa: BLE001
            payload = {}

        job_id = str(uuid.uuid4())
        job_op_id = str(uuid.uuid4())
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        customer_id = _camel_or_snake(payload, "customerId", "customer_id", _demo_store["customers"][0]["customer_id"])
        part_id = _camel_or_snake(payload, "partId", "part_id", _demo_store["parts"][0]["part_id"])
        customer = next((item for item in _demo_store["customers"] if item.get("customer_id") == customer_id), _demo_store["customers"][0])
        part = next((item for item in _demo_store["parts"] if item.get("part_id") == part_id), _demo_store["parts"][0])
        job_number = payload.get("jobNumber") or payload.get("job_number") or f"DEMO-{len(_demo_store['jobs']) + 1:04d}"
        operation = {
            "job_op_id": job_op_id,
            "jobOperationId": job_op_id,
            "tenant_id": tenant_id,
            "job_id": job_id,
            "jobId": job_id,
            "op_id": "33333333-3333-4333-8333-333333333333",
            "opId": "33333333-3333-4333-8333-333333333333",
            "operation_name": "Cutting",
            "operationName": "Cutting",
            "machine_id": "demo-machine-1",
            "machineId": "demo-machine-1",
            "worker_id": None,
            "workerId": None,
            "shift_id": None,
            "shiftId": None,
            "sequence_number": 1,
            "sequenceNumber": 1,
            "status": "NOT_STARTED",
            "actual_start_time": None,
            "actualStartTime": None,
            "actual_end_time": None,
            "actualEndTime": None,
            "planned_start_date": None,
            "plannedStartDate": None,
            "planned_end_date": None,
            "plannedEndDate": None,
            "quantity_completed": 0,
            "quantityCompleted": 0,
            "quantity_rejected": 0,
            "quantityRejected": 0,
        }
        due_date = _camel_or_snake(payload, "dueDate", "due_date")
        job = {
            "job_id": job_id,
            "jobId": job_id,
            "tenant_id": tenant_id,
            "job_number": job_number,
            "jobNumber": job_number,
            "customer_id": customer_id,
            "customerId": customer_id,
            "customer_name": customer.get("name", "Demo Customer"),
            "customerName": customer.get("name", "Demo Customer"),
            "part_id": part_id,
            "partId": part_id,
            "part_number": part.get("part_number", "DEMO-PART-001"),
            "partNumber": part.get("part_number", "DEMO-PART-001"),
            "quantity": _camel_or_snake(payload, "quantity", "quantity", 1),
            "due_date": due_date,
            "dueDate": due_date,
            "priority": str(_camel_or_snake(payload, "priority", "priority", "MEDIUM")).upper(),
            "status": "NOT_STARTED",
            "alert_priority": "NORMAL",
            "alertPriority": "NORMAL",
            "created_at": now,
            "createdAt": now,
            "updated_at": now,
            "updatedAt": now,
            "created_by": user.get("user_id", "dev-user-id"),
            "createdBy": user.get("user_id", "dev-user-id"),
            "updated_by": user.get("user_id", "dev-user-id"),
            "updatedBy": user.get("user_id", "dev-user-id"),
            "operations": [operation],
        }
        _demo_store["jobs"].append(job)
        _demo_store["job_operations"].append(operation)
        estimated_cost = _demo_estimated_cost(job)
        return _api_success(
            {
                "job": job,
                "operations": [operation],
                "costing": {
                    "estimated_cost": estimated_cost,
                    "operation_count": 1,
                    "quantity": job["quantity"],
                    "machine_cost": int(estimated_cost * 0.45),
                    "labour_cost": int(estimated_cost * 0.35),
                    "material_cost": 0,
                    "total_cost": estimated_cost,
                },
            },
            "Job created successfully with expanded operations route",
            status_code=201,
        )

    jobs_prefix = "/api/jobs/"
    if path.startswith(jobs_prefix):
        suffix = path.removeprefix(jobs_prefix).strip("/")
        parts = suffix.split("/")
        job = _demo_find_job(parts[0]) if parts else None
        if not job:
            return JSONResponse(status_code=404, content={"success": False, "message": "Job not found", "data": None})

        if len(parts) == 1 and method == "GET":
            return _api_success({"job": job, "operations": job.get("operations", [])}, "Job synchronized")

        if len(parts) == 2 and parts[1] == "operations" and method == "GET":
            return _api_success(job.get("operations", []), "Job operations synchronized")

        if len(parts) == 2 and parts[1] == "audit" and method == "GET":
            return _api_success({"auditTrail": [], "audit_trail": []}, "Job audit synchronized")

        if len(parts) == 2 and parts[1] == "cost-summary" and method == "GET":
            estimated_cost = _demo_estimated_cost(job)
            return _api_success(
                {
                    "job_id": job["job_id"],
                    "jobId": job["job_id"],
                    "machine_cost": int(estimated_cost * 0.45),
                    "machineCost": int(estimated_cost * 0.45),
                    "labour_cost": int(estimated_cost * 0.35),
                    "labourCost": int(estimated_cost * 0.35),
                    "material_cost": 0,
                    "materialCost": 0,
                    "total_cost": estimated_cost,
                    "totalCost": estimated_cost,
                    "margin": int(estimated_cost * 0.2),
                },
                "Job cost synchronized",
            )

        if len(parts) == 2 and parts[1] in {"recalculate-cost", "quoted-price"} and method in {"POST", "PATCH"}:
            return _api_success(job, "Job updated")

        if len(parts) == 2 and parts[1] in {"invoice", "download-invoice"} and method == "GET":
            pdf_stub = (
                b"%PDF-1.4\n"
                b"1 0 obj<<>>endobj\n"
                b"2 0 obj<< /Length 44 >>stream\n"
                b"BT /F1 18 Tf 72 720 Td (Demo Invoice) Tj ET\n"
                b"endstream endobj\n"
                b"trailer<<>>\n%%EOF\n"
            )
            return Response(
                content=pdf_stub,
                media_type="application/pdf",
                headers={"Content-Disposition": f"attachment; filename=Invoice_{job['job_number']}.pdf"},
            )

    operations_prefix = "/api/job-operations/"
    if path.startswith(operations_prefix):
        suffix = path.removeprefix(operations_prefix).strip("/")
        parts = suffix.split("/")
        operation = _demo_find_operation(parts[0]) if parts else None
        if not operation:
            return JSONResponse(status_code=404, content={"success": False, "message": "Operation not found", "data": None})

        if len(parts) == 1 and method == "GET":
            return _api_success(operation, "Operation synchronized")

        if len(parts) == 2 and parts[1] == "audit" and method == "GET":
            return _api_success([], "Operation audit synchronized")

        if len(parts) == 2 and parts[1] in {"status", "plan"} and method == "PATCH":
            try:
                payload = await request.json()
            except Exception:  # noqa: BLE001
                payload = {}
            for key, value in payload.items():
                operation[key] = value
            if "status" in payload:
                operation["status"] = str(payload["status"]).upper()
            return _api_success(operation, "Operation updated")

    if path == "/api/notifications" and method == "GET":
        notifications = [
            {
                "notification_id": "demo-notification-1",
                "type": "SYSTEM",
                "message": "Demo workspace is ready. Create jobs, export CSVs, and review analytics without a database connection.",
                "is_read": False,
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "user_id": None,
            }
        ]
        if request.query_params.get("unread_only", "false").lower() == "true":
            notifications = [item for item in notifications if not item["is_read"]]
        return _api_success(
            {"notifications": notifications, "unread_count": len([item for item in notifications if not item["is_read"]])},
            "Notifications synchronized",
        )

    notification_read_prefix = "/api/notifications/"
    if path.startswith(notification_read_prefix) and path.endswith("/read") and method == "PATCH":
        notification_id = path.removeprefix(notification_read_prefix).removesuffix("/read").strip("/")
        return _api_success(
            {
                "notification_id": notification_id,
                "is_read": True,
                "read_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            },
            "Notification marked as read",
        )

    if path == "/api/users/invite" and method == "POST":
        try:
            payload = await request.json()
        except Exception:  # noqa: BLE001
            payload = {}
        email = payload.get("email") or "employee@example.com"
        role = str(payload.get("role") or "OPERATOR").upper()
        return _api_success(
            {
                "email": email,
                "role": role,
                "tenant_id": tenant_id,
                "machine_id": payload.get("machine_id"),
                "cognito_username": email,
                "delivery_medium": "EMAIL",
            },
            "Employee invite sent",
        )

    if path == "/api/planning" and method == "GET":
        return _api_success({}, "Planning calendar synchronized")

    if path == "/api/planning/calendar" and method == "GET":
        return _api_success({}, "Planning calendar synchronized")

    if path in {"/api/planning/auto-assign", "/api/planning/auto-schedule"} and method == "POST":
        return _api_success({"suggestions": []}, "Auto-schedule suggestions synchronized")

    if path == "/api/exports/jobs" and method in {"GET", "POST"}:
        rows = ["job_number,customer,part,quantity,due_date,priority,status"]
        for job in _demo_metric_jobs():
            rows.append(
                ",".join(
                    [
                        str(job.get("job_number", "")),
                        str(job.get("customer_name", "")),
                        str(job.get("part_number", "")),
                        str(job.get("quantity", "")),
                        str(job.get("due_date", "") or ""),
                        str(job.get("priority", "")),
                        str(job.get("status", "")),
                    ]
                )
            )
        return _api_success(
            _demo_csv_download("active_jobs.csv", "\n".join(rows) + "\n"),
            "Jobs CSV export ready",
        )

    if path == "/api/exports/machine-load" and method in {"GET", "POST"}:
        metric_jobs = _demo_metric_jobs()
        booked_hours = round(sum(_demo_booked_hours(job) for job in metric_jobs if job.get("status") != "COMPLETED"), 2)
        csv_text = "machine_id,machine_name,date,total_hours,is_overloaded\n"
        csv_text += f"demo-machine-1,CNC-01,,{booked_hours},{str(booked_hours > 8).lower()}\n"
        return _api_success(
            _demo_csv_download("machine_load.csv", csv_text),
            "Machine load CSV export ready",
        )

    if path == "/api/metrics/wip" and method == "GET":
        metric_jobs = _demo_metric_jobs()
        not_started_jobs = len([job for job in metric_jobs if job.get("status") == "NOT_STARTED"])
        in_progress_jobs = len([job for job in metric_jobs if job.get("status") == "IN_PROGRESS"])
        completed_jobs = len([job for job in metric_jobs if job.get("status") == "COMPLETED"])
        return _api_success(
            {
                "wip_by_stage": [
                    {"stage": "NOT_STARTED", "count": not_started_jobs},
                    {"stage": "IN_PROGRESS", "count": in_progress_jobs},
                    {"stage": "COMPLETED", "count": completed_jobs},
                ],
                "stages": [
                    {
                        "stage_id": "NOT_STARTED",
                        "stage_name": "Not Started",
                        "jobs": [_demo_job_card(job) for job in metric_jobs if job.get("status") == "NOT_STARTED"],
                    },
                    {
                        "stage_id": "IN_PROGRESS",
                        "stage_name": "In Progress",
                        "jobs": [_demo_job_card(job) for job in metric_jobs if job.get("status") == "IN_PROGRESS"],
                    },
                    {
                        "stage_id": "COMPLETED",
                        "stage_name": "Completed",
                        "jobs": [_demo_job_card(job) for job in metric_jobs if job.get("status") == "COMPLETED"],
                    },
                ],
            },
            "WIP metrics synchronized",
        )

    if path == "/api/metrics/bottlenecks" and method == "GET":
        metric_jobs = _demo_metric_jobs()
        pending_operations = sum(len(job.get("operations") or []) for job in metric_jobs)
        return _api_success(
            {
                "bottlenecks": [
                    {
                        "machine_id": "demo-machine-1",
                        "machine_name": "CNC-01",
                        "pending_operations": pending_operations,
                        "count": pending_operations,
                        "total_hours": pending_operations * 2,
                        "is_overloaded": False,
                    }
                ]
            },
            "Bottleneck metrics synchronized",
        )

    if path == "/api/metrics/late-jobs" and method == "GET":
        return _api_success(
            {
                "total_late": 0,
                "jobs": [],
            },
            "Late jobs metrics synchronized",
        )

    if path == "/api/metrics/costing-summary" and method == "GET":
        metric_jobs = _demo_metric_jobs()
        total_jobs = len(metric_jobs)
        completed_jobs = len([job for job in metric_jobs if job.get("status") == "COMPLETED"])
        active_jobs = max(total_jobs - completed_jobs, 0)
        total_estimated_cost = sum(_demo_estimated_cost(job) for job in metric_jobs)
        average_estimated_cost = int(total_estimated_cost / total_jobs) if total_jobs else 0
        top_jobs = sorted(metric_jobs, key=_demo_estimated_cost, reverse=True)
        return _api_success(
            {
                "overview": {
                    "total_jobs": total_jobs,
                    "active_jobs": active_jobs,
                    "completed_jobs": completed_jobs,
                    "late_jobs": 0,
                    "total_estimated_cost": total_estimated_cost,
                    "open_estimated_cost": total_estimated_cost,
                    "completed_estimated_cost": 0,
                    "average_estimated_job_cost": average_estimated_cost,
                    "highest_estimated_job_cost": _demo_estimated_cost(top_jobs[0]) if top_jobs else 0,
                    "highest_estimated_job_number": top_jobs[0]["job_number"] if top_jobs else None,
                },
                "recent_completed_jobs": [],
                "top_estimated_jobs": [
                    {
                        "job_id": job["job_id"],
                        "job_number": job["job_number"],
                        "customer_name": job.get("customer_name", "Demo Customer"),
                        "operation_count": len(job.get("operations", [])),
                        "quantity": job.get("quantity", 0),
                        "estimated_cost": _demo_estimated_cost(job),
                        "status": job.get("status", "NOT_STARTED"),
                    }
                    for job in top_jobs[:5]
                ],
            },
            "Costing summary synchronized",
        )

    master_prefix = "/api/master-data/"
    if path.startswith(master_prefix):
        master_suffix = path.removeprefix(master_prefix).strip("/")
        resource_parts = master_suffix.split("/")
        resource = resource_parts[0]
        if resource in _demo_store:
            if method == "GET":
                if len(resource_parts) > 1:
                    item_id = resource_parts[1]
                    singular = resource[:-1] if resource.endswith("s") else resource
                    item = next(
                        (
                            item
                            for item in _demo_store[resource]
                            if str(item.get("id")) == item_id or str(item.get(f"{singular}_id")) == item_id
                        ),
                        None,
                    )
                    if item is None:
                        return JSONResponse(status_code=404, content={"success": False, "message": f"{singular.title()} not found", "data": None})
                    return _api_success(item, f"{singular.title()} synchronized")
                return _api_success(_demo_store[resource], f"{resource.title()} synchronized")

            if method == "POST":
                try:
                    payload = await request.json()
                except Exception:  # noqa: BLE001
                    payload = {}

                singular = resource[:-1] if resource.endswith("s") else resource
                item_id = str(uuid.uuid4())
                item = {
                    **payload,
                    "tenant_id": tenant_id,
                    "id": item_id,
                    f"{singular}_id": item_id,
                    "is_active": payload.get("is_active", True) if isinstance(payload, dict) else True,
                }
                _demo_store[resource].append(item)
                return _api_success(item, f"{singular.title()} created", status_code=201)

            if len(resource_parts) > 1 and method in {"PATCH", "DELETE"}:
                item_id = resource_parts[1]
                singular = resource[:-1] if resource.endswith("s") else resource
                item = next(
                    (
                        item
                        for item in _demo_store[resource]
                        if str(item.get("id")) == item_id or str(item.get(f"{singular}_id")) == item_id
                    ),
                    None,
                )
                if item is None:
                    return JSONResponse(status_code=404, content={"success": False, "message": f"{singular.title()} not found", "data": None})

                if method == "PATCH":
                    try:
                        payload = await request.json()
                    except Exception:  # noqa: BLE001
                        payload = {}
                    if isinstance(payload, dict):
                        item.update(payload)
                    return _api_success(item, f"{singular.title()} updated")

                item["is_active"] = False
                return _api_success(item, f"{singular.title()} deleted")

    return None

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
            "/api/ping",
            "/docs", "/openapi.json", "/redoc",
            "/maintenance/batch-costing",
        }
        if request.url.path in public_paths or request.url.path.startswith("/maintenance"):
            return await call_next(request)

        token, token_error = _extract_bearer_token(request)
        if token_error:
            return _unauthorized(token_error)

        # --- DEV BYPASS ---
        allow_dev_pass = _allow_dev_pass()
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

        if _allow_demo_api_stubs() and token == dev_token:
            demo_response = await _demo_response_for_request(request, user)
            if demo_response is not None:
                return demo_response

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
