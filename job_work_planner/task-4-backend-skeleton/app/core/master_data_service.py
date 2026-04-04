import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app import models

ONGOING_JOB_OPERATION_STATUSES = {"NOT_STARTED", "READY", "IN_PROGRESS", "PAUSED"}


def _generate_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


def _get_or_404(db: Session, model, object_id: str, tenant_id: str, id_field: str):
    instance = (
        db.query(model)
        .filter(getattr(model, id_field) == object_id, model.tenant_id == tenant_id)
        .first()
    )
    if not instance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{model.__name__} not found",
        )
    return instance


def _normalize_text(value: str | None) -> str | None:
    if value is None:
        return None

    normalized = value.strip()
    return normalized or None


def _patch_instance(instance, payload: dict):
    for key, value in payload.items():
        setattr(instance, key, value)


def _validate_part_route(route: list[dict]):
    if not route:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="default_operations_route is mandatory and cannot be empty",
        )

    for step in route:
        if not isinstance(step, dict) or not step:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Each route step must be a non-empty object",
            )


def _has_ongoing_machine_assignments(db: Session, tenant_id: str, machine_id: str) -> bool:
    active_assignment = (
        db.query(models.JobOperation)
        .filter(
            models.JobOperation.tenant_id == tenant_id,
            models.JobOperation.machine_id == machine_id,
            models.JobOperation.status.in_(ONGOING_JOB_OPERATION_STATUSES),
        )
        .first()
    )
    return active_assignment is not None


def machine_has_active_jobs(db: Session, tenant_id: str, machine_id: str) -> bool:
    return _has_ongoing_machine_assignments(db, tenant_id, machine_id)


def create_customer(db: Session, tenant_id: str, payload):
    customer = models.Customer(
        customer_id=_generate_id("CUS"),
        tenant_id=tenant_id,
        name=_normalize_text(payload.name),
        contact_person=_normalize_text(payload.contact),
        is_active=payload.is_active,
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


def list_customers(db: Session, tenant_id: str, include_inactive: bool = False):
    query = db.query(models.Customer).filter(models.Customer.tenant_id == tenant_id)
    if not include_inactive:
        query = query.filter(models.Customer.is_active.is_(True))
    return query.all()


def get_customer(db: Session, tenant_id: str, customer_id: str):
    return _get_or_404(db, models.Customer, customer_id, tenant_id, "customer_id")


def update_customer(db: Session, tenant_id: str, customer_id: str, payload):
    customer = _get_or_404(db, models.Customer, customer_id, tenant_id, "customer_id")
    updates = payload.model_dump(exclude_unset=True)

    if "name" in updates:
        updates["name"] = _normalize_text(updates["name"])
    if "contact" in updates:
        updates["contact_person"] = _normalize_text(updates.pop("contact"))

    _patch_instance(customer, updates)
    db.commit()
    db.refresh(customer)
    return customer


def delete_customer(db: Session, tenant_id: str, customer_id: str):
    customer = _get_or_404(db, models.Customer, customer_id, tenant_id, "customer_id")

    existing_job = (
        db.query(models.Job)
        .filter(models.Job.tenant_id == tenant_id, models.Job.customer_id == customer.customer_id)
        .first()
    )
    if existing_job:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete customer with existing jobs. Deactivate instead.",
        )

    db.delete(customer)
    db.commit()
    return {"customer_id": customer_id}


def create_machine(db: Session, tenant_id: str, payload):
    machine = models.Machine(
        machine_id=_generate_id("MAC"),
        tenant_id=tenant_id,
        name=_normalize_text(payload.name),
        type=_normalize_text(payload.type),
        is_active=payload.is_active,
    )
    db.add(machine)
    db.commit()
    db.refresh(machine)
    return machine


def list_machines(db: Session, tenant_id: str):
    return db.query(models.Machine).filter(models.Machine.tenant_id == tenant_id).all()


def get_machine(db: Session, tenant_id: str, machine_id: str):
    return _get_or_404(db, models.Machine, machine_id, tenant_id, "machine_id")


def update_machine(db: Session, tenant_id: str, machine_id: str, payload):
    machine = _get_or_404(db, models.Machine, machine_id, tenant_id, "machine_id")
    updates = payload.model_dump(exclude_unset=True)

    if "name" in updates:
        updates["name"] = _normalize_text(updates["name"])
    if "type" in updates:
        updates["type"] = _normalize_text(updates["type"])
    if updates.get("is_active") is False and machine.is_active is True:
        if _has_ongoing_machine_assignments(db, tenant_id, machine_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot deactivate machine with ongoing jobs assigned.",
            )

    _patch_instance(machine, updates)
    db.commit()
    db.refresh(machine)
    return machine


