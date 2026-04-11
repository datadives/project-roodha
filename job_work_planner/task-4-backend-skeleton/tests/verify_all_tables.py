from pathlib import Path
import sys
import unittest

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


from app import models  # noqa: E402


TENANT_ID = "TENANT-1"


class VerifyAllTables(unittest.TestCase):
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
        self.db = self.SessionLocal()

    def tearDown(self):
        self.db.close()

    def test_create_and_delete_across_all_13_tables(self):
        tenant = models.Tenant(
            tenant_id=TENANT_ID,
            company_name="Integrity Factory",
            subscription_plan="V1",
        )
        user = models.User(
            tenant_id=TENANT_ID,
            user_id="USR-VERIFY",
            email="verify@test.com",
            role="ADMIN",
        )
        customer = models.Customer(
            customer_id="CUS-VERIFY",
            tenant_id=TENANT_ID,
            name="Integrity Customer",
            contact_person="Verifier",
            is_active=True,
        )
        operation = models.OperationsMaster(
            operation_id="OP-VERIFY",
            tenant_id=TENANT_ID,
            name="Verification Step",
            standard_cycle_time_mins=15,
        )
        machine = models.Machine(
            machine_id="MAC-VERIFY",
            tenant_id=TENANT_ID,
            name="Verifier Machine",
            type="CNC",
            is_active=True,
        )
        shift = models.Shift(
            shift_id="SHF-VERIFY",
            tenant_id=TENANT_ID,
            name="General",
            start_time="08:00",
            end_time="16:00",
        )
        worker = models.Worker(
            worker_id="WRK-VERIFY",
            tenant_id=TENANT_ID,
            name="Verifier Worker",
            role="OPERATOR",
            is_active=True,
        )
        part = models.Part(
            part_id="PRT-VERIFY",
            tenant_id=TENANT_ID,
            customer_id="CUS-VERIFY",
            part_number="PART-VERIFY",
            default_operations_route=[{"operation_id": "OP-VERIFY", "sequence": 1}],
        )
        job = models.Job(
            job_id="JOB-VERIFY",
            tenant_id=TENANT_ID,
            job_number="JW-VERIFY-001",
            customer_id="CUS-VERIFY",
            part_id="PRT-VERIFY",
            quantity=5,
            due_date="2026-05-01",
            priority="HIGH",
            status="READY",
        )
        job_operation = models.JobOperation(
            job_operation_id="JOP-VERIFY",
            tenant_id=TENANT_ID,
            job_id="JOB-VERIFY",
            operation_id="OP-VERIFY",
            machine_id="MAC-VERIFY",
            shift_id="SHF-VERIFY",
            sequence_number=1,
            status="READY",
            planned_start_date="2026-04-10",
            planned_end_date="2026-04-10",
        )
        production_entry = models.ProductionEntry(
            entry_id="PRD-VERIFY",
            tenant_id=TENANT_ID,
            job_operation_id="JOP-VERIFY",
            operator_id="WRK-VERIFY",
            produced_qty=5,
            scrap_qty=0,
            rework_qty=0,
            timestamp="2026-04-10T09:00:00",
        )
        audit_log = models.AuditLog(
            audit_id="AUD-VERIFY",
            tenant_id=TENANT_ID,
            entity_type="JOB",
            entity_id="JOB-VERIFY",
            action="CREATED",
            user_id="USR-VERIFY",
            before_state={},
            after_state={"job_id": "JOB-VERIFY"},
            timestamp="2026-04-10T09:05:00",
        )
        notification = models.Notification(
            notification_id="NOT-VERIFY",
            tenant_id=TENANT_ID,
            user_id="USR-VERIFY",
            type="INFO",
            message="Verification notification",
            is_read=False,
            created_at="2026-04-10T09:10:00",
        )

        created_records = [
            tenant,
            user,
            customer,
            operation,
            machine,
            shift,
            worker,
            part,
            job,
            job_operation,
            production_entry,
            audit_log,
            notification,
        ]

        self.db.add_all(created_records)
        self.db.commit()

        counts_by_table = {
            "tenants": self.db.query(models.Tenant).count(),
            "users": self.db.query(models.User).count(),
            "customers": self.db.query(models.Customer).count(),
            "operations_master": self.db.query(models.OperationsMaster).count(),
            "machines": self.db.query(models.Machine).count(),
            "shifts": self.db.query(models.Shift).count(),
            "workers": self.db.query(models.Worker).count(),
            "parts": self.db.query(models.Part).count(),
            "jobs": self.db.query(models.Job).count(),
            "job_operations": self.db.query(models.JobOperation).count(),
            "production_entries": self.db.query(models.ProductionEntry).count(),
            "audit_logs": self.db.query(models.AuditLog).count(),
            "notifications": self.db.query(models.Notification).count(),
        }

        self.assertEqual(sum(counts_by_table.values()), 13)
        self.assertTrue(all(count == 1 for count in counts_by_table.values()))

        for record in created_records:
            if hasattr(record, "tenant_id") and record.__tablename__ != "tenants":
                self.assertEqual(record.tenant_id, TENANT_ID)

        self.db.delete(notification)
        self.db.delete(audit_log)
        self.db.delete(production_entry)
        self.db.delete(job_operation)
        self.db.delete(job)
        self.db.delete(part)
        self.db.delete(worker)
        self.db.delete(shift)
        self.db.delete(machine)
        self.db.delete(operation)
        self.db.delete(customer)
        self.db.delete(user)
        self.db.delete(tenant)
        self.db.commit()

        self.assertEqual(self.db.query(models.Tenant).count(), 0)
        self.assertEqual(self.db.query(models.User).count(), 0)
        self.assertEqual(self.db.query(models.Customer).count(), 0)
        self.assertEqual(self.db.query(models.OperationsMaster).count(), 0)
        self.assertEqual(self.db.query(models.Machine).count(), 0)
        self.assertEqual(self.db.query(models.Shift).count(), 0)
        self.assertEqual(self.db.query(models.Worker).count(), 0)
        self.assertEqual(self.db.query(models.Part).count(), 0)
        self.assertEqual(self.db.query(models.Job).count(), 0)
        self.assertEqual(self.db.query(models.JobOperation).count(), 0)
        self.assertEqual(self.db.query(models.ProductionEntry).count(), 0)
        self.assertEqual(self.db.query(models.AuditLog).count(), 0)
        self.assertEqual(self.db.query(models.Notification).count(), 0)


if __name__ == "__main__":
    unittest.main()
