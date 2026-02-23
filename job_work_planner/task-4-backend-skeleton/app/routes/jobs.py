"""
jobs.py
-------
Job APIs

RESPONSIBILITIES:
- Scrum 24: Create Job Header
- Scrum 25: Auto-generate Job Operations from Part Route

IMPORTANT DESIGN RULES:
- tenant_id NEVER comes from request payload
- tenant_id ALWAYS comes from JWT (request.state.user)
- Job operations are generated ONLY AFTER job header is created
- If operation creation fails → job is rolled back (atomic behavior)
"""

from fastapi import APIRouter, HTTPException, Request, status
from datetime import datetime
import uuid
import logging

# ---------------------------------------------------------------
# Import Scrum 25 service (business logic, NOT API)
# ---------------------------------------------------------------
from app.core.job_operations_service import create_job_operations

# ---------------------------------------------------------------
# Router
# ---------------------------------------------------------------
router = APIRouter(
    prefix="/jobs",
    tags=["Jobs"]
)

# ---------------------------------------------------------------
# Logger (shared application logger)
# ---------------------------------------------------------------
logger = logging.getLogger("jobwork-backend")

# ---------------------------------------------------------------
# MOCK DATABASES (TEMPORARY – replaced by DB later)
# ---------------------------------------------------------------
JOBS_TABLE = {}  # job_id -> job header

# Mock master data (simulating DB validation)
MOCK_CUSTOMERS = {
    "cust-1": {"tenant_id": "tenant-1"}
}

MOCK_PARTS = {
    "part-1": {"tenant_id": "tenant-1"}
}

# ---------------------------------------------------------------
# Constants
# ---------------------------------------------------------------
ALLOWED_PRIORITY = {"LOW", "MEDIUM", "HIGH"}
ALLOWED_CREATOR_ROLES = {"OWNER", "SUPERVISOR"}

# ---------------------------------------------------------------
# POST /jobs
# ---------------------------------------------------------------
@router.post("/", status_code=status.HTTP_201_CREATED)
def create_job(payload: dict, request: Request):
    """
    POST /jobs

    FLOW:
    1. Authenticate user
    2. Validate job header input (Scrum 24)
    3. Create job header
    4. Auto-generate job operations (Scrum 25)
    5. Return job + operations
    """

    # -----------------------------------------------------------
    # 1. Authentication & Context
    # -----------------------------------------------------------
    if not hasattr(request.state, "user"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized"
        )

    user = request.state.user
    tenant_id = user["tenant_id"]
    created_by = user["user_id"]
    role = user.get("role", "OWNER")  # mock default role

    # -----------------------------------------------------------
    # 2. RBAC (Role-Based Access Control)
    # -----------------------------------------------------------
    if role not in ALLOWED_CREATOR_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden"
        )

    # -----------------------------------------------------------
    # 3. Read request payload
    # -----------------------------------------------------------
    customer_id = payload.get("customer_id")
    part_id = payload.get("part_id")
    quantity = payload.get("quantity")
    received_date = payload.get("received_date")
    due_date = payload.get("due_date")
    priority = payload.get("priority")

    # -----------------------------------------------------------
    # 4. Validations (Scrum 24)
    # -----------------------------------------------------------
    # Explicit None checks (IMPORTANT: quantity=0 must not be treated as missing)
    if (
        customer_id is None
        or part_id is None
        or quantity is None
        or received_date is None
        or due_date is None
        or priority is None
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required fields"
        )

    if quantity <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Quantity must be > 0"
        )

    if priority not in ALLOWED_PRIORITY:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid priority"
        )

    # ISO date string comparison works correctly here
    if due_date < received_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid date range"
        )

    # -----------------------------------------------------------
    # 5. Tenant isolation checks (mocked)
    # -----------------------------------------------------------
    if (
        customer_id not in MOCK_CUSTOMERS
        or MOCK_CUSTOMERS[customer_id]["tenant_id"] != tenant_id
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid customer"
        )

    if (
        part_id not in MOCK_PARTS
        or MOCK_PARTS[part_id]["tenant_id"] != tenant_id
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid part"
        )

    # -----------------------------------------------------------
    # 6. Generate Job Header (Scrum 24)
    # -----------------------------------------------------------
    job_id = str(uuid.uuid4())

    tenant_job_count = sum(
        1 for job in JOBS_TABLE.values()
        if job["tenant_id"] == tenant_id
    )

    job_number = f"JOB-{tenant_id.upper()}-{tenant_job_count + 1:04d}"

    now = datetime.utcnow().isoformat()

    job = {
        "job_id": job_id,
        "job_number": job_number,
        "customer_id": customer_id,
        "part_id": part_id,
        "tenant_id": tenant_id,
        "quantity": quantity,
        "received_date": received_date,
        "due_date": due_date,
        "priority": priority,
        "status": "NOT_STARTED",
        "created_by": created_by,
        "created_at": now,
        "updated_at": now,
    }

    # Persist job header
    JOBS_TABLE[job_id] = job

    # -----------------------------------------------------------
    # 7. SCRUM 25 – Auto-generate Job Operations (ATOMIC)
    # -----------------------------------------------------------
    try:
        job_operations = create_job_operations(
            job_id=job_id,
            part_id=part_id,
            tenant_id=tenant_id
        )
    except Exception as e:
        # 🔥 Rollback job header if route creation fails
        JOBS_TABLE.pop(job_id, None)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    # -----------------------------------------------------------
    # 8. Audit Logging (Scrum 24 + 25)
    # -----------------------------------------------------------
    logger.info(
        "JOB_CREATED",
        extra={
            "event": "JOB_CREATED",
            "job_id": job_id,
            "tenant_id": tenant_id,
            "created_by": created_by
        }
    )

    logger.info(
        "JOB_ROUTE_CREATED",
        extra={
            "event": "JOB_ROUTE_CREATED",
            "job_id": job_id,
            "tenant_id": tenant_id
        }
    )

    # -----------------------------------------------------------
    # 9. Response
    # -----------------------------------------------------------
    return {
        "job": job,
        "operations": job_operations
    }

