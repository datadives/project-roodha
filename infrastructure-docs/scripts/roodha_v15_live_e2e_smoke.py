#!/usr/bin/env python3
"""
Live AWS smoke test for Roodha V1.5.

This script intentionally mutates only timestamp-prefixed E2E data. It refuses to
run unless RUN_LIVE_AWS_E2E=true is set and AWS credentials are available.
Secrets are read from environment or Elastic Beanstalk configuration and are
never printed.
"""

from __future__ import annotations

import base64
import json
import os
import secrets
import string
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

import boto3
import psycopg2
import requests


REGION = os.getenv("REGION", "ap-south-1")
EB_APP_NAME = os.getenv("EB_APP_NAME", "roodha-backend")
EB_ENV_NAME = os.getenv("EB_ENV_NAME", "Roodha-backend-env")
BACKEND_URL = os.getenv(
    "BACKEND_URL",
    "http://roodha-backend-env.eba-52xsapkh.ap-south-1.elasticbeanstalk.com",
).rstrip("/")
USER_POOL_ID = os.getenv("COGNITO_USER_POOL_ID", "ap-south-1_U3JeTevgw")
USER_POOL_CLIENT_ID = os.getenv("COGNITO_APP_CLIENT_ID", "3ab798pg0k2p8hp7v6bbtlh4mj")


def fail(message: str) -> None:
    print(f"FAIL {message}")
    raise SystemExit(1)


def ok(marker: str, **details: Any) -> None:
    sanitized = " ".join(f"{key}={value}" for key, value in details.items())
    print(f"{marker}{(' ' + sanitized) if sanitized else ''}")


def require_live_flag() -> None:
    if os.getenv("RUN_LIVE_AWS_E2E", "").lower() != "true":
        fail("Set RUN_LIVE_AWS_E2E=true to run the live AWS smoke test.")


def eb_env() -> dict[str, str]:
    eb = boto3.client("elasticbeanstalk", region_name=REGION)
    response = eb.describe_configuration_settings(
        ApplicationName=EB_APP_NAME,
        EnvironmentName=EB_ENV_NAME,
    )
    settings = response["ConfigurationSettings"][0]["OptionSettings"]
    return {
        item["OptionName"]: item.get("Value", "")
        for item in settings
        if item.get("Namespace") == "aws:elasticbeanstalk:application:environment"
    }


def get_config() -> dict[str, str]:
    sts = boto3.client("sts", region_name=REGION)
    identity = sts.get_caller_identity()
    ok("AWS_IDENTITY_OK", account=identity.get("Account"))

    env = eb_env()
    config = {
        "DATABASE_URL": os.getenv("DATABASE_URL") or env.get("DATABASE_URL", ""),
        "INTEGRATION_WEBHOOK_TOKEN": os.getenv("INTEGRATION_WEBHOOK_TOKEN") or env.get("INTEGRATION_WEBHOOK_TOKEN", ""),
        "MAINTENANCE_SECRET": os.getenv("MAINTENANCE_SECRET") or env.get("MAINTENANCE_SECRET", ""),
        "EXPORTS_S3_BUCKET": os.getenv("EXPORTS_S3_BUCKET") or env.get("EXPORTS_S3_BUCKET", ""),
        "WEBHOOK_URL": os.getenv("V15_E2E_WEBHOOK_URL", ""),
        "WEBHOOK_VERIFY_URL": os.getenv("V15_E2E_WEBHOOK_VERIFY_URL", ""),
    }
    missing = [key for key in ["DATABASE_URL", "INTEGRATION_WEBHOOK_TOKEN", "MAINTENANCE_SECRET"] if not config[key]]
    if missing:
        fail(f"Missing required live config: {', '.join(missing)}")
    if not config["WEBHOOK_URL"]:
        fail("Set V15_E2E_WEBHOOK_URL to a mock external webhook capture URL.")
    return config


def sync_database_url(url: str) -> str:
    return url.replace("postgresql+asyncpg://", "postgresql://", 1)


def generated_password() -> str:
    alphabet = string.ascii_letters + string.digits
    return f"Roodha@{''.join(secrets.choice(alphabet) for _ in range(18))}1"


@dataclass
class TestUser:
    email: str
    role: str
    password: str
    token: str = ""
    sub: str = ""


