"""
/**
 * PROJECT ROODHA - v1.5.7 "Gold Baseline"
 * File: logger.py
 * 
 * 1) Purpose: Core framework configurations, middlewares, and utilities.
 * 2) Roadmap Connection: This file is a critical component of the Stage 2 (v1.5) Industrial 
 *    Hardening phase. It enforces multi-tenancy, security (RBAC), and transactional 
 *    resilience as defined in the formal Roadmap.
 */
"""
# app/core/logger.py
"""
Central logging configuration for JobWork backend.
"""
 
import logging
 
 
def get_logger(name: str = "jobwork-backend") -> logging.Logger:
    """
    Returns a configured logger instance.
    """
 
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)  
 
    if not logger.handlers:
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
        )
 
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
 
    return logger