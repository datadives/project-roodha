from pathlib import Path
import asyncio
import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.requests import Request
from starlette.responses import JSONResponse

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

try:
    from jose import JWTError
except ImportError:
    class JWTError(Exception):
        pass

    class _DummyJWT:
        @staticmethod
        def get_unverified_header(_token):
            return {}

        @staticmethod
        def decode(*_args, **_kwargs):
            raise JWTError("python-jose is not installed")

    sys.modules["jose"] = SimpleNamespace(JWTError=JWTError, jwt=_DummyJWT())

try:
    import requests as _requests  # noqa: F401
except ImportError:
    class _DummyRequestException(Exception):
        pass

    def _dummy_get(*_args, **_kwargs):
        raise _DummyRequestException("requests is not installed")

    sys.modules["requests"] = SimpleNamespace(
        RequestException=_DummyRequestException,
        get=_dummy_get,
    )


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(_element, _compiler, **_kwargs):
    return "JSON"


from app import models  # noqa: E402
from app.core import auth_middleware  # noqa: E402
from app.routes import auth, job_operations, jobs, master_data  # noqa: E402


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def make_request(path: str = "/", token: str | None = None, user: dict | None = None, method: str = "GET") -> Request:
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

    request = Request(scope, receive=receive)
    if user is not None:
        request.state.user = user
    return request


def seed_tenant(db, tenant_id: str, user_id: str, role: str):
    db.add(models.Tenant(tenant_id=tenant_id, company_name=f"Tenant {tenant_id}", subscription_plan="V1"))
    db.add(models.User(tenant_id=tenant_id, user_id=user_id, email=f"{user_id}@example.com", role=role))


def seed_customer(db, tenant_id: str, customer_id: str, name: str):
    db.add(
        models.Customer(
            customer_id=customer_id,
            tenant_id=tenant_id,
            name=name,
            contact_person=f"{name} Contact",
            is_active=True,
        )
    )


def seed_part(db, tenant_id: str, customer_id: str, part_id: str, part_number: str):
    db.add(
        models.Part(
            part_id=part_id,
            tenant_id=tenant_id,
            customer_id=customer_id,
            part_number=part_number,
            default_operations_route=[
                {"operation_id": "CUTTING", "sequence": 1},
                {"operation_id": "QC", "sequence": 2},
            ],
        )
    )


def seed_job(db, tenant_id: str, job_id: str, customer_id: str, part_id: str, job_number: str, status: str = "NOT_STARTED"):
    db.add(
        models.Job(
            job_id=job_id,
            tenant_id=tenant_id,
            job_number=job_number,
            customer_id=customer_id,
            part_id=part_id,
            quantity=10,
            due_date="2026-04-30",
            priority="HIGH",
            status=status,
        )
    )


def seed_operation(db, tenant_id: str, job_id: str, job_operation_id: str, sequence_number: int, status: str):
    db.add(
        models.JobOperation(
            job_operation_id=job_operation_id,
            tenant_id=tenant_id,
            job_id=job_id,
            operation_id=f"OP-{sequence_number}",
            machine_id=None,
            shift_id=None,
            sequence_number=sequence_number,
            status=status,
            actual_start_time=None,
            actual_end_time=None,
            planned_start_date="2026-04-10" if status == "PLANNED" else None,
            planned_end_date="2026-04-10" if status == "PLANNED" else None,
        )
    )


