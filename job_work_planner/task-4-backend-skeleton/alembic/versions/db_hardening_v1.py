"""Multi-Tenant Row Level Security and Performance Baselines

Revision ID: db_hardening_v1
Revises: 6dee1d9c7adb
Create Date: 2026-04-12 01:27:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'db_hardening_v1'
down_revision: Union[str, Sequence[str], None] = '6dee1d9c7adb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TENANT_TABLES = [
    "users", "customers", "parts", "operations_master", 
    "machines", "shifts", "workers", "jobs", "job_operations", 
    "production_entries", "audit_logs", "notifications", "job_cost_summaries"
]

def upgrade() -> None:
    # 1. Performance Strategy: Composite Indexing for Tenant Boundaries
    # This ensures Aurora Postgres avoids full table scans even as the total database size grows.
    
    op.create_index('ix_jobs_tenant_status', 'jobs', ['tenant_id', 'status'])
    op.create_index('ix_job_operations_tenant_job', 'job_operations', ['tenant_id', 'job_id'])
    op.create_index('ix_production_entries_tenant_operation', 'production_entries', ['tenant_id', 'job_operation_id'])
    
    # 2. Security Strategy: Row Level Security (RLS)
    # Senior DBA Directive: Design all schemas with a mandatory tenant_id column and enforce boundaries at the DB level.
    
    for table in TENANT_TABLES:
        # Enable RLS
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;")
        
        # Create Generic Isolation Policy
        # Using current_setting('app.current_tenant') which is set by the backend middleware.
        # Idempotent policy creation
        op.execute(f"""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_policies 
                    WHERE tablename = '{table}' AND policyname = 'tenant_isolation_policy'
                ) THEN
                    CREATE POLICY tenant_isolation_policy ON {table}
                    USING (tenant_id = current_setting('app.current_tenant'));
                END IF;
            END
            $$;
        """)

def downgrade() -> None:
    # Remove Policies and Disable RLS
    for table in TENANT_TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {table};")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;")
    
    # Remove Indexes
    op.drop_index('ix_production_entries_tenant_operation', table_name='production_entries')
    op.drop_index('ix_job_operations_tenant_job', table_name='job_operations')
    op.drop_index('ix_jobs_tenant_status', table_name='jobs')
