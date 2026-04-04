# app/routes/metrics.py

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy.orm import Session
from app.database import get_db

from app.core.metrics_service import (
    get_wip_metrics_service,
    get_bottleneck_metrics_service,
    get_late_jobs_service,
)
from app.routes.response_utils import api_success

router = APIRouter(
    prefix="/metrics",
    tags=["Dashboard & Metrics"],
)


def _get_dashboard_user(request: Request):
<<<<<<< ours
<<<<<<< ours
    """Helper to enforce RBAC for dashboard access."""
    # Fallback to test tenant for local development if JWT is missing
    if not hasattr(request.state, "user"):
        return "tenant-123"
        # raise HTTPException(status_code=401, detail="Unauthorized")
        
    user = request.state.user
    role = user.get("role", "PLANNER")
    
    # Operators don't usually need the global analytics dashboard
=======
    if not hasattr(request.state, "user"):
        raise HTTPException(status_code=401, detail="Unauthorized")

    user = request.state.user
    role = user.get("role")

>>>>>>> theirs
=======
    if not hasattr(request.state, "user"):
        raise HTTPException(status_code=401, detail="Unauthorized")

    user = request.state.user
    role = user.get("role")

>>>>>>> theirs
    if role not in {"PLANNER", "SUPERVISOR", "ADMIN", "OWNER"}:
        raise HTTPException(status_code=403, detail="Forbidden: Dashboard access denied.")

    return user["tenant_id"]


@router.get("/wip")
def get_wip_metrics(
    request: Request,
    from_date: str | None = Query(None, description="YYYY-MM-DD"),
    to_date: str | None = Query(None, description="YYYY-MM-DD"),
<<<<<<< ours
<<<<<<< ours
    db: Session = Depends(get_db)  # 👈 NEW: Get AWS Database session
):
    tenant_id = _get_dashboard_user(request)
    return {"wip_by_stage": get_wip_metrics_service(db, tenant_id, from_date, to_date)}
=======
):
    tenant_id = _get_dashboard_user(request)
    return api_success({"wip_by_stage": get_wip_metrics_service(tenant_id, from_date, to_date)})

>>>>>>> theirs
=======
):
    tenant_id = _get_dashboard_user(request)
    return api_success({"wip_by_stage": get_wip_metrics_service(tenant_id, from_date, to_date)})

>>>>>>> theirs

@router.get("/bottlenecks")
def get_bottleneck_metrics(
    request: Request,
    from_date: str | None = Query(None, description="YYYY-MM-DD"),
    to_date: str | None = Query(None, description="YYYY-MM-DD"),
<<<<<<< ours
<<<<<<< ours
    db: Session = Depends(get_db)  # 👈 NEW: Get AWS Database session
):
    tenant_id = _get_dashboard_user(request)
    return {"bottlenecks": get_bottleneck_metrics_service(db, tenant_id, from_date, to_date)}
=======
):
    tenant_id = _get_dashboard_user(request)
    return api_success({"bottlenecks": get_bottleneck_metrics_service(tenant_id, from_date, to_date)})

>>>>>>> theirs
=======
):
    tenant_id = _get_dashboard_user(request)
    return api_success({"bottlenecks": get_bottleneck_metrics_service(tenant_id, from_date, to_date)})

>>>>>>> theirs

@router.get("/late-jobs")
def get_late_jobs_metrics(
    request: Request,
    db: Session = Depends(get_db)  # 👈 NEW: Get AWS Database session
):
    tenant_id = _get_dashboard_user(request)
<<<<<<< ours
<<<<<<< ours
    return get_late_jobs_service(db, tenant_id)
=======
    return api_success(get_late_jobs_service(tenant_id))
>>>>>>> theirs
=======
    return api_success(get_late_jobs_service(tenant_id))
>>>>>>> theirs
