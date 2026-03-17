import os
import uuid
import shutil
from datetime import datetime, timezone
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
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

# In-memory stores
documents: dict = {}      # document_id → extraction result
analyzers: dict = {}      # document_id → ComplianceAnalyzer instance
results_store: dict = {}  # document_id → ComplianceReport
job_status: dict = {}     # document_id → {"status": "pending/processing/ready/failed", "error": str}

extractor = PDFExtractor()

@app.get("/api/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}

def background_upload_process(document_id: str, filepath: str, filename: str):
    """Internal task to handle extraction and indexing without blocking the API."""
    try:
        job_status[document_id] = {"status": "processing"}
        
        # 1. Extract content (Existing Service)
        extraction = extractor.extract(filepath)
        extraction["document_id"] = document_id
        extraction["filename"] = filename
        documents[document_id] = extraction

        # 2. Build vector index (Existing Service)
        full_text = extractor.get_full_text(extraction)
        analyzer = ComplianceAnalyzer(model_name=settings.model_name)
        analyzer.build_index(full_text)
        analyzers[document_id] = analyzer
        
        job_status[document_id] = {"status": "ready"}
    except Exception as e:
        job_status[document_id] = {"status": "failed", "error": str(e)}

@app.post("/api/upload", response_model=UploadResponse)
async def upload_contract(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """Upload a PDF contract and trigger extraction/indexing in the background."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    document_id = str(uuid.uuid4())
    filepath = os.path.join("uploads", f"{document_id}.pdf")
    os.makedirs("uploads", exist_ok=True)

    with open(filepath, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Trigger background processing
    job_status[document_id] = {"status": "pending"}
    background_tasks.add_task(background_upload_process, document_id, filepath, file.filename)

    return UploadResponse(
        document_id=document_id,
        filename=file.filename,
        page_count=0, # Will be updated once extraction is done
        status="processing",
    )

@app.get("/api/status/{document_id}")
async def get_job_status(document_id: str):
    """Check the status of an upload or analysis job."""
    status = job_status.get(document_id, {"status": "not_found"})
    if document_id in documents:
        status["page_count"] = documents[document_id].get("page_count", 0)
    return status

@app.post("/api/analyze/{document_id}")
async def analyze_compliance(document_id: str, background_tasks: BackgroundTasks):
    """Trigger compliance analysis in the background."""
    if document_id not in analyzers:
        raise HTTPException(status_code=404, detail="Document not indexed or found")

    job_status[document_id] = {"status": "analyzing"}

    def run_analysis(id: str):
        try:
            analyzer = analyzers[id]
            contract_name = documents[id]["filename"]
            report = analyzer.analyze_compliance(contract_name)
            results_store[id] = report
            job_status[id] = {"status": "analysis_complete"}
        except Exception as e:
            job_status[id] = {"status": "failed", "error": str(e)}

    background_tasks.add_task(run_analysis, document_id)
    return {"message": "Analysis started", "document_id": document_id}

@app.get("/api/results/{document_id}", response_model=ComplianceReport)
async def get_results(document_id: str):
    """Retrieve previously computed compliance results."""
    if document_id not in results_store:
        raise HTTPException(status_code=404, detail="No results found")
    return results_store[document_id]

@app.post("/api/chat", response_model=ChatResponse)
async def chat_with_document(request: ChatRequest):
    """Bonus: chat over the uploaded document (remains synchronous for responsiveness)."""
    if request.document_id not in analyzers:
        raise HTTPException(status_code=404, detail="Document not found")

    analyzer = analyzers[request.document_id]
    history = [{"role": m.role, "content": m.content} for m in (request.history or [])]
    response = analyzer.chat(request.message, history)

    return ChatResponse(
        answer=response["answer"],
        source_quotes=response["source_quotes"],
    )