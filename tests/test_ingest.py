# tests/test_ingest.py
import pytest
from reportlab.pdfgen import canvas
from pathlib import Path

from backend.app.ingest import extract_text_pymupdf4llm

@pytest.fixture
def sample_pdf(tmp_path):
    """
    Create a tiny valid PDF with two pages so the ingestion code
    and the mocked pymupdf4llm.to_markdown can produce two pages.
    """
    path = tmp_path / "sample.pdf"
    c = canvas.Canvas(str(path))
    # Page 1
    c.drawString(100, 750, "Hello PDF - page 1")
    c.showPage()
    # Page 2
    c.drawString(100, 750, "Hello PDF - page 2")
    c.showPage()
    c.save()
    return str(path)


def test_extract_text_calls_pymupdf4llm(sample_pdf, monkeypatch):
    # Mock pymupdf4llm.to_markdown to return two pages separated by form feed
    import pymupdf4llm
    monkeypatch.setattr(pymupdf4llm, "to_markdown", lambda p: "page1 text\fpage2 text")
    pages = extract_text_pymupdf4llm(sample_pdf)
    assert isinstance(pages, list)
    assert len(pages) == 2
    assert pages[0]["page"] == 1
    assert "page1" in pages[0]["text"]
