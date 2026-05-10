"""Data Layer Hardening: Tenant Short Code and Job Sequence

Revision ID: v1_1_data_layer_hardening
Revises: v1_0_prd_compliance
Create Date: 2026-04-13 10:20:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'v1_1_data_layer_hardening'
down_revision: Union[str, Sequence[str], None] = 'v1_0_prd_compliance'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # 1. Add short_code to tenants
    op.add_column('tenants', sa.Column('short_code', sa.String(length=10), nullable=True))
    op.create_index(op.f('ix_tenants_short_code'), 'tenants', ['short_code'], unique=True)

    # 2. Create Job Number Sequence
    op.execute("CREATE SEQUENCE job_number_seq START WITH 1001;")

    # 3. Seed initial short_codes for existing tenants (if any)
    # Using a substring approach as a baseline
    op.execute("UPDATE tenants SET short_code = UPPER(SUBSTRING(tenant_id FROM 1 FOR 3)) WHERE short_code IS NULL;")

def downgrade() -> None:
    op.execute("DROP SEQUENCE IF EXISTS job_number_seq;")
    op.drop_index(op.f('ix_tenants_short_code'), table_name='tenants')
    op.drop_column('tenants', 'short_code')
