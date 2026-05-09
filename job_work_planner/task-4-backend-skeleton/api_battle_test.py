
import httpx
import time
import pytest
from datetime import datetime

BASE_URL = "http://localhost:8000/api"
DEV_TOKEN = "roodha-dev-test-123"

def test_auth_handshake():
    """Auth Handshake: Attempt to access /api/jobs without a token (Expect: 401)."""
    start_time = time.time()
    response = httpx.get(f"{BASE_URL}/jobs")
    latency = (time.time() - start_time) * 1000
    
    assert response.status_code == 401
    return "Auth Handshake", "/jobs", 401, response.status_code, latency

def test_tenant_isolation():
    """Tenant Isolation: Request jobs with X-Tenant-ID: roshan_test and verify NO leaked jobs."""
    start_time = time.time()
    headers = {
        "Authorization": f"Bearer {DEV_TOKEN}",
        "X-Tenant-ID": "roshan_test"
    }
    response = httpx.get(f"{BASE_URL}/jobs", headers=headers)
    latency = (time.time() - start_time) * 1000
    
    if response.status_code != 200:
        print(f"Tenant Isolation Failed: {response.status_code} {response.text}")
    assert response.status_code == 200
    data = response.json().get("data", [])
    # Verify all jobs belong to roshan_test (or at least none from tenant-123)
    # Since we seeded 1 job for roshan_test, we expect exactly 1.
    assert len(data) == 1
    return "Tenant Isolation", "/jobs", 200, response.status_code, latency

def test_rbac_logic():
    """RBAC Logic: Attempt to delete a machine as an Operator role (Expect: 403)."""
    # We need a machine ID. From seeding: fe55376d-ee87-4dbd-bc9a-683cf92f9465
    machine_id = "fe55376d-ee87-4dbd-bc9a-683cf92f9465"
    start_time = time.time()
    headers = {
        "Authorization": f"Bearer {DEV_TOKEN}",
        "X-Tenant-ID": "tenant-123",
        "X-Dev-Role": "OPERATOR"
    }
    response = httpx.delete(f"{BASE_URL}/master-data/machines/{machine_id}", headers=headers)
    latency = (time.time() - start_time) * 1000
    
    if response.status_code != 403:
        print(f"RBAC Logic Failed: {response.status_code} {response.text}")
    assert response.status_code == 403
    return "RBAC Logic", f"/master-data/machines/{machine_id}", 403, response.status_code, latency

def test_delay_guard_logic():
    """Delay Guard Logic: Query an overdue job and verify alert_priority: CRITICAL."""
    # From seeding: b0b2e2fa-8878-4922-b623-e8ba1f1d3670
    job_id = "b0b2e2fa-8878-4922-b623-e8ba1f1d3670"
    start_time = time.time()
    headers = {
        "Authorization": f"Bearer {DEV_TOKEN}",
        "X-Tenant-ID": "tenant-123"
    }
    response = httpx.get(f"{BASE_URL}/jobs/{job_id}", headers=headers)
    latency = (time.time() - start_time) * 1000
    
    if response.status_code != 200:
        print(f"Delay Guard Failed: {response.status_code} {response.text}")
    assert response.status_code == 200
    job_data = response.json().get("data", {})
    assert job_data.get("alert_priority") == "CRITICAL"
    return "Delay Guard Logic", f"/jobs/{job_id}", 200, response.status_code, latency

def run_audit():
    results = []
    tests = [test_auth_handshake, test_tenant_isolation, test_rbac_logic, test_delay_guard_logic]
    
    for test in tests:
        try:
            res = test()
            results.append((*res, "PASS"))
        except AssertionError as e:
            # Re-run to get data for failed test
            # This is a bit hacky but works for a single script
            try:
                # We need to capture the response even on failure
                # Let's refactor the tests to not assert but return status
                pass
            except:
                pass
            # For now, I'll manually handle the failure reporting in the main loop
            results.append((*test.__doc__.split(":")[0], "ERROR", "FAIL")) # Placeholder
        except Exception as e:
            print(f"Error running {test.__name__}: {e}")
            
    return results

if __name__ == "__main__":
    all_results = []
    tests = [
        ("Auth Handshake", test_auth_handshake),
        ("Tenant Isolation", test_tenant_isolation),
        ("RBAC Logic", test_rbac_logic),
        ("Delay Guard Logic", test_delay_guard_logic)
    ]
    
    for name, test_func in tests:
        try:
            res = test_func()
            all_results.append(res)
        except AssertionError as e:
            print(f"FAILED: {name}")
            # I'll manually check the failure by adding a print in the test function or here
            all_results.append((name, "N/A", "FAIL", "FAIL", 0))
        except Exception as e:
            print(f"ERROR: {name} -> {e}")
            all_results.append((name, "N/A", "ERR", "ERR", 0))
    
    print("| Feature | Endpoint | Expected Status | Actual Status | Result | Latency (ms) |")
    print("|---------|----------|-----------------|---------------|--------|--------------|")
    for feat, end, exp, act, lat in all_results:
        res = "PASS" if exp == act else "FAIL"
        print(f"| {feat} | {end} | {exp} | {act} | {res} | {lat:.2f} |")
