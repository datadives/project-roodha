import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app import models


async def record_event(
    db: AsyncSession,
    tenant_id: str,
    event_type: str,
    entity_type: str,
    entity_id: str,
    payload: dict[str, Any] | None = None,
    *,
    flush_only: bool = True,
) -> models.Event:
    event = models.Event(
        event_id=uuid.uuid4(),
        tenant_id=tenant_id,
        event_type=event_type,
        entity_type=entity_type,
        entity_id=str(entity_id),
        payload_json=payload or {},
        status="PENDING",
        created_at=datetime.now(UTC).replace(tzinfo=None),
    )
    db.add(event)
    if flush_only:
        await db.flush()
    else:
        await db.commit()
        await db.refresh(event)
    return event
