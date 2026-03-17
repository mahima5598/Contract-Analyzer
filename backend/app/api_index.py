# backend/app/api_index.py
import os
import uuid
import logging
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse

router = APIRouter()
JOB_RESULTS_DIR = "job_results"
os.makedirs(JOB_RESULTS_DIR, exist_ok=True)
os.makedirs("uploads", exist_ok=True)

logger = logging.getLogger(__name__)

@router.post("/index/build")
async def build_index_from_upload(file: UploadFile = File(...)):
    logger.info("Received upload request: filename=%s", file.filename)
    try:
        from backend.jobs.tasks import task_ingest_and_index
    except Exception as e:
        logger.exception("Failed to import Celery task module")
        raise HTTPException(status_code=500, detail=f"Server import error: {e}")

    os.makedirs("uploads", exist_ok=True)
    filename = file.filename
    path = os.path.join("uploads", filename)
    try:
        content = await file.read()
        with open(path, "wb") as f:
            f.write(content)
    except Exception as e:
        logger.exception("Failed to save uploaded file")
        raise HTTPException(status_code=500, detail=f"Failed to save file: {e}")

    # enqueue Celery task
    try:
        async_result = task_ingest_and_index.delay(path, filename)
    except Exception as e:
        logger.exception("Failed to enqueue Celery task")
        raise HTTPException(status_code=500, detail=f"Failed to enqueue task: {e}")

    return JSONResponse({"task_id": async_result.id, "state": "queued"})

@router.get("/jobs/{task_id}/status")
async def job_status(task_id: str):
    from celery.result import AsyncResult
    res = AsyncResult(task_id)
    return {"task_id": task_id, "state": res.state, "info": res.info}

@router.get("/jobs/{task_id}/results")
async def job_results(task_id: str):
    # Celery result backend may have the result; also check job_results folder
    result_file = os.path.join(JOB_RESULTS_DIR, f"{task_id}.json")
    if os.path.exists(result_file):
        import json
        with open(result_file, "r", encoding="utf-8") as f:
            return json.load(f)
    # fallback to Celery result backend
    from celery.result import AsyncResult
    res = AsyncResult(task_id)
    if res.ready():
        return {"task_id": task_id, "state": res.state, "result": res.result}
    raise HTTPException(status_code=404, detail="Result not found yet")

@router.post("/analyze")
async def analyze_endpoint(question: str = None, file: UploadFile = None):
    if file:
        try:
            from backend.jobs.tasks import task_ingest_and_index
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Server import error: {e}")
        # ... (save file and enqueue as in build handler) ...
    if not question:
        raise HTTPException(status_code=400, detail="Provide a question or a file + question")
    try:
        from backend.jobs.tasks import task_run_analysis
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Server import error: {e}")
    async_result = task_run_analysis.delay(question)
    return {"task_id": async_result.id, "state": "queued"}

@router.get("/debug/env")
async def debug_env():
    import importlib, traceback, os
    info = {"cwd": os.getcwd(), "uploads_writable": os.access("uploads", os.W_OK)}
    try:
        importlib.import_module("backend.jobs.tasks")
        info["worker_import"] = "ok"
    except Exception as e:
        info["worker_import"] = str(e)
        info["worker_trace"] = traceback.format_exc()
    return info
