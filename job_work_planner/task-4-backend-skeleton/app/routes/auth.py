"""
auth.py
-------
Authentication-related APIs.
JWT is already validated by middleware.
"""
 
from fastapi import APIRouter, Request
 
router = APIRouter()
 
 
@router.get("/me")
def get_current_user(request: Request):
    """
    Returns current logged-in user.
 
    Middleware guarantees:
    - JWT is valid
    - user exists in request.state
    """
    return {
        "user": request.state.user
    }