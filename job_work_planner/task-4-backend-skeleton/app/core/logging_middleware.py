"""
/**
 * PROJECT ROODHA - v1.5.7 "Gold Baseline"
 * File: logging_middleware.py
 * 
 * 1) Purpose: Core framework configurations, middlewares, and utilities.
 * 2) Roadmap Connection: This file is a critical component of the Stage 2 (v1.5) Industrial 
 *    Hardening phase. It enforces multi-tenancy, security (RBAC), and transactional 
 *    resilience as defined in the formal Roadmap.
 */
"""
import time
import uuid
import logging
from contextvars import ContextVar
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

# Context variables for logging
trace_id_var: ContextVar[str] = ContextVar("trace_id", default="")
tenant_id_var: ContextVar[str] = ContextVar("tenant_id", default="")
user_id_var: ContextVar[str] = ContextVar("user_id", default="")

class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        trace_id = request.headers.get("X-Trace-ID", str(uuid.uuid4()))
        trace_id_token = trace_id_var.set(trace_id)
        
        start_time = time.time()
        
        # Initial logging tokens
        tenant_id_token = tenant_id_var.set("unauthenticated")
        user_id_token = user_id_var.set("unauthenticated")
        
        try:
            response = await call_next(request)
            
            # After JWTAuthMiddleware, request.state.user should be populated
            user = getattr(request.state, "user", None)
            if user:
                tenant_id_var.set(user.get("tenant_id", "unknown"))
                user_id_var.set(user.get("user_id", "unknown"))
            
            process_time = (time.time() - start_time) * 1000
            
            # Set trace ID in response header
            response.headers["X-Trace-ID"] = trace_id
            
            return response
        finally:
            # Clean up context vars
            trace_id_var.reset(trace_id_token)
            tenant_id_var.reset(tenant_id_token)
            user_id_var.reset(user_id_token)
