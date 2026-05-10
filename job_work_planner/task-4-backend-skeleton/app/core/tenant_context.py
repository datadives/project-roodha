"""
/**
 * PROJECT ROODHA - v1.5.7 "Gold Baseline"
 * File: tenant_context.py
 * 
 * 1) Purpose: Core framework configurations, middlewares, and utilities.
 * 2) Roadmap Connection: This file is a critical component of the Stage 2 (v1.5) Industrial 
 *    Hardening phase. It enforces multi-tenancy, security (RBAC), and transactional 
 *    resilience as defined in the formal Roadmap.
 */
"""
from contextvars import ContextVar
from typing import Optional

# Global request context for tenant_id, user_id, and short_code
tenant_id_context: ContextVar[Optional[str]] = ContextVar("tenant_id_context", default=None)
user_id_context: ContextVar[Optional[str]] = ContextVar("user_id_context", default=None)
tenant_short_code_context: ContextVar[Optional[str]] = ContextVar("tenant_short_code_context", default=None)

def get_current_tenant_id() -> Optional[str]:
    return tenant_id_context.get()

def set_current_tenant_id(tenant_id: str) -> None:
    tenant_id_context.set(tenant_id)

def get_current_user_id() -> Optional[str]:
    return user_id_context.get()

def set_current_user_id(user_id: str) -> None:
    user_id_context.set(user_id)

def get_current_tenant_short_code() -> Optional[str]:
    return tenant_short_code_context.get()

def set_current_tenant_short_code(short_code: str) -> None:
    tenant_short_code_context.set(short_code)
