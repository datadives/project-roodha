from __future__ import annotations

import os
import sys
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import models  # noqa: E402
from app.database import SQLALCHEMY_DATABASE_URL  # noqa: E402

TENANT_ID = "tenant-123"
CUSTOMER_ID = "CUST-DATADIVES"
PART_ID = "PART-STEEL-SHAFT"
JOB_ID = "JOB-STEEL-SHAFT-001"
OPERATION_CUTTING_ID = "CUTTING"
OPERATION_MACHINING_ID = "MACHINING"
MACHINE_CNC_ID = "MACH-CNC-MILL-01"
MACHINE_LATHE_ID = "MACH-LATHE-PRO"
JOB_OPERATION_1_ID = "JOP-STEEL-SHAFT-01"
JOB_OPERATION_2_ID = "JOP-STEEL-SHAFT-02"
DEV_ADMIN_USER_ID = "USER-ROSHAN-DEV"


def get_database_url() -> str:
    return (
        os.getenv("LOCAL_DATABASE_URL")
        or os.getenv("DATABASE_URL")
        or os.getenv("SQLALCHEMY_DATABASE_URL")
        or SQLALCHEMY_DATABASE_URL
    )


def get_session_factory() -> sessionmaker:
    engine = create_engine(get_database_url())
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)


def ensure_tenant_and_user(db: Session) -> None:
    tenant = db.query(models.Tenant).filter(models.Tenant.tenant_id == TENANT_ID).first()
    if not tenant:
        tenant = models.Tenant(
            tenant_id=TENANT_ID,
            company_name="Project Roodha Development Tenant",
            subscription_plan="V1-LOCAL",
        )
        db.add(tenant)

    user = db.query(models.User).filter(
        models.User.tenant_id == TENANT_ID,
        models.User.user_id == DEV_ADMIN_USER_ID,
    ).first()
    if not user:
        user = models.User(
            tenant_id=TENANT_ID,
            user_id=DEV_ADMIN_USER_ID,
            email="roshan@test.com",
            role="ADMIN",
        )
        db.add(user)


def ensure_customer(db: Session) -> None:
    customer = db.query(models.Customer).filter(
        models.Customer.tenant_id == TENANT_ID,
        models.Customer.customer_id == CUSTOMER_ID,
    ).first()

    if not customer:
        customer = models.Customer(
            customer_id=CUSTOMER_ID,
            tenant_id=TENANT_ID,
            name="DataDives Manufacturing",
            contact_person="Sourabh J.",
            is_active=True,
        )
        db.add(customer)
    else:
        customer.name = "DataDives Manufacturing"
        customer.contact_person = "Sourabh J."
        customer.is_active = True


def ensure_operations_master(db: Session) -> None:
    operations = [
        (OPERATION_CUTTING_ID, "Cutting", 35),
        (OPERATION_MACHINING_ID, "Machining", 55),
    ]

    for operation_id, name, cycle_time in operations:
        operation = db.query(models.OperationsMaster).filter(
            models.OperationsMaster.tenant_id == TENANT_ID,
            models.OperationsMaster.operation_id == operation_id,
        ).first()
        if not operation:
            operation = models.OperationsMaster(
                operation_id=operation_id,
                tenant_id=TENANT_ID,
                name=name,
                standard_cycle_time_mins=cycle_time,
            )
            db.add(operation)
        else:
            operation.name = name
            operation.standard_cycle_time_mins = cycle_time


def ensure_machines(db: Session) -> None:
    machines = [
        (MACHINE_CNC_ID, "CNC-Mill-01", "MILLING"),
        (MACHINE_LATHE_ID, "Lathe-Pro", "TURNING"),
    ]

    for machine_id, name, machine_type in machines:
        machine = db.query(models.Machine).filter(
            models.Machine.tenant_id == TENANT_ID,
            models.Machine.machine_id == machine_id,
        ).first()
        if not machine:
            machine = models.Machine(
                machine_id=machine_id,
                tenant_id=TENANT_ID,
                name=name,
                type=machine_type,
                is_active=True,
            )
            db.add(machine)
        else:
            machine.name = name
            machine.type = machine_type
            machine.is_active = True


