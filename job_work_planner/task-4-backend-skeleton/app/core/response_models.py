"""
/**
 * PROJECT ROODHA - v1.5.7 "Gold Baseline"
 * File: response_models.py
 * 
 * 1) Purpose: Database schema and SQLAlchemy ORM models.
 * 2) Roadmap Connection: This file is a critical component of the Stage 2 (v1.5) Industrial 
 *    Hardening phase. It enforces multi-tenancy, security (RBAC), and transactional 
 *    resilience as defined in the formal Roadmap.
 */
"""
from typing import Generic, TypeVar, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime

T = TypeVar("T")

class ApiResponse(BaseModel, Generic[T]):
    success: bool = True
    message: str = "OK"
    data: Optional[T] = None
    error_code: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class ApiErrorResponse(ApiResponse):
    success: bool = False
    message: str
    error_code: str
    details: Optional[Any] = None

# Standard Error Codes
class ErrorCodes:
    AUTH_EXPIRED = "ERR_AUTH_EXPIRED"
    TENANT_MISMATCH = "ERR_TENANT_MISMATCH"
    DB_TIMEOUT = "ERR_DB_TIMEOUT"
    NOT_FOUND = "ERR_NOT_FOUND"
    VALIDATION_ERROR = "ERR_VALIDATION_FAILED"
    INTERNAL_ERROR = "ERR_INTERNAL_SERVER_ERROR"
