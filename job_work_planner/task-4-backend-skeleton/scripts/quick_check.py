
import httpx

def test_health():
    response = httpx.get("http://localhost:8000/api/health")
    print(f"Health: {response.status_code} {response.json()}")

def test_jobs_no_auth():
    response = httpx.get("http://localhost:8000/api/jobs")
    print(f"Jobs No Auth: {response.status_code} {response.json()}")

if __name__ == "__main__":
    test_health()
    test_jobs_no_auth()
