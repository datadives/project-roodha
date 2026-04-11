from datetime import datetime
from sqlalchemy import Column, String, Integer, Boolean, ForeignKey, JSON, Numeric, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

# ---------------------------------------------------------
# System & Auth Tables (Assuming these are already built, 
# but included here for ForeignKey relationships to work)
# ---------------------------------------------------------
class Tenant(Base):
    __tablename__ = "tenants"
    tenant_id = Column(String, primary_key=True, index=True)
    company_name = Column(String)
    subscription_plan = Column(String)

class User(Base):
    __tablename__ = "users"
    tenant_id = Column(String, ForeignKey("tenants.tenant_id"), primary_key=True)
    user_id = Column(String, primary_key=True) # Sort Key in Dynamo, PK here
    email = Column(String)
    role = Column(String) # OWNER, SUPERVISOR, OPERATOR

# ---------------------------------------------------------
# Master Data Tables
# ---------------------------------------------------------
class Customer(Base):
    __tablename__ = "customers"
    customer_id = Column(String, primary_key=True, index=True)
    tenant_id = Column(String, ForeignKey("tenants.tenant_id"))
    name = Column(String)
    contact_person = Column(String)
    is_active = Column(Boolean, default=True)

class Part(Base):
    __tablename__ = "parts"
    part_id = Column(String, primary_key=True, index=True)
    tenant_id = Column(String, ForeignKey("tenants.tenant_id"))
    customer_id = Column(String, ForeignKey("customers.customer_id"))
    part_number = Column(String)
    default_operations_route = Column(JSONB) # Uses PostgreSQL JSONB
    default_material_cost_per_unit = Column(Numeric(10, 2))

class OperationsMaster(Base):
    __tablename__ = "operations_master"
    operation_id = Column(String, primary_key=True, index=True)
    tenant_id = Column(String, ForeignKey("tenants.tenant_id"))
    name = Column(String)
    standard_cycle_time_mins = Column(Integer)

class Machine(Base):
    __tablename__ = "machines"
    machine_id = Column(String, primary_key=True, index=True)
    tenant_id = Column(String, ForeignKey("tenants.tenant_id"))
    name = Column(String)
    type = Column(String)
    is_active = Column(Boolean, default=True)
    hourly_rate = Column(Numeric(10, 2))

class Shift(Base):
    __tablename__ = "shifts"
    shift_id = Column(String, primary_key=True, index=True)
    tenant_id = Column(String, ForeignKey("tenants.tenant_id"))
    name = Column(String)
    start_time = Column(String)
    end_time = Column(String)

class Worker(Base):
    __tablename__ = "workers"
    worker_id = Column(String, primary_key=True, index=True)
    tenant_id = Column(String, ForeignKey("tenants.tenant_id"))
    name = Column(String)
    role = Column(String)
    is_active = Column(Boolean, default=True)
    hourly_rate = Column(Numeric(10, 2))

# ---------------------------------------------------------
# Transactional Tables (Jobs & WIP)
# ---------------------------------------------------------
class Job(Base):
    __tablename__ = "jobs"
    job_id = Column(String, primary_key=True, index=True)
    tenant_id = Column(String, ForeignKey("tenants.tenant_id"))
    job_number = Column(String)
    customer_id = Column(String, ForeignKey("customers.customer_id"))
    part_id = Column(String, ForeignKey("parts.part_id"))
    quantity = Column(Integer)
    due_date = Column(String)
    priority = Column(String)  # HIGH, MEDIUM, LOW
    status = Column(String)    # NOT_STARTED, IN_PROGRESS, COMPLETED
    quoted_price = Column(Numeric(10, 2), nullable=True)  # V1.0: Customer-facing price for profitability comparison

class JobOperation(Base):
    __tablename__ = "job_operations"
    job_operation_id = Column(String, primary_key=True, index=True)
    tenant_id = Column(String, ForeignKey("tenants.tenant_id"))
    job_id = Column(String, ForeignKey("jobs.job_id"))
    operation_id = Column(String, ForeignKey("operations_master.operation_id"))
    machine_id = Column(String, ForeignKey("machines.machine_id"), nullable=True)
    shift_id = Column(String, ForeignKey("shifts.shift_id"), nullable=True)
    sequence_number = Column(Integer)
    status = Column(String)
    actual_start_time = Column(DateTime, nullable=True)
    actual_end_time = Column(DateTime, nullable=True)
    quantity_completed = Column(Integer, default=0)
    quantity_rejected = Column(Integer, default=0)
    planned_start_date = Column(String, nullable=True)
    planned_end_date = Column(String, nullable=True)

class ProductionEntry(Base):
    __tablename__ = "production_entries"
    entry_id = Column(String, primary_key=True, index=True)
    tenant_id = Column(String, ForeignKey("tenants.tenant_id"))
    job_operation_id = Column(String, ForeignKey("job_operations.job_operation_id"))
    operator_id = Column(String, ForeignKey("workers.worker_id"))
    produced_qty = Column(Integer)
    scrap_qty = Column(Integer)
    rework_qty = Column(Integer)
    timestamp = Column(String)

# ---------------------------------------------------------
# System Utility Tables
# ---------------------------------------------------------
class AuditLog(Base):
    __tablename__ = "audit_logs"
    audit_id = Column(String, primary_key=True, index=True)
    tenant_id = Column(String, ForeignKey("tenants.tenant_id"))
    entity_type = Column(String) # JOB or OPERATION
    entity_id = Column(String)
    action = Column(String) # e.g., STATUS_CHANGED
    user_id = Column(String)
    before_state = Column(JSONB)
    after_state = Column(JSONB)
    timestamp = Column(String)

class Notification(Base):
    __tablename__ = "notifications"
    notification_id = Column(String, primary_key=True, index=True)
    tenant_id = Column(String, ForeignKey("tenants.tenant_id"))
    user_id = Column(String, nullable=True) # Nullable for Broadcasts
    type = Column(String) # e.g., MACHINE_OVERLOAD
    message = Column(String)
    is_read = Column(Boolean, default=False)
    created_at = Column(String)

# ---------------------------------------------------------
# Cost Summary Table
# ---------------------------------------------------------
class JobCostSummary(Base):
    __tablename__ = "job_cost_summaries"
    summary_id = Column(String, primary_key=True, index=True)
    tenant_id = Column(String, ForeignKey("tenants.tenant_id"))
    job_id = Column(String, ForeignKey("jobs.job_id"))
    machine_cost = Column(Numeric(10, 2))
    labour_cost = Column(Numeric(10, 2))
    material_cost = Column(Numeric(10, 2))
    total_cost = Column(Numeric(10, 2))
    last_calculated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)