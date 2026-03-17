from pydantic import BaseModel, Field
from enum import Enum
from typing import List, Optional


class ComplianceState(str, Enum):
    FULLY_COMPLIANT = "Fully Compliant"
    PARTIALLY_COMPLIANT = "Partially Compliant"
    NON_COMPLIANT = "Non-Compliant"


class ComplianceResult(BaseModel):
    """Schema for a single compliance question result."""
    compliance_question: str = Field(
        ..., description="The compliance requirement being evaluated"
    )
    compliance_state: ComplianceState = Field(
        ..., description="Fully Compliant, Partially Compliant, or Non-Compliant"
    )
    confidence: float = Field(
        ..., ge=0, le=100, description="Confidence percentage (0-100)"
    )
    relevant_quotes: List[str] = Field(
        ..., description="Exact quotes from the contract supporting the assessment"
    )
    rationale: str = Field(
        ..., description="Explanation of why this compliance state was assigned"
    )


class ComplianceReport(BaseModel):
    """Full compliance analysis report for all 5 questions."""
    contract_name: str
    analysis_timestamp: str
    results: List[ComplianceResult] = Field(
        ..., min_length=5, max_length=5,
        description="Exactly 5 compliance question results"
    )
    model_used: str = Field(
        ..., description="LLM model name and version used for analysis"
    )


class UploadResponse(BaseModel):
    document_id: str
    filename: str
    page_count: int
    status: str


class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    document_id: str
    message: str
    history: Optional[List[ChatMessage]] = []


class ChatResponse(BaseModel):
    answer: str
    source_quotes: List[str] = []