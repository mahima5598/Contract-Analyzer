# tests/test_tasks.py
import os
from backend.jobs import tasks as tasks_module

def test_task_ingest_and_index_runs(tmp_path, monkeypatch):
    pdf = tmp_path / "t.pdf"
    # create a valid tiny PDF (reportlab) or write bytes that fitz can open
    from reportlab.pdfgen import canvas
    c = canvas.Canvas(str(pdf))
    c.drawString(100, 750, "Test")
    c.showPage()
    c.save()

    # Patch the symbol used inside tasks module directly
    monkeypatch.setattr(tasks_module, "extract_all", lambda p: [{"source": p, "pages": []}])
    monkeypatch.setattr(tasks_module, "build_documents", lambda ingest_result, **kw: [{"id": "doc1", "text": "x"}])
    monkeypatch.setattr(tasks_module, "save_docs_json", lambda docs, path: None)

    class DummyRetriever:
        def __init__(self, *a, **k): pass
        def build_index(self, docs, index_type=None): pass
        def save(self, index_dir=None): pass

    monkeypatch.setattr(tasks_module, "FaissRetriever", DummyRetriever)

    # run the task synchronously (no broker)
    result = tasks_module.task_ingest_and_index.run(str(pdf), pdf.name)
    assert result["state"] == "done"
    assert "job_id" in result
