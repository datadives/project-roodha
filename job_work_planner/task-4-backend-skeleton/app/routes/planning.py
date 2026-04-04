# app/routes/planning.py

from fastapi import APIRouter, Depends, HTTPException, Request, Query, status
from sqlalchemy.orm import Session
from app.database import get_db

from app.core.planning_service import get_planning_calendar_service
from app.routes.response_utils import api_success

router = APIRouter(
    prefix="/planning",
    tags=["Planning Calendar"],
)


@router.get("/")
def get_planning_calendar(
    request: Request,
    from_date: str | None = Query(None, description="YYYY-MM-DD"),
    to_date: str | None = Query(None, description="YYYY-MM-DD"),
    machine_id: str | None = Query(None),
    shift_id: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db)  # 👈 NEW: Get AWS Database session
):
<<<<<<< ours
<<<<<<< ours
    """
    GET /planning
    
    Returns operations grouped by machine → shift → date.
    Contract defined for Frontend Gantt / Calendar views.
    """
    
    # 1. Auth & Context
    tenant_id = "tenant-123"
    if hasattr(request.state, "user"):
        tenant_id = request.state.user.get("tenant_id", "tenant-123")
=======
    if not hasattr(request.state, "user"):
        raise HTTPException(status_code=401, detail="Unauthorized")
>>>>>>> theirs

    tenant_id = request.state.user["tenant_id"]

=======
    if not hasattr(request.state, "user"):
        raise HTTPException(status_code=401, detail="Unauthorized")

    tenant_id = request.state.user["tenant_id"]

>>>>>>> theirs
    try:
        response = get_planning_calendar_service(
            db=db,  # 👈 NEW: Pass database session to service
            tenant_id=tenant_id,
            from_date=from_date,
            to_date=to_date,
            machine_id=machine_id,
            shift_id=shift_id,
            status=status_filter,
            page=page,
            page_size=page_size,
        )
        return api_success(response)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
