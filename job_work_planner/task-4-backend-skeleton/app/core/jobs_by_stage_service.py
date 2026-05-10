"""
/**
 * PROJECT ROODHA - v1.5.7 "Gold Baseline"
 * File: jobs_by_stage_service.py
 * 
 * 1) Purpose: Core framework configurations, middlewares, and utilities.
 * 2) Roadmap Connection: This file is a critical component of the Stage 2 (v1.5) Industrial 
 *    Hardening phase. It enforces multi-tenancy, security (RBAC), and transactional 
 *    resilience as defined in the formal Roadmap.
 */
"""
"""
jobs_by_stage_service.py
------------------------
Asynchronous service for the Kanban view (Single Source of Truth).
"""

import logging
from datetime import datetime
from collections import defaultdict
from typing import List, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import selectinload

from app import models
from app.schemas.kanban import KanbanBoardResponse, KanbanStage, KanbanJobCard
from app.core.proactive_delay_guard import calculate_alert_priority

logger = logging.getLogger("jobwork-backend")

async def get_jobs_by_stage_service(
    db: AsyncSession,
    tenant_id: str,
    date_filter: str | None = None,
    machine_id: str | None = None,
) -> Dict[str, Any]:
    """
    Fetches and groups jobs by their current active operation stage.
    """
    # 1. Fetch ALL defined operations (Columns) for the tenant
    # This ensures we show empty columns as requested.
    op_query = select(models.OperationsMaster).where(
        models.OperationsMaster.tenant_id == tenant_id
    ).order_by(
        models.OperationsMaster.sequence_number.asc().nulls_last(),
        models.OperationsMaster.name.asc()
    )
    
    op_result = await db.execute(op_query)
    all_operations = op_result.scalars().all()
    
    # Initialize the board structure with all stages
    stages_map: Dict[Any, KanbanStage] = {
        op.operation_id: KanbanStage(
            stage_id=op.operation_id,
            stage_name=op.name,
            jobs=[]
        ) for op in all_operations
    }

    # 2. Fetch all active Jobs with Customer and Part enrichment
    # Exclude COMPLETED and CANCELLED for the Kanban board
    job_query = (
        select(models.Job, models.Customer.name, models.Part.part_number)
        .join(models.Customer, models.Job.customer_id == models.Customer.customer_id, isouter=True)
        .join(models.Part, models.Job.part_id == models.Part.part_id, isouter=True)
        .where(
            models.Job.tenant_id == tenant_id,
            models.Job.status.in_([models.JobStatus.NOT_STARTED, models.JobStatus.IN_PROGRESS])
        )
    )
    job_result = await db.execute(job_query)
    jobs_data = job_result.all()

    if not jobs_data:
        return {"stages": list(stages_map.values())}

    # 3. Fetch all operations for these jobs to determine current stage
    job_ids = [row[0].job_id for row in jobs_data]
    op_query = (
        select(models.JobOperation)
        .where(
            models.JobOperation.job_id.in_(job_ids),
            models.JobOperation.tenant_id == tenant_id
        )
        .order_by(models.JobOperation.job_id, models.JobOperation.sequence_number)
    )
    ops_result = await db.execute(op_query)
    all_job_ops = ops_result.scalars().all()

    # Group operations by job_id
    ops_by_job = defaultdict(list)
    for op in all_job_ops:
        ops_by_job[op.job_id].append(op)

    # 4. Map jobs to their "Lowest Incomplete Sequence"
    today = datetime.utcnow().date()
    
    for job_row in jobs_data:
        job, customer_name, part_number = job_row
        job_ops = ops_by_job.get(job.job_id, [])
        
        # Determine current stage: First NOT_COMPLETED operation
        current_op = None
        for op in job_ops:
            if op.status != models.OperationStatus.COMPLETED:
                current_op = op
                break
        
        if not current_op:
            # Job is fully completed but status might not be updated yet
            continue

        if machine_id and str(current_op.machine_id or "") != str(machine_id):
            continue
            
        stage_id = current_op.op_id
        if stage_id not in stages_map:
            # Fallback if operation was deleted from master but exists in job
            continue

        # Calculate delayed flag
        delayed = False
        if job.due_date:
            job_due = job.due_date.date() if hasattr(job.due_date, 'date') else job.due_date
            delayed = today > job_due

        # Build Card
        card = KanbanJobCard(
            job_id=job.job_id,
            job_number=job.job_number,
            customer_name=customer_name or "Unknown Customer",
            part_number=part_number or "Unknown Part",
            quantity=job.quantity,
            due_date=job.due_date,
            priority=job.priority or "MEDIUM",
            delayed=delayed,
            alert_priority=calculate_alert_priority(job.due_date),
        )
        
        stages_map[stage_id].jobs.append(card)
        stages_map[stage_id].counts["total"] += 1
        if delayed:
            stages_map[stage_id].counts["delayed"] += 1

    # 5. Final Sorting
    # Jobs inside each stage: Priority DESC, then Due Date ASC
    priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    
    for stage in stages_map.values():
        stage.jobs.sort(key=lambda x: (
            priority_order.get(x.priority.upper(), 1),
            x.due_date or datetime.max
        ))

    return {"stages": list(stages_map.values())}
