"""
Integration test — full pipeline with the sample contract.

Run with: pytest backend/tests/test_integration.py -v -s

NOTE: This test requires:
  1. A valid OPENAI_API_KEY in your .env file
  2. The sample contract at docs/task_docs/Sample Contract.pdf
  
It will make actual API calls to OpenAI and may take 1-2 minutes.
Skip with: pytest -m "not integration"
"""
import os
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app


# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration

client = TestClient(app)

SAMPLE_PDF_PATH = "docs/task_docs/Sample Contract.pdf"


@pytest.fixture
def uploaded_document():
    """Upload the sample contract and return the document info."""
    if not os.path.exists(SAMPLE_PDF_PATH):
        pytest.skip("Sample contract PDF not found")

    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY not set")

    with open(SAMPLE_PDF_PATH, "rb") as f:
        response = client.post(
            "/api/upload",
            files={"file": ("Sample Contract.pdf", f, "application/pdf")},
        )

    assert response.status_code == 200
    return response.json()


class TestFullPipeline:

    def test_upload_sample_contract(self, uploaded_document):
        """Sample contract should upload successfully."""
        assert uploaded_document["status"] == "ready"
        assert uploaded_document["page_count"] > 0
        print(f"\n  ✅ Uploaded: {uploaded_document['page_count']} pages")

    def test_analyze_sample_contract(self, uploaded_document):
        """Full compliance analysis should return 5 results."""
        doc_id = uploaded_document["document_id"]

        response = client.post(f"/api/analyze/{doc_id}")
        assert response.status_code == 200

        report = response.json()
        assert len(report["results"]) == 5
        assert report["contract_name"] == "Sample Contract.pdf"

        # Print results for visual inspection
        print(f"\n  📊 Compliance Report for: {report['contract_name']}")
        print(f"  Model: {report['model_used']}")
        for i, r in enumerate(report["results"], 1):
            print(f"  Q{i}: {r['compliance_question']}")
            print(f"      State: {r['compliance_state']} ({r['confidence']}%)")
            print(f"      Rationale: {r['rationale'][:100]}...")
            print()

        # Validate each result
        valid_states = {"Fully Compliant", "Partially Compliant", "Non-Compliant"}
        for r in report["results"]:
            assert r["compliance_state"] in valid_states
            assert 0 <= r["confidence"] <= 100
            assert len(r["rationale"]) > 0

    def test_chat_with_sample_contract(self, uploaded_document):
        """Chat should return an answer grounded in the contract."""
        doc_id = uploaded_document["document_id"]

        response = client.post(
            "/api/chat",
            json={
                "document_id": doc_id,
                "message": "Does this contract mention encryption requirements?",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["answer"]) > 0
        print(f"\n  💬 Chat answer: {data['answer'][:200]}...")

    def test_get_results_after_analysis(self, uploaded_document):
        """Results should be retrievable after analysis."""
        doc_id = uploaded_document["document_id"]

        # First run analysis
        client.post(f"/api/analyze/{doc_id}")

        # Then retrieve results
        response = client.get(f"/api/results/{doc_id}")
        assert response.status_code == 200
        assert len(response.json()["results"]) == 5