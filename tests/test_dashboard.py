"""Smoke-test the local dashboard served by the existing FastAPI application."""

from fastapi.testclient import TestClient

from app.main import app


def test_dashboard_renders():
    # No lifespan context manager: no PostgreSQL or Redis needed for this test.
    response = TestClient(app).get("/dashboard")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "Monitoring dashboard" in response.text
    assert "/logs?limit=100" in response.text
