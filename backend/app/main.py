import os
import uuid
import shutil
import logging
from datetime import datetime, timezone

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware

from backend.app.models.schemas import (
    UploadResponse, ComplianceReport, ChatRequest, ChatResponse,
)
from backend.app.services.pdf_extractor import PDFExtractor
from backend.app.services.compliance_analyzer import ComplianceAnalyzer
from backend.app.api.routes import router as api_router
from backend.app.config import settings

logger = logging.getLogger(__name__)

# ── App & Middleware ──────────────────────────────────────────────────────
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

# ── Register the API router ──────────────────────────────────────────────
# All routes defined in backend/app/api/routes.py are now mounted under /api
app.include_router(api_router, prefix="/api/v2", tags=["router"])
# ── In-memory stores (used by the inline endpoints below) ────────────────
documents: dict = {}      # document_id → extraction dict
analyzers: dict = {}      # document_id → ComplianceAnalyzer instance
results_store: dict = {}  # document_id → ComplianceReport
job_status: dict = {}     # document_id → {"status": ..., "error": ...}

extractor = PDFExtractor()


# ── Health ────────────────────────────────────────────────────────────────
@app.get("/api/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}


# ── Background upload (async flow used by the Streamlit frontend) ────────
def background_upload_process(document_id: str, filepath: str, filename: str):
    """Extract PDF content and build a vector index in the background."""
    try:
        job_status[document_id] = {"status": "processing"}

        # 1. Extract text + tables → dict
        extraction = extractor.extract(filepath)
        extraction["document_id"] = document_id
        extraction["filename"] = filename
        documents[document_id] = extraction

        # 2. Build FAISS vector index
        full_text = extractor.get_full_text(extraction)
        analyzer = ComplianceAnalyzer(model_name=settings.model_name)
        analyzer.build_index(full_text)
        analyzers[document_id] = analyzer

        job_status[document_id] = {"status": "ready"}
    except Exception as e:
        logger.exception("Background upload failed for %s", document_id)
        job_status[document_id] = {"status": "failed", "error": str(e)}


@app.post("/api/upload", response_model=UploadResponse)
async def upload_contract(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    """Upload a PDF contract and trigger extraction/indexing in the background."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    document_id = str(uuid.uuid4())
    filepath = os.path.join("uploads", f"{document_id}.pdf")
    os.makedirs("uploads", exist_ok=True)

    with open(filepath, "wb") as f:
        shutil.copyfileobj(file.file, f)

    job_status[document_id] = {"status": "pending"}
    background_tasks.add_task(
        background_upload_process, document_id, filepath, file.filename
    )

    return UploadResponse(
        document_id=document_id,
        filename=file.filename,
        page_count=0,  # Updated once extraction completes
        status="processing",
    )


# ── Status polling ────────────────────────────────────────────────────────
@app.get("/api/status/{document_id}")
async def get_job_status(document_id: str):
    """Check the status of an upload or analysis job."""
    status = job_status.get(document_id, {"status": "not_found"})
    if document_id in documents:
        status["page_count"] = documents[document_id].get("page_count", 0)
    return status


# ── Analyze (background) ─────────────────────────────────────────────────
@app.post("/api/analyze/{document_id}")
async def analyze_compliance(
    document_id: str,
    background_tasks: BackgroundTasks,
):
    """Trigger compliance analysis in the background."""
    if document_id not in analyzers:
        raise HTTPException(status_code=404, detail="Document not indexed or found")

    job_status[document_id] = {"status": "analyzing"}

    def run_analysis(doc_id: str):
        try:
            analyzer = analyzers[doc_id]
            contract_name = documents[doc_id]["filename"]
            report = analyzer.analyze_compliance(contract_name)
            results_store[doc_id] = report
            job_status[doc_id] = {"status": "analysis_complete"}
        except Exception as e:
            logger.exception("Analysis failed for %s", doc_id)
            job_status[doc_id] = {"status": "failed", "error": str(e)}

    background_tasks.add_task(run_analysis, document_id)
    return {"message": "Analysis started", "document_id": document_id}


# ── Results ───────────────────────────────────────────────────────────────
@app.get("/api/results/{document_id}", response_model=ComplianceReport)
async def get_results(document_id: str):
    """Retrieve previously computed compliance results."""
    if document_id not in results_store:
        raise HTTPException(status_code=404, detail="No results found")
    return results_store[document_id]


# ── Chat ──────────────────────────────────────────────────────────────────
@app.post("/api/chat", response_model=ChatResponse)
async def chat_with_document(request: ChatRequest):
    """Chat over the uploaded document using RAG."""
    if request.document_id not in analyzers:
        raise HTTPException(status_code=404, detail="Document not found")

    analyzer = analyzers[request.document_id]
    history = [
        {"role": m.role, "content": m.content}
        for m in (request.history or [])
    ]
    response = analyzer.chat(request.message, history)

    return ChatResponse(
        answer=response["answer"],
        source_quotes=response["source_quotes"],
    )