# -------------------------------------------------------------------
# GET /jobs  (Scrum 26)
# -------------------------------------------------------------------
@router.get("/")
def list_jobs(
    request: Request,
    status: str | None = None,
    customer_id: str | None = None,
    priority: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    page: int = 1,
    page_size: int = 25,
):
    """
    GET /jobs

    PURPOSE:
    - List jobs for current tenant
    - Supports filters + pagination

    FILTERS:
    - status
    - customer_id
    - priority
    - from_date / to_date (received_date based)

    PAGINATION:
    - page (default = 1)
    - page_size (default = 25, max = 100)

    NOTE:
    - In-memory filtering (MVP)
    - In production, DynamoDB GSI will be used
    """

    # ---------------------------------------------------------------
    # 1. Authentication
    # ---------------------------------------------------------------
    if not hasattr(request.state, "user"):
        raise HTTPException(status_code=401, detail="Unauthorized")

    tenant_id = request.state.user["tenant_id"]

    # ---------------------------------------------------------------
    # 2. Pagination validation
    # ---------------------------------------------------------------
    if page < 1:
        raise HTTPException(status_code=400, detail="page must be >= 1")

    if page_size < 1 or page_size > 100:
        raise HTTPException(status_code=400, detail="page_size must be between 1 and 100")

    # ---------------------------------------------------------------
    # 3. Tenant isolation
    # ---------------------------------------------------------------
    jobs = [
        job for job in JOBS_TABLE.values()
        if job["tenant_id"] == tenant_id
    ]

    # ---------------------------------------------------------------
    # 4. Apply filters
    # ---------------------------------------------------------------
    if status:
        jobs = [job for job in jobs if job["status"] == status]

    if customer_id:
        jobs = [job for job in jobs if job["customer_id"] == customer_id]

    if priority:
        jobs = [job for job in jobs if job["priority"] == priority]

    if from_date:
        jobs = [job for job in jobs if job["received_date"] >= from_date]

    if to_date:
        jobs = [job for job in jobs if job["received_date"] <= to_date]

    # ---------------------------------------------------------------
    # 5. Sorting
    #   - due_date ASC
    #   - priority DESC
    # ---------------------------------------------------------------
    priority_rank = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}

    jobs.sort(
        key=lambda job: (
            job["due_date"],
            -priority_rank.get(job["priority"], 0)
        )
    )

    # ---------------------------------------------------------------
    # 6. Pagination slice
    # ---------------------------------------------------------------
    total_count = len(jobs)
    start = (page - 1) * page_size
    end = start + page_size
    paginated_jobs = jobs[start:end]

    # ---------------------------------------------------------------
    # 7. Response
    # ---------------------------------------------------------------
    return {
        "items": paginated_jobs,
        "page": page,
        "page_size": page_size,
        "total_count": total_count
    }


