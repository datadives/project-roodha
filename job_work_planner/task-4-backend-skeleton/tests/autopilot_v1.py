from __future__ import annotations

import os
from pathlib import Path
import socket
import sys
import threading
import time

import httpx
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(_element, _compiler, **_kwargs):
    return "JSON"


import uvicorn  # noqa: E402
from app import models  # noqa: E402
from app.database import get_db  # noqa: E402
from app.main import app  # noqa: E402


class AutopilotError(RuntimeError):
    pass


def log(message: str) -> None:
    print(f"[autopilot] {message}")


def expect_success(response: httpx.Response, context: str, expected_status: int = 200):
    if response.status_code != expected_status:
        raise AutopilotError(f"{context} failed with {response.status_code}: {response.text}")

    payload = response.json()
    if not payload.get("success"):
        raise AutopilotError(f"{context} returned unsuccessful envelope: {payload}")
    return payload["data"]


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def seed_tenant(session_factory) -> None:
    db = session_factory()
    try:
        tenant = models.Tenant(
            tenant_id="tenant-123",
            company_name="Autopilot Tenant",
            subscription_plan="v1",
        )
        db.add(tenant)
        db.commit()
    finally:
        db.close()


def start_local_server(session_factory, port: int):
    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    base_url = f"http://127.0.0.1:{port}"
    with httpx.Client(timeout=10.0) as client:
        for _ in range(50):
            try:
                response = client.get(f"{base_url}/health")
                if response.status_code == 200:
                    return server, thread, base_url
            except httpx.HTTPError:
                pass
            time.sleep(0.2)

    server.should_exit = True
    thread.join(timeout=5)
    raise AutopilotError("Local API failed to start within the expected time")


def stop_local_server(server: uvicorn.Server, thread: threading.Thread) -> None:
    server.should_exit = True
    thread.join(timeout=10)
    app.dependency_overrides.clear()


def main() -> int:
    os.environ["ENV"] = "development"
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    models.Base.metadata.create_all(bind=engine)
    seed_tenant(session_factory)

    port = find_free_port()
    server, thread, base_url = start_local_server(session_factory, port)

    try:
        headers = {"Authorization": "Bearer test123"}
        with httpx.Client(base_url=base_url, timeout=15.0, headers=headers) as client:
            log("Creating tenant-scoped customer")
            customer_payload = expect_success(
                client.post(
                    "/master-data/customers",
                    json={"name": "Autopilot Customer", "contact": "qa@roodha.local", "is_active": True},
                ),
                "Create customer",
                expected_status=201,
            )

            log("Creating routable part with two operations")
            part_payload = expect_success(
                client.post(
                    "/master-data/parts",
                    json={
                        "part_number": "AUTO-PART-001",
                        "customer_id": customer_payload["customer_id"],
                        "default_operations_route": [
                            {"sequence": 1, "operation": "Cutting", "operation_id": "CUTTING"},
                            {"sequence": 2, "operation": "QC", "operation_id": "QC"},
                        ],
                    },
                ),
                "Create part",
                expected_status=201,
            )

            log("Fetching customers to confirm tenant-aware visibility")
            customers = expect_success(client.get("/master-data/customers"), "List customers")
            if not any(item["customer_id"] == customer_payload["customer_id"] for item in customers):
                raise AutopilotError("Created customer was not returned in the tenant-scoped customer list")

            due_date = "2026-12-31"
            log("Creating job through the API")
            created_job = expect_success(
                client.post(
                    "/jobs/",
                    json={
                        "customer_id": customer_payload["customer_id"],
                        "part_id": part_payload["part_id"],
                        "quantity": 5,
                        "due_date": due_date,
                        "priority": "HIGH",
                    },
                ),
                "Create job",
                expected_status=201,
            )

            job = created_job["job"]
            operations = sorted(created_job["operations"], key=lambda item: item["sequence_number"])
            if len(operations) != 2:
                raise AutopilotError(f"Expected 2 generated operations, found {len(operations)}")

            job_id = job["job_id"]
            log(f"Created job {job['job_number']} with {len(operations)} operations")

            for index, operation in enumerate(operations, start=1):
                operation_id = operation["job_operation_id"]
                log(f"Marking operation {index} as IN_PROGRESS")
                expect_success(
                    client.patch(f"/job-operations/{operation_id}/status", json={"status": "IN_PROGRESS"}),
                    f"Start operation {index}",
                )

                log(f"Marking operation {index} as COMPLETED")
                expect_success(
                    client.patch(f"/job-operations/{operation_id}/status", json={"status": "COMPLETED"}),
                    f"Complete operation {index}",
                )

            time.sleep(1)
            refreshed_job = expect_success(client.get(f"/jobs/{job_id}"), "Fetch completed job")

            if refreshed_job["job"]["status"] != "COMPLETED":
                raise AutopilotError(
                    f"Parent job did not auto-sync to COMPLETED. Current status: {refreshed_job['job']['status']}"
                )

            final_operations = refreshed_job["operations"]
            if any(operation["status"] != "COMPLETED" for operation in final_operations):
                raise AutopilotError("Not all operations reached COMPLETED status")

            log("Autopilot lifecycle passed: tenant-aware creation -> op 1 complete -> op 2 complete -> job sync")
            return 0
    finally:
        stop_local_server(server, thread)
        engine.dispose()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AutopilotError as exc:
        log(f"FAILED: {exc}")
        raise SystemExit(1)
