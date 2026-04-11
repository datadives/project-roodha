from fastapi import APIRouter, HTTPException, Request, status

from app.routes.response_utils import api_success

router = APIRouter(tags=["System"])


@router.get("/health")
def health_check():
    return api_success({"status": "ok", "service": "jobwork-backend"}, message="Health check passed")


@router.get("/ready")
def readiness_check():
    return api_success(
        {
            "status": "ready",
            "dependencies": {"database": "not_checked", "s3": "not_checked"},
        },
        message="Readiness check passed",
    )


@router.get("/tenant/current")
def get_current_tenant(request: Request):
    user = getattr(request.state, "user", None)
    if not user or not user.get("tenant_id"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    tenant = {
        "tenant_id": user["tenant_id"],
        "tenant_name": "Demo Company Pvt Ltd",
        "plan": "trial",
    }

    return api_success({"user": user, "tenant": tenant}, message="Current tenant fetched")
