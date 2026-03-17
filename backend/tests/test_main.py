import pytest
from httpx import AsyncClient
from backend.app.main import app

@pytest.mark.asyncio
async def test_health_check():
    """Verify the backend is alive."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

@pytest.mark.asyncio
async def test_upload_endpoint_no_file():
    """Verify upload fails correctly without a file."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.post("/api/upload")
    assert response.status_code == 422  # Unprocessable Entity (missing file)