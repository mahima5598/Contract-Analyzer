"""
Standalone API router for contract operations.

This router is intended for lightweight / single-user use (e.g. local dev or
a quick demo) where you want one POST /upload endpoint that extracts, indexes,
and is immediately ready for analysis — no background tasks.

For the full async/multi-user flow, use the endpoints in main.py instead.
"""

import os
import uuid
import tempfile
import logging
import traceback

from fastapi import APIRouter, UploadFile, File, HTTPException

from backend.app.services.pdf_extractor import PDFExtractor
from backend.app.services.compliance_analyzer import ComplianceAnalyzer
from backend.app.config import settings
from backend.app.models.schemas import UploadResponse

logger = logging.getLogger(__name__)

router = APIRouter()

# Shared extractor (stateless — safe to reuse)
extractor = PDFExtractor()

# Per-document stores so each upload gets its own analyzer
_analyzers: dict = {}   # document_id → ComplianceAnalyzer
_documents: dict = {}   # document_id → extraction dict


# ── Upload & Index ────────────────────────────────────────────────────────
@router.post("/upload", response_model=UploadResponse)
async def upload_contract(file: UploadFile = File(...)):
    """
    Upload a PDF, extract text + tables, build a FAISS vector index,
    and return a document_id the caller can use for /analyze and /chat.
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    document_id = str(uuid.uuid4())

    # Write to a temp file so pdfplumber can open it by path
    tmp = tempfile.NamedTemporaryFile(
        delete=False,
        suffix=os.path.splitext(file.filename)[1],
    )
    temp_path = tmp.name

    try:
        content = await file.read()
        tmp.write(content)
        tmp.close()

        # ── 1. Extract (returns dict with pages, tables, page_count) ──
        extraction = extractor.extract(temp_path)
        extraction["document_id"] = document_id
        extraction["filename"] = file.filename

        # ── 2. Get full text for indexing ─────────────────────────────
        full_text = extractor.get_full_text(extraction)

        if not full_text.strip():
            raise ValueError(
                "No readable text found in PDF. It might be an image-only scan."
            )

        # ── 3. Build vector index ─────────────────────────────────────
        analyzer = ComplianceAnalyzer(model_name=settings.model_name)
        analyzer.build_index(full_text)

        # Store for downstream /analyze and /chat calls
        _analyzers[document_id] = analyzer
        _documents[document_id] = extraction

        return UploadResponse(
            document_id=document_id,
            filename=file.filename,
            page_count=extraction["page_count"],
            status="ready",
        )

    except ValueError as ve:
        raise HTTPException(status_code=422, detail=str(ve))

    except Exception as e:
        tb = traceback.format_exc()
        logger.error("Upload failed: %s\n%s", e, tb)
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        except Exception:
            logger.exception("Failed to remove temp file %s", temp_path)


# ── Analyze ───────────────────────────────────────────────────────────────
@router.post("/analyze/{document_id}")
async def analyze_compliance(document_id: str):
    """Run the 5 compliance questions against a previously uploaded document."""
    if document_id not in _analyzers:
        raise HTTPException(status_code=404, detail="Document not found or not indexed")

    try:
        analyzer = _analyzers[document_id]
        contract_name = _documents[document_id]["filename"]
        report = analyzer.analyze_compliance(contract_name)
        return report
    except Exception as e:
        logger.exception("Analysis failed for %s", document_id)
        raise HTTPException(status_code=500, detail=str(e))


# ── Chat ──────────────────────────────────────────────────────────────────
@router.post("/chat")
async def chat_with_document(document_id: str, message: str):
    """Ask a free-form question about a previously uploaded document."""
    if document_id not in _analyzers:
        raise HTTPException(status_code=404, detail="Document not found or not indexed")

    try:
        analyzer = _analyzers[document_id]
        response = analyzer.chat(message)
        return response
    except Exception as e:
        logger.exception("Chat failed for %s", document_id)
        raise HTTPException(status_code=500, detail=str(e))