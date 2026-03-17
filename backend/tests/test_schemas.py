"""
Pydantic schema validation tests.

Run with: pytest backend/tests/test_schemas.py -v
"""
import pytest
from pydantic import ValidationError
from backend.app.models.schemas import (
    ComplianceState,
    ComplianceResult,
    ComplianceReport,
    UploadResponse,
    ChatRequest,
    ChatResponse,
)


class TestComplianceState:
    """Tests for the ComplianceState enum."""

    def test_valid_states(self):
        assert ComplianceState("Fully Compliant") == ComplianceState.FULLY_COMPLIANT
        assert ComplianceState("Partially Compliant") == ComplianceState.PARTIALLY_COMPLIANT
        assert ComplianceState("Non-Compliant") == ComplianceState.NON_COMPLIANT

    def test_invalid_state_raises(self):
        with pytest.raises(ValueError):
            ComplianceState("Invalid State")


class TestComplianceResult:
    """Tests for a single compliance result."""

    def _valid_result(self, **overrides):
        defaults = {
            "compliance_question": "Password Management",
            "compliance_state": "Fully Compliant",
            "confidence": 95.0,
            "relevant_quotes": ["Section 4.1 requires strong passwords."],
            "rationale": "All password criteria are met.",
        }
        defaults.update(overrides)
        return ComplianceResult(**defaults)

    def test_valid_result(self):
        result = self._valid_result()
        assert result.compliance_question == "Password Management"
        assert result.compliance_state == ComplianceState.FULLY_COMPLIANT
        assert result.confidence == 95.0

    def test_confidence_must_be_0_to_100(self):
        """Confidence should be between 0 and 100."""
        with pytest.raises(ValidationError):
            self._valid_result(confidence=101.0)

        with pytest.raises(ValidationError):
            self._valid_result(confidence=-5.0)

    def test_confidence_boundary_values(self):
        """0 and 100 should be valid."""
        r1 = self._valid_result(confidence=0)
        assert r1.confidence == 0

        r2 = self._valid_result(confidence=100)
        assert r2.confidence == 100

    def test_invalid_compliance_state(self):
        with pytest.raises(ValidationError):
            self._valid_result(compliance_state="Maybe Compliant")

    def test_empty_quotes_allowed(self):
        """Empty quotes list should be valid (for Non-Compliant cases)."""
        result = self._valid_result(relevant_quotes=[])
        assert result.relevant_quotes == []


class TestComplianceReport:
    """Tests for the full compliance report."""

    def _valid_result(self, question="Password Management"):
        return {
            "compliance_question": question,
            "compliance_state": "Fully Compliant",
            "confidence": 90.0,
            "relevant_quotes": ["Quote"],
            "rationale": "Rationale",
        }

    def _valid_report(self, **overrides):
        defaults = {
            "contract_name": "Sample Contract.pdf",
            "analysis_timestamp": "2026-03-17T00:00:00Z",
            "model_used": "gpt-4o",
            "results": [
                self._valid_result("Password Management"),
                self._valid_result("IT Asset Management"),
                self._valid_result("Security Training"),
                self._valid_result("Data in Transit Encryption"),
                self._valid_result("Network Auth & Authorization"),
            ],
        }
        defaults.update(overrides)
        return ComplianceReport(**defaults)

    def test_valid_report(self):
        report = self._valid_report()
        assert report.contract_name == "Sample Contract.pdf"
        assert len(report.results) == 5

    def test_must_have_exactly_5_results(self):
        """The assignment requires exactly 5 compliance questions."""
        with pytest.raises(ValidationError):
            self._valid_report(results=[self._valid_result()])  # Only 1

    def test_report_json_serialization(self):
        """Report should serialize to JSON correctly."""
        report = self._valid_report()
        json_str = report.model_dump_json()
        assert "Password Management" in json_str
        assert "gpt-4o" in json_str


class TestUploadResponse:
    """Tests for upload response schema."""

    def test_valid_upload_response(self):
        resp = UploadResponse(
            document_id="abc-123",
            filename="test.pdf",
            page_count=10,
            status="ready",
        )
        assert resp.document_id == "abc-123"
        assert resp.page_count == 10


class TestChatSchemas:
    """Tests for chat request/response schemas."""

    def test_chat_request_minimal(self):
        req = ChatRequest(document_id="abc", message="Hello")
        assert req.document_id == "abc"
        assert req.history == []

    def test_chat_response(self):
        resp = ChatResponse(answer="The contract says...", source_quotes=["Quote 1"])
        assert resp.answer == "The contract says..."
        assert len(resp.source_quotes) == 1