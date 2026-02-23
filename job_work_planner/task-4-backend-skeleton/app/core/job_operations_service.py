# app/core/job_operations_service.py

"""
job_operations_service.py
-------------------------

SCRUM 25 – Auto Generate Job Operations
SCRUM 28 - State Machine & Status Updates
SCRUM 29 - Planning (Machine/Shift)
SCRUM 31 - Execution Controls (Start/Pause/Resume)

Responsibilities:
- Validate part routes
- Create operations atomically
- Enforce state machine rules
- Capture execution timestamps & user audit
- Update parent job status automatically
"""

from datetime import datetime
from typing import List, Dict
import logging

logger = logging.getLogger("jobwork-backend")

# -----------------------------
# MOCK DATABASE TABLES
# (Replace with DynamoDB later)
# -----------------------------

MACHINES_TABLE = {
    "machine-1": {"machine_id": "machine-1", "tenant_id": "tenant-1"},
    "machine-2": {"machine_id": "machine-2", "tenant_id": "tenant-1"},
}

SHIFTS_TABLE = {
    "shift-A": {"shift_id": "shift-A", "tenant_id": "tenant-1"},
    "shift-B": {"shift_id": "shift-B", "tenant_id": "tenant-1"},
}

PARTS_TABLE = {
    "part-1": {
        "part_id": "part-1",
        "tenant_id": "tenant-1",
        "default_operations_route": ["op-cut", "op-drill", "op-paint"],
    }
}

OPERATIONS_TABLE = {
    "op-cut": {"operation_id": "op-cut", "name": "Cut"},
    "op-drill": {"operation_id": "op-drill", "name": "Drill"},
    "op-paint": {"operation_id": "op-paint", "name": "Paint"},
}

# job_operation_id -> record
JOB_OPERATIONS_TABLE: Dict[str, Dict] = {}

# -------------------------------------------------------
# SCRUM 32: Production Entries Table
# -------------------------------------------------------

# job_operation_id -> list of production entries
JOB_OPERATION_PRODUCTION_TABLE: Dict[str, List[Dict]] = {}

# -------------------------------------------------------
# STEP 1: Route Validation
# -------------------------------------------------------

def validate_part_route(part_id: str, tenant_id: str) -> List[str]:
    """
    Validates Part default operation route.
    """
    part = PARTS_TABLE.get(part_id)
    if not part:
        raise ValueError("Part does not exist")

    if part["tenant_id"] != tenant_id:
        raise ValueError("Part does not belong to tenant")

    route = part.get("default_operations_route")
    if not route:
        raise ValueError("Part has no operation route defined")

    for op_id in route:
        if op_id not in OPERATIONS_TABLE:
            raise ValueError(f"Invalid operation in route: {op_id}")

    return route


# -------------------------------------------------------
# STEP 2: Job Operation Creation (ATOMIC)
# -------------------------------------------------------

def create_job_operations(job_id: str, part_id: str, tenant_id: str) -> List[Dict]:
    """
    Creates job operations from part route.
    """
    created_operation_ids = []

    try:
        route = validate_part_route(part_id, tenant_id)

        for index, op_id in enumerate(route):
            job_operation_id = f"{job_id}-{op_id}"

            job_operation = {
              "job_operation_id": job_operation_id,
              "job_id": job_id,
              "tenant_id": tenant_id,
              "operation_id": op_id,
              "sequence_number": index + 1,
              "status": "READY" if index == 0 else "NOT_STARTED",
            }

            JOB_OPERATIONS_TABLE[job_operation_id] = job_operation
            created_operation_ids.append(job_operation_id)

        logger.info(
            "JOB_ROUTE_CREATED",
            extra={"job_id": job_id, "tenant_id": tenant_id},
        )

        return created_operation_ids

    except Exception as exc:
        # ROLLBACK
        for op_id in created_operation_ids:
            JOB_OPERATIONS_TABLE.pop(op_id, None)
        raise exc


# -------------------------------------------------------
# STEP 3: Read Operations for a Job
# -------------------------------------------------------

def get_job_operations(job_id: str) -> List[Dict]:
    """
    Returns job operations ordered by sequence_number.
    """
    operations = [
        op for op in JOB_OPERATIONS_TABLE.values()
        if op["job_id"] == job_id
    ]
    return sorted(operations, key=lambda x: x["sequence_number"])


# -------------------------------------------------------
# SCRUM 28/31: Operation Status Constants
# -------------------------------------------------------

