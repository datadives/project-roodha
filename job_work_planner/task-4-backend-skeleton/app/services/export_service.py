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
from sqlalchemy import case, cast, Float, func, select
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
        logger.info("Export S3 bucket is not configured; returning inline CSV data URL.")
        return _csv_data_url(csv_content)

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
        ExpiresIn=int(os.getenv("EXPORT_PRESIGN_TTL_SECONDS", "300")),
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
                "job_id": job.job_id,
                "job_number": job.job_number,
                "part_name": part_description or part_number or "",
                "machine": machine_name or "",
                "status": job.status.value if hasattr(job.status, "value") else str(job.status or ""),
                "due_date": job.due_date.date().isoformat() if job.due_date else "",
            }
        elif not rows_by_job[job_key]["machine"] and machine_name:
            rows_by_job[job_key]["machine"] = machine_name

    field_result = await db.execute(
        select(models.CustomField)
        .where(
            models.CustomField.tenant_id == tenant_id,
            models.CustomField.entity_type == "JOB",
        )
        .order_by(models.CustomField.field_name.asc())
    )
    custom_fields = field_result.scalars().all()
    custom_values: dict[tuple[str, str], str] = {}
    if custom_fields and rows_by_job:
        value_result = await db.execute(
            select(
                models.CustomFieldValue.field_id,
                models.CustomFieldValue.entity_id,
                models.CustomFieldValue.value_text,
                models.CustomFieldValue.field_value,
            ).where(
                models.CustomFieldValue.tenant_id == tenant_id,
                models.CustomFieldValue.field_id.in_([field.field_id for field in custom_fields]),
                models.CustomFieldValue.entity_id.in_([row["job_id"] for row in rows_by_job.values()]),
            )
        )
        for field_id, entity_id, value_text, field_value in value_result.all():
            custom_values[(str(entity_id), str(field_id))] = value_text or field_value or ""

    output = io.StringIO()
    writer = csv.writer(output)
    custom_headers = [field.field_name for field in custom_fields]
    writer.writerow(["Job Number", "Part Name", "Machine", "Status", "Due Date", *custom_headers])
    for job_key, row in rows_by_job.items():
        writer.writerow([
            row["job_number"],
            row["part_name"],
            row["machine"],
            row["status"],
            row["due_date"],
            *[custom_values.get((job_key, str(field.field_id)), "") for field in custom_fields],
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
        "download_url": _upload_csv_to_s3(csv_content, tenant_id, f"datadives_machine_load_report_{timestamp}.csv"),
        "filename": f"datadives_machine_load_report_{timestamp}.csv",
    }


async def generate_wip_by_stage_csv(db: AsyncSession, tenant_id: str) -> dict:
    stmt = (
        select(models.OperationsMaster.name, func.count(models.JobOperation.job_op_id))
        .join(models.JobOperation, models.JobOperation.op_id == models.OperationsMaster.operation_id)
        .join(models.Job, models.Job.job_id == models.JobOperation.job_id)
        .where(
            models.OperationsMaster.tenant_id == tenant_id,
            models.JobOperation.tenant_id == tenant_id,
            models.Job.tenant_id == tenant_id,
            models.Job.status != models.JobStatus.COMPLETED,
            models.JobOperation.status.notin_([
                models.OperationStatus.COMPLETED,
                models.OperationStatus.CANCELLED,
            ]),
        )
        .group_by(models.OperationsMaster.name)
        .order_by(models.OperationsMaster.name.asc())
    )
    result = await db.execute(stmt)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Stage", "Active Operation Count"])
    for stage, count in result.all():
        writer.writerow([stage, count])
    csv_content = output.getvalue()
    output.close()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"datadives_wip_by_stage_{timestamp}.csv"
    return {"download_url": _upload_csv_to_s3(csv_content, tenant_id, filename), "filename": filename}


async def generate_costing_summary_csv(db: AsyncSession, tenant_id: str) -> dict:
    operation_hours = case(
        (models.OperationsMaster.standard_cycle_time_mins <= 0, 0.1),
        else_=(cast(models.Job.quantity, Float) * cast(models.OperationsMaster.standard_cycle_time_mins, Float)) / 60.0,
    )
    stmt = (
        select(
            models.Job.job_number,
            models.Job.status,
            models.Job.quantity,
            models.Part.default_material_cost_per_unit,
            func.coalesce(func.sum(operation_hours), 0.0),
            func.coalesce(func.sum(func.coalesce(models.Machine.hourly_rate, 0) * operation_hours), 0.0),
        )
        .join(models.Part, models.Part.part_id == models.Job.part_id, isouter=True)
        .join(models.JobOperation, models.JobOperation.job_id == models.Job.job_id, isouter=True)
        .join(models.OperationsMaster, models.OperationsMaster.operation_id == models.JobOperation.op_id, isouter=True)
        .join(models.Machine, models.Machine.machine_id == models.JobOperation.machine_id, isouter=True)
        .where(models.Job.tenant_id == tenant_id)
        .group_by(models.Job.job_number, models.Job.status, models.Job.quantity, models.Part.default_material_cost_per_unit)
        .order_by(models.Job.job_number.asc())
    )
    result = await db.execute(stmt)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Job Number", "Status", "Quantity", "Material Cost", "Estimated Machine Hours", "Estimated Machine Cost", "Estimated Total"])
    for job_number, status, quantity, material_unit, hours, machine_cost in result.all():
        material_cost = float(material_unit or 0) * float(quantity or 0)
        total = material_cost + float(machine_cost or 0)
        writer.writerow([job_number, getattr(status, "value", status), quantity, round(material_cost, 2), round(float(hours or 0), 2), round(float(machine_cost or 0), 2), round(total, 2)])
    csv_content = output.getvalue()
    output.close()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"datadives_costing_summary_{timestamp}.csv"
    return {"download_url": _upload_csv_to_s3(csv_content, tenant_id, filename), "filename": filename}


async def generate_delivery_performance_csv(db: AsyncSession, tenant_id: str) -> dict:
    completion_date = func.max(models.JobOperation.actual_end_time)
    stmt = (
        select(
            models.Job.job_number,
            models.Job.due_date,
            models.Job.status,
            completion_date.label("completion_date"),
        )
        .join(models.JobOperation, models.JobOperation.job_id == models.Job.job_id, isouter=True)
        .where(models.Job.tenant_id == tenant_id)
        .group_by(models.Job.job_number, models.Job.due_date, models.Job.status)
        .order_by(models.Job.due_date.asc().nulls_last())
    )
    result = await db.execute(stmt)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Job Number", "Due Date", "Completion Date", "Status", "On Time"])
    for job_number, due_date, status, completed_at in result.all():
        on_time = "PENDING"
        if completed_at and due_date:
            on_time = "YES" if completed_at <= due_date else "NO"
        writer.writerow([
            job_number,
            due_date.date().isoformat() if due_date else "",
            completed_at.date().isoformat() if completed_at else "",
            getattr(status, "value", status),
            on_time,
        ])
    csv_content = output.getvalue()
    output.close()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"datadives_delivery_performance_{timestamp}.csv"
    return {"download_url": _upload_csv_to_s3(csv_content, tenant_id, filename), "filename": filename}
