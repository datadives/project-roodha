import csv
import io
import sys
from datetime import datetime, timedelta
from types import SimpleNamespace
from urllib.parse import parse_qs, unquote, urlparse
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

from app import models
from app.routes.jobs import _resolve_job_custom_field_values
from app.services.export_service import generate_jobs_csv_and_upload


TENANT_ID = "tenant-custom-field-export-test"
FIELD_ID = UUID("20000000-0000-4000-8000-000000000001")
JOB_ID = UUID("20000000-0000-4000-8000-000000000002")


class FakeScalarList:
    def __init__(self, values):
        self.values = values

    def scalars(self):
        return self

    def all(self):
        return self.values


class FakeRows:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows


class CustomFieldDB:
    def __init__(self):
        self.field = SimpleNamespace(
            field_id=FIELD_ID,
            tenant_id=TENANT_ID,
            entity_type="JOB",
            field_name="Material Grade",
            field_type="DROPDOWN",
            options_json=["EN8", "EN24", "MS"],
            is_required=True,
        )

    async def execute(self, _statement):
        return FakeScalarList([self.field])


class ExportDB:
    def __init__(self):
        self.calls = 0
        self.field = SimpleNamespace(
            field_id=FIELD_ID,
            tenant_id=TENANT_ID,
            entity_type="JOB",
            field_name="Material Grade",
            field_type="DROPDOWN",
            options_json=["EN8", "EN24", "MS"],
            is_required=True,
        )
        self.job = SimpleNamespace(
            job_id=JOB_ID,
            tenant_id=TENANT_ID,
            job_number="CF-EXP-001",
            status=models.JobStatus.NOT_STARTED,
            due_date=datetime(2026, 5, 20),
            created_at=datetime(2026, 5, 15),
        )

    async def execute(self, _statement):
        self.calls += 1
        if self.calls == 1:
            return FakeRows([(self.job, "Bracket", "BR-001", "Lathe-01", 1)])
        if self.calls == 2:
            return FakeScalarList([self.field])
        if self.calls == 3:
            return FakeRows([(FIELD_ID, JOB_ID, "EN24", None)])
        raise AssertionError("Unexpected export query")


class EmptyExportDB:
    def __init__(self):
        self.calls = 0

    async def execute(self, _statement):
        self.calls += 1
        if self.calls == 1:
            return FakeRows([])
        if self.calls == 2:
            return FakeScalarList([])
        raise AssertionError("Unexpected empty export query")


class FakeS3Client:
    def __init__(self):
        self.objects = {}
        self.last_body = ""

    def put_object(self, Bucket, Key, Body, ContentType):
        self.last_body = Body.decode("utf-8-sig")
        self.objects[(Bucket, Key)] = {"body": self.last_body, "content_type": ContentType}

    def generate_presigned_url(self, _operation, Params, ExpiresIn):
        issued_at = datetime(2026, 5, 15, 12, 0, 0)
        return (
            f"https://s3.fake/{Params['Bucket']}/{Params['Key']}"
            f"?X-Amz-Date={issued_at.strftime('%Y%m%dT%H%M%SZ')}"
            f"&X-Amz-Expires={ExpiresIn}"
            f"&response-content-disposition={Params['ResponseContentDisposition']}"
        )


def parse_csv(csv_content: str):
    return list(csv.DictReader(io.StringIO(csv_content)))


def simulated_s3_get_presigned_url(url: str, at_time: datetime):
    query = parse_qs(urlparse(url).query)
    issued_at = datetime.strptime(query["X-Amz-Date"][0], "%Y%m%dT%H%M%SZ")
    expires_in = int(query["X-Amz-Expires"][0])
    if at_time > issued_at + timedelta(seconds=expires_in):
        return SimpleNamespace(status_code=403, text="AccessDenied: Request has expired")
    return SimpleNamespace(status_code=200, text="OK")


@pytest.mark.asyncio
async def test_job_dropdown_custom_field_rejects_invalid_value_and_accepts_valid(capsys):
    db = CustomFieldDB()

    with pytest.raises(HTTPException) as exc:
        await _resolve_job_custom_field_values(db, TENANT_ID, {"Material Grade": "WOOD"})

    print(f"CUSTOM_FIELD_REJECT field='Material Grade' value=WOOD status={exc.value.status_code} detail={exc.value.detail}")
    assert exc.value.status_code == 400
    assert "Invalid value for 'Material Grade'" in exc.value.detail

    resolved = await _resolve_job_custom_field_values(db, TENANT_ID, {"Material Grade": "EN24"})
    print("CUSTOM_FIELD_ACCEPT field='Material Grade' value=EN24 status=accepted")
    assert [(field.field_name, value) for field, value in resolved] == [("Material Grade", "EN24")]


@pytest.mark.asyncio
async def test_jobs_export_includes_custom_field_and_presigned_url_expires(monkeypatch, capsys):
    fake_s3 = FakeS3Client()
    monkeypatch.setenv("EXPORTS_S3_BUCKET", "roodha-test-exports")
    monkeypatch.setenv("EXPORT_PRESIGN_TTL_SECONDS", "300")
    monkeypatch.setitem(sys.modules, "boto3", SimpleNamespace(client=lambda *_args, **_kwargs: fake_s3))

    result = await generate_jobs_csv_and_upload(ExportDB(), TENANT_ID)
    rows = parse_csv(fake_s3.last_body)

    print(f"EXPORT_CSV_HEADERS headers={list(rows[0].keys())}")
    print(f"EXPORT_CSV_ROW job={rows[0]['Job Number']} material_grade={rows[0]['Material Grade']}")

    assert result["download_url"].startswith("https://s3.fake/")
    assert "Material Grade" in rows[0]
    assert rows[0]["Material Grade"] == "EN24"

    expired_response = simulated_s3_get_presigned_url(
        result["download_url"],
        at_time=datetime(2026, 5, 15, 12, 5, 1),
    )
    print(f"S3_PRESIGNED_EXPIRY elapsed=301s status={expired_response.status_code} body={expired_response.text}")

    assert expired_response.status_code == 403
    assert "AccessDenied" in expired_response.text


@pytest.mark.asyncio
async def test_jobs_export_empty_tenant_uploads_header_only_csv(monkeypatch, capsys):
    fake_s3 = FakeS3Client()
    monkeypatch.setenv("EXPORTS_S3_BUCKET", "roodha-test-exports")
    monkeypatch.setenv("EXPORT_PRESIGN_TTL_SECONDS", "300")
    monkeypatch.setitem(sys.modules, "boto3", SimpleNamespace(client=lambda *_args, **_kwargs: fake_s3))

    result = await generate_jobs_csv_and_upload(EmptyExportDB(), "tenant-empty-export-test")
    csv_rows = list(csv.reader(io.StringIO(fake_s3.last_body)))

    print(
        "EXPORT_EMPTY_JOBS "
        f"rows={len(csv_rows)} headers={csv_rows[0]} "
        f"download_url={result['download_url'].split('?')[0]}"
    )

    assert result["download_url"].startswith("https://s3.fake/")
    assert result["filename"].startswith("datadives_jobs_report_")
    assert csv_rows == [["Job Number", "Part Name", "Machine", "Status", "Due Date"]]
