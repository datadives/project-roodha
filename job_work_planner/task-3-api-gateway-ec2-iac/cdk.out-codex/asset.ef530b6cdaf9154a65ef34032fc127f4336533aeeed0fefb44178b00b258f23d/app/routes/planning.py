from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.core.planning_service import get_planning_calendar_service
from app.database import get_db
from app.routes.response_utils import api_success

router = APIRouter(prefix="/planning", tags=["Planning Calendar"])


def _require_planning_user(request: Request) -> dict:
    user = getattr(request.state, "user", None)
    if not user or not user.get("tenant_id"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    role = user.get("role")
    if role not in {"PLANNER", "SUPERVISOR", "ADMIN", "OWNER"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Planning access denied.",
        )

    return user


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
    db: Session = Depends(get_db),
):
    user = _require_planning_user(request)

    try:
        response = get_planning_calendar_service(
            db=db,
            tenant_id=user["tenant_id"],
            from_date=from_date,
            to_date=to_date,
            machine_id=machine_id,
            shift_id=shift_id,
            status=status_filter,
            page=page,
            page_size=page_size,
        )
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return api_success(response)
