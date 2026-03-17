# tests/test_api.py
from fastapi.testclient import TestClient
from backend.app.main import app
client = TestClient(app)

class DummyAsync:
    def __init__(self): self.id = "fake-id"
class DummyTask:
    def delay(self, *a, **k): return DummyAsync()

def test_build_index_endpoint(monkeypatch, tmp_path):
    # create a valid PDF
    fpath = tmp_path / "t.pdf"
    from reportlab.pdfgen import canvas
    c = canvas.Canvas(str(fpath))
    c.drawString(100, 750, "Test")
    c.showPage()
    c.save()

    # Patch the task symbol where the endpoint will import it from.
    # If api_index imports from backend.jobs.tasks as `from backend.jobs.tasks import task_ingest_and_index`
    # then patch that module attribute:
    import backend.jobs.tasks as tasks_module
    monkeypatch.setattr(tasks_module, "task_ingest_and_index", DummyTask())

    with open(str(fpath), "rb") as fh:
        files = {"file": ("t.pdf", fh, "application/pdf")}
        resp = client.post("/api/index/index/build", files=files)
    assert resp.status_code == 200
    data = resp.json()
    assert data["task_id"] == "fake-id"
