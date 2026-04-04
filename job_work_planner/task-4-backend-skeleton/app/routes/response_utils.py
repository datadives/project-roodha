from typing import Any


def api_success(data: Any, message: str = "OK") -> dict:
    return {
        "success": True,
        "message": message,
        "data": data,
    }
