"""
/**
 * PROJECT ROODHA - v1.5.7 "Gold Baseline"
 * File: resilience.py
 * 
 * 1) Purpose: Core framework configurations, middlewares, and utilities.
 * 2) Roadmap Connection: This file is a critical component of the Stage 2 (v1.5) Industrial 
 *    Hardening phase. It enforces multi-tenancy, security (RBAC), and transactional 
 *    resilience as defined in the formal Roadmap.
 */
"""
import logging
import functools
import asyncio
from typing import Callable, Any, TypeVar
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from sqlalchemy.exc import OperationalError, DBAPIError

logger = logging.getLogger("jobwork-backend")
T = TypeVar("T")

# Retry logic for database operations
retry_on_db_error = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((OperationalError, DBAPIError)),
    before_sleep=lambda retry_state: logger.warning(
        f"Database operation failed. Retrying... (Attempt {retry_state.attempt_number})"
    ),
    reraise=True
)

class CircuitBreaker:
    """Simple Circuit Breaker implementation."""
    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 30.0):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = 0
        self.state = "CLOSED" # CLOSED, OPEN, HALF-OPEN

    def __call__(self, func: Callable[..., Any]):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            if self.state == "OPEN":
                if asyncio.get_event_loop().time() - self.last_failure_time > self.recovery_timeout:
                    self.state = "HALF-OPEN"
                    logger.info("Circuit Breaker moving to HALF-OPEN state")
                else:
                    raise RuntimeError("Circuit Breaker is OPEN. Request rejected.")

            try:
                result = await func(*args, **kwargs)
                if self.state == "HALF-OPEN":
                    self.state = "CLOSED"
                    self.failure_count = 0
                    logger.info("Circuit Breaker CLOSED")
                return result
            except Exception as e:
                self.failure_count += 1
                self.last_failure_time = asyncio.get_event_loop().time()
                if self.failure_count >= self.failure_threshold:
                    self.state = "OPEN"
                    logger.error(f"Circuit Breaker OPEN after {self.failure_count} failures: {e}")
                raise e
        return wrapper

# Standard circuit breaker for external calls
external_service_breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=30)
