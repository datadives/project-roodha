"""Schema alignment for ORM/runtime drift

Revision ID: v1_2_schema_alignment
Revises: v1_1_data_layer_hardening
Create Date: 2026-04-16 11:10:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "v1_2_schema_alignment"
down_revision: Union[str, Sequence[str], None] = "v1_1_data_layer_hardening"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto";')

    for status in ("PLANNED", "READY", "PAUSED", "CANCELLED"):
        op.execute(
            f"""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1
                    FROM pg_enum e
                    JOIN pg_type t ON t.oid = e.enumtypid
                    WHERE t.typname = 'operation_status'
                      AND e.enumlabel = '{status}'
                ) THEN
                    ALTER TYPE operation_status ADD VALUE '{status}';
                END IF;
            END
            $$;
            """
        )

    op.execute(
        """
        ALTER TABLE job_operations
        ADD COLUMN IF NOT EXISTS worker_id uuid NULL;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'job_operations_worker_id_fkey'
            ) THEN
                ALTER TABLE job_operations
                ADD CONSTRAINT job_operations_worker_id_fkey
                FOREIGN KEY (worker_id) REFERENCES workers(worker_id);
            END IF;
        END
        $$;
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'shifts'
                  AND column_name = 'start_time'
                  AND data_type = 'character varying'
            ) THEN
                IF EXISTS (
                    SELECT 1
                    FROM shifts
                    WHERE start_time !~ '^[0-9]{2}:[0-9]{2}(:[0-9]{2})?$'
                       OR end_time !~ '^[0-9]{2}:[0-9]{2}(:[0-9]{2})?$'
                ) THEN
                    RAISE EXCEPTION 'shifts.start_time/end_time contain non-time values; clean the data before running v1_2_schema_alignment';
                END IF;

                ALTER TABLE shifts
                    ALTER COLUMN start_time TYPE time USING start_time::time,
                    ALTER COLUMN end_time TYPE time USING end_time::time;
            END IF;
        END
        $$;
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM job_cost_summaries
                WHERE summary_id IS NOT NULL
                  AND summary_id <> ''
                  AND summary_id !~* '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
            ) THEN
                RAISE EXCEPTION 'job_cost_summaries.summary_id contains non-UUID values; manual cleanup required before migration';
            END IF;

            IF EXISTS (
                SELECT 1
                FROM job_cost_summaries
                WHERE job_id IS NOT NULL
                  AND job_id <> ''
                  AND job_id !~* '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
            ) THEN
                RAISE EXCEPTION 'job_cost_summaries.job_id contains non-UUID values; manual cleanup required before migration';
            END IF;
        END
        $$;
        """
    )
    op.execute(
        """
        ALTER TABLE job_cost_summaries
            ALTER COLUMN summary_id TYPE uuid USING NULLIF(summary_id, '')::uuid,
            ALTER COLUMN summary_id SET DEFAULT gen_random_uuid(),
            ALTER COLUMN job_id TYPE uuid USING NULLIF(job_id, '')::uuid,
            ALTER COLUMN tenant_id SET NOT NULL;
        """
    )
    op.execute(
        """
        ALTER TABLE job_cost_summaries
        ADD COLUMN IF NOT EXISTS created_at timestamp without time zone NOT NULL DEFAULT now(),
        ADD COLUMN IF NOT EXISTS updated_at timestamp without time zone NOT NULL DEFAULT now(),
        ADD COLUMN IF NOT EXISTS created_by character varying NOT NULL DEFAULT 'system',
        ADD COLUMN IF NOT EXISTS updated_by character varying NOT NULL DEFAULT 'system';
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM job_cost_summaries
                WHERE job_id IS NOT NULL
                GROUP BY job_id
                HAVING COUNT(*) > 1
            ) THEN
                RAISE EXCEPTION 'job_cost_summaries has duplicate job_id values; deduplicate before adding the unique constraint';
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
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'job_cost_summaries_job_id_key'
            ) THEN
                ALTER TABLE job_cost_summaries
                ADD CONSTRAINT job_cost_summaries_job_id_key UNIQUE (job_id);
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
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'job_cost_summaries_job_id_fkey'
            ) THEN
                ALTER TABLE job_cost_summaries
                ADD CONSTRAINT job_cost_summaries_job_id_fkey
                FOREIGN KEY (job_id) REFERENCES jobs(job_id);
            END IF;
        END
        $$;
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM parts
                GROUP BY tenant_id, part_number
                HAVING COUNT(*) > 1
            ) THEN
                RAISE EXCEPTION 'parts contains duplicate (tenant_id, part_number) values; deduplicate before adding uq_part_number_tenant';
            END IF;

            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'uq_part_number_tenant'
            ) THEN
                ALTER TABLE parts
                ADD CONSTRAINT uq_part_number_tenant UNIQUE (tenant_id, part_number);
            END IF;
        END
        $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM operations_master
                GROUP BY tenant_id, name
                HAVING COUNT(*) > 1
            ) THEN
                RAISE EXCEPTION 'operations_master contains duplicate (tenant_id, name) values; deduplicate before adding uq_operation_name_tenant';
            END IF;

            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'uq_operation_name_tenant'
            ) THEN
                ALTER TABLE operations_master
                ADD CONSTRAINT uq_operation_name_tenant UNIQUE (tenant_id, name);
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE operations_master DROP CONSTRAINT IF EXISTS uq_operation_name_tenant;")
    op.execute("ALTER TABLE parts DROP CONSTRAINT IF EXISTS uq_part_number_tenant;")
    op.execute("ALTER TABLE job_cost_summaries DROP CONSTRAINT IF EXISTS job_cost_summaries_job_id_fkey;")
    op.execute("ALTER TABLE job_cost_summaries DROP CONSTRAINT IF EXISTS job_cost_summaries_job_id_key;")
    op.execute("ALTER TABLE job_operations DROP CONSTRAINT IF EXISTS job_operations_worker_id_fkey;")
    op.execute("ALTER TABLE job_operations DROP COLUMN IF EXISTS worker_id;")
