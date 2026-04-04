from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.core import master_data_service as service
from app.database import get_db
from app.routes.response_utils import api_success
from app.schemas import (
    CustomerCreate,
    CustomerUpdate,
    MachineCreate,
    MachineUpdate,
    PartCreate,
    PartUpdate,
    ShiftCreate,
    ShiftUpdate,
    WorkerCreate,
    WorkerUpdate,
)

router = APIRouter(prefix="/master-data", tags=["Master Data"])


def _tenant_id_from_request(request: Request) -> str:
    user = getattr(request.state, "user", None)
    tenant_id = user.get("tenant_id") if user else None
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    return tenant_id


def _serialize_customer(customer) -> dict:
    return {
        "customer_id": customer.customer_id,
        "tenant_id": customer.tenant_id,
        "name": customer.name,
        "contact": customer.contact_person,
        "is_active": customer.is_active,
    }


def _serialize_machine(machine, db: Session) -> dict:
    return {
        "machine_id": machine.machine_id,
        "tenant_id": machine.tenant_id,
        "name": machine.name,
        "type": machine.type,
        "is_active": machine.is_active,
        "has_active_jobs": service.machine_has_active_jobs(db, machine.tenant_id, machine.machine_id),
    }


def _serialize_shift(shift) -> dict:
    return {
        "shift_id": shift.shift_id,
        "tenant_id": shift.tenant_id,
        "name": shift.name,
        "start_time": shift.start_time,
        "end_time": shift.end_time,
    }


def _serialize_part(part) -> dict:
    return {
        "part_id": part.part_id,
        "tenant_id": part.tenant_id,
        "part_number": part.part_number,
        "customer_id": part.customer_id,
        "default_operations_route": part.default_operations_route,
    }


def _serialize_worker(worker) -> dict:
    return {
        "worker_id": worker.worker_id,
        "tenant_id": worker.tenant_id,
        "name": worker.name,
        "role": worker.role,
        "is_active": worker.is_active,
    }


@router.post("/customers", status_code=status.HTTP_201_CREATED)
def create_customer(payload: CustomerCreate, request: Request, db: Session = Depends(get_db)):
    customer = service.create_customer(db, _tenant_id_from_request(request), payload)
    return api_success(_serialize_customer(customer), message="Customer created")


@router.get("/customers")
def list_customers(
    request: Request,
    include_inactive: bool = Query(False, description="Set true for settings/admin screens"),
    db: Session = Depends(get_db),
):
    customers = service.list_customers(db, _tenant_id_from_request(request), include_inactive=include_inactive)
    return api_success([_serialize_customer(customer) for customer in customers])


@router.get("/customers/{customer_id}")
def get_customer(customer_id: str, request: Request, db: Session = Depends(get_db)):
    customer = service.get_customer(db, _tenant_id_from_request(request), customer_id)
    return api_success(_serialize_customer(customer))


@router.patch("/customers/{customer_id}")
def update_customer(customer_id: str, payload: CustomerUpdate, request: Request, db: Session = Depends(get_db)):
    customer = service.update_customer(db, _tenant_id_from_request(request), customer_id, payload)
    return api_success(_serialize_customer(customer), message="Customer updated")


@router.delete("/customers/{customer_id}")
def delete_customer(customer_id: str, request: Request, db: Session = Depends(get_db)):
    result = service.delete_customer(db, _tenant_id_from_request(request), customer_id)
    return api_success(result, message="Customer deleted")


@router.post("/machines", status_code=status.HTTP_201_CREATED)
def create_machine(payload: MachineCreate, request: Request, db: Session = Depends(get_db)):
    machine = service.create_machine(db, _tenant_id_from_request(request), payload)
    return api_success(_serialize_machine(machine, db), message="Machine created")


@router.get("/machines")
def list_machines(request: Request, db: Session = Depends(get_db)):
    machines = service.list_machines(db, _tenant_id_from_request(request))
    return api_success([_serialize_machine(machine, db) for machine in machines])


@router.get("/machines/{machine_id}")
def get_machine(machine_id: str, request: Request, db: Session = Depends(get_db)):
    machine = service.get_machine(db, _tenant_id_from_request(request), machine_id)
    return api_success(_serialize_machine(machine, db))


@router.patch("/machines/{machine_id}")
def update_machine(machine_id: str, payload: MachineUpdate, request: Request, db: Session = Depends(get_db)):
    machine = service.update_machine(db, _tenant_id_from_request(request), machine_id, payload)
    return api_success(_serialize_machine(machine, db), message="Machine updated")


