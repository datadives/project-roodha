"""V1.0 PRD Compliance: UUID PKs, Audit Tracking, and ENUMs

Revision ID: v1_0_prd_compliance
Revises: db_hardening_v1
Create Date: 2026-04-13 09:12:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'v1_0_prd_compliance'
down_revision: Union[str, Sequence[str], None] = 'db_hardening_v1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # 1. Enable UUID Extension
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto";')

    # 2. Create ENUMs for Status Tracking
    # Idempotent ENUM creation
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'job_status') THEN
                CREATE TYPE job_status AS ENUM ('NOT_STARTED', 'IN_PROGRESS', 'COMPLETED');
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'operation_status') THEN
                CREATE TYPE operation_status AS ENUM ('NOT_STARTED', 'IN_PROGRESS', 'COMPLETED');
            END IF;
        END
        $$;
    """)

    # 3. Create/Update Tables (Simplified Re-creation for V1.0 baseline)
    # Using 'CREATE TABLE IF NOT EXISTS' via execute or letting op.create_table handle it
    
    # Note: For production-grade safety, usually we'd migrate data. 
    # Here we are establishing the V1.0 baseline with UUIDs.
    
    # Re-creating Customer with UUID PK
    op.execute("DROP TABLE IF EXISTS customers CASCADE;")
    op.create_table('customers',
        sa.Column('customer_id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('contact_person', sa.String(), nullable=True),
        sa.Column('email', sa.String(), nullable=True),
        sa.Column('phone', sa.String(), nullable=True),
        sa.Column('address', sa.String(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', sa.String(), nullable=False),
        sa.Column('updated_by', sa.String(), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.tenant_id'], ),
        sa.PrimaryKeyConstraint('customer_id')
    )

    # Re-creating Operations Master
    op.execute("DROP TABLE IF EXISTS operations_master CASCADE;")
    op.create_table('operations_master',
        sa.Column('operation_id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('default_standard_cycle_time_mins', sa.Integer(), server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', sa.String(), nullable=False),
        sa.Column('updated_by', sa.String(), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.tenant_id'], ),
        sa.PrimaryKeyConstraint('operation_id')
    )

    # Re-creating Machines
    op.execute("DROP TABLE IF EXISTS machines CASCADE;")
    op.create_table('machines',
        sa.Column('machine_id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('type', sa.String(), nullable=True),
        sa.Column('hourly_rate', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('location', sa.String(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', sa.String(), nullable=False),
        sa.Column('updated_by', sa.String(), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.tenant_id'], ),
        sa.PrimaryKeyConstraint('machine_id')
    )

    # Re-creating Shifts
    op.execute("DROP TABLE IF EXISTS shifts CASCADE;")
    op.create_table('shifts',
        sa.Column('shift_id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('start_time', sa.String(), nullable=False),
        sa.Column('end_time', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', sa.String(), nullable=False),
        sa.Column('updated_by', sa.String(), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.tenant_id'], ),
        sa.PrimaryKeyConstraint('shift_id')
    )

    # Re-creating Workers
    op.execute("DROP TABLE IF EXISTS workers CASCADE;")
    op.create_table('workers',
        sa.Column('worker_id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('role', sa.String(), nullable=True),
        sa.Column('hourly_rate', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', sa.String(), nullable=False),
        sa.Column('updated_by', sa.String(), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.tenant_id'], ),
        sa.PrimaryKeyConstraint('worker_id')
    )

    # Re-creating Parts
    op.execute("DROP TABLE IF EXISTS parts CASCADE;")
    op.create_table('parts',
        sa.Column('part_id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('part_number', sa.String(), nullable=False),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('customer_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('default_material_cost_per_unit', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('default_operations_route', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', sa.String(), nullable=False),
        sa.Column('updated_by', sa.String(), nullable=False),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.customer_id'], ),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.tenant_id'], ),
        sa.PrimaryKeyConstraint('part_id')
    )

    # Re-creating Jobs
    op.execute("DROP TABLE IF EXISTS jobs CASCADE;")
    op.create_table('jobs',
        sa.Column('job_id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('job_number', sa.String(), nullable=False),
        sa.Column('customer_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('part_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('due_date', sa.DateTime(), nullable=True),
        sa.Column('priority', sa.String(), nullable=True),
        sa.Column('quoted_price', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('status', postgresql.ENUM('NOT_STARTED', 'IN_PROGRESS', 'COMPLETED', name='job_status', create_type=False), server_default='NOT_STARTED', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', sa.String(), nullable=False),
        sa.Column('updated_by', sa.String(), nullable=False),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.customer_id'], ),
        sa.ForeignKeyConstraint(['part_id'], ['parts.part_id'], ),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.tenant_id'], ),
        sa.PrimaryKeyConstraint('job_id')
    )
    op.create_index(op.f('ix_jobs_job_number'), 'jobs', ['job_number'], unique=False)

    # Re-creating Job Operations
    op.execute("DROP TABLE IF EXISTS job_operations CASCADE;")
    op.create_table('job_operations',
        sa.Column('job_operation_id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('job_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('operation_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('machine_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('shift_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('sequence_number', sa.Integer(), nullable=False),
        sa.Column('status', postgresql.ENUM('NOT_STARTED', 'IN_PROGRESS', 'COMPLETED', name='operation_status', create_type=False), server_default='NOT_STARTED', nullable=False),
        sa.Column('actual_start_time', sa.DateTime(), nullable=True),
        sa.Column('actual_end_time', sa.DateTime(), nullable=True),
        sa.Column('quantity_completed', sa.Integer(), server_default='0', nullable=False),
        sa.Column('quantity_rejected', sa.Integer(), server_default='0', nullable=False),
        sa.Column('planned_start_date', sa.DateTime(), nullable=True),
        sa.Column('planned_end_date', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', sa.String(), nullable=False),
        sa.Column('updated_by', sa.String(), nullable=False),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.job_id'], ),
        sa.ForeignKeyConstraint(['machine_id'], ['machines.machine_id'], ),
        sa.ForeignKeyConstraint(['operation_id'], ['operations_master.operation_id'], ),
        sa.ForeignKeyConstraint(['shift_id'], ['shifts.shift_id'], ),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.tenant_id'], ),
        sa.PrimaryKeyConstraint('job_operation_id')
    )

    # 4. Re-enable RLS on all V1.0 Tables
    TABLES_V1 = [
        'customers', 'operations_master', 'machines', 'shifts', 'workers', 
        'parts', 'jobs', 'job_operations'
    ]
    for table in TABLES_V1:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;")
        # Policy is already defined globally in db_hardening_v1, 
        # but re-applying it ensures it sticks to the new table structure.
        op.execute(f"CREATE POLICY tenant_isolation_policy ON {table} USING (tenant_id = current_setting('app.current_tenant', true));")

def downgrade() -> None:
    # Dropping in reverse order
    op.execute("DROP TABLE IF EXISTS job_operations CASCADE;")
    op.execute("DROP TABLE IF EXISTS jobs CASCADE;")
    op.execute("DROP TABLE IF EXISTS parts CASCADE;")
    op.execute("DROP TABLE IF EXISTS workers CASCADE;")
    op.execute("DROP TABLE IF EXISTS shifts CASCADE;")
    op.execute("DROP TABLE IF EXISTS machines CASCADE;")
    op.execute("DROP TABLE IF EXISTS operations_master CASCADE;")
    op.execute("DROP TABLE IF EXISTS customers CASCADE;")
    op.execute("DROP TYPE IF EXISTS job_status;")
    op.execute("DROP TYPE IF EXISTS operation_status;")