class LiveSmoke:
    def __init__(self, config: dict[str, str]):
        self.config = config
        self.prefix = f"e2e-v15-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        self.tenant_id = self.prefix
        self.short_code = ("E2E" + self.prefix[-6:]).upper()[:10]
        self.cognito = boto3.client("cognito-idp", region_name=REGION)
        self.db = psycopg2.connect(sync_database_url(config["DATABASE_URL"]))
        self.db.autocommit = False
        self.owner = TestUser(f"{self.prefix}.owner@example.com", "OWNER", generated_password())
        self.supervisor = TestUser(f"{self.prefix}.supervisor@example.com", "SUPERVISOR", generated_password())
        self.operator = TestUser(f"{self.prefix}.operator@example.com", "OPERATOR", generated_password())
        self.machine_id = str(uuid.uuid4())
        self.worker_id = str(uuid.uuid4())
        self.shift_id = str(uuid.uuid4())
        self.operation_id = str(uuid.uuid4())
        self.part_number = f"{self.prefix}-PART"
        self.job_ids: list[str] = []
        self.job_operation_ids: list[str] = []

    def close(self) -> None:
        self.db.close()

    def db_exec(self, sql: str, params: tuple[Any, ...] = ()) -> list[tuple[Any, ...]]:
        with self.db.cursor() as cursor:
            cursor.execute(sql, params)
            if cursor.description:
                return cursor.fetchall()
            return []

    def commit(self) -> None:
        self.db.commit()

    def seed_base_data(self) -> None:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        self.db_exec(
            """
            INSERT INTO tenants (tenant_id, company_name, short_code, subscription_plan)
            VALUES (%s, %s, %s, 'e2e')
            ON CONFLICT (tenant_id) DO NOTHING
            """,
            (self.tenant_id, f"Roodha {self.prefix}", self.short_code),
        )
        self.db_exec(
            """
            INSERT INTO machines (machine_id, tenant_id, name, type, hourly_rate, is_active, created_at, updated_at, created_by, updated_by)
            VALUES (%s, %s, %s, 'Lathe', 500, true, %s, %s, 'live-e2e', 'live-e2e')
            """,
            (self.machine_id, self.tenant_id, f"{self.prefix}-Lathe", now, now),
        )
        self.db_exec(
            """
            INSERT INTO workers (worker_id, tenant_id, name, role, hourly_rate, is_active, created_at, updated_at, created_by, updated_by)
            VALUES (%s, %s, %s, 'Operator', 150, true, %s, %s, 'live-e2e', 'live-e2e')
            """,
            (self.worker_id, self.tenant_id, f"{self.prefix}-Worker", now, now),
        )
        self.db_exec(
            """
            INSERT INTO shifts (shift_id, tenant_id, name, start_time, end_time, created_at, updated_at, created_by, updated_by)
            VALUES (%s, %s, 'Day Shift', '09:00', '17:00', %s, %s, 'live-e2e', 'live-e2e')
            """,
            (self.shift_id, self.tenant_id, now, now),
        )
        self.db_exec(
            """
            INSERT INTO operations_master (
              operation_id, tenant_id, name, description, default_machine_type,
              default_standard_cycle_time_mins, sequence_number, created_at, updated_at, created_by, updated_by
            )
            VALUES (%s, %s, 'Turning', 'Live E2E turning op', 'Lathe', 120, 1, %s, %s, 'live-e2e', 'live-e2e')
            """,
            (self.operation_id, self.tenant_id, now, now),
        )
        self.db_exec(
            """
            INSERT INTO custom_fields (
              field_id, tenant_id, entity_type, field_name, field_type, options_json,
              is_required, created_at, updated_at, created_by, updated_by
            )
            VALUES (%s, %s, 'JOB', 'Material Grade', 'DROPDOWN', %s, true, %s, %s, 'live-e2e', 'live-e2e')
            """,
            (str(uuid.uuid4()), self.tenant_id, json.dumps(["EN8", "EN24", "MS"]), now, now),
        )
        self.db_exec(
            """
            INSERT INTO integration_webhooks (
              webhook_id, tenant_id, name, direction, url, event_types_json, is_active,
              created_at, updated_at, created_by, updated_by
            )
            VALUES (%s, %s, 'Live E2E Webhook', 'OUTBOUND', %s, %s, true, %s, %s, 'live-e2e', 'live-e2e')
            """,
            (str(uuid.uuid4()), self.tenant_id, self.config["WEBHOOK_URL"], json.dumps(["JOB_COMPLETED"]), now, now),
        )
        self.commit()

    def create_cognito_user(self, user: TestUser) -> None:
        attrs = [
            {"Name": "email", "Value": user.email},
            {"Name": "email_verified", "Value": "true"},
            {"Name": "custom:tenant_id", "Value": self.tenant_id},
            {"Name": "custom:user_role", "Value": user.role},
        ]
        if user.role == "OPERATOR":
            attrs.append({"Name": "custom:machine_id", "Value": self.machine_id})
        try:
            self.cognito.admin_create_user(
                UserPoolId=USER_POOL_ID,
                Username=user.email,
                UserAttributes=attrs,
                MessageAction="SUPPRESS",
            )
        except self.cognito.exceptions.UsernameExistsException:
            pass
        self.cognito.admin_set_user_password(
            UserPoolId=USER_POOL_ID,
            Username=user.email,
            Password=user.password,
            Permanent=True,
        )
        self.cognito.admin_add_user_to_group(UserPoolId=USER_POOL_ID, Username=user.email, GroupName=user.role)
        detail = self.cognito.admin_get_user(UserPoolId=USER_POOL_ID, Username=user.email)
        user.sub = next(attr["Value"] for attr in detail["UserAttributes"] if attr["Name"] == "sub")
        self.db_exec(
            """
            INSERT INTO users (tenant_id, user_id, email, role)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (tenant_id, user_id) DO UPDATE SET email = EXCLUDED.email, role = EXCLUDED.role
            """,
            (self.tenant_id, user.sub, user.email, user.role),
        )
        self.commit()

    def login(self, user: TestUser) -> None:
        try:
            response = self.cognito.admin_initiate_auth(
                UserPoolId=USER_POOL_ID,
                ClientId=USER_POOL_CLIENT_ID,
                AuthFlow="ADMIN_USER_PASSWORD_AUTH",
                AuthParameters={"USERNAME": user.email, "PASSWORD": user.password},
            )
        except Exception:
            response = self.cognito.initiate_auth(
                ClientId=USER_POOL_CLIENT_ID,
                AuthFlow="USER_PASSWORD_AUTH",
                AuthParameters={"USERNAME": user.email, "PASSWORD": user.password},
            )
        user.token = response["AuthenticationResult"]["IdToken"]

    def headers(self, user: TestUser) -> dict[str, str]:
        return {"Authorization": f"Bearer {user.token}", "X-Tenant-ID": self.tenant_id}

    def api(self, method: str, path: str, user: TestUser | None = None, **kwargs):
        headers = kwargs.pop("headers", {})
        if user:
            headers.update(self.headers(user))
        response = requests.request(method, f"{BACKEND_URL}/api{path}", headers=headers, timeout=30, **kwargs)
        if response.status_code >= 400:
            raise AssertionError(f"{method} {path} failed status={response.status_code} body={response.text[:240]}")
        data = response.json()
        return data.get("data", data)

    def create_jobs_via_integration(self) -> None:
        for index in range(6):
            payload = {
                "tenant_id": self.tenant_id,
                "customer_name": f"{self.prefix}-Customer",
                "part_number": self.part_number,
                "part_description": "Live V1.5 smoke part",
                "default_operations_route": [
                    {
                        "operation_id": self.operation_id,
                        "operation": "Turning",
                        "sequence_number": 1,
                        "default_machine_type": "Lathe",
                    }
                ],
                "quantity": 4,
                "due_date": (datetime.now(timezone.utc) + timedelta(days=index + 1)).isoformat(),
                "priority": "HIGH" if index == 0 else "MEDIUM",
                "custom_fields": {"Material Grade": "EN24"},
                "tags": ["Critical"] if index == 0 else [],
            }
            response = requests.post(
                f"{BACKEND_URL}/api/integrations/jobs",
                headers={"x-roodha-integration-token": self.config["INTEGRATION_WEBHOOK_TOKEN"]},
                json=payload,
                timeout=30,
            )
            if response.status_code != 201:
                raise AssertionError(f"integration job create failed status={response.status_code} body={response.text[:240]}")
            data = response.json()["data"]
            self.job_ids.append(data["job_id"])
        rows = self.db_exec(
            """
            SELECT jo.job_op_id::text
            FROM job_operations jo
            JOIN jobs j ON j.job_id = jo.job_id
            WHERE jo.tenant_id = %s AND j.job_id::text = ANY(%s)
            ORDER BY j.due_date ASC, jo.sequence_number ASC
            """,
            (self.tenant_id, self.job_ids),
        )
        self.job_operation_ids = [row[0] for row in rows]
        if len(self.job_operation_ids) != 6:
            raise AssertionError(f"expected 6 job operations, got {len(self.job_operation_ids)}")
        custom_rows = self.db_exec(
            """
            SELECT cfv.value_text, j.tags_json
            FROM custom_field_values cfv
            JOIN custom_fields cf ON cf.field_id = cfv.field_id
            JOIN jobs j ON j.job_id = cfv.entity_id
            WHERE cf.tenant_id = %s AND cf.field_name = 'Material Grade' AND j.job_id::text = %s
            """,
            (self.tenant_id, self.job_ids[0]),
        )
        if not custom_rows or custom_rows[0][0] != "EN24" or "Critical" not in (custom_rows[0][1] or []):
            raise AssertionError("custom field or Critical tag did not persist")
        ok("CUSTOM_FIELDS_WEBHOOK_PASS", jobs=len(self.job_ids), operations=len(self.job_operation_ids))

    def run_scheduler(self) -> None:
        preview = self.api(
            "POST",
            "/planning/auto-schedule/preview",
            user=self.supervisor,
            json={
                "from_date": datetime.now(timezone.utc).date().isoformat(),
                "to_date": (datetime.now(timezone.utc).date() + timedelta(days=7)).isoformat(),
                "job_ids": self.job_ids,
                "limit": 10,
            },
        )
        suggestions = [item for item in preview["suggestions"] if item.get("machine_id")]
        if len(suggestions) < 6:
            raise AssertionError(f"expected 6 machine-backed suggestions, got {len(suggestions)}")
        first = suggestions[0]
        manual_start = (datetime.now(timezone.utc) + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
        first["planned_start_date"] = manual_start.isoformat()
        first["planned_end_date"] = (manual_start + timedelta(hours=2)).isoformat()
        applied = self.api("POST", "/planning/auto-schedule/apply", user=self.supervisor, json={"suggestions": suggestions})
        if applied["applied_count"] != len(suggestions):
            raise AssertionError(f"bulk apply count mismatch: {applied}")
        rows = self.db_exec(
            """
            SELECT machine_id::text, planned_start_date, planned_end_date
            FROM job_operations
            WHERE tenant_id = %s AND job_op_id::text = ANY(%s)
            """,
            (self.tenant_id, [item["job_operation_id"] for item in suggestions]),
        )
        if any(row[0] != self.machine_id or row[1] is None or row[2] is None for row in rows):
            raise AssertionError("planned machine/date fields were not persisted")
        ok("AUTO_SCHEDULER_PASS", applied=applied["applied_count"])

    def run_worklist_and_completion(self) -> None:
        first_op = self.job_operation_ids[0]
        self.db_exec(
            "UPDATE job_operations SET worker_id = %s, shift_id = %s WHERE tenant_id = %s AND job_op_id = %s",
            (self.worker_id, self.shift_id, self.tenant_id, first_op),
        )
        self.commit()
        queue = self.api(
            "GET",
            f"/worklist?worker_id={self.worker_id}&machine_id={self.machine_id}",
            user=self.operator,
        )
        items = queue.get("items", queue if isinstance(queue, list) else [])
        if not items:
            raise AssertionError("operator worklist returned no assigned operations")
        self.api("PATCH", f"/job-operations/{first_op}/status", user=self.operator, json={"status": "IN_PROGRESS"})
        self.api(
            "PATCH",
            f"/job-operations/{first_op}/status",
            user=self.operator,
            json={"status": "COMPLETED", "quantity_completed": 4, "quantity_rejected": 0},
        )
        queue_after = self.api(
            "GET",
            f"/worklist?worker_id={self.worker_id}&machine_id={self.machine_id}",
            user=self.operator,
        )
        after_items = queue_after.get("items", queue_after if isinstance(queue_after, list) else [])
        if any(str(item.get("job_operation_id")) == first_op for item in after_items):
            raise AssertionError("completed operation still appears in worklist")
        ok("WORKLIST_OPERATOR_PASS", completed_operation=first_op)

    def run_notifications(self) -> None:
        self.db_exec(
            """
            UPDATE job_operations
            SET planned_end_date = %s
            WHERE tenant_id = %s AND job_op_id = %s
            """,
            (datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=1), self.tenant_id, self.job_operation_ids[1]),
        )
        self.commit()
        response = requests.post(
            f"{BACKEND_URL}/api/maintenance/v15-nightly",
            headers={"x-roodha-maintenance-secret": self.config["MAINTENANCE_SECRET"]},
            timeout=60,
        )
        if response.status_code != 200:
            raise AssertionError(f"maintenance failed status={response.status_code} body={response.text[:240]}")
        rows = self.db_exec(
            """
            SELECT type FROM notifications
            WHERE tenant_id = %s AND type IN ('JOB_DELAY_RISK', 'MACHINE_OVERLOAD')
            """,
            (self.tenant_id,),
        )
        found = {row[0] for row in rows}
        if not {"JOB_DELAY_RISK", "MACHINE_OVERLOAD"}.issubset(found):
            raise AssertionError(f"missing expected notifications: {found}")
        notif_data = self.api("GET", "/notifications", user=self.owner)
        if int(notif_data.get("unread_count", 0)) < 2:
            raise AssertionError("notification unread count did not increment")
        ok("NIGHTLY_NOTIFICATIONS_PASS", unread=notif_data.get("unread_count"))

    def verify_outbound_webhook(self) -> None:
        rows = self.db_exec(
            "SELECT event_type FROM events WHERE tenant_id = %s AND event_type = 'JOB_COMPLETED'",
            (self.tenant_id,),
        )
        if not rows:
            raise AssertionError("JOB_COMPLETED event was not recorded")
        verify_url = self.config.get("WEBHOOK_VERIFY_URL")
        if verify_url:
            receipt = requests.get(verify_url, timeout=30).text
            if self.job_ids[0] not in receipt or "COMPLETED" not in receipt:
                raise AssertionError("mock webhook verification endpoint did not contain completed job payload")
        ok("OUTBOUND_WEBHOOK_PASS", event="JOB_COMPLETED", receipt="verified" if verify_url else "event-only")

    def verify_exports_and_rbac(self) -> None:
        export = self.api("POST", "/exports/jobs", user=self.owner, json={})
        url = export.get("download_url") or export.get("downloadUrl")
        if not url:
            raise AssertionError("export did not return a download URL")
        if self.config["EXPORTS_S3_BUCKET"]:
            parsed = urlparse(url)
            qs = parse_qs(parsed.query)
            if qs.get("X-Amz-Expires", [""])[0] != "300":
                raise AssertionError("S3 export URL does not expose a 300 second TTL")
            csv_response = requests.get(url, timeout=30)
            if csv_response.status_code != 200 or "Material Grade" not in csv_response.text:
                raise AssertionError("S3 jobs CSV did not include Material Grade column")
        else:
            if not url.startswith("data:text/csv"):
                raise AssertionError("export without S3 bucket should return data URL fallback")
            csv_text = (
                base64.b64decode(url.split(",", 1)[1]).decode("utf-8-sig")
                if ";base64," in url
                else unquote(url.split(",", 1)[1])
            )
            if "Material Grade" not in csv_text:
                raise AssertionError("jobs CSV did not include Material Grade column")

        for method, path, kwargs in [
            ("POST", "/planning/auto-schedule/preview", {"json": {"limit": 1}}),
            ("POST", "/exports/jobs", {"json": {}}),
            ("POST", "/users/invite", {"json": {"email": f"{self.prefix}.blocked@example.com", "role": "SUPERVISOR"}}),
        ]:
            response = requests.request(
                method,
                f"{BACKEND_URL}/api{path}",
                headers=self.headers(self.operator),
                timeout=30,
                **kwargs,
            )
            if response.status_code != 403:
                raise AssertionError(f"operator RBAC expected 403 for {path}, got {response.status_code}")
        ok("EXPORT_RBAC_PASS", export="ok", operator_blocks=3)

    def run(self) -> None:
        self.seed_base_data()
        for user in [self.owner, self.supervisor, self.operator]:
            self.create_cognito_user(user)
            self.login(user)
        self.api("GET", "/ping")
        self.create_jobs_via_integration()
        self.run_scheduler()
        self.run_worklist_and_completion()
        time.sleep(2)
        self.run_notifications()
        self.verify_outbound_webhook()
        self.verify_exports_and_rbac()


def main() -> None:
    require_live_flag()
    config = get_config()
    smoke = LiveSmoke(config)
    try:
        smoke.run()
        ok("ROODHA_V15_LIVE_E2E_PASS", tenant=smoke.tenant_id)
    finally:
        smoke.close()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        raise
    except Exception as exc:  # noqa: BLE001
        print(f"LIVE_E2E_FAIL {exc.__class__.__name__}: {str(exc)[:260]}")
        sys.exit(1)
