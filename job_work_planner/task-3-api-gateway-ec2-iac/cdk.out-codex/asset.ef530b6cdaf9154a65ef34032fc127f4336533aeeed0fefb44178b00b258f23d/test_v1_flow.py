"""
test_v1_flow.py
---------------
Automated V1.0 integration test suite for Project Roodha.

Tests:
  1. API health check
  2. Quoted price PATCH validation
  3. PDF invoice download validation
  4. CORS validation for both staging origins
"""

from __future__ import annotations

import os
import sys

try:
    import requests
except ImportError:
    print("[FAIL] 'requests' is not installed. Run: pip install requests")
    sys.exit(1)

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000").rstrip("/")
STAGING_ORIGINS = [
    "http://roodha-staging.s3-website-ap-south-1.amazonaws.com",
    "https://roodha-staging.s3-website-ap-south-1.amazonaws.com",
]

AUTH_TOKEN = os.getenv("TEST_JWT_TOKEN", "")
AUTH_HEADERS = {"Authorization": f"Bearer {AUTH_TOKEN}"} if AUTH_TOKEN else {}
TEST_JOB_ID = os.getenv("TEST_JOB_ID", "")
TEST_QUOTED_PRICE = float(os.getenv("TEST_QUOTED_PRICE", "123456.78"))

PASS = "\033[92m[PASS]\033[0m"
FAIL = "\033[91m[FAIL]\033[0m"
SKIP = "\033[93m[SKIP]\033[0m"
INFO = "\033[94m[INFO]\033[0m"

results: list[tuple[str, str]] = []


def record(label: str, passed: bool, detail: str = "") -> None:
    status = PASS if passed else FAIL
    message = f"{status} {label}"
    if detail:
        message += f"\n       {detail}"
    print(message)
    results.append((label, "PASS" if passed else "FAIL"))


def skip(label: str, detail: str) -> None:
    print(f"{SKIP} {label}\n       {detail}")
    results.append((label, "SKIP"))


print(f"\n{INFO} Project Roodha V1.0 Integration Test Suite")
print(f"{INFO} Target: {BASE_URL}\n")

print("=== Test 1: API Health Check ===")
try:
    response = requests.get(f"{BASE_URL}/health", timeout=8)
    record("API is reachable", response.status_code == 200, f"HTTP {response.status_code}")
except requests.exceptions.ConnectionError:
    record("API is reachable", False, f"Connection refused. Is the server running at {BASE_URL}?")
except requests.exceptions.Timeout:
    record("API is reachable", False, "Request timed out after 8 seconds.")

print("\n=== Test 2: Quoted Price PATCH ===")
if not TEST_JOB_ID:
    skip("Quoted price PATCH", "Set TEST_JOB_ID to a real job ID to validate quoted pricing.")
elif not AUTH_TOKEN:
    skip("Quoted price PATCH", "Set TEST_JWT_TOKEN to a valid bearer token to validate quoted pricing.")
else:
    try:
        patch_response = requests.patch(
            f"{BASE_URL}/jobs/{TEST_JOB_ID}/quoted-price",
            headers=AUTH_HEADERS,
            json={"quoted_price": TEST_QUOTED_PRICE},
            timeout=12,
        )
        record(
            "Quoted price PATCH returns HTTP 200",
            patch_response.status_code == 200,
            f"HTTP {patch_response.status_code}",
        )
        if patch_response.status_code == 200:
            payload = patch_response.json()
            data = payload.get("data", {})
            record(
                "Quoted price PATCH returns the updated amount",
                abs(float(data.get("quoted_price", -1)) - TEST_QUOTED_PRICE) < 0.001,
                f"Returned quoted_price={data.get('quoted_price')}",
            )

            job_response = requests.get(
                f"{BASE_URL}/jobs/{TEST_JOB_ID}",
                headers=AUTH_HEADERS,
                timeout=12,
            )
            record(
                "GET job returns HTTP 200 after quoted price update",
                job_response.status_code == 200,
                f"HTTP {job_response.status_code}",
            )
            if job_response.status_code == 200:
                job_payload = job_response.json().get("data", {}).get("job", {})
                record(
                    "GET job reflects quoted_price",
                    abs(float(job_payload.get("quoted_price", -1)) - TEST_QUOTED_PRICE) < 0.001,
                    f"job.quoted_price={job_payload.get('quoted_price')}",
                )
    except requests.exceptions.RequestException as exc:
        record("Quoted price PATCH", False, str(exc))

print("\n=== Test 3: PDF Invoice Download ===")
if not TEST_JOB_ID:
    skip("PDF invoice download", "Set TEST_JOB_ID to a real job ID to run this test.")
elif not AUTH_TOKEN:
    skip("PDF invoice download", "Set TEST_JWT_TOKEN to a valid bearer token to run this test.")
else:
    try:
        invoice_response = requests.get(
            f"{BASE_URL}/jobs/{TEST_JOB_ID}/download-invoice",
            headers=AUTH_HEADERS,
            timeout=15,
            stream=True,
        )

        record(
            "Invoice endpoint returns HTTP 200",
            invoice_response.status_code == 200,
            f"HTTP {invoice_response.status_code}",
        )
        if invoice_response.status_code == 200:
            content_type = invoice_response.headers.get("Content-Type", "")
            record(
                "Invoice response is PDF",
                "application/pdf" in content_type,
                f"Content-Type={content_type}",
            )

            first_bytes = b""
            for chunk in invoice_response.iter_content(chunk_size=16):
                first_bytes = chunk
                break

            record(
                "Invoice payload begins with PDF header",
                first_bytes.startswith(b"%PDF-"),
                f"First bytes={first_bytes[:16]}",
            )

            disposition = invoice_response.headers.get("Content-Disposition", "")
            record(
                "Invoice response is downloadable",
                "attachment" in disposition.lower(),
                f"Content-Disposition={disposition}",
            )
    except requests.exceptions.RequestException as exc:
        record("PDF invoice download", False, str(exc))

print("\n=== Test 4: CORS Header Validation ===")
for origin in STAGING_ORIGINS:
    try:
        cors_response = requests.options(
            f"{BASE_URL}/jobs",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "Authorization",
            },
            timeout=8,
        )
        allowed_origin = cors_response.headers.get("Access-Control-Allow-Origin", "")
        allowed_creds = cors_response.headers.get("Access-Control-Allow-Credentials", "").lower()
        allowed_methods = cors_response.headers.get("Access-Control-Allow-Methods", "")

        record(
            f"CORS allows staging origin {origin}",
            allowed_origin in (origin, "*"),
            f"Access-Control-Allow-Origin={allowed_origin!r}",
        )
        record(
            f"CORS allows credentials for {origin}",
            allowed_creds == "true",
            f"Access-Control-Allow-Credentials={allowed_creds!r}",
        )
        record(
            f"CORS exposes GET for {origin}",
            any(token in allowed_methods.upper() for token in ["GET", "*"]),
            f"Access-Control-Allow-Methods={allowed_methods!r}",
        )
    except requests.exceptions.RequestException as exc:
        record(f"CORS preflight request for {origin}", False, str(exc))

print("\n=== Summary ===")
passed = sum(1 for _, result in results if result == "PASS")
failed = sum(1 for _, result in results if result == "FAIL")
skipped = sum(1 for _, result in results if result == "SKIP")
total = len(results)
print(f"  Total: {total}  |  Passed: {passed}  |  Failed: {failed}  |  Skipped: {skipped}\n")

if failed > 0:
    sys.exit(1)
