"""
/**
 * PROJECT ROODHA - v1.5.7 "Gold Baseline"
 * File: maintenance_service.py
 * 
 * 1) Purpose: Business logic and service layer for maintenance_service.
 * 2) Roadmap Connection: This file is a critical component of the Stage 2 (v1.5) Industrial 
 *    Hardening phase. It enforces multi-tenancy, security (RBAC), and transactional 
 *    resilience as defined in the formal Roadmap.
 */
"""
"""
maintenance_service.py
----------------------
Asynchronous service for batch processing and automated maintenance.
"""

import logging
from datetime import datetime, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models
from app.services.costing_service import calculate_job_costs
from app.core.tenant_context import tenant_id_context

logger = logging.getLogger("jobwork-backend")

async def run_batch_costing_service(db: AsyncSession):
    """
    Recalculates costing for all jobs completed in the last 26 hours.
    Used for daily morning reconciliation.
    """
    # 26-hour lookback window for safety as per recommendation
    lookback_period = datetime.utcnow() - timedelta(hours=26)
    
    # Query all completed jobs updated within the window
    query = select(models.Job).where(
        models.Job.status == models.JobStatus.COMPLETED,
        models.Job.updated_at >= lookback_period
    )
    
    result = await db.execute(query)
    jobs_to_process = result.scalars().all()
    
    processed_count = 0
    errors_count = 0
    
    for job in jobs_to_process:
        try:
            # Set tenant context to ensure isolation in service layers
            token = tenant_id_context.set(job.tenant_id)
            
            await calculate_job_costs(db, job.tenant_id, job.job_id)
            
            tenant_id_context.reset(token)
            processed_count += 1
        except Exception as e:
            logger.error(f"Batch costing failed for job {job.job_id}: {str(e)}")
            errors_count += 1
            
    return {
        "processed_jobs": processed_count,
        "failed_jobs": errors_count,
        "lookback_window_hours": 26,
        "timestamp": datetime.utcnow().isoformat()
    }
