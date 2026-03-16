# backend/app/api_index.py
import os
import uuid
from fastapi import APIRouter, UploadFile, File, BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse

router = APIRouter()
JOB_RESULTS_DIR = "job_results"

@router.post("/index/build")
async def build_index_from_upload(file: UploadFile = File(...)):
    from backend.jobs.worker_celery import task_ingest_and_index

    # task = task_ingest_and_index.delay(path, file.filename)
    
    # return {"job_id": task.id, "state": "queued"}

    os.makedirs("uploads", exist_ok=True)
    filename = file.filename
    path = os.path.join("uploads", filename)
    with open(path, "wb") as f:
        f.write(await file.read())

    # enqueue Celery task
    async_result = task_ingest_and_index.delay(path, filename)
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
    """
    Two modes:
      - Provide a file + question: enqueue ingest+index then analysis (not implemented as chained here).
      - Provide question only: run analysis against existing index.
    For simplicity, if file provided we first enqueue ingest task and return its task id.
    """
    if file:
        # upload and build index first
        os.makedirs("uploads", exist_ok=True)
        filename = file.filename
        path = os.path.join("uploads", filename)
        with open(path, "wb") as f:
            f.write(await file.read())
        async_result = task_ingest_and_index.delay(path, filename)
        return {"task_id": async_result.id, "state": "queued", "message": "Indexing started. Poll /jobs/{task_id}/status"}
    if not question:
        raise HTTPException(status_code=400, detail="Provide a question or a file + question")
    async_result = task_run_analysis.delay(question)
    return {"task_id": async_result.id, "state": "queued"}
