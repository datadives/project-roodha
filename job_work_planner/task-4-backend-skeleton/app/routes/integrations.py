import os
import uuid
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models
from app.core.event_service import record_event
from app.core.notification_service import create_notification
from app.database import get_async_db
from app.routes.jobs import _resolve_job_custom_field_values, _resolve_route_operation
from app.routes.response_utils import api_success

router = APIRouter(prefix="/integrations", tags=["Integration Hooks"])


class IntegrationJobPayload(BaseModel):
    tenant_id: str = Field(..., min_length=1)
    customer_name: str = Field(..., min_length=1)
    customer_email: str | None = None
    customer_phone: str | None = None
    part_number: str = Field(..., min_length=1)
    part_description: str | None = None
    default_operations_route: list[dict[str, Any]] | None = None
    quantity: int = Field(..., gt=0)
    due_date: datetime | None = None
    priority: str = "MEDIUM"
    custom_fields: dict[str, str] | None = None
    tags: list[str] | None = None


def _check_token(token: str | None):
    configured = os.getenv("INTEGRATION_WEBHOOK_TOKEN")
    if not configured or token != configured:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid integration token")


async def integration_validation_exception_handler(_request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "success": False,
            "message": "Malformed integration job payload",
            "detail": exc.errors(),
        },
    )


@router.post("/jobs", status_code=status.HTTP_201_CREATED)
async def create_job_from_integration(
    payload: IntegrationJobPayload,
    x_roodha_integration_token: str | None = Header(default=None),
    db: AsyncSession = Depends(get_async_db),
):
    _check_token(x_roodha_integration_token)
    tenant = await db.get(models.Tenant, payload.tenant_id)
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    customer_result = await db.execute(
        select(models.Customer).where(
            models.Customer.tenant_id == payload.tenant_id,
            models.Customer.name == payload.customer_name,
        )
    )
    customer = customer_result.scalar_one_or_none()
    if not customer:
        customer = models.Customer(
            tenant_id=payload.tenant_id,
            name=payload.customer_name,
            email=payload.customer_email,
            phone=payload.customer_phone,
            is_active=True,
        )
        db.add(customer)
        await db.flush()

    part_result = await db.execute(
        select(models.Part).where(
            models.Part.tenant_id == payload.tenant_id,
            models.Part.part_number == payload.part_number,
        )
    )
    part = part_result.scalar_one_or_none()
    if not part:
        part = models.Part(
            tenant_id=payload.tenant_id,
            customer_id=customer.customer_id,
            part_number=payload.part_number,
            description=payload.part_description or payload.part_number,
            default_operations_route=payload.default_operations_route or [{"operation": "General Operation", "sequence_number": 1}],
            is_active=True,
        )
        db.add(part)
        await db.flush()
    elif payload.default_operations_route and not part.default_operations_route:
        part.default_operations_route = payload.default_operations_route

    custom_field_values = await _resolve_job_custom_field_values(db, payload.tenant_id, payload.custom_fields)
    job = models.Job(
        job_id=uuid.uuid4(),
        tenant_id=payload.tenant_id,
        customer_id=customer.customer_id,
        part_id=part.part_id,
        quantity=payload.quantity,
        due_date=payload.due_date or datetime.utcnow() + timedelta(days=7),
        priority=payload.priority.upper(),
        status=models.JobStatus.NOT_STARTED,
        tags_json=payload.tags or [],
    )
    db.add(job)
    await db.flush()

    for field, field_value in custom_field_values:
        db.add(
            models.CustomFieldValue(
                value_id=uuid.uuid4(),
                tenant_id=payload.tenant_id,
                field_id=field.field_id,
                entity_id=job.job_id,
                field_value=field_value,
                value_text=field_value,
            )
        )

    ops_route = part.default_operations_route or [{"operation": "General Operation", "sequence_number": 1}]
    job_operations = []
    for index, op_data in enumerate(ops_route):
        sequence_number = op_data.get("sequence_number") or op_data.get("sequence") or index + 1
        operation = await _resolve_route_operation(db, payload.tenant_id, op_data, sequence_number)
        job_op = models.JobOperation(
            tenant_id=payload.tenant_id,
            job_id=job.job_id,
            op_id=operation.operation_id,
            sequence_number=sequence_number,
            status=models.OperationStatus.NOT_STARTED,
        )
        db.add(job_op)
        job_operations.append(job_op)

    await record_event(
        db,
        payload.tenant_id,
        "JOB_CREATED",
        "JOB",
        str(job.job_id),
        {"source": "integration", "priority": payload.priority.upper(), "tags": payload.tags or []},
    )
    await db.commit()

    if payload.priority.upper() == "HIGH":
        await create_notification(
            db=db,
            tenant_id=payload.tenant_id,
            user_id=None,
            notif_type="HIGH_PRIORITY_JOB",
            title="High priority job created",
            message=f"Job {job.job_number} was created with high priority.",
            entity_ref=job.job_number,
            entity_type="JOB",
            entity_id=str(job.job_id),
        )

    return api_success(
        {
            "job_id": str(job.job_id),
            "job_number": job.job_number,
            "operation_count": len(job_operations),
            "tags": payload.tags or [],
        },
        message="Integration job created",
    )