OP_STATUS_NOT_STARTED = "NOT_STARTED"
OP_STATUS_READY = "READY"
OP_STATUS_IN_PROGRESS = "IN_PROGRESS"
OP_STATUS_PAUSED = "PAUSED"       # <--- SCRUM 31: Added PAUSED
OP_STATUS_COMPLETED = "COMPLETED"
OP_STATUS_CANCELLED = "CANCELLED"


# -------------------------------------------------------
# SCRUM 28/31: Allowed Status Transitions (State Machine)
# -------------------------------------------------------

ALLOWED_STATUS_TRANSITIONS = {
    OP_STATUS_NOT_STARTED: {OP_STATUS_IN_PROGRESS, OP_STATUS_CANCELLED},
    OP_STATUS_READY: {OP_STATUS_IN_PROGRESS},
    OP_STATUS_IN_PROGRESS: {OP_STATUS_COMPLETED, OP_STATUS_PAUSED}, # <--- Can Pause or Complete
    OP_STATUS_PAUSED: {OP_STATUS_IN_PROGRESS},                       # <--- Can Resume
    OP_STATUS_COMPLETED: set(),
    OP_STATUS_CANCELLED: set(),
}

def is_valid_status_transition(current_status: str, new_status: str) -> bool:
    """
    Validates whether a status change is allowed
    based on the defined state machine.
    """
    allowed = ALLOWED_STATUS_TRANSITIONS.get(current_status, set())
    return new_status in allowed


# -------------------------------------------------------
# SCRUM 28/31: Update Job Operation Status (Service Logic)
# -------------------------------------------------------

def update_job_operation_status(
    job_operation_id: str,
    new_status: str,
    *,
    user_id: str,
    quantity_completed: int | None = None,
    quantity_rejected: int | None = None,
    rework_flag: bool = False,
    rework_note: str | None = None,
    override_sequence: bool = False,
):
    """
    Clean implementation:
    - State machine enforcement
    - Planning prerequisite
    - Sequence enforcement
    - Execution timestamps
    - Auto-advance workflow
    - Parent job status update
    """

    # ---------------------------------------------------
    # 1️⃣ Fetch operation
    # ---------------------------------------------------
    job_op = JOB_OPERATIONS_TABLE.get(job_operation_id)
    if not job_op:
        raise ValueError("Job operation not found")

    current_status = job_op["status"]

    # ---------------------------------------------------
    # 2️⃣ State machine validation
    # ---------------------------------------------------
    if not is_valid_status_transition(current_status, new_status):
        raise ValueError(
            f"Invalid status transition: {current_status} → {new_status}"
        )

    # ---------------------------------------------------
    # 3️⃣ Planning prerequisite (for starting only)
    # ---------------------------------------------------
    if new_status == OP_STATUS_IN_PROGRESS and current_status != OP_STATUS_PAUSED:
        if not job_op.get("machine_id"):
            raise ValueError("Cannot start operation: Machine not assigned (Planning required)")

    # ---------------------------------------------------
    # 4️⃣ Sequence enforcement
    # ---------------------------------------------------
    if new_status == OP_STATUS_IN_PROGRESS and not override_sequence:
        if job_op["sequence_number"] > 1:
            prev_ops = [
                op for op in JOB_OPERATIONS_TABLE.values()
                if op["job_id"] == job_op["job_id"]
                and op["sequence_number"] == job_op["sequence_number"] - 1
            ]
            if not prev_ops or prev_ops[0]["status"] != OP_STATUS_COMPLETED:
                raise ValueError("Previous operation must be COMPLETED first")

    # ---------------------------------------------------
    # 5️⃣ Completion quantity validation
    # ---------------------------------------------------
    if new_status == OP_STATUS_COMPLETED:
        if quantity_completed is None:
            raise ValueError("quantity_completed is required when completing")
        if quantity_completed < 0:
            raise ValueError("quantity_completed cannot be negative")

        quantity_rejected = quantity_rejected or 0
        if quantity_rejected < 0:
            raise ValueError("quantity_rejected cannot be negative")

        if rework_flag and not rework_note:
            raise ValueError("rework_note is required when rework_flag is true")

    now = datetime.utcnow().isoformat()

    # ---------------------------------------------------
    # 6️⃣ Timestamp handling
    # ---------------------------------------------------
    if new_status == OP_STATUS_IN_PROGRESS and current_status != OP_STATUS_PAUSED:
        job_op["actual_start_time"] = now
        job_op["started_by"] = user_id

    elif new_status == OP_STATUS_PAUSED:
        job_op["paused_at"] = now
        job_op["paused_by"] = user_id

    elif new_status == OP_STATUS_IN_PROGRESS and current_status == OP_STATUS_PAUSED:
        job_op["resumed_at"] = now
        job_op["resumed_by"] = user_id

    elif new_status == OP_STATUS_COMPLETED:
        job_op["actual_end_time"] = now
        job_op["completed_by"] = user_id
        job_op["quantity_completed"] = quantity_completed
        job_op["quantity_rejected"] = quantity_rejected

    # ---------------------------------------------------
    # 7️⃣ Update status
    # ---------------------------------------------------
    job_op["status"] = new_status

    # ---------------------------------------------------
    # 8️⃣ SCRUM 33 – Auto-Advance Workflow
    # ---------------------------------------------------
    if new_status == OP_STATUS_COMPLETED:

        next_ops = [
            op for op in JOB_OPERATIONS_TABLE.values()
            if op["job_id"] == job_op["job_id"]
            and op["sequence_number"] == job_op["sequence_number"] + 1
        ]

        if next_ops:
            next_op = next_ops[0]

            if (
                next_op.get("machine_id")
                and next_op.get("shift_id")
                and next_op.get("planned_start_date")
                and next_op.get("planned_end_date")
            ):
                next_op["status"] = OP_STATUS_READY
            else:
                next_op["status"] = OP_STATUS_NOT_STARTED
                next_op["needs_planning"] = True

    # ---------------------------------------------------
    # 9️⃣ Parent Job Status Update
    # ---------------------------------------------------
    from app.routes.jobs import JOBS_TABLE
    job = JOBS_TABLE.get(job_op["job_id"])

    if job:
        all_ops = [
            op for op in JOB_OPERATIONS_TABLE.values()
            if op["job_id"] == job["job_id"]
        ]

        if all(op["status"] == OP_STATUS_COMPLETED for op in all_ops):
            job["status"] = "COMPLETED"
        elif any(op["status"] == OP_STATUS_IN_PROGRESS for op in all_ops):
            job["status"] = "IN_PROGRESS"

        job["updated_at"] = now

    logger.info(
        "OP_STATUS_CHANGED",
        extra={
            "job_operation_id": job_operation_id,
            "old_status": current_status,
            "new_status": new_status,
            "user_id": user_id,
        },
    )

    return job_op




