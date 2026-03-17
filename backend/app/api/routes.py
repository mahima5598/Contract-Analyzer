import tempfile
import traceback
from fastapi import APIRouter, UploadFile, File, HTTPException
from backend.app.services.pdf_extractor import PDFExtractor
from backend.app.services.compliance_analyzer import ComplianceAnalyzer
import os, logging

logger = logging.getLogger(__name__)

router = APIRouter()
extractor = PDFExtractor()
analyzer = ComplianceAnalyzer()

@router.post("/upload")
async def upload_contract(file: UploadFile = File(...)):
    # use a safe unique temp file
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1])
    temp_path = tmp.name
    try:
        content = await file.read()
        tmp.write(content)
        tmp.close()

        # get extracted content
        extracted = extractor.extract_text(temp_path)

        # normalize to list of docs/chunks expected by analyzer
        if isinstance(extracted, str):
            docs = [extracted]
        elif isinstance(extracted, (list, tuple)):
            docs = list(extracted)
        else:
            # if extractor returns a custom object, adapt accordingly
            docs = [str(extracted)]

        if not docs or all(not (isinstance(d, str) and d.strip()) for d in docs):
            raise ValueError("No readable text found in PDF. It might be an image-only scan.")

        # pass a list to build_index (avoid passing a raw string)
        analyzer.build_index(docs)

        return {
            "filename": file.filename,
            "status": "ready",
            "message": f"Successfully indexed {file.filename}"
        }

    except Exception as e:
        # full traceback for debugging
        tb = traceback.format_exc()
        logger.error("Upload failed: %s\n%s", e, tb)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        except Exception:
            logger.exception("Failed to remove temp file %s", temp_path)
