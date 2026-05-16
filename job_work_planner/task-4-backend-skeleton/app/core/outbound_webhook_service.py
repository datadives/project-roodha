import logging
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models


logger = logging.getLogger("jobwork-backend")


def _webhook_matches_event(webhook: models.IntegrationWebhook, event_type: str) -> bool:
    configured_events = webhook.event_types_json or []
    if not configured_events:
        return True
    return event_type in {str(item).upper() for item in configured_events}


async def dispatch_outbound_webhooks(
    db: AsyncSession,
    tenant_id: str,
    event_type: str,
    payload: dict[str, Any],
    timeout_seconds: float = 3.0,
) -> list[dict[str, Any]]:
    result = await db.execute(
        select(models.IntegrationWebhook).where(
            models.IntegrationWebhook.tenant_id == tenant_id,
            models.IntegrationWebhook.direction == "OUTBOUND",
            models.IntegrationWebhook.is_active.is_(True),
        )
    )
    webhooks = [
        webhook
        for webhook in result.scalars().all()
        if _webhook_matches_event(webhook, event_type)
    ]

    outcomes: list[dict[str, Any]] = []
    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        for webhook in webhooks:
            started_at = datetime.now(UTC)
            try:
                response = await client.post(str(webhook.url), json=payload)
                ok = response.status_code < 500
                outcomes.append(
                    {
                        "webhook_id": str(webhook.webhook_id),
                        "url": webhook.url,
                        "status_code": response.status_code,
                        "ok": ok,
                    }
                )
                if not ok:
                    logger.warning(
                        "OUTBOUND_WEBHOOK_FAILED | tenant=%s | event=%s | webhook=%s | status=%s",
                        tenant_id,
                        event_type,
                        webhook.webhook_id,
                        response.status_code,
                    )
            except Exception as exc:
                outcomes.append(
                    {
                        "webhook_id": str(webhook.webhook_id),
                        "url": webhook.url,
                        "status_code": None,
                        "ok": False,
                        "error": exc.__class__.__name__,
                    }
                )
                logger.warning(
                    "OUTBOUND_WEBHOOK_EXCEPTION | tenant=%s | event=%s | webhook=%s | elapsed_ms=%s | error=%s",
                    tenant_id,
                    event_type,
                    webhook.webhook_id,
                    int((datetime.now(UTC) - started_at).total_seconds() * 1000),
                    exc,
                )
    return outcomes
