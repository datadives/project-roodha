from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.core.metrics_service import (
    get_bottleneck_metrics_service,
    get_late_jobs_service,
    get_wip_metrics_service,
)
from app.database import get_db
from app.routes.response_utils import api_success

router = APIRouter(prefix="/metrics", tags=["Dashboard & Metrics"])


def _get_dashboard_user(request: Request) -> dict:
    user = getattr(request.state, "user", None)
    if not user or not user.get("tenant_id"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    role = user.get("role")
    if role not in {"PLANNER", "SUPERVISOR", "ADMIN", "OWNER"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: Dashboard access denied.")

    return user


@router.get("/wip")
def get_wip_metrics(
    request: Request,
    from_date: str | None = Query(None, description="YYYY-MM-DD"),
    to_date: str | None = Query(None, description="YYYY-MM-DD"),
    db: Session = Depends(get_db),
):
    tenant_id = _get_dashboard_user(request)["tenant_id"]
    return api_success({"wip_by_stage": get_wip_metrics_service(db, tenant_id, from_date, to_date)})


@router.get("/bottlenecks")
def get_bottleneck_metrics(
    request: Request,
    from_date: str | None = Query(None, description="YYYY-MM-DD"),
    to_date: str | None = Query(None, description="YYYY-MM-DD"),
    db: Session = Depends(get_db),
):
    tenant_id = _get_dashboard_user(request)["tenant_id"]
    return api_success({"bottlenecks": get_bottleneck_metrics_service(db, tenant_id, from_date, to_date)})


@router.get("/late-jobs")
def get_late_jobs_metrics(request: Request, db: Session = Depends(get_db)):
    tenant_id = _get_dashboard_user(request)["tenant_id"]
    return api_success(get_late_jobs_service(db, tenant_id))
