"""
PROJECT ROODHA - BACKEND MODELS
FILE: models.py
PURPOSE: Defines the SQLAlchemy ORM models for the Project Roodha ecosystem.
         Includes core entities (Tenants, Users, Parts) and transactional records (Jobs, Operations).
         Implements Row-Level Security (RLS) compatible multi-tenancy.
"""

import uuid
import enum
from datetime import datetime
from sqlalchemy import Column, String, Integer, Boolean, ForeignKey, Numeric, DateTime, Enum, event, text, Time, UniqueConstraint, Text, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship

from app.core.tenant_context import user_id_context

Base = declarative_base()

# ---------------------------------------------------------
# --- ENUMERATIONS & DATA TYPES ---
# ---------------------------------------------------------

class JobStatus(str, enum.Enum):
    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"

class OperationStatus(str, enum.Enum):
    NOT_STARTED = "NOT_STARTED"
    PLANNED = "PLANNED"
    READY = "READY"
    IN_PROGRESS = "IN_PROGRESS"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"

# ---------------------------------------------------------
# --- MULTI-TENANCY SHIELD (AUDIT MIXIN) ---
# ---------------------------------------------------------

class TenantAuditMixin:
    """
    Automatically tracks creation and updates using request context.
    Ensures every record is stamped with the user identity for forensic auditing.
    """
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    created_by = Column(String, nullable=False)
    updated_by = Column(String, nullable=False)

@event.listens_for(Base, "before_insert", propagate=True)
def receive_before_insert(mapper, connection, target):
    user_id = user_id_context.get() or "system"
    if hasattr(target, "created_by") and target.created_by is None:
        target.created_by = user_id
    if hasattr(target, "updated_by") and target.updated_by is None:
        target.updated_by = user_id

@event.listens_for(Base, "before_update", propagate=True)
def receive_before_update(mapper, connection, target):
    user_id = user_id_context.get() or "system"
    if hasattr(target, "updated_by"):
        target.updated_by = user_id

# ---------------------------------------------------------
# --- MASTER DATA ENTITIES ---
# ---------------------------------------------------------

class Tenant(Base):
    __tablename__ = "tenants"
    tenant_id = Column(String, primary_key=True, index=True)
    company_name = Column(String)
    short_code = Column(String(10), unique=True, index=True)
    subscription_plan = Column(String)

class User(Base):
    __tablename__ = "users"
    tenant_id = Column(String, ForeignKey("tenants.tenant_id"), primary_key=True)
    user_id = Column(String, primary_key=True)
    email = Column(String)
    role = Column(String) # OWNER, SUPERVISOR, OPERATOR

class Customer(Base, TenantAuditMixin):
    __tablename__ = "customers"
    customer_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String, ForeignKey("tenants.tenant_id"), nullable=False)
    name = Column(String, nullable=False)
    contact_person = Column(String)
    email = Column(String)
    phone = Column(String)
    address = Column(String)
    is_active = Column(Boolean, default=True, nullable=False)

    jobs = relationship("Job", back_populates="customer")

class Part(Base, TenantAuditMixin):
    __tablename__ = "parts"
    part_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String, ForeignKey("tenants.tenant_id"), nullable=False)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.customer_id"))
    part_number = Column(String, nullable=False)
    description = Column(String)
    default_operations_route = Column(JSON)
    default_material_cost_per_unit = Column(Numeric(10, 2))
    is_active = Column(Boolean, default=True, nullable=False, server_default="true")

    __table_args__ = (
        UniqueConstraint('tenant_id', 'part_number', name='uq_part_number_tenant'),
    )

    jobs = relationship("Job", back_populates="part")

class OperationsMaster(Base, TenantAuditMixin):
    __tablename__ = "operations_master"
    operation_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String, ForeignKey("tenants.tenant_id"), nullable=False)
    name = Column(String, nullable=False)
    description = Column(String)
    standard_cycle_time_mins = Column("default_standard_cycle_time_mins", Integer, default=0, nullable=False)
    sequence_number = Column(Integer, nullable=True)

    __table_args__ = (
        UniqueConstraint('tenant_id', 'name', name='uq_operation_name_tenant'),
    )

class Machine(Base, TenantAuditMixin):
    __tablename__ = "machines"
    machine_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String, ForeignKey("tenants.tenant_id"), nullable=False)
    name = Column(String, nullable=False)
    type = Column(String)
    hourly_rate = Column(Numeric(10, 2))
    location = Column(String)
    is_active = Column(Boolean, default=True, nullable=False)

class Shift(Base, TenantAuditMixin):
    __tablename__ = "shifts"
    shift_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String, ForeignKey("tenants.tenant_id"), nullable=False)
    name = Column(String, nullable=False)
    start_time = Column(Time, nullable=False) # e.g., "08:00"
    end_time = Column(Time, nullable=False)   # e.g., "16:00"

class Worker(Base, TenantAuditMixin):
    __tablename__ = "workers"
    worker_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String, ForeignKey("tenants.tenant_id"), nullable=False)
    name = Column(String, nullable=False)
    role = Column(String)
    hourly_rate = Column(Numeric(10, 2))
    is_active = Column(Boolean, default=True, nullable=False)

# ---------------------------------------------------------
# --- TRANSACTIONAL LOGIC (JOBS & OPERATIONS) ---
# ---------------------------------------------------------

