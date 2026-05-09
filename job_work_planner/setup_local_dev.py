from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
    select,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker


ROOT = Path(__file__).resolve().parent
BACKEND_ENV = ROOT / "Backend" / ".env"
DEFAULT_DATABASE_URL = (
    "postgresql+psycopg2://postgres:postgres@localhost:5432/roodha_v15_local"
)


def load_backend_env() -> None:
    if not BACKEND_ENV.exists():
        return

    for raw_line in BACKEND_ENV.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_backend_env()

DATABASE_URL = (
    os.getenv("DATABASE_URL")
    or os.getenv("SQLALCHEMY_DATABASE_URL")
    or DEFAULT_DATABASE_URL
)

Base = declarative_base()


class Machine(Base):
    __tablename__ = "machines"

    id = Column(Integer, primary_key=True)
    code = Column(String(32), nullable=False, unique=True, index=True)
    name = Column(String(120), nullable=False)
    area = Column(String(80), nullable=False)
    status = Column(String(32), nullable=False, default="Available")
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False)

    jobs = relationship("Job", back_populates="machine")
    tasks = relationship("Task", back_populates="machine")


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True)
    job_number = Column(String(32), nullable=False, unique=True, index=True)
    title = Column(String(160), nullable=False)
    customer = Column(String(120), nullable=False)
    priority = Column(String(32), nullable=False, index=True)
    status = Column(String(32), nullable=False, default="Queued", index=True)
    due_at = Column(DateTime(timezone=True), nullable=False, index=True)
    estimated_minutes = Column(Integer, nullable=False)
    machine_id = Column(Integer, ForeignKey("machines.id"), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)

    machine = relationship("Machine", back_populates="jobs")
    tasks = relationship("Task", back_populates="job")


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False, index=True)
    machine_id = Column(Integer, ForeignKey("machines.id"), nullable=True, index=True)
    title = Column(String(160), nullable=False)
    status = Column(String(32), nullable=False, default="Pending", index=True)
    sequence = Column(Integer, nullable=False)
    planned_start_at = Column(DateTime(timezone=True), nullable=True)
    planned_end_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)

    job = relationship("Job", back_populates="tasks")
    machine = relationship("Machine", back_populates="tasks")


def seed_machines(now: datetime) -> list[Machine]:
    return [
        Machine(id=1, code="LASER-01", name="Laser Cutter 01", area="Cutting", status="Available", created_at=now),
        Machine(id=2, code="PRESS-02", name="Press Brake 02", area="Forming", status="Busy", created_at=now),
        Machine(id=3, code="CNC-03", name="CNC Mill 03", area="Machining", status="Available", created_at=now),
        Machine(id=4, code="WELD-04", name="Welding Bay 04", area="Fabrication", status="Maintenance", created_at=now),
        Machine(id=5, code="PACK-05", name="Packing Line 05", area="Dispatch", status="Available", created_at=now),
    ]


