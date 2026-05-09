import asyncio
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from app import models
from app.database import AsyncSessionLocal


DEMO_TENANT_ID = "ROODHA_DEMO_01"
SYSTEM_USER = "demo-seed"

OP_CUTTING_ID = UUID("aaaaaaaa-0000-4000-8000-000000000001")
OP_MACHINING_ID = UUID("aaaaaaaa-0000-4000-8000-000000000002")
OP_QC_ID = UUID("aaaaaaaa-0000-4000-8000-000000000003")

MACHINE_MAIN_ID = UUID("bbbbbbbb-1111-4111-8111-111111111101")
MACHINE_SECONDARY_ID = UUID("bbbbbbbb-1111-4111-8111-111111111102")
MACHINE_QC_ID = UUID("bbbbbbbb-1111-4111-8111-111111111103")


def audit_kwargs():
    return {"created_by": SYSTEM_USER, "updated_by": SYSTEM_USER}


async def seed():
    now = datetime.now(timezone.utc).replace(microsecond=0)

    async with AsyncSessionLocal() as db:
        for table_name in [
            "job_cost_summaries",
            "notifications",
            "audit_logs",
            "job_operations",
            "jobs",
            "parts",
            "customers",
            "workers",
            "shifts",
            "operations_master",
            "machines",
            "users",
            "tenants",
        ]:
            await db.execute(models.text(f"DELETE FROM {table_name}"))
        await db.commit()

        tenant = models.Tenant(
            tenant_id=DEMO_TENANT_ID,
            company_name="Roodha Demo Works",
            short_code="ROODHA",
            subscription_plan="demo",
        )
        db.add(tenant)

        db.add_all([
            models.User(tenant_id=DEMO_TENANT_ID, user_id="dev-user-id", email="demo@roodha.local", role="OWNER"),
            models.User(tenant_id=DEMO_TENANT_ID, user_id="operator-id", email="operator@roodha.local", role="OPERATOR"),
        ])
        await db.commit()

        customer = models.Customer(
            customer_id=uuid4(),
            tenant_id=DEMO_TENANT_ID,
            name="Apex Mobility Components",
            contact_person="Nisha Rao",
            email="nisha.rao@example.com",
            phone="+91-98765-43210",
            **audit_kwargs(),
        )
        db.add(customer)
        await db.commit()

        part = models.Part(
            part_id=uuid4(),
            tenant_id=DEMO_TENANT_ID,
            customer_id=customer.customer_id,
            part_number="AXLE-HOUSING-204",
            description="Precision-machined axle housing",
            default_material_cost_per_unit=1800,
            default_operations_route=[
                {"id": str(OP_CUTTING_ID), "name": "Cutting", "sequence": 1},
                {"id": str(OP_MACHINING_ID), "name": "Machining", "sequence": 2},
                {"id": str(OP_QC_ID), "name": "Quality Check", "sequence": 3},
            ],
            **audit_kwargs(),
        )
        db.add(part)

        operations = [
            models.OperationsMaster(
                operation_id=OP_CUTTING_ID,
                tenant_id=DEMO_TENANT_ID,
                name="Cutting",
                standard_cycle_time_mins=30,
                sequence_number=1,
                **audit_kwargs(),
            ),
            models.OperationsMaster(
                operation_id=OP_MACHINING_ID,
                tenant_id=DEMO_TENANT_ID,
                name="Machining",
                standard_cycle_time_mins=150,
                sequence_number=2,
                **audit_kwargs(),
            ),
            models.OperationsMaster(
                operation_id=OP_QC_ID,
                tenant_id=DEMO_TENANT_ID,
                name="Quality Check",
                standard_cycle_time_mins=18,
                sequence_number=3,
                **audit_kwargs(),
            ),
        ]

        machines = [
            models.Machine(
                machine_id=MACHINE_MAIN_ID,
                tenant_id=DEMO_TENANT_ID,
                name="CNC-Main-01",
                type="CNC Turning Center",
                hourly_rate=1250,
                location="Bay A",
                is_active=True,
                **audit_kwargs(),
            ),
            models.Machine(
                machine_id=MACHINE_SECONDARY_ID,
                tenant_id=DEMO_TENANT_ID,
                name="CNC-Relief-02",
                type="CNC Turning Center",
                hourly_rate=980,
                location="Bay B",
                is_active=True,
                **audit_kwargs(),
            ),
            models.Machine(
                machine_id=MACHINE_QC_ID,
                tenant_id=DEMO_TENANT_ID,
                name="QC-Cell-01",
                type="Inspection Cell",
                hourly_rate=650,
                location="QC Lab",
                is_active=True,
                **audit_kwargs(),
            ),
        ]
        db.add_all(operations + machines)
        await db.commit()

        active_jobs = [
            ("ROODHA-DEMO-1001", 2, now - timedelta(minutes=10), models.JobStatus.IN_PROGRESS),
            ("ROODHA-DEMO-1002", 2, now + timedelta(hours=3), models.JobStatus.NOT_STARTED),
            ("ROODHA-DEMO-1003", 2, now + timedelta(hours=5), models.JobStatus.NOT_STARTED),
        ]

        for index, (job_number, quantity, due_date, status) in enumerate(active_jobs, start=1):
            job = models.Job(
                job_id=uuid4(),
                tenant_id=DEMO_TENANT_ID,
                job_number=job_number,
                customer_id=customer.customer_id,
                part_id=part.part_id,
                quantity=quantity,
                due_date=due_date,
                priority="HIGH",
                status=status,
                quoted_price=quantity * 5600,
                **audit_kwargs(),
            )
            db.add(job)
            await db.flush()
            db.add(
                models.JobOperation(
                    job_op_id=uuid4(),
                    tenant_id=DEMO_TENANT_ID,
                    job_id=job.job_id,
                    op_id=OP_MACHINING_ID,
                    machine_id=MACHINE_MAIN_ID,
                    sequence_number=1,
                    status=models.OperationStatus.IN_PROGRESS if index == 1 else models.OperationStatus.PLANNED,
                    planned_start_date=now + timedelta(hours=index - 1),
                    planned_end_date=now + timedelta(hours=index + 4),
                    actual_start_time=now - timedelta(hours=1) if index == 1 else None,
                    **audit_kwargs(),
                )
            )

        completed_windows = [
            (MACHINE_SECONDARY_ID, now - timedelta(hours=23), 1),
            (MACHINE_QC_ID, now - timedelta(hours=20), 1),
            (MACHINE_SECONDARY_ID, now - timedelta(hours=16), 2),
            (MACHINE_QC_ID, now - timedelta(hours=9), 1),
            (MACHINE_SECONDARY_ID, now - timedelta(hours=3), 1),
        ]

        for index, (machine_id, started_at, quantity) in enumerate(completed_windows, start=1):
            job = models.Job(
                job_id=uuid4(),
                tenant_id=DEMO_TENANT_ID,
                job_number=f"ROODHA-DONE-{index:04d}",
                customer_id=customer.customer_id,
                part_id=part.part_id,
                quantity=quantity,
                due_date=started_at + timedelta(hours=8),
                priority="MEDIUM",
                status=models.JobStatus.COMPLETED,
                quoted_price=quantity * 5200,
                **audit_kwargs(),
            )
            db.add(job)
            await db.flush()
            db.add(
                models.JobOperation(
                    job_op_id=uuid4(),
                    tenant_id=DEMO_TENANT_ID,
                    job_id=job.job_id,
                    op_id=OP_MACHINING_ID,
                    machine_id=machine_id,
                    sequence_number=1,
                    status=models.OperationStatus.COMPLETED,
                    planned_start_date=started_at,
                    planned_end_date=started_at + timedelta(hours=3),
                    actual_start_time=started_at,
                    actual_end_time=started_at + timedelta(hours=2, minutes=35),
                    quantity_completed=quantity,
                    **audit_kwargs(),
                )
            )

        await db.commit()

        print("Roodha demo seed complete.")
        print(f"Tenant: {DEMO_TENANT_ID}")
        print("Bottleneck: CNC-Main-01 has 3 queued jobs; ROODHA-DEMO-1001 is 10 minutes overdue.")
        print("History: 5 completed jobs from the last 24 hours are available for Machine Load Radar.")


if __name__ == "__main__":
    asyncio.run(seed())