# =======================================================
# SCRUM 30 – Jobs by Stage (Kanban View)
# GET /jobs/by-stage?date=YYYY-MM-DD
# =======================================================

from fastapi import Query

from app.core.jobs_by_stage_service import get_jobs_by_stage_service


@router.get("/by-stage")
def get_jobs_by_stage(
    request: Request,
    date: str | None = Query(
        default=None,
        description="Optional date filter (YYYY-MM-DD)"
    ),
):
    """
    SCRUM 30 – Jobs by Stage API

    Purpose:
    - Kanban-style backend response for supervisor UI
    - Groups jobs by current_stage

    Query Params:
    - date (optional): YYYY-MM-DD
    """

    # ---------------------------------------------------
    # 1. Authentication
    # ---------------------------------------------------
    if not hasattr(request.state, "user"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized"
        )

    tenant_id = request.state.user["tenant_id"]

    # ---------------------------------------------------
    # 2. Call service layer
    # ---------------------------------------------------
    try:
        response = get_jobs_by_stage_service(
            tenant_id=tenant_id,
            date=date
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc)
        )

    # ---------------------------------------------------
    # 3. Response
    # ---------------------------------------------------
    return response














# -------------------------------------------------------------------
# GET /jobs/{job_id}  (Scrum 27)
# -------------------------------------------------------------------
@router.get("/{job_id}")
def get_job_detail(job_id: str, request: Request):
    """
    GET /jobs/{job_id}

    PURPOSE:
    - Fetch single job header
    - Fetch ordered job operations
    - Compute current_stage
    - Compute delayed flag
    """

    # ---------------------------------------------------------------
    # 1. Authentication
    # ---------------------------------------------------------------
    if not hasattr(request.state, "user"):
        raise HTTPException(status_code=401, detail="Unauthorized")

    tenant_id = request.state.user["tenant_id"]

    # ---------------------------------------------------------------
    # 2. Fetch job header
    # ---------------------------------------------------------------
    job = JOBS_TABLE.get(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Tenant isolation (preferred: 404)
    if job["tenant_id"] != tenant_id:
        raise HTTPException(status_code=404, detail="Job not found")

    # ---------------------------------------------------------------
    # 3. Fetch job operations (Scrum 25 data)
    # ---------------------------------------------------------------
    from app.core.job_operations_service import JOB_OPERATIONS_TABLE

    operations = [
        op for op in JOB_OPERATIONS_TABLE.values()
        if op["job_id"] == job_id
    ]

    # Sort by sequence_number
    operations.sort(key=lambda op: op["sequence_number"])

    # ---------------------------------------------------------------
    # 4. Compute current_stage
    # ---------------------------------------------------------------
    current_stage = "COMPLETED"

    for op in operations:
        if op["status"] != "COMPLETED":
            current_stage = op["operation_id"]
            break

    # ---------------------------------------------------------------
    # 5. Compute delayed flag
    # ---------------------------------------------------------------
    today = datetime.utcnow().date()
    due_date = datetime.fromisoformat(job["due_date"]).date()

    delayed = today > due_date and job["status"] != "COMPLETED"

    # ---------------------------------------------------------------
    # 6. Response
    # ---------------------------------------------------------------
    return {
        "job": {
            **job,
            "current_stage": current_stage,
            "delayed": delayed
        },
        "operations": operations
    }



