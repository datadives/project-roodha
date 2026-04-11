"""
auth.py
-------
Authentication-related APIs.
JWT is already validated by middleware.
"""

from fastapi import APIRouter, Request
from app.routes.response_utils import api_success

router = APIRouter()


@router.get("/me")
def get_current_user(request: Request):
    return api_success({"user": request.state.user}, message="Current user fetched")
