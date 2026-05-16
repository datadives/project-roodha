import uuid
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models
from app.core.auth_middleware import require_roles
from app.database import get_async_db
from app.routes.response_utils import api_success

router = APIRouter(prefix="/settings/custom-fields", tags=["Custom Fields"])


class CustomFieldCreate(BaseModel):
    entity_type: str = Field(..., min_length=2, max_length=50)
    field_name: str = Field(..., min_length=1, max_length=120)
    field_type: str = Field(..., min_length=2, max_length=30)
    options_json: list[str] | None = None
    is_required: bool = False


class CustomFieldValueUpsert(BaseModel):
    entity_id: UUID
    field_id: UUID
    value_text: str | None = None


def _serialize(field: models.CustomField) -> dict[str, Any]:
    return {
        "field_id": str(field.field_id),
        "tenant_id": field.tenant_id,
        "entity_type": field.entity_type,
        "field_name": field.field_name,
        "field_type": field.field_type,
        "options_json": field.options_json or [],
        "is_required": bool(field.is_required),
    }


@router.get("")
async def list_custom_fields(
    entity_type: str | None = None,
    user: dict = Depends(require_roles(["OWNER", "SUPERVISOR"])),
    db: AsyncSession = Depends(get_async_db),
):
    stmt = select(models.CustomField).where(models.CustomField.tenant_id == user["tenant_id"])
    if entity_type:
        stmt = stmt.where(models.CustomField.entity_type == entity_type.upper())
    stmt = stmt.order_by(models.CustomField.entity_type.asc(), models.CustomField.field_name.asc())
    result = await db.execute(stmt)
    return api_success({"fields": [_serialize(field) for field in result.scalars().all()]})


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_custom_field(
    payload: CustomFieldCreate,
    user: dict = Depends(require_roles(["OWNER"])),
    db: AsyncSession = Depends(get_async_db),
):
    field = models.CustomField(
        field_id=uuid.uuid4(),
        tenant_id=user["tenant_id"],
        entity_type=payload.entity_type.upper(),
        field_name=payload.field_name.strip(),
        field_type=payload.field_type.upper(),
        options_json=payload.options_json or [],
        is_required=payload.is_required,
    )
    db.add(field)
    await db.commit()
    await db.refresh(field)
    return api_success(_serialize(field), message="Custom field created")


@router.post("/values")
async def upsert_custom_field_value(
    payload: CustomFieldValueUpsert,
    user: dict = Depends(require_roles(["OWNER", "SUPERVISOR"])),
    db: AsyncSession = Depends(get_async_db),
):
    field_check = await db.execute(
        select(models.CustomField).where(
            models.CustomField.tenant_id == user["tenant_id"],
            models.CustomField.field_id == payload.field_id,
        )
    )
    if not field_check.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Custom field not found")
    result = await db.execute(
        select(models.CustomFieldValue).where(
            models.CustomFieldValue.tenant_id == user["tenant_id"],
            models.CustomFieldValue.field_id == payload.field_id,
            models.CustomFieldValue.entity_id == payload.entity_id,
        )
    )
    value = result.scalar_one_or_none()
    if not value:
        value = models.CustomFieldValue(
            value_id=uuid.uuid4(),
            tenant_id=user["tenant_id"],
            field_id=payload.field_id,
            entity_id=payload.entity_id,
        )
        db.add(value)
    value.field_value = payload.value_text
    value.value_text = payload.value_text
    await db.commit()
    return api_success({"field_value_id": str(value.value_id)}, message="Custom field value saved")