def delete_machine(db: Session, tenant_id: str, machine_id: str):
    machine = _get_or_404(db, models.Machine, machine_id, tenant_id, "machine_id")
    db.delete(machine)
    db.commit()
    return {"machine_id": machine_id}


def create_shift(db: Session, tenant_id: str, payload):
    shift = models.Shift(
        shift_id=_generate_id("SHF"),
        tenant_id=tenant_id,
        name=_normalize_text(payload.name),
        start_time=payload.start_time,
        end_time=payload.end_time,
    )
    db.add(shift)
    db.commit()
    db.refresh(shift)
    return shift


def list_shifts(db: Session, tenant_id: str):
    return db.query(models.Shift).filter(models.Shift.tenant_id == tenant_id).all()


def get_shift(db: Session, tenant_id: str, shift_id: str):
    return _get_or_404(db, models.Shift, shift_id, tenant_id, "shift_id")


def update_shift(db: Session, tenant_id: str, shift_id: str, payload):
    shift = _get_or_404(db, models.Shift, shift_id, tenant_id, "shift_id")
    updates = payload.model_dump(exclude_unset=True)

    if "name" in updates:
        updates["name"] = _normalize_text(updates["name"])

    _patch_instance(shift, updates)
    db.commit()
    db.refresh(shift)
    return shift


def delete_shift(db: Session, tenant_id: str, shift_id: str):
    shift = _get_or_404(db, models.Shift, shift_id, tenant_id, "shift_id")
    db.delete(shift)
    db.commit()
    return {"shift_id": shift_id}


def create_worker(db: Session, tenant_id: str, payload):
    worker = models.Worker(
        worker_id=_generate_id("WRK"),
        tenant_id=tenant_id,
        name=_normalize_text(payload.name),
        role=_normalize_text(payload.role),
        is_active=payload.is_active,
    )
    db.add(worker)
    db.commit()
    db.refresh(worker)
    return worker


def list_workers(db: Session, tenant_id: str, include_inactive: bool = True):
    query = db.query(models.Worker).filter(models.Worker.tenant_id == tenant_id)
    if not include_inactive:
        query = query.filter(models.Worker.is_active.is_(True))
    return query.order_by(models.Worker.name.asc()).all()


def get_worker(db: Session, tenant_id: str, worker_id: str):
    return _get_or_404(db, models.Worker, worker_id, tenant_id, "worker_id")


def update_worker(db: Session, tenant_id: str, worker_id: str, payload):
    worker = _get_or_404(db, models.Worker, worker_id, tenant_id, "worker_id")
    updates = payload.model_dump(exclude_unset=True)

    if "name" in updates:
        updates["name"] = _normalize_text(updates["name"])
    if "role" in updates:
        updates["role"] = _normalize_text(updates["role"])

    _patch_instance(worker, updates)
    db.commit()
    db.refresh(worker)
    return worker


def delete_worker(db: Session, tenant_id: str, worker_id: str):
    worker = _get_or_404(db, models.Worker, worker_id, tenant_id, "worker_id")
    db.delete(worker)
    db.commit()
    return {"worker_id": worker_id}


def create_part(db: Session, tenant_id: str, payload):
    _get_or_404(db, models.Customer, payload.customer_id, tenant_id, "customer_id")
    _validate_part_route(payload.default_operations_route)

    part = models.Part(
        part_id=_generate_id("PRT"),
        tenant_id=tenant_id,
        part_number=_normalize_text(payload.part_number),
        customer_id=payload.customer_id,
        default_operations_route=payload.default_operations_route,
    )
    db.add(part)
    db.commit()
    db.refresh(part)
    return part


def list_parts(db: Session, tenant_id: str):
    return db.query(models.Part).filter(models.Part.tenant_id == tenant_id).all()


def get_part(db: Session, tenant_id: str, part_id: str):
    return _get_or_404(db, models.Part, part_id, tenant_id, "part_id")


def update_part(db: Session, tenant_id: str, part_id: str, payload):
    part = _get_or_404(db, models.Part, part_id, tenant_id, "part_id")
    updates = payload.model_dump(exclude_unset=True)

    if "customer_id" in updates:
        _get_or_404(db, models.Customer, updates["customer_id"], tenant_id, "customer_id")
    if "part_number" in updates:
        updates["part_number"] = _normalize_text(updates["part_number"])
    if "default_operations_route" in updates:
        _validate_part_route(updates["default_operations_route"])

    _patch_instance(part, updates)
    db.commit()
    db.refresh(part)
    return part


def delete_part(db: Session, tenant_id: str, part_id: str):
    part = _get_or_404(db, models.Part, part_id, tenant_id, "part_id")
    db.delete(part)
    db.commit()
    return {"part_id": part_id}
