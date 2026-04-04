# app/routes/system.py

<<<<<<< ours
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
import uuid

from app.database import get_db
from app import models

# We use the /masters prefix to match your API Gateway routing!
router = APIRouter(prefix="/masters", tags=["Master Data"])

# --- PYDANTIC SCHEMAS (For Input Validation) ---
class MachineCreate(BaseModel):
    name: str
    type: str
    is_active: bool = True

class ShiftCreate(BaseModel):
    name: str
    start_time: str
    end_time: str

# Hardcoded tenant_id for local testing (until we turn Cognito back on)
TEST_TENANT_ID = "tenant-123"

# ==========================================
# MACHINE ROUTES
# ==========================================
@router.post("/machines")
def create_machine(machine: MachineCreate, db: Session = Depends(get_db)):
    new_machine = models.Machine(
        machine_id=f"MAC-{str(uuid.uuid4())[:8]}", # Generates a unique ID
        tenant_id=TEST_TENANT_ID,
        name=machine.name,
        type=machine.type,
        is_active=machine.is_active
    )
    db.add(new_machine)
    db.commit()      # This actually saves it to AWS RDS!
    db.refresh(new_machine)
    return {"message": "Machine created successfully", "machine": new_machine}

@router.get("/machines")
def get_machines(db: Session = Depends(get_db)):
    # Fetch all machines for this specific tenant from AWS
    machines = db.query(models.Machine).filter(models.Machine.tenant_id == TEST_TENANT_ID).all()
    return machines

# ==========================================
# SHIFT ROUTES
# ==========================================
@router.post("/shifts")
def create_shift(shift: ShiftCreate, db: Session = Depends(get_db)):
    new_shift = models.Shift(
        shift_id=f"SHF-{str(uuid.uuid4())[:8]}",
        tenant_id=TEST_TENANT_ID,
        name=shift.name,
        start_time=shift.start_time,
        end_time=shift.end_time
    )
    db.add(new_shift)
    db.commit()
    db.refresh(new_shift)
    return {"message": "Shift created successfully", "shift": new_shift}

@router.get("/shifts")
def get_shifts(db: Session = Depends(get_db)):
    shifts = db.query(models.Shift).filter(models.Shift.tenant_id == TEST_TENANT_ID).all()
    return shifts
=======
from fastapi import APIRouter, Request, HTTPException
from app.routes.response_utils import api_success

router = APIRouter(
    tags=["System"]
)


@router.get("/health")
def health_check():
    """Health check for Load Balancers & Kubernetes."""
    return api_success({"status": "ok", "service": "jobwork-backend"}, message="Health check passed")


@router.get("/ready")
def readiness_check():
    """Readiness probe for traffic routing."""
    return api_success(
        {
            "status": "ready",
            "dependencies": {"database": "not_checked", "s3": "not_checked"},
        },
        message="Readiness check passed",
    )


@router.get("/tenant/current")
def get_current_tenant(request: Request):
    if not hasattr(request.state, "user"):
        raise HTTPException(status_code=401, detail="Unauthorized")

    user = request.state.user
    tenant = {
        "tenant_id": user["tenant_id"],
        "tenant_name": "Demo Company Pvt Ltd",
        "plan": "trial",
    }

    return api_success({"user": user, "tenant": tenant}, message="Current tenant fetched")
<<<<<<< ours
>>>>>>> theirs
=======
>>>>>>> theirs