class TestV1Logic(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        cls.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=cls.engine)
        models.Base.metadata.create_all(bind=cls.engine)

    @classmethod
    def tearDownClass(cls):
        models.Base.metadata.drop_all(bind=cls.engine)
        cls.engine.dispose()

    def setUp(self):
        models.Base.metadata.drop_all(bind=self.engine)
        models.Base.metadata.create_all(bind=self.engine)
        self.env_patch = patch.dict(os.environ, {"ENV": "production"}, clear=False)
        self.env_patch.start()

    def tearDown(self):
        self.env_patch.stop()

    def db_session(self):
        return self.SessionLocal()

    def install_token_decoder(self, claims_by_token: dict[str, dict]):
        def fake_decode_verified_token(token: str):
            payload = claims_by_token.get(token)
            if payload is None:
                raise JWTError("Invalid token")
            return payload

        patcher = patch.object(auth_middleware, "_decode_verified_token", side_effect=fake_decode_verified_token)
        patcher.start()
        self.addCleanup(patcher.stop)

    def register_token(self, token: str, tenant_id: str, role: str, user_id: str) -> dict:
        return {
            token: {
                "sub": user_id,
                "email": f"{user_id}@example.com",
                "custom:tenant_id": tenant_id,
                "custom:user_role": role,
            }
        }

    def test_production_rejects_test123_bearer_token(self):
        middleware = auth_middleware.JWTAuthMiddleware(app=lambda scope, receive, send: None)

        async def call_next(_request):
            return JSONResponse({"ok": True})

        with patch.object(auth_middleware, "_decode_verified_token", side_effect=JWTError("Invalid token")):
            response = asyncio.run(middleware.dispatch(make_request("/me", token="test123"), call_next))

        self.assertEqual(response.status_code, 401)
        self.assertIn("Invalid or expired token", response.body.decode("utf-8"))

    def test_cannot_complete_planned_job_operation(self):
        db = self.db_session()
        try:
            seed_tenant(db, "tenant-alpha", "user-supervisor", "SUPERVISOR")
            seed_customer(db, "tenant-alpha", "CUS-ALPHA", "Alpha Customer")
            seed_part(db, "tenant-alpha", "CUS-ALPHA", "PRT-ALPHA", "PART-ALPHA")
            seed_job(db, "tenant-alpha", "JOB-ALPHA", "CUS-ALPHA", "PRT-ALPHA", "JW-ALPHA-001")
            seed_operation(db, "tenant-alpha", "JOB-ALPHA", "JOP-ALPHA-001", 1, "PLANNED")
            db.commit()
            request = make_request(
                "/job-operations/JOP-ALPHA-001/status",
                user={"tenant_id": "tenant-alpha", "role": "SUPERVISOR", "user_id": "user-supervisor"},
                method="PATCH",
            )

            with self.assertRaises(HTTPException) as context:
                job_operations.update_operation_status(
                    "JOP-ALPHA-001",
                    payload=job_operations.StatusUpdatePayload(status="COMPLETED"),
                    request=request,
                    db=db,
                )
        finally:
            db.close()

        self.assertEqual(context.exception.status_code, 400)
        self.assertEqual(context.exception.detail, "Operation must be IN_PROGRESS before it can be marked COMPLETED")

    def test_completing_last_operation_marks_parent_job_completed(self):
        db = self.db_session()
        try:
            seed_tenant(db, "tenant-sync", "user-operator", "OPERATOR")
            seed_customer(db, "tenant-sync", "CUS-SYNC", "Sync Customer")
            seed_part(db, "tenant-sync", "CUS-SYNC", "PRT-SYNC", "PART-SYNC")
            seed_job(db, "tenant-sync", "JOB-SYNC", "CUS-SYNC", "PRT-SYNC", "JW-SYNC-001")
            seed_operation(db, "tenant-sync", "JOB-SYNC", "JOP-SYNC-001", 1, "COMPLETED")
            seed_operation(db, "tenant-sync", "JOB-SYNC", "JOP-SYNC-002", 2, "IN_PROGRESS")
            db.commit()
            request = make_request(
                "/job-operations/JOP-SYNC-002/status",
                user={"tenant_id": "tenant-sync", "role": "OPERATOR", "user_id": "user-operator"},
                method="PATCH",
            )
            response = job_operations.update_operation_status(
                "JOP-SYNC-002",
                payload=job_operations.StatusUpdatePayload(status="COMPLETED"),
                request=request,
                db=db,
            )

            self.assertTrue(response["success"])
            job = db.query(models.Job).filter(models.Job.job_id == "JOB-SYNC").first()
            self.assertIsNotNone(job)
            self.assertEqual(job.status, "COMPLETED")
        finally:
            db.close()

    def test_tenant_isolation_blocks_cross_tenant_customers_and_jobs(self):
        db = self.db_session()
        try:
            seed_tenant(db, "tenant-a", "user-a", "OWNER")
            seed_tenant(db, "tenant-b", "user-b", "OWNER")

            seed_customer(db, "tenant-a", "CUS-A", "Customer A")
            seed_customer(db, "tenant-b", "CUS-B", "Customer B")
            seed_part(db, "tenant-a", "CUS-A", "PRT-A", "PART-A")
            seed_part(db, "tenant-b", "CUS-B", "PRT-B", "PART-B")
            seed_job(db, "tenant-a", "JOB-A", "CUS-A", "PRT-A", "JW-A-001")
            seed_job(db, "tenant-b", "JOB-B", "CUS-B", "PRT-B", "JW-B-001")
            db.commit()

            request_a = make_request("/master-data/customers", user={"tenant_id": "tenant-a", "role": "OWNER", "user_id": "user-a"})

            customer_list_response = master_data.list_customers(
                request=request_a,
                include_inactive=False,
                db=db,
            )
            self.assertEqual([customer["customer_id"] for customer in customer_list_response["data"]], ["CUS-A"])

            jobs_list_response = jobs.list_jobs(
                request=request_a,
                page=1,
                page_size=20,
                status_filter=None,
                priority=None,
                customer_id=None,
                db=db,
            )
            self.assertEqual([job["job_id"] for job in jobs_list_response["data"]["items"]], ["JOB-A"])

            with self.assertRaises(HTTPException) as customer_context:
                master_data.get_customer("CUS-B", request=request_a, db=db)
            self.assertEqual(customer_context.exception.status_code, 404)

            with self.assertRaises(HTTPException) as job_context:
                jobs.get_job("JOB-B", request=request_a, db=db)
            self.assertEqual(job_context.exception.status_code, 404)
        finally:
            db.close()

    def test_job_stays_active_until_final_operation_then_completes(self):
        db = self.db_session()
        try:
            seed_tenant(db, "tenant-gold", "user-supervisor", "SUPERVISOR")
            seed_customer(db, "tenant-gold", "CUS-GOLD", "Gold Customer")
            db.add(
                models.Part(
                    part_id="PRT-GOLD",
                    tenant_id="tenant-gold",
                    customer_id="CUS-GOLD",
                    part_number="PART-GOLD",
                    default_operations_route=[
                        {"operation_id": "CUTTING", "sequence": 1},
                        {"operation_id": "MACHINING", "sequence": 2},
                        {"operation_id": "QC", "sequence": 3},
                    ],
                )
            )
            seed_job(db, "tenant-gold", "JOB-GOLD", "CUS-GOLD", "PRT-GOLD", "JW-GOLD-001")
            seed_operation(db, "tenant-gold", "JOB-GOLD", "JOP-GOLD-001", 1, "COMPLETED")
            seed_operation(db, "tenant-gold", "JOB-GOLD", "JOP-GOLD-002", 2, "IN_PROGRESS")
            seed_operation(db, "tenant-gold", "JOB-GOLD", "JOP-GOLD-003", 3, "READY")
            db.commit()

            request = make_request(
                "/job-operations/JOP-GOLD-002/status",
                user={"tenant_id": "tenant-gold", "role": "SUPERVISOR", "user_id": "user-supervisor"},
                method="PATCH",
            )

            second_step_response = job_operations.update_operation_status(
                "JOP-GOLD-002",
                payload=job_operations.StatusUpdatePayload(status="COMPLETED"),
                request=request,
                db=db,
            )
            self.assertTrue(second_step_response["success"])

            job_after_second_step = db.query(models.Job).filter(models.Job.job_id == "JOB-GOLD").first()
            self.assertIsNotNone(job_after_second_step)
            self.assertEqual(job_after_second_step.status, "IN_PROGRESS")

            third_step_start_request = make_request(
                "/job-operations/JOP-GOLD-003/status",
                user={"tenant_id": "tenant-gold", "role": "SUPERVISOR", "user_id": "user-supervisor"},
                method="PATCH",
            )
            start_response = job_operations.update_operation_status(
                "JOP-GOLD-003",
                payload=job_operations.StatusUpdatePayload(status="IN_PROGRESS"),
                request=third_step_start_request,
                db=db,
            )
            self.assertTrue(start_response["success"])

            third_step_complete_request = make_request(
                "/job-operations/JOP-GOLD-003/status",
                user={"tenant_id": "tenant-gold", "role": "SUPERVISOR", "user_id": "user-supervisor"},
                method="PATCH",
            )
            final_response = job_operations.update_operation_status(
                "JOP-GOLD-003",
                payload=job_operations.StatusUpdatePayload(status="COMPLETED"),
                request=third_step_complete_request,
                db=db,
            )
            self.assertTrue(final_response["success"])

            job_after_final_step = db.query(models.Job).filter(models.Job.job_id == "JOB-GOLD").first()
            self.assertIsNotNone(job_after_final_step)
            self.assertEqual(job_after_final_step.status, "COMPLETED")
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
