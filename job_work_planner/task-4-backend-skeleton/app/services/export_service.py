"""
/**
 * PROJECT ROODHA - v1.5.7 "Gold Baseline"
 * File: export_service.py
 * 
 * 1) Purpose: Business logic and service layer for export_service.
 * 2) Roadmap Connection: This file is a critical component of the Stage 2 (v1.5) Industrial 
 *    Hardening phase. It enforces multi-tenancy, security (RBAC), and transactional 
 *    resilience as defined in the formal Roadmap.
 */
"""
import io
import csv
import logging
import os
from datetime import datetime
from urllib.parse import quote

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app import models

logger = logging.getLogger("jobwork-backend")

def _csv_data_url(csv_content: str) -> str:
    return f"data:text/csv;charset=utf-8,{quote(csv_content)}"


def _get_exports_bucket_name() -> str | None:
    return (
        os.getenv("EXPORTS_S3_BUCKET")
        or os.getenv("S3_EXPORT_BUCKET")
        or os.getenv("S3_BUCKET_NAME")
        or os.getenv("AWS_EXPORTS_BUCKET")
    )


def _upload_csv_to_s3(csv_content: str, tenant_id: str, filename: str) -> str:
    bucket_name = _get_exports_bucket_name()
    if not bucket_name:
        if os.getenv("ALLOW_LOCAL_EXPORT_FALLBACK", "false").lower() == "true":
            return _csv_data_url(csv_content)
        raise RuntimeError(
            "Export S3 bucket is not configured. Set EXPORTS_S3_BUCKET or S3_EXPORT_BUCKET."
        )

    try:
        import boto3
    except ImportError as exc:
        raise RuntimeError("boto3 is required for S3-backed exports") from exc

    region_name = os.getenv("AWS_REGION", "ap-south-1")
    s3_client = boto3.client("s3", region_name=region_name)
    object_key = f"exports/{tenant_id}/jobs/{filename}"

    s3_client.put_object(
        Bucket=bucket_name,
        Key=object_key,
        Body=csv_content.encode("utf-8-sig"),
        ContentType="text/csv; charset=utf-8",
    )
    return s3_client.generate_presigned_url(
        "get_object",
        Params={
            "Bucket": bucket_name,
            "Key": object_key,
            "ResponseContentDisposition": f'attachment; filename="{filename}"',
            "ResponseContentType": "text/csv",
        },
        ExpiresIn=int(os.getenv("EXPORT_PRESIGN_TTL_SECONDS", "900")),
    )


async def generate_jobs_csv_and_upload(db: AsyncSession, tenant_id: str) -> dict:
    """Generate the Owner's Report CSV, upload it to S3, and return a pre-signed URL."""
    stmt = (
        select(
            models.Job,
            models.Part.description,
            models.Part.part_number,
            models.Machine.name,
            models.JobOperation.sequence_number,
        )
        .join(
            models.Part,
            (models.Job.part_id == models.Part.part_id)
            & (models.Part.tenant_id == tenant_id),
            isouter=True,
        )
        .join(
            models.JobOperation,
            (models.Job.job_id == models.JobOperation.job_id)
            & (models.JobOperation.tenant_id == tenant_id),
            isouter=True,
        )
        .join(
            models.Machine,
            (models.JobOperation.machine_id == models.Machine.machine_id)
            & (models.Machine.tenant_id == tenant_id),
            isouter=True,
        )
        .where(models.Job.tenant_id == tenant_id)
        .order_by(models.Job.created_at.desc(), models.JobOperation.sequence_number.asc().nulls_last())
    )

    result = await db.execute(stmt)
    rows_by_job = {}
    for job, part_description, part_number, machine_name, _sequence_number in result.all():
        job_key = str(job.job_id)
        if job_key not in rows_by_job:
            rows_by_job[job_key] = {
                "job_number": job.job_number,
                "part_name": part_description or part_number or "",
                "machine": machine_name or "",
                "status": job.status.value if hasattr(job.status, "value") else str(job.status or ""),
                "due_date": job.due_date.date().isoformat() if job.due_date else "",
            }
        elif not rows_by_job[job_key]["machine"] and machine_name:
            rows_by_job[job_key]["machine"] = machine_name

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Job Number", "Part Name", "Machine", "Status", "Due Date"])
    for row in rows_by_job.values():
        writer.writerow([
            row["job_number"],
            row["part_name"],
            row["machine"],
            row["status"],
            row["due_date"],
        ])

    csv_content = output.getvalue()
    output.close()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"datadives_jobs_report_{timestamp}.csv"
    return {
        "download_url": _upload_csv_to_s3(csv_content, tenant_id, filename),
        "filename": filename,
    }


async def generate_machine_load_csv(db: AsyncSession, tenant_id: str) -> dict:
    """Aggregate planned hours per machine from active job operations."""
    stmt = (
        select(
            models.Machine.name,
            models.JobOperation.machine_id,
            models.Job.quantity,
            models.OperationsMaster.standard_cycle_time_mins,
            models.JobOperation.status,
        )
        .join(
            models.Job,
            (models.JobOperation.job_id == models.Job.job_id)
            & (models.Job.tenant_id == tenant_id),
        )
        .join(
            models.Machine,
            (models.JobOperation.machine_id == models.Machine.machine_id)
            & (models.Machine.tenant_id == tenant_id),
        )
        .join(
            models.OperationsMaster,
            (models.JobOperation.op_id == models.OperationsMaster.operation_id)
            & (models.OperationsMaster.tenant_id == tenant_id),
            isouter=True,
        )
        .where(
            models.JobOperation.tenant_id == tenant_id,
            models.Job.status != models.JobStatus.COMPLETED,
            models.JobOperation.status.notin_([
                models.OperationStatus.COMPLETED,
                models.OperationStatus.CANCELLED,
            ]),
            models.JobOperation.machine_id.is_not(None),
        )
    )

    result = await db.execute(stmt)
    load_by_machine = {}
    for machine_name, machine_id, quantity, cycle_minutes, _status in result.all():
        key = str(machine_id)
        current = load_by_machine.setdefault(
            key,
            {
                "machine_name": machine_name or key,
                "machine_id": key,
                "planned_hours": 0.0,
                "operation_count": 0,
            },
        )
        current["operation_count"] += 1
        current["planned_hours"] += ((cycle_minutes or 0) * max(quantity or 1, 1)) / 60

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Machine", "Machine ID", "Planned Hours", "Operation Count", "Overloaded"])
    for row in sorted(load_by_machine.values(), key=lambda item: item["machine_name"]):
        planned_hours = round(row["planned_hours"], 2)
        writer.writerow([
            row["machine_name"],
            row["machine_id"],
            planned_hours,
            row["operation_count"],
            "YES" if planned_hours > 10 else "NO",
        ])

    csv_content = output.getvalue()
    output.close()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return {
        "download_url": _csv_data_url(csv_content),
        "filename": f"datadives_machine_load_report_{timestamp}.csv",
    }