class Job(Base, TenantAuditMixin):
    __tablename__ = "jobs"
    job_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String, ForeignKey("tenants.tenant_id"), nullable=False)
    job_number = Column(String, nullable=False, index=True)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.customer_id"))
    part_id = Column(UUID(as_uuid=True), ForeignKey("parts.part_id"))
    quantity = Column(Integer, nullable=False)
    due_date = Column(DateTime)
    priority = Column(String) # HIGH, MEDIUM, LOW
    status = Column(Enum(JobStatus, name="job_status"), default=JobStatus.NOT_STARTED, server_default="NOT_STARTED", nullable=False)
    quoted_price = Column(Numeric(10, 2), nullable=True)

    part = relationship("Part", back_populates="jobs")
    customer = relationship("Customer", back_populates="jobs")

@event.listens_for(Job, "before_insert")
def generate_job_number(mapper, connection, target):
    """
    Automates Global Job Numbering with Tenant Prefix.
    Format: [TENANT_SHORT_CODE]-[SEQUENCE_VAL]
    """
    if target.job_number:
        return

    # 1. Fetch the next value from the global sequence
    res = connection.execute(text("SELECT nextval('job_number_seq')"))
    seq_val = res.scalar()

    # 2. Fetch the tenant's short_code from context (high-perf) or DB (fallback)
    from app.core.tenant_context import get_current_tenant_short_code
    short_code = get_current_tenant_short_code()
    
    if not short_code:
        tenant_res = connection.execute(
            text("SELECT short_code FROM tenants WHERE tenant_id = :tid"),
            {"tid": target.tenant_id}
        )
        short_code = tenant_res.scalar() or "JOB"

    target.job_number = f"{short_code}-{seq_val}"

class JobOperation(Base, TenantAuditMixin):
    __tablename__ = "job_operations"
    job_op_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String, ForeignKey("tenants.tenant_id"), nullable=False)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.job_id"))
    op_id = Column(UUID(as_uuid=True), ForeignKey("operations_master.operation_id"))

    machine_id = Column(UUID(as_uuid=True), ForeignKey("machines.machine_id"), nullable=True)
    worker_id = Column(UUID(as_uuid=True), ForeignKey("workers.worker_id"), nullable=True)
    shift_id = Column(UUID(as_uuid=True), ForeignKey("shifts.shift_id"), nullable=True)
    sequence_number = Column(Integer, nullable=False)
    status = Column(Enum(OperationStatus, name="operation_status"), default=OperationStatus.NOT_STARTED, server_default="NOT_STARTED", nullable=False)
    actual_start_time = Column(DateTime, nullable=True)
    actual_end_time = Column(DateTime, nullable=True)
    quantity_completed = Column(Integer, default=0, nullable=False, server_default="0")
    quantity_rejected = Column(Integer, default=0, nullable=False, server_default="0")
    planned_start_date = Column(DateTime, nullable=True)
    planned_end_date = Column(DateTime, nullable=True)

# ---------------------------------------------------------
# --- NOTIFICATIONS & AUDITING ---
# ---------------------------------------------------------

class Notification(Base):
    """In-app notification records. user_id=None means a tenant-wide broadcast."""
    __tablename__ = "notifications"

    notification_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String, ForeignKey("tenants.tenant_id"), nullable=False, index=True)
    user_id = Column(String, nullable=True, index=True)  # NULL = broadcast to all tenant users
    type = Column(String, nullable=False)                 # e.g. 'READY', 'CONFLICT', 'DELAY'
    message = Column(Text, nullable=False)
    entity_reference = Column(String, nullable=True)      # e.g. 'JOB-001', 'OP-XYZ'
    is_read = Column(Boolean, default=False, nullable=False, server_default="false")
    read_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    audit_id = Column(String, primary_key=True, index=True)
    tenant_id = Column(String, ForeignKey("tenants.tenant_id"))
    entity_type = Column(String)
    entity_id = Column(String)
    action = Column(String)
    user_id = Column(String)
    before_state = Column(JSON)
    after_state = Column(JSON)
    timestamp = Column(String)

# ---------------------------------------------------------
# --- INDUSTRIAL INTELLIGENCE (COSTING) ---
# ---------------------------------------------------------

class JobCostSummary(Base, TenantAuditMixin):
    __tablename__ = "job_cost_summaries"
    summary_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String, ForeignKey("tenants.tenant_id"), nullable=False)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.job_id"), unique=True)
    machine_cost = Column(Numeric(10, 2), default=0)
    labour_cost = Column(Numeric(10, 2), default=0)
    material_cost = Column(Numeric(10, 2), default=0)
    total_cost = Column(Numeric(10, 2), default=0)
    last_calculated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class CustomField(Base, TenantAuditMixin):
    __tablename__ = "custom_fields"
    field_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String, ForeignKey("tenants.tenant_id"), nullable=False)
    entity_type = Column(String, nullable=False) # e.g., 'JOB', 'PART'
    field_name = Column(String, nullable=False)
    field_type = Column(String, nullable=False) # e.g., 'STRING', 'NUMBER', 'DATE'
    is_required = Column(Boolean, default=False)

class CustomFieldValue(Base, TenantAuditMixin):
    __tablename__ = "custom_field_values"
    value_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String, ForeignKey("tenants.tenant_id"), nullable=False)
    field_id = Column(UUID(as_uuid=True), ForeignKey("custom_fields.field_id"), nullable=False)
    entity_id = Column(UUID(as_uuid=True), nullable=False) # The ID of the specific Job or Part
    field_value = Column(String, nullable=True) # Always stored as string, casted on frontend

