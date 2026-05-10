"""V1.0 blocker fixes: notifications table, Part.is_active, OperationsMaster.sequence_number

Revision ID: v1_3_v1_blockers
Revises: v1_2_schema_alignment
Create Date: 2026-04-17 17:00:00.000000

Changes:
    1. Create `notifications` table with all required columns.
    2. Add `is_active` (boolean, NOT NULL, default TRUE) to `parts` for soft-delete support.
    3. Add `sequence_number` (integer, nullable) to `operations_master` for proper sorting.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# ---------------------------------------------------------------------------
# Revision identifiers
# ---------------------------------------------------------------------------
revision: str = "v1_3_v1_blockers"
down_revision: Union[str, Sequence[str], None] = "v1_2_schema_alignment"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ---------------------------------------------------------------------------
# Upgrade
# ---------------------------------------------------------------------------

def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1.  Create the `notifications` table
    # ------------------------------------------------------------------
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto";')

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS notifications (
            notification_id UUID         NOT NULL DEFAULT gen_random_uuid(),
            tenant_id       VARCHAR      NOT NULL,
            user_id         VARCHAR      NULL,
            type            VARCHAR      NOT NULL,
            message         TEXT         NOT NULL,
            entity_reference VARCHAR     NULL,
            is_read         BOOLEAN      NOT NULL DEFAULT FALSE,
            read_at         TIMESTAMP    NULL,
            created_at      TIMESTAMP    NOT NULL DEFAULT NOW(),
            CONSTRAINT pk_notifications PRIMARY KEY (notification_id),
            CONSTRAINT fk_notifications_tenant
                FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id)
        );
        """
    )

    # Indexes for the most common query patterns
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_indexes
                WHERE tablename = 'notifications'
                  AND indexname = 'ix_notifications_tenant_id'
            ) THEN
                CREATE INDEX ix_notifications_tenant_id ON notifications (tenant_id);
            END IF;
        END
        $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_indexes
                WHERE tablename = 'notifications'
                  AND indexname = 'ix_notifications_user_id'
            ) THEN
                CREATE INDEX ix_notifications_user_id ON notifications (user_id);
            END IF;
        END
        $$;
        """
    )

    # ------------------------------------------------------------------
    # 2.  Add `is_active` to `parts` (soft-delete support)
    # ------------------------------------------------------------------
    op.execute(
        """
        ALTER TABLE parts
        ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE;
        """
    )

    # ------------------------------------------------------------------
    # 3.  Add `sequence_number` to `operations_master` (sorting support)
    # ------------------------------------------------------------------
    op.execute(
        """
        ALTER TABLE operations_master
        ADD COLUMN IF NOT EXISTS sequence_number INTEGER NULL;
        """
    )


# ---------------------------------------------------------------------------
# Downgrade
# ---------------------------------------------------------------------------

def downgrade() -> None:
    # Reverse order of upgrade
    op.execute(
        "ALTER TABLE operations_master DROP COLUMN IF EXISTS sequence_number;"
    )
    op.execute(
        "ALTER TABLE parts DROP COLUMN IF EXISTS is_active;"
    )
    op.execute("DROP TABLE IF EXISTS notifications;")