def seed_jobs(now: datetime) -> list[Job]:
    return [
        Job(id=1, job_number="ROO-LCL-1001", title="Emergency pump bracket", customer="Apex Utilities", priority="Critical", status="Queued", due_at=now + timedelta(minutes=45), estimated_minutes=90, machine_id=1, notes="Delay Guard should pulse Safety Orange.", created_at=now, updated_at=now),
        Job(id=2, job_number="ROO-LCL-1002", title="Conveyor guard repair", customer="Metro Foods", priority="Critical", status="Queued", due_at=now + timedelta(minutes=95), estimated_minutes=75, machine_id=2, notes="Second urgent job due inside two hours.", created_at=now, updated_at=now),
        Job(id=3, job_number="ROO-LCL-1003", title="Stainless spacer batch", customer="Northline Labs", priority="High", status="In Progress", due_at=now + timedelta(hours=4), estimated_minutes=180, machine_id=3, created_at=now, updated_at=now),
        Job(id=4, job_number="ROO-LCL-1004", title="Panel hinge set", customer="BrightRail", priority="Medium", status="Queued", due_at=now + timedelta(hours=8), estimated_minutes=120, machine_id=1, created_at=now, updated_at=now),
        Job(id=5, job_number="ROO-LCL-1005", title="Valve cover plate", customer="Kaveri Process", priority="Medium", status="Queued", due_at=now + timedelta(hours=12), estimated_minutes=150, machine_id=3, created_at=now, updated_at=now),
        Job(id=6, job_number="ROO-LCL-1006", title="Dispatch crate inserts", customer="Zenith Motors", priority="Low", status="Ready", due_at=now + timedelta(hours=18), estimated_minutes=60, machine_id=5, created_at=now, updated_at=now),
        Job(id=7, job_number="ROO-LCL-1007", title="Formed cable tray", customer="GreenGrid", priority="High", status="Queued", due_at=now + timedelta(days=1), estimated_minutes=240, machine_id=2, created_at=now, updated_at=now),
        Job(id=8, job_number="ROO-LCL-1008", title="Machine foot shim kit", customer="Orbital Packaging", priority="Medium", status="Queued", due_at=now + timedelta(days=2), estimated_minutes=110, machine_id=3, created_at=now, updated_at=now),
        Job(id=9, job_number="ROO-LCL-1009", title="Welded frame touch-up", customer="Harbor Tools", priority="Low", status="Blocked", due_at=now + timedelta(days=3), estimated_minutes=200, machine_id=4, notes="Blocked while welding bay is in maintenance.", created_at=now, updated_at=now),
        Job(id=10, job_number="ROO-LCL-1010", title="Final pack and label run", customer="BlueStone Medical", priority="Medium", status="Ready", due_at=now + timedelta(days=4), estimated_minutes=80, machine_id=5, created_at=now, updated_at=now),
    ]


def seed_tasks(now: datetime, jobs: list[Job]) -> list[Task]:
    tasks: list[Task] = []
    task_id = 1

    for job in jobs:
        start = now + timedelta(minutes=15 * job.id)
        steps = [
            ("Material check", 20),
            ("Machine operation", max(30, job.estimated_minutes - 45)),
            ("Quality check", 25),
        ]

        for sequence, (title, minutes) in enumerate(steps, start=1):
            end = start + timedelta(minutes=minutes)
            tasks.append(
                Task(
                    id=task_id,
                    job_id=job.id,
                    machine_id=job.machine_id,
                    title=title,
                    status="In Progress" if job.status == "In Progress" and sequence == 2 else "Pending",
                    sequence=sequence,
                    planned_start_at=start,
                    planned_end_at=end,
                    created_at=now,
                )
            )
            task_id += 1
            start = end

    return tasks


def add_if_empty(session, model, rows) -> int:
    existing_id = session.execute(select(model.id).limit(1)).scalar_one_or_none()
    if existing_id is not None:
        return 0

    session.add_all(rows)
    return len(rows)


def main() -> None:
    engine = create_engine(DATABASE_URL, future=True)
    Base.metadata.create_all(engine)

    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    now = datetime.now(timezone.utc).replace(microsecond=0)

    with SessionLocal() as session:
        machines = seed_machines(now)
        jobs = seed_jobs(now)
        tasks = seed_tasks(now, jobs)

        inserted_machines = add_if_empty(session, Machine, machines)
        inserted_jobs = add_if_empty(session, Job, jobs)
        inserted_tasks = add_if_empty(session, Task, tasks)
        session.commit()

    print("Local Roodha database is ready.")
    print(f"Database: {DATABASE_URL}")
    print(f"Machines inserted: {inserted_machines}")
    print(f"Jobs inserted: {inserted_jobs}")
    print(f"Tasks inserted: {inserted_tasks}")
    print("Critical Delay Guard jobs: ROO-LCL-1001 and ROO-LCL-1002")


if __name__ == "__main__":
    main()
