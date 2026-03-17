"""
FastAPI backend for Contract Compliance Analyzer.

Endpoints:
  POST /api/upload          → Upload PDF, extract content, build index
  POST /api/analyze/{id}    → Run compliance analysis on uploaded document
  GET  /api/results/{id}    → Retrieve analysis results
  POST /api/chat            → Chat over document (bonus)
  GET  /api/health          → Health check
"""
import os
import uuid
import shutil
from datetime import datetime, timezone
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend.app.models.schemas import (
    UploadResponse, ComplianceReport, ChatRequest, ChatResponse
)
from backend.app.services.pdf_extractor import PDFExtractor
from backend.app.services.compliance_analyzer import ComplianceAnalyzer
from backend.app.config import settings

app = FastAPI(
    title="Contract Compliance Analyzer",
    description="AI-powered contract compliance analysis using RAG",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory store (use Redis/DB for production)
documents: dict = {}     # document_id → extraction result
analyzers: dict = {}     # document_id → ComplianceAnalyzer instance
results_store: dict = {} # document_id → ComplianceReport

extractor = PDFExtractor()


@app.get("/api/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.post("/api/upload", response_model=UploadResponse)
async def upload_contract(file: UploadFile = File(...)):
    """Upload a PDF contract and extract its content."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    # Save uploaded file
    document_id = str(uuid.uuid4())
    filepath = os.path.join("uploads", f"{document_id}.pdf")
    os.makedirs("uploads", exist_ok=True)

    with open(filepath, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Extract content
    extraction = extractor.extract(filepath)
    extraction["document_id"] = document_id
    documents[document_id] = extraction

    # Build vector index
    full_text = extractor.get_full_text(extraction)
    analyzer = ComplianceAnalyzer(model_name=settings.model_name)
    analyzer.build_index(full_text)
    analyzers[document_id] = analyzer

    return UploadResponse(
        document_id=document_id,
        filename=file.filename,
        page_count=extraction["page_count"],
        status="ready",
    )


@app.post("/api/analyze/{document_id}", response_model=ComplianceReport)
async def analyze_compliance(document_id: str):
    """Run compliance analysis on an uploaded document."""
    if document_id not in analyzers:
        raise HTTPException(status_code=404, detail="Document not found")

    analyzer = analyzers[document_id]
    contract_name = documents[document_id]["filename"]
    report = analyzer.analyze_compliance(contract_name)

    results_store[document_id] = report
    return report


@app.get("/api/results/{document_id}", response_model=ComplianceReport)
async def get_results(document_id: str):
    """Retrieve previously computed compliance results."""
    if document_id not in results_store:
        raise HTTPException(status_code=404, detail="No results found")
    return results_store[document_id]


@app.post("/api/chat", response_model=ChatResponse)
async def chat_with_document(request: ChatRequest):
    """Bonus: chat over the uploaded document."""
    if request.document_id not in analyzers:
        raise HTTPException(status_code=404, detail="Document not found")

    analyzer = analyzers[request.document_id]
    history = [{"role": m.role, "content": m.content} for m in (request.history or [])]
    response = analyzer.chat(request.message, history)

    return ChatResponse(
        answer=response["answer"],
        source_quotes=response["source_quotes"],
    )