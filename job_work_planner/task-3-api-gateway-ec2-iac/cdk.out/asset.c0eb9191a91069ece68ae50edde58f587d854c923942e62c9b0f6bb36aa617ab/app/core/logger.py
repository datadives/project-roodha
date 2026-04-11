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