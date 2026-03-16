from fastapi import APIRouter, UploadFile, File, BackgroundTasks
from fastapi.responses import JSONResponse
from .ingest import extract_all
from .ingest import extract_text_pymupdf4llm as extract_pages
import os

router = APIRouter()

@router.post("/upload")
async def upload_contract(file: UploadFile = File(...), background_tasks: BackgroundTasks = None):
    # Make sure the folder exists first!
    os.makedirs("uploads", exist_ok=True)
    
    path = f"uploads/{file.filename}"
    with open(path, "wb") as f:
        f.write(await file.read())

    # Only call the "Master Expert" (extract_all)
    # It already handles text, tables, and images!
    background_tasks.add_task(extract_all, path)

    return JSONResponse({
        "status": "processing", 
        "message": f"Successfully uploaded {file.filename}. Processing started!"
    })


@router.get("/health")
async def health():
    return {"status": "ok"}