# -------------------------------------------------------
# SCRUM 29: Plan Job Operation (Service Layer)
# -------------------------------------------------------

def plan_job_operation_service(
    job_operation_id: str,
    machine_id: str,
    shift_id: str,
    planned_start_date: str,
    planned_end_date: str,
):
    """
    SCRUM 29 – Plan Job Operation
    """
    conflict_warning = None

    # 1. Fetch job operation
    job_op = JOB_OPERATIONS_TABLE.get(job_operation_id)
    if not job_op:
        raise ValueError("Job operation not found")

    tenant_id = job_op.get("tenant_id")

    # 2. Validate machine & shift (tenant isolation)
    machine = MACHINES_TABLE.get(machine_id)
    if not machine:
        raise ValueError("Machine not found")
    shift = SHIFTS_TABLE.get(shift_id)
    if not shift:
        raise ValueError("Shift not found")

    if machine["tenant_id"] != tenant_id:
        raise ValueError("Machine does not belong to tenant")
    if shift["tenant_id"] != tenant_id:
        raise ValueError("Shift does not belong to tenant")

    # 3. Validate planning dates
    try:
        start_date = datetime.fromisoformat(planned_start_date)
        end_date = datetime.fromisoformat(planned_end_date)
    except ValueError:
        raise ValueError("Invalid date format. Use ISO format YYYY-MM-DD")

    if start_date > end_date:
        raise ValueError("planned_start_date cannot be after planned_end_date")

    # 4. Detect conflicts (SOFT)
    for op in JOB_OPERATIONS_TABLE.values():
        if op["job_operation_id"] == job_operation_id:
            continue
        if op.get("machine_id") != machine_id:
            continue

        existing_start = op.get("planned_start_date")
        existing_end = op.get("planned_end_date")
        if not existing_start or not existing_end:
            continue

        existing_start_dt = datetime.fromisoformat(existing_start)
        existing_end_dt = datetime.fromisoformat(existing_end)

        if start_date <= existing_end_dt and end_date >= existing_start_dt:
            conflict_warning = "Machine has overlapping planned operation in this time window"
            break

    # 5. Update planning fields
    now = datetime.utcnow().isoformat()
    job_op.update({
        "machine_id": machine_id,
        "shift_id": shift_id,
        "planned_start_date": planned_start_date,
        "planned_end_date": planned_end_date,
        "updated_at": now,
    })

    # 6. Audit log
    logger.info(
        "OP_PLANNED",
        extra={
            "event": "OP_PLANNED",
            "job_operation_id": job_operation_id,
            "machine_id": machine_id,
            "shift_id": shift_id,
        },
    )

    # 7. Response
    if conflict_warning:
        return {"job_operation": job_op, "warning": conflict_warning}

    return job_op 





