from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from jose import JWTError
from starlette.requests import Request
from starlette.responses import JSONResponse

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core import auth_middleware
from app.core.invoice_generator import generate_invoice


def make_request(path: str, token: str | None = None, method: str = "GET") -> Request:
    headers = []
    if token is not None:
        headers.append((b"authorization", f"Bearer {token}".encode("utf-8")))

    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": method,
        "path": path,
        "raw_path": path.encode("utf-8"),
        "headers": headers,
        "query_string": b"",
        "client": ("testclient", 50000),
        "server": ("testserver", 80),
        "scheme": "http",
    }

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    return Request(scope, receive=receive)


@pytest.fixture(autouse=True)
def production_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ENV", "production")


def test_empty_job_zero_cost_pdf_still_generates():
    pdf_bytes = generate_invoice(
        {
            "job_id": "JOB-EMPTY-001",
            "job_number": "JW-EMPTY-001",
            "customer_name": "Zero Cost Customer",
            "factory_name": "Project Roodha",
            "due_date": "2026-04-08",
            "quantity": 1,
            "quoted_price": 0,
            "machine_cost": 0,
            "labour_cost": None,
            "material_cost": 0,
            "total_cost": None,
            "last_calculated_at": None,
        }
    )

    assert pdf_bytes.startswith(b"%PDF-")
    assert len(pdf_bytes) > 500


def test_huge_number_invoice_pdf_still_generates_cleanly():
    pdf_bytes = generate_invoice(
        {
            "job_id": "JOB-HUGE-001",
            "job_number": "JW-HUGE-001",
            "customer_name": "Enterprise Customer",
            "factory_name": "Project Roodha",
            "due_date": "2026-04-30",
            "quantity": 2500,
            "quoted_price": 2450000.75,
            "machine_cost": 1200000.5,
            "labour_cost": 450000.25,
            "material_cost": 350000.75,
            "total_cost": 2000001.5,
            "last_calculated_at": "2026-04-08T12:00:00Z",
        }
    )

    assert pdf_bytes.startswith(b"%PDF-")
    assert len(pdf_bytes) > 500


def test_expired_jwt_cannot_download_invoice():
    middleware = auth_middleware.JWTAuthMiddleware(app=lambda scope, receive, send: None)

    async def call_next(_request):
        return JSONResponse({"ok": True})

    with patch.object(
        auth_middleware,
        "_decode_verified_token",
        side_effect=JWTError("Signature has expired"),
    ):
        response = asyncio.run(
            middleware.dispatch(
                make_request("/jobs/JOB-EDGE-001/download-invoice", token="expired.jwt"),
                call_next,
            )
        )

    assert response.status_code == 401
    assert "expired" in response.body.decode("utf-8").lower()