@router.delete("/machines/{machine_id}")
def delete_machine(machine_id: str, request: Request, db: Session = Depends(get_db)):
    result = service.delete_machine(db, _tenant_id_from_request(request), machine_id)
    return api_success(result, message="Machine deleted")


@router.post("/shifts", status_code=status.HTTP_201_CREATED)
def create_shift(payload: ShiftCreate, request: Request, db: Session = Depends(get_db)):
    shift = service.create_shift(db, _tenant_id_from_request(request), payload)
    return api_success(_serialize_shift(shift), message="Shift created")


@router.get("/shifts")
def list_shifts(request: Request, db: Session = Depends(get_db)):
    shifts = service.list_shifts(db, _tenant_id_from_request(request))
    return api_success([_serialize_shift(shift) for shift in shifts])


@router.get("/shifts/{shift_id}")
def get_shift(shift_id: str, request: Request, db: Session = Depends(get_db)):
    shift = service.get_shift(db, _tenant_id_from_request(request), shift_id)
    return api_success(_serialize_shift(shift))


@router.patch("/shifts/{shift_id}")
def update_shift(shift_id: str, payload: ShiftUpdate, request: Request, db: Session = Depends(get_db)):
    shift = service.update_shift(db, _tenant_id_from_request(request), shift_id, payload)
    return api_success(_serialize_shift(shift), message="Shift updated")


@router.delete("/shifts/{shift_id}")
def delete_shift(shift_id: str, request: Request, db: Session = Depends(get_db)):
    result = service.delete_shift(db, _tenant_id_from_request(request), shift_id)
    return api_success(result, message="Shift deleted")


@router.post("/workers", status_code=status.HTTP_201_CREATED)
def create_worker(payload: WorkerCreate, request: Request, db: Session = Depends(get_db)):
    worker = service.create_worker(db, _tenant_id_from_request(request), payload)
    return api_success(_serialize_worker(worker), message="Worker created")


@router.get("/workers")
def list_workers(
    request: Request,
    include_inactive: bool = Query(True, description="Set false to show only active workers"),
    db: Session = Depends(get_db),
):
    workers = service.list_workers(db, _tenant_id_from_request(request), include_inactive=include_inactive)
    return api_success([_serialize_worker(worker) for worker in workers])


@router.get("/workers/{worker_id}")
def get_worker(worker_id: str, request: Request, db: Session = Depends(get_db)):
    worker = service.get_worker(db, _tenant_id_from_request(request), worker_id)
    return api_success(_serialize_worker(worker))


@router.patch("/workers/{worker_id}")
def update_worker(worker_id: str, payload: WorkerUpdate, request: Request, db: Session = Depends(get_db)):
    worker = service.update_worker(db, _tenant_id_from_request(request), worker_id, payload)
    return api_success(_serialize_worker(worker), message="Worker updated")


@router.delete("/workers/{worker_id}")
def delete_worker(worker_id: str, request: Request, db: Session = Depends(get_db)):
    result = service.delete_worker(db, _tenant_id_from_request(request), worker_id)
    return api_success(result, message="Worker deleted")


@router.post("/parts", status_code=status.HTTP_201_CREATED)
def create_part(payload: PartCreate, request: Request, db: Session = Depends(get_db)):
    part = service.create_part(db, _tenant_id_from_request(request), payload)
    return api_success(_serialize_part(part), message="Part created")


@router.get("/parts")
def list_parts(request: Request, db: Session = Depends(get_db)):
    parts = service.list_parts(db, _tenant_id_from_request(request))
    return api_success([_serialize_part(part) for part in parts])


@router.get("/parts/{part_id}")
def get_part(part_id: str, request: Request, db: Session = Depends(get_db)):
    part = service.get_part(db, _tenant_id_from_request(request), part_id)
    return api_success(_serialize_part(part))


@router.patch("/parts/{part_id}")
def update_part(part_id: str, payload: PartUpdate, request: Request, db: Session = Depends(get_db)):
    part = service.update_part(db, _tenant_id_from_request(request), part_id, payload)
    return api_success(_serialize_part(part), message="Part updated")


@router.delete("/parts/{part_id}")
def delete_part(part_id: str, request: Request, db: Session = Depends(get_db)):
    result = service.delete_part(db, _tenant_id_from_request(request), part_id)
    return api_success(result, message="Part deleted")
