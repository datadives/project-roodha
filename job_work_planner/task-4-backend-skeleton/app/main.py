import logging
import os
import sys
from pathlib import Path
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, PlainTextResponse
from starlette.middleware.base import BaseHTTPMiddleware

# --- SYSTEM PATH INITIALIZATION ---
APP_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = APP_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.auth_middleware import (
    JWTAuthMiddleware,
    _get_cognito_client_id,
    _get_cognito_issuer,
    _get_cognito_pool_id,
    _get_cognito_region,
    _get_jwks,
)
from app.database import refresh_engine_pools
from app.routes import (
    auth, job_operations, jobs, master_data, metrics, 
    notifications, planning, system, kanban, maintenance, exports,
    worklist, custom_fields, integrations
)

logger = logging.getLogger("jobwork-backend")


def _get_allowed_origins() -> list[str]:
    raw_origins = os.getenv("ALLOWED_ORIGINS") or os.getenv("CORS_ALLOW_ORIGINS")
    if not raw_origins:
        raw_origins = ",".join(
            [
                "http://localhost:5173",
                "http://localhost:5174",
                "http://roodha-v1-live-918172959197.s3-website.ap-south-1.amazonaws.com",
                "http://roodha-build-src-918172959197.s3-website.ap-south-1.amazonaws.com",
            ]
        )
    origins = [origin.strip() for origin in raw_origins.split(",") if origin.strip()]
    if not origins or "*" in origins:
        return ["*"]
    return origins


def _is_origin_allowed(origin: str | None, allowed_origins: list[str]) -> bool:
    if not origin:
        return False
    if "*" in allowed_origins:
        return True
    return origin in allowed_origins


def _build_cors_headers(
    origin: str | None,
    allowed_origins: list[str],
    requested_headers: str | None = None,
) -> dict[str, str]:
    if not _is_origin_allowed(origin, allowed_origins):
        return {}

    resolved_origin = origin if "*" in allowed_origins else origin
    return {
        "Access-Control-Allow-Origin": resolved_origin or "*",
        "Access-Control-Allow-Credentials": "true",
        "Access-Control-Allow-Methods": "GET,POST,PATCH,PUT,DELETE,OPTIONS",
        "Access-Control-Allow-Headers": "authorization,content-type,x-tenant-id",
        "Access-Control-Max-Age": "86400",
        "Vary": "Origin",
    }


class DynamicCORSMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, allowed_origins: list[str]):
        super().__init__(app)
        self.allowed_origins = allowed_origins

    async def dispatch(self, request, call_next):
        origin = request.headers.get("origin")
        if request.method == "OPTIONS" and origin and request.headers.get("access-control-request-method"):
            headers = _build_cors_headers(
                origin,
                self.allowed_origins,
                request.headers.get("access-control-request-headers"),
            )
            return PlainTextResponse("", status_code=204, headers=headers)

        try:
            response = await call_next(request)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Unhandled request failure for %s %s", request.method, request.url.path)
            response = JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "message": "Backend request failed before a module response was produced.",
                    "detail": str(exc),
                    "path": request.url.path,
                },
            )
        headers = _build_cors_headers(origin, self.allowed_origins)
        for key, value in headers.items():
            response.headers[key] = value
        return response


app = FastAPI(
    title="Project Roodha Backend",
    version="1.5.7",
    redirect_slashes=False,
)

# --- MIDDLEWARE (ORDER MATTERS) ---

# 1. Add Auth FIRST (Inner Layer)
app.add_middleware(JWTAuthMiddleware)

# 2. Add dynamic CORS LAST (Outer Layer - this makes it execute first for requests)
app.add_middleware(DynamicCORSMiddleware, allowed_origins=_get_allowed_origins())

@app.on_event("startup")
async def startup_event():
    await refresh_engine_pools()
    try:
        pool_id = _get_cognito_pool_id()
        _get_cognito_client_id()  # fail fast on missing app client id
        region = _get_cognito_region(pool_id)
        issuer = _get_cognito_issuer(region, pool_id)
        await _get_jwks(issuer)
        logger.info("Cognito JWKS cache warmed successfully")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Cognito JWKS warmup failed at startup: %s", exc)
    logger.info("✅ Backend started and connected to AWS RDS")

# --- ROUTE REGISTRATION ---
app.include_router(system.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(master_data.router, prefix="/api")
app.include_router(jobs.router, prefix="/api")
app.include_router(job_operations.router, prefix="/api")
app.include_router(planning.router, prefix="/api")
app.include_router(metrics.router, prefix="/api")
app.include_router(notifications.router, prefix="/api")
app.include_router(kanban.router, prefix="/api")
app.include_router(maintenance.router, prefix="/api")
app.include_router(exports.router, prefix="/api")
app.include_router(worklist.router, prefix="/api")
app.include_router(custom_fields.router, prefix="/api")
app.include_router(integrations.router, prefix="/api")


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(request, exc):
    if request.url.path == "/api/integrations/jobs":
        return await integrations.integration_validation_exception_handler(request, exc)
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()},
    )

@app.get("/api/ping")
async def ping():
    return {"message": "pong"}
