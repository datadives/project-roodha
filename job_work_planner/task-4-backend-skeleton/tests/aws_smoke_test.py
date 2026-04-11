"""
Live AWS smoke test for Project Roodha.

This script performs a real happy-path validation against the deployed API and
AWS Cognito using only HTTP requests. It does not use mocks or local test
clients.

Required environment variables:
  ROODHA_API_BASE_URL
  ROODHA_COGNITO_REGION
  ROODHA_COGNITO_CLIENT_ID
  ROODHA_COGNITO_USERNAME
  ROODHA_COGNITO_PASSWORD

Optional environment variables:
  ROODHA_COGNITO_CLIENT_SECRET
  ROODHA_CORS_ORIGIN                (default: http://localhost:5173)
  ROODHA_CUSTOMER_ID                (prefer an existing tenant-scoped customer)
  ROODHA_PART_ID                    (prefer a part that belongs to the customer)
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import date, timedelta
import hashlib
import hmac
import os
import sys
import time
from typing import Any

import requests


class SmokeTestError(RuntimeError):
    pass


@dataclass(frozen=True)
class SmokeConfig:
    api_base_url: str
    cognito_region: str
    cognito_client_id: str
    cognito_username: str
    cognito_password: str
    cognito_client_secret: str | None
    cors_origin: str
    customer_id: str | None
    part_id: str | None


def require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise SmokeTestError(f"Missing required environment variable: {name}")
    return value


def load_config() -> SmokeConfig:
    return SmokeConfig(
        api_base_url=require_env("ROODHA_API_BASE_URL").rstrip("/"),
        cognito_region=require_env("ROODHA_COGNITO_REGION"),
        cognito_client_id=require_env("ROODHA_COGNITO_CLIENT_ID"),
        cognito_username=require_env("ROODHA_COGNITO_USERNAME"),
        cognito_password=require_env("ROODHA_COGNITO_PASSWORD"),
        cognito_client_secret=os.getenv("ROODHA_COGNITO_CLIENT_SECRET") or None,
        cors_origin=(os.getenv("ROODHA_CORS_ORIGIN") or "http://localhost:5173").strip(),
        customer_id=(os.getenv("ROODHA_CUSTOMER_ID") or "").strip() or None,
        part_id=(os.getenv("ROODHA_PART_ID") or "").strip() or None,
    )


def log(message: str) -> None:
    print(f"[smoke] {message}")


def build_url(config: SmokeConfig, path: str) -> str:
    return f"{config.api_base_url}/{path.lstrip('/')}"


def build_secret_hash(username: str, client_id: str, client_secret: str) -> str:
    digest = hmac.new(
        client_secret.encode("utf-8"),
        f"{username}{client_id}".encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return base64.b64encode(digest).decode("utf-8")


def raise_for_failure(response: requests.Response, context: str) -> None:
    try:
        payload = response.json()
    except ValueError:
        payload = response.text
    raise SmokeTestError(f"{context} failed with {response.status_code}: {payload}")


def expect_envelope(response: requests.Response, context: str, expected_status: int = 200) -> Any:
    if response.status_code != expected_status:
        raise_for_failure(response, context)

    try:
        payload = response.json()
    except ValueError as exc:
        raise SmokeTestError(f"{context} returned non-JSON response: {response.text}") from exc

    if isinstance(payload, dict) and "success" in payload:
        if not payload.get("success"):
            raise SmokeTestError(f"{context} returned unsuccessful envelope: {payload}")
        return payload.get("data")

    return payload


def cognito_login(config: SmokeConfig) -> dict[str, str]:
    log("Logging in against AWS Cognito")
    auth_parameters = {
        "USERNAME": config.cognito_username,
        "PASSWORD": config.cognito_password,
    }
    if config.cognito_client_secret:
        auth_parameters["SECRET_HASH"] = build_secret_hash(
            config.cognito_username,
            config.cognito_client_id,
            config.cognito_client_secret,
        )

    response = requests.post(
        f"https://cognito-idp.{config.cognito_region}.amazonaws.com/",
        headers={
            "Content-Type": "application/x-amz-json-1.1",
            "X-Amz-Target": "AWSCognitoIdentityProviderService.InitiateAuth",
        },
        json={
            "AuthFlow": "USER_PASSWORD_AUTH",
            "ClientId": config.cognito_client_id,
            "AuthParameters": auth_parameters,
        },
        timeout=30,
    )

    if response.status_code != 200:
        raise_for_failure(response, "Cognito login")

    payload = response.json()
    if payload.get("ChallengeName"):
        raise SmokeTestError(
            "Cognito returned a challenge instead of tokens. "
            "Ensure the app client supports USER_PASSWORD_AUTH for this smoke user."
        )

    auth_result = payload.get("AuthenticationResult") or {}
    id_token = auth_result.get("IdToken")
    access_token = auth_result.get("AccessToken")
    if not id_token and not access_token:
        raise SmokeTestError(f"Cognito login did not return usable tokens: {payload}")

    return {
        "id_token": id_token or "",
        "access_token": access_token or "",
        "bearer_token": id_token or access_token,
    }


def cors_preflight(session: requests.Session, config: SmokeConfig, path: str) -> None:
    log(f"Checking CORS preflight for {path}")
    response = session.options(
        build_url(config, path),
        headers={
            "Origin": config.cors_origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
        timeout=20,
    )

    if response.status_code >= 400:
        raise_for_failure(response, "CORS preflight")

    allow_origin = response.headers.get("access-control-allow-origin")
    if allow_origin not in {"*", config.cors_origin}:
        raise SmokeTestError(
            f"CORS preflight did not return an expected access-control-allow-origin header: {allow_origin!r}"
        )


def api_request(
    session: requests.Session,
    config: SmokeConfig,
    method: str,
    path: str,
    bearer_token: str,
    *,
    expected_status: int = 200,
    **kwargs,
) -> Any:
    headers = kwargs.pop("headers", {})
    headers["Authorization"] = f"Bearer {bearer_token}"
    response = session.request(
        method=method,
        url=build_url(config, path),
        headers=headers,
        timeout=30,
        **kwargs,
    )

    if response.status_code == 403:
        raise SmokeTestError(f"{method} {path} returned 403 Forbidden. Check API Gateway/CORS/auth wiring.")

    return expect_envelope(response, f"{method} {path}", expected_status=expected_status)


def resolve_list_path(
    session: requests.Session,
    config: SmokeConfig,
    bearer_token: str,
    candidates: list[str],
) -> tuple[str, Any]:
    last_error: SmokeTestError | None = None
    for path in candidates:
        try:
            return path, api_request(session, config, "GET", path, bearer_token)
        except SmokeTestError as exc:
            if "404" in str(exc):
                last_error = exc
                continue
            raise
    raise last_error or SmokeTestError(f"Unable to resolve a working endpoint from {candidates}")


def choose_customer(customers: list[dict[str, Any]], requested_customer_id: str | None) -> dict[str, Any]:
    if not customers:
        raise SmokeTestError("Customer list is empty; the smoke user has no accessible customers.")

    if requested_customer_id:
        for customer in customers:
            if customer.get("customer_id") == requested_customer_id:
                return customer
        raise SmokeTestError(f"Customer {requested_customer_id} was not found in the tenant-scoped customer list.")

    return customers[0]


def choose_part(parts: list[dict[str, Any]], customer_id: str, requested_part_id: str | None) -> dict[str, Any]:
    if requested_part_id:
        for part in parts:
            if part.get("part_id") == requested_part_id:
                return part
        raise SmokeTestError(f"Part {requested_part_id} was not found in the tenant-scoped part list.")

    matching_parts = [part for part in parts if part.get("customer_id") == customer_id]
    if not matching_parts:
        raise SmokeTestError(f"No parts were found for customer {customer_id}.")
    return matching_parts[0]


def mark_operation_complete(
    session: requests.Session,
    config: SmokeConfig,
    bearer_token: str,
    job_operation_id: str,
) -> None:
    api_request(
        session,
        config,
        "PATCH",
        f"/job-operations/{job_operation_id}/status",
        bearer_token,
        json={"status": "IN_PROGRESS"},
    )
    api_request(
        session,
        config,
        "PATCH",
        f"/job-operations/{job_operation_id}/status",
        bearer_token,
        json={"status": "COMPLETED"},
    )


def main() -> int:
    config = load_config()
    session = requests.Session()

    cors_preflight(session, config, "/jobs/")
    tokens = cognito_login(config)
    bearer_token = tokens["bearer_token"]
    if not bearer_token:
        raise SmokeTestError("No usable Cognito token was returned.")

    customers_path, customers = resolve_list_path(
        session,
        config,
        bearer_token,
        ["/customers/", "/master-data/customers"],
    )
    log(f"Customer endpoint reachable at {customers_path}")
    customer = choose_customer(customers, config.customer_id)
    log(f"Using customer {customer['customer_id']}")

    parts_path, parts = resolve_list_path(
        session,
        config,
        bearer_token,
        ["/parts/", "/master-data/parts"],
    )
    log(f"Part endpoint reachable at {parts_path}")
    part = choose_part(parts, customer["customer_id"], config.part_id)
    log(f"Using part {part['part_id']}")

    due_date = (date.today() + timedelta(days=3)).isoformat()
    created_job = api_request(
        session,
        config,
        "POST",
        "/jobs/",
        bearer_token,
        expected_status=201,
        json={
            "customer_id": customer["customer_id"],
            "part_id": part["part_id"],
            "quantity": 1,
            "due_date": due_date,
            "priority": "HIGH",
        },
    )

    job = created_job.get("job") or {}
    operations = created_job.get("operations") or []
    job_id = job.get("job_id")
    job_number = job.get("job_number")
    if not job_id or not job_number:
        raise SmokeTestError(f"Job creation did not return job_id/job_number: {created_job}")
    if not operations:
        raise SmokeTestError(f"Job creation did not return generated operations: {created_job}")

    log(f"Created job {job_number} ({job_id}) with {len(operations)} operation(s)")

    time.sleep(2)
    job_after_create = api_request(session, config, "GET", f"/jobs/{job_id}", bearer_token)
    if job_after_create.get("job", {}).get("job_number") != job_number:
        raise SmokeTestError("Job persistence check failed after delay; fetched job_number did not match.")
    log("RDS persistence check passed after delayed fetch")

    first_operation_id = operations[0]["job_operation_id"]
    log(f"Driving first operation {first_operation_id} through IN_PROGRESS -> COMPLETED")
    mark_operation_complete(session, config, bearer_token, first_operation_id)

    refreshed_job = api_request(session, config, "GET", f"/jobs/{job_id}", bearer_token)
    refreshed_operations = refreshed_job.get("operations") or []

    if len(refreshed_operations) == 1:
        if refreshed_job.get("job", {}).get("status") != "COMPLETED":
            raise SmokeTestError(
                "Single-operation job did not auto-sync parent job status to COMPLETED after the last operation finished."
            )
        log("Automatic parent-job completion sync verified on the last operation")
    else:
        log("Job has multiple operations; completing remaining operations to verify final automatic sync")
        remaining_operations = [
            operation
            for operation in refreshed_operations
            if operation.get("job_operation_id") != first_operation_id and operation.get("status") != "COMPLETED"
        ]

        for operation in sorted(remaining_operations, key=lambda item: item.get("sequence_number", 0)):
            log(f"Completing operation {operation['job_operation_id']}")
            mark_operation_complete(session, config, bearer_token, operation["job_operation_id"])

        time.sleep(2)
        refreshed_job = api_request(session, config, "GET", f"/jobs/{job_id}", bearer_token)
        if refreshed_job.get("job", {}).get("status") != "COMPLETED":
            raise SmokeTestError("Parent job status did not sync to COMPLETED after all operations finished.")
        log("Automatic parent-job completion sync verified after the final operation")

    log("AWS smoke test completed successfully")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SmokeTestError as exc:
        log(f"FAILED: {exc}")
        raise SystemExit(1)
