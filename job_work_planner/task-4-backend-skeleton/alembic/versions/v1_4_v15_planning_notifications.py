"""V1.5 planning automation, notifications, exports, and integration hooks

Revision ID: v1_4_v15_planning_notifications
Revises: 2727fe7803fb
Create Date: 2026-05-15 22:00:00.000000
"""
from typing import Sequence, Union

from alembic import op


revision: str = "v1_4_v15_planning_notifications"
down_revision: Union[str, Sequence[str], None] = "2727fe7803fb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto";')
    op.execute("ALTER TABLE operations_master ADD COLUMN IF NOT EXISTS default_machine_type VARCHAR NULL;")
    op.execute("ALTER TABLE notifications ADD COLUMN IF NOT EXISTS title VARCHAR NULL;")
    op.execute("ALTER TABLE notifications ADD COLUMN IF NOT EXISTS entity_type VARCHAR NULL;")
    op.execute("ALTER TABLE notifications ADD COLUMN IF NOT EXISTS entity_id VARCHAR NULL;")
    op.execute("ALTER TABLE custom_fields ADD COLUMN IF NOT EXISTS options_json JSON NULL;")
    op.execute("ALTER TABLE custom_field_values ADD COLUMN IF NOT EXISTS value_text VARCHAR NULL;")
    op.execute("UPDATE custom_field_values SET value_text = field_value WHERE value_text IS NULL;")
    op.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS tags_json JSON NULL;")
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS events (
            event_id UUID NOT NULL DEFAULT gen_random_uuid(),
            tenant_id VARCHAR NOT NULL,
            event_type VARCHAR NOT NULL,
            entity_type VARCHAR NOT NULL,
            entity_id VARCHAR NOT NULL,
            payload_json JSON NULL,
            status VARCHAR NOT NULL DEFAULT 'PENDING',
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            processed_at TIMESTAMP NULL,
            CONSTRAINT pk_events PRIMARY KEY (event_id),
            CONSTRAINT fk_events_tenant FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id)
        );
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_events_tenant_id ON events (tenant_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_events_event_type ON events (event_type);")
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS integration_webhooks (
            webhook_id UUID NOT NULL DEFAULT gen_random_uuid(),
            tenant_id VARCHAR NOT NULL,
            name VARCHAR NOT NULL,
            direction VARCHAR NOT NULL DEFAULT 'OUTBOUND',
            url VARCHAR NOT NULL,
            secret_hash VARCHAR NULL,
            event_types_json JSON NULL,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
            created_by VARCHAR NOT NULL DEFAULT 'system',
            updated_by VARCHAR NOT NULL DEFAULT 'system',
            CONSTRAINT pk_integration_webhooks PRIMARY KEY (webhook_id),
            CONSTRAINT fk_integration_webhooks_tenant FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id)
        );
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_integration_webhooks_tenant_id ON integration_webhooks (tenant_id);")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS integration_webhooks;")
    op.execute("DROP TABLE IF EXISTS events;")
    op.execute("ALTER TABLE jobs DROP COLUMN IF EXISTS tags_json;")
    op.execute("ALTER TABLE custom_field_values DROP COLUMN IF EXISTS value_text;")
    op.execute("ALTER TABLE custom_fields DROP COLUMN IF EXISTS options_json;")
    op.execute("ALTER TABLE notifications DROP COLUMN IF EXISTS entity_id;")
    op.execute("ALTER TABLE notifications DROP COLUMN IF EXISTS entity_type;")
    op.execute("ALTER TABLE notifications DROP COLUMN IF EXISTS title;")
    op.execute("ALTER TABLE operations_master DROP COLUMN IF EXISTS default_machine_type;")