def ensure_part(db: Session) -> None:
    route = [
        {"operation_id": OPERATION_CUTTING_ID, "sequence": 1, "label": "Cutting"},
        {"operation_id": OPERATION_MACHINING_ID, "sequence": 2, "label": "Machining"},
    ]

    part = db.query(models.Part).filter(
        models.Part.tenant_id == TENANT_ID,
        models.Part.part_id == PART_ID,
    ).first()

    if not part:
        part = models.Part(
            part_id=PART_ID,
            tenant_id=TENANT_ID,
            customer_id=CUSTOMER_ID,
            part_number="Steel Shaft",
            default_operations_route=route,
        )
        db.add(part)
    else:
        part.customer_id = CUSTOMER_ID
        part.part_number = "Steel Shaft"
        part.default_operations_route = route


def ensure_job(db: Session) -> None:
    due_date = (date.today() + timedelta(days=7)).isoformat()
    job = db.query(models.Job).filter(
        models.Job.tenant_id == TENANT_ID,
        models.Job.job_id == JOB_ID,
    ).first()

    if not job:
        job = models.Job(
            job_id=JOB_ID,
            tenant_id=TENANT_ID,
            job_number="JW-LOCAL-001",
            customer_id=CUSTOMER_ID,
            part_id=PART_ID,
            quantity=120,
            due_date=due_date,
            priority="HIGH",
            status="IN_PROGRESS",
        )
        db.add(job)
    else:
        job.job_number = "JW-LOCAL-001"
        job.customer_id = CUSTOMER_ID
        job.part_id = PART_ID
        job.quantity = 120
        job.due_date = due_date
        job.priority = "HIGH"
        job.status = "IN_PROGRESS"


def ensure_job_operations(db: Session) -> None:
    operations = [
        {
            "job_operation_id": JOB_OPERATION_1_ID,
            "operation_id": OPERATION_CUTTING_ID,
            "machine_id": MACHINE_CNC_ID,
            "sequence_number": 1,
            "status": "IN_PROGRESS",
        },
        {
            "job_operation_id": JOB_OPERATION_2_ID,
            "operation_id": OPERATION_MACHINING_ID,
            "machine_id": MACHINE_LATHE_ID,
            "sequence_number": 2,
            "status": "READY",
        },
    ]

    for payload in operations:
        job_operation = db.query(models.JobOperation).filter(
            models.JobOperation.tenant_id == TENANT_ID,
            models.JobOperation.job_operation_id == payload["job_operation_id"],
        ).first()

        if not job_operation:
            job_operation = models.JobOperation(
                job_operation_id=payload["job_operation_id"],
                tenant_id=TENANT_ID,
                job_id=JOB_ID,
                operation_id=payload["operation_id"],
                machine_id=payload["machine_id"],
                shift_id=None,
                sequence_number=payload["sequence_number"],
                status=payload["status"],
                planned_start_date=date.today().isoformat(),
                planned_end_date=(date.today() + timedelta(days=1)).isoformat(),
            )
            db.add(job_operation)
        else:
            job_operation.job_id = JOB_ID
            job_operation.operation_id = payload["operation_id"]
            job_operation.machine_id = payload["machine_id"]
            job_operation.shift_id = None
            job_operation.sequence_number = payload["sequence_number"]
            job_operation.status = payload["status"]
            job_operation.planned_start_date = date.today().isoformat()
            job_operation.planned_end_date = (date.today() + timedelta(days=1)).isoformat()


def seed_starter_data() -> None:
    session_factory = get_session_factory()
    db = session_factory()
    try:
        ensure_tenant_and_user(db)
        ensure_customer(db)
        ensure_operations_master(db)
        ensure_machines(db)
        ensure_part(db)
        ensure_job(db)
        ensure_job_operations(db)
        db.commit()
        print("Seeded V1.0 starter data for tenant tenant-123.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_starter_data()