# -------------------------------------------------------
# SCRUM 32 – Add Production Entry (Service Layer)
# -------------------------------------------------------

def add_production_entry_service(
    *,
    job_operation_id: str,
    produced_qty: int,
    scrap_qty: int,
    rework_qty: int,
    operator_id: str,
    notes: str | None = None,
):
    """
    Records production quantities for an operation.
    """

    # ---------------------------------------------------
    # 1. Fetch operation
    # ---------------------------------------------------
    job_op = JOB_OPERATIONS_TABLE.get(job_operation_id)
    if not job_op:
        raise ValueError("Job operation not found")

    # ---------------------------------------------------
    # 2. Prevent editing if COMPLETED
    # ---------------------------------------------------
    if job_op["status"] == OP_STATUS_COMPLETED:
        raise ValueError("Cannot record production. Operation already COMPLETED")

    # ---------------------------------------------------
    # 3. Validate quantities
    # ---------------------------------------------------
    if produced_qty < 0 or scrap_qty < 0 or rework_qty < 0:
        raise ValueError("Quantities cannot be negative")

    total_entry = produced_qty + scrap_qty + rework_qty

    if total_entry == 0:
        raise ValueError("At least one quantity must be greater than zero")

    # ---------------------------------------------------
    # 4. Get existing production entries
    # ---------------------------------------------------
    existing_entries = JOB_OPERATION_PRODUCTION_TABLE.get(job_operation_id, [])

    total_produced = sum(e["produced_qty"] for e in existing_entries)
    total_scrap = sum(e["scrap_qty"] for e in existing_entries)
    total_rework = sum(e["rework_qty"] for e in existing_entries)

    # ---------------------------------------------------
    # 5. Job Quantity Validation (STRICT RULE)
    # ---------------------------------------------------
    from app.routes.jobs import JOBS_TABLE

    job = JOBS_TABLE.get(job_op["job_id"])
    if not job:
        raise ValueError("Parent job not found")

    planned_qty = job["quantity"]

    if total_produced + total_scrap + total_rework + total_entry > planned_qty:
        raise ValueError("Production exceeds job quantity") 

    # ---------------------------------------------------
    # 6. Create production record
    # ---------------------------------------------------
    now = datetime.utcnow().isoformat()

    production_record = {
        "timestamp": now,
        "operator_id": operator_id,
        "produced_qty": produced_qty,
        "scrap_qty": scrap_qty,
        "rework_qty": rework_qty,
        "notes": notes,
    }

    # Save entry
    existing_entries.append(production_record)
    JOB_OPERATION_PRODUCTION_TABLE[job_operation_id] = existing_entries

    # ---------------------------------------------------
    # 7. Update computed totals on operation
    # ---------------------------------------------------
    job_op["total_produced"] = total_produced + produced_qty
    job_op["total_scrap"] = total_scrap + scrap_qty
    job_op["total_rework"] = total_rework + rework_qty

    job_op["updated_at"] = now

    # ---------------------------------------------------
    # 8. Audit log
    # ---------------------------------------------------
    logger.info(
        "PRODUCTION_RECORDED",
        extra={
            "job_operation_id": job_operation_id,
            "operator_id": operator_id,
            "produced_qty": produced_qty,
            "scrap_qty": scrap_qty,
            "rework_qty": rework_qty,
        },
    )

    return {
        "job_operation_id": job_operation_id,
        "totals": {
            "total_produced": job_op["total_produced"],
            "total_scrap": job_op["total_scrap"],
            "total_rework": job_op["total_rework"],
        },
        "entries_count": len(existing_entries),
    }