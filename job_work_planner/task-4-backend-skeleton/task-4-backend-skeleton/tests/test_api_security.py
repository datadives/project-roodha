from fastapi.testclient import TestClient
from app.main import app  # Ensure this points to your FastAPI app instance
import pytest

client = TestClient(app)

def test_missing_auth_header_returns_401():
    """Test that requests with no token are rejected."""
    response = client.get("/api/users/me")
    assert response.status_code == 401

def test_malformed_auth_header_returns_401():
    """Test the bug we fixed where 'Bearer null' or 'Bearer undefined' crashes the server."""
    headers_to_test = [
        {"Authorization": "Bearer null"},
        {"Authorization": "Bearer undefined"},
        {"Authorization": "Bearer "},
        {"Authorization": "just-a-random-string"}
    ]
    
    for headers in headers_to_test:
        response = client.get("/api/users/me", headers=headers)
        assert response.status_code == 401
        assert "Invalid" in response.json()["detail"] or "Missing" in response.json()["detail"] or "undefined" in response.json()["detail"]

def test_cors_preflight_options_bypasses_auth():
    """Test that the browser's OPTIONS check doesn't get blocked by Auth."""
    response = client.options(
        "/api/users/me",
        headers={
            "Origin": "https://d1k4eogtw67m2o.cloudfront.net",
            "Access-Control-Request-Method": "GET"
        }
    )
    assert response.status_code == 200