"""
auth_middleware.py
------------------
Mock JWT authentication middleware.

Responsibilities:
- Allow /health without authentication
- Require Authorization header for all other routes
- Attach user + tenant context to request.state
- MUST return Response objects (not raise HTTPException)
"""

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.status import HTTP_401_UNAUTHORIZED


class JWTAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        """
        Middleware entry point.

        IMPORTANT:
        - Do NOT raise HTTPException here
        - Always return a Response
        """

        
        
        # -------------------------------------------------
        # 1. Public endpoints (no auth)
        # -------------------------------------------------
        # Allow documentation and health checks to bypass auth
        public_paths = {
            "/health", 
            "/docs", 
            "/openapi.json", 
            "/redoc"
        }
        
        if request.url.path in public_paths:
            return await call_next(request)

        # -------------------------------------------------
        # 2. Read Authorization header
        # -------------------------------------------------
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

        token = auth_header.replace("Bearer ", "")

        # -------------------------------------------------
        # 3. MOCK JWT validation (Cognito later)
        # -------------------------------------------------
        # NOTE:
        # In real life:
        # - Verify signature using Cognito JWKs
        # - Validate exp, iss, aud
        # -------------------------------------------------

        if token != "test123":
            return JSONResponse(
                status_code=HTTP_401_UNAUTHORIZED,
                content={"detail": "Invalid or expired token"},
            )

        # -------------------------------------------------
        # 4. Attach user context (CRITICAL)
        # -------------------------------------------------
        request.state.user = {
            "user_id": "mock-user-id",
            "email": "mock.user@jobwork.com",
            "tenant_id": "tenant-1",
            "role": "OWNER",
        }

        # -------------------------------------------------
        # 5. Continue request
        # -------------------------------------------------
        return await call_next(request)