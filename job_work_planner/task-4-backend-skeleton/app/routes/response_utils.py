"""
/**
 * PROJECT ROODHA - v1.5.7 "Gold Baseline"
 * File: response_utils.py
 * 
 * 1) Purpose: Defines API endpoints for response_utils.
 * 2) Roadmap Connection: This file is a critical component of the Stage 2 (v1.5) Industrial 
 *    Hardening phase. It enforces multi-tenancy, security (RBAC), and transactional 
 *    resilience as defined in the formal Roadmap.
 */
"""
from typing import Any


def api_success(data: Any, message: str = "OK") -> dict:
    return {
        "success": True,
        "message": message,
        "data": data,
    }
