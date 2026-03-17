"""
API endpoint tests.

Run with: pytest backend/tests/test_api.py -v
"""
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
import os


client = TestClient(app)


class TestHealthEndpoint:
    """Tests for the /api/health endpoint."""

    def test_health_returns_200(self):
        response = client.get("/api/health")
        assert response.status_code == 200

    def test_health_returns_status(self):
        response = client.get("/api/health")
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data


class TestUploadEndpoint:
    """Tests for the /api/upload endpoint."""

    def test_upload_rejects_non_pdf(self):
        """Only PDF files should be accepted."""
        response = client.post(
            "/api/upload",
            files={"file": ("test.txt", b"not a pdf", "text/plain")},
        )
        assert response.status_code == 400
        assert "PDF" in response.json()["detail"]

    def test_upload_requires_file(self):
        """Endpoint should fail without a file."""
        response = client.post("/api/upload")
        assert response.status_code == 422  # Validation error

    def test_upload_accepts_pdf(self):
        """A valid PDF should be accepted (uses sample contract if available)."""
        sample_path = "docs/task_docs/Sample Contract.pdf"
        if not os.path.exists(sample_path):
            pytest.skip("Sample contract PDF not found")

        with open(sample_path, "rb") as f:
            response = client.post(
                "/api/upload",
                files={"file": ("Sample Contract.pdf", f, "application/pdf")},
            )

        assert response.status_code == 200
        data = response.json()
        assert "document_id" in data
        assert data["filename"] == "Sample Contract.pdf"
        assert data["page_count"] > 0
        assert data["status"] == "ready"


class TestAnalyzeEndpoint:
    """Tests for the /api/analyze endpoint."""

    def test_analyze_returns_404_for_unknown_doc(self):
        """Analyzing a non-existent document should return 404."""
        response = client.post("/api/analyze/nonexistent-doc-id")
        assert response.status_code == 404

    def test_analyze_detail_message(self):
        response = client.post("/api/analyze/fake-id-12345")
        assert response.json()["detail"] == "Document not found"


class TestResultsEndpoint:
    """Tests for the /api/results endpoint."""

    def test_results_returns_404_for_unknown_doc(self):
        """Getting results for a non-existent document should return 404."""
        response = client.get("/api/results/nonexistent-doc-id")
        assert response.status_code == 404


class TestChatEndpoint:
    """Tests for the /api/chat endpoint."""

    def test_chat_returns_404_for_unknown_doc(self):
        """Chatting with a non-existent document should return 404."""
        response = client.post(
            "/api/chat",
            json={
                "document_id": "nonexistent-doc-id",
                "message": "Hello",
            },
        )
        assert response.status_code == 404

    def test_chat_validates_request_body(self):
        """Chat endpoint should validate the request body."""
        response = client.post("/api/chat", json={})
        assert response.status_code == 422  # Validation error