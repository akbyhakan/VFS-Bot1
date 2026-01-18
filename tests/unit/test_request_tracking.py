"""Tests for request tracking middleware."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from src.middleware.request_tracking import RequestTrackingMiddleware


@pytest.fixture
def app_with_tracking():
    """Create test app with tracking middleware."""
    app = FastAPI()
    app.add_middleware(RequestTrackingMiddleware)
    
    @app.get("/test")
    async def test_endpoint():
        return {"status": "ok"}
    
    return app


def test_request_id_generated(app_with_tracking):
    """Test that request ID is generated when not provided."""
    client = TestClient(app_with_tracking)
    response = client.get("/test")
    
    assert response.status_code == 200
    assert "X-Request-ID" in response.headers
    assert len(response.headers["X-Request-ID"]) == 36  # UUID length


def test_request_id_preserved(app_with_tracking):
    """Test that provided request ID is preserved."""
    client = TestClient(app_with_tracking)
    custom_id = "custom-request-id-123"
    
    response = client.get("/test", headers={"X-Request-ID": custom_id})
    
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == custom_id


def test_request_id_different_for_each_request(app_with_tracking):
    """Test that different requests get different IDs."""
    client = TestClient(app_with_tracking)
    
    response1 = client.get("/test")
    response2 = client.get("/test")
    
    assert response1.status_code == 200
    assert response2.status_code == 200
    assert response1.headers["X-Request-ID"] != response2.headers["X-Request-ID"]


def test_request_tracking_with_error(app_with_tracking):
    """Test that request tracking works even when endpoint raises error."""
    
    @app_with_tracking.get("/error")
    async def error_endpoint():
        raise ValueError("Test error")
    
    client = TestClient(app_with_tracking)
    
    with pytest.raises(ValueError):
        response = client.get("/error")
