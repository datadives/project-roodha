"""
Seed script for JobWork Planner local development.

Inserts one dummy record each for:
- Tenant
- User
- Machine
- Customer
- Part

Usage:
    python seed_db.py
"""

from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.db.models import Customer, Machine, Part, Tenant, User


def seed(db: Session):
    tenant = db.query(Tenant).filter(Tenant.tenant_id == "tenant-demo").first()
    if not tenant:
        tenant = Tenant(tenant_id="tenant-demo", name="Demo Factory")
        db.add(tenant)
        db.flush()

    user = (
        db.query(User)
        .filter(User.tenant_id == tenant.tenant_id, User.email == "owner@demo.com")
        .first()
    )
    if not user:
        user = User(
            tenant_id=tenant.tenant_id,
            email="owner@demo.com",
            name="Demo Owner",
            role="OWNER",
            is_active=True,
        )
        db.add(user)

    customer = (
        db.query(Customer)
        .filter(Customer.tenant_id == tenant.tenant_id, Customer.name == "Demo OEM")
        .first()
    )
    if not customer:
        customer = Customer(
            tenant_id=tenant.tenant_id,
            name="Demo OEM",
            contact="+91-9999999999",
            is_active=True,
        )
        db.add(customer)
        db.flush()

    machine = (
        db.query(Machine)
        .filter(Machine.tenant_id == tenant.tenant_id, Machine.name == "CNC-01")
        .first()
    )
    if not machine:
        machine = Machine(
            tenant_id=tenant.tenant_id,
            name="CNC-01",
            type="CNC",
            is_active=True,
        )
        db.add(machine)

    part = (
        db.query(Part)
        .filter(Part.tenant_id == tenant.tenant_id, Part.part_number == "PART-DEMO-001")
        .first()
    )
    if not part:
        part = Part(
            tenant_id=tenant.tenant_id,
            part_number="PART-DEMO-001",
            customer_id=customer.customer_id,
            default_operations_route=[
                {"sequence": 1, "operation": "Cutting"},
                {"sequence": 2, "operation": "Machining"},
                {"sequence": 3, "operation": "QC"},
            ],
        )
        db.add(part)

    db.commit()
    print("✅ Seed data inserted/verified successfully.")


if __name__ == "__main__":
    db = SessionLocal()
    try:
        seed(db)
    finally:
        db.close()
