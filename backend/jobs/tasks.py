# backend/jobs/tasks.py
import os
import uuid
import json
from pathlib import Path

from backend.jobs.celery_app import celery_app

from backend.app.ingest import extract_all
from backend.app.indexer import build_documents, save_docs_json
from backend.app.retrieval import FaissRetriever
from backend.app.llm import analyze_question


INDEX_DIR = "indexes"
DOCS_STORE = os.path.join(INDEX_DIR, "docs.json")
JOB_RESULTS_DIR = "job_results"
os.makedirs(JOB_RESULTS_DIR, exist_ok=True)

import logging
logger = logging.getLogger(__name__)

@celery_app.task(bind=True)
def task_ingest_and_index(self, upload_path: str, source_filename: str = None) -> dict:
    logger.info("task_ingest_and_index started for %s", upload_path)
    job_id = str(uuid.uuid4())
    result_path = os.path.join(JOB_RESULTS_DIR, f"{job_id}.json")
    try:
        ingest_result = extract_all(upload_path)
        docs = build_documents(ingest_result, source_filename=source_filename, use_token_chunking=True)

        os.makedirs(INDEX_DIR, exist_ok=True)
        save_docs_json(docs, DOCS_STORE)

        retriever = FaissRetriever(index_path=os.path.join(INDEX_DIR, "faiss.index"),
                                   meta_path=os.path.join(INDEX_DIR, "meta.json"))
        retriever.build_index(docs, index_type="hnsw")
        retriever.save(index_dir=INDEX_DIR)

        payload = {"job_id": job_id, "state": "done", "num_docs": len(docs)}
        with open(result_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        return payload
    except Exception as e:
        payload = {"job_id": job_id, "state": "error", "error": str(e)}
        with open(result_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        raise

@celery_app.task(bind=True)
def task_run_analysis(self, question: str, top_k: int = 6, ef_search: int = 200) -> dict:
    job_id = str(uuid.uuid4())
    result_path = os.path.join(JOB_RESULTS_DIR, f"{job_id}.json")
    try:
        # load index and docs
        retriever = FaissRetriever(index_path=os.path.join(INDEX_DIR, "faiss.index"),
                                   meta_path=os.path.join(INDEX_DIR, "meta.json"))
        retriever.load(index_dir=INDEX_DIR)

        hits = retriever.query(question, top_k=top_k, ef_search=ef_search)
        # prepare retrieved_docs in expected shape
        retrieved_docs = [{"id": h["id"], "text": h["text"], "metadata": h["metadata"]} for h in hits]

        analysis = analyze_question(question, retrieved_docs)
        payload = {"job_id": job_id, "state": "done", "question": question, "analysis": analysis}
        with open(result_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        return payload
    except Exception as e:
        payload = {"job_id": job_id, "state": "error", "error": str(e)}
        with open(result_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        raise
