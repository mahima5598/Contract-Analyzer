"""
Chunker unit tests.

Run with: pytest backend/tests/test_chunker.py -v
"""
import pytest
from backend.app.services.chunker import DocumentChunker, Chunk


class TestDocumentChunker:
    """Tests for the document chunking service."""

    def setup_method(self):
        self.chunker = DocumentChunker(chunk_size=200, chunk_overlap=50)

    def test_chunk_simple_text(self):
        """Short text that fits in one chunk."""
        extraction = {
            "pages": [{"page_number": 1, "text": "This is a short contract."}],
            "tables": [],
            "images_text": [],
        }
        chunks = self.chunker.chunk_document(extraction)
        assert len(chunks) == 1
        assert chunks[0].content == "This is a short contract."
        assert chunks[0].page_number == 1

    def test_chunk_long_text_splits(self):
        """Long text should be split into multiple chunks."""
        long_text = "This is a sentence about compliance. " * 50
        extraction = {
            "pages": [{"page_number": 1, "text": long_text}],
            "tables": [],
            "images_text": [],
        }
        chunks = self.chunker.chunk_document(extraction)
        assert len(chunks) > 1

    def test_chunk_preserves_page_metadata(self):
        """Each chunk should retain the page number it came from."""
        extraction = {
            "pages": [
                {"page_number": 1, "text": "Page one content."},
                {"page_number": 2, "text": "Page two content."},
            ],
            "tables": [],
            "images_text": [],
        }
        chunks = self.chunker.chunk_document(extraction)
        pages = [c.page_number for c in chunks]
        assert 1 in pages
        assert 2 in pages

    def test_chunk_tables_get_prefix(self):
        """Table chunks should be prefixed with [TABLE]."""
        extraction = {
            "pages": [],
            "tables": [
                {"page_number": 3, "markdown": "| Col1 | Col2 |\n|---|---|\n| A | B |"}
            ],
            "images_text": [],
        }
        chunks = self.chunker.chunk_document(extraction)
        assert len(chunks) == 1
        assert "[TABLE on Page 3]" in chunks[0].content
        assert chunks[0].source_type == "table"

    def test_chunk_images_get_prefix(self):
        """Image OCR chunks should be prefixed with [IMAGE/EXHIBIT]."""
        extraction = {
            "pages": [],
            "tables": [],
            "images_text": [
                {"page_number": 5, "extracted_text": "Exhibit G: Security Controls detailed table with many requirements listed."}
            ],
        }
        chunks = self.chunker.chunk_document(extraction)
        assert len(chunks) == 1
        assert "[IMAGE/EXHIBIT on Page 5]" in chunks[0].content
        assert chunks[0].source_type == "image_ocr"

    def test_empty_pages_skipped(self):
        """Pages with empty text should be skipped."""
        extraction = {
            "pages": [
                {"page_number": 1, "text": ""},
                {"page_number": 2, "text": "   "},
                {"page_number": 3, "text": "Has content."},
            ],
            "tables": [],
            "images_text": [],
        }
        chunks = self.chunker.chunk_document(extraction)
        assert len(chunks) == 1
        assert chunks[0].page_number == 3

    def test_short_image_text_skipped(self):
        """Very short OCR text (likely noise) should be skipped."""
        extraction = {
            "pages": [],
            "tables": [],
            "images_text": [
                {"page_number": 1, "extracted_text": "abc"},  # Too short
            ],
        }
        chunks = self.chunker.chunk_document(extraction)
        assert len(chunks) == 0

    def test_get_texts_and_metadatas(self):
        """Convenience method should return parallel lists."""
        chunks = [
            Chunk(content="Text 1", metadata={"page_number": 1}),
            Chunk(content="Text 2", metadata={"page_number": 2}),
        ]
        texts, metadatas = self.chunker.get_texts_and_metadatas(chunks)
        assert texts == ["Text 1", "Text 2"]
        assert metadatas[0]["page_number"] == 1

    def test_get_stats(self):
        """Stats should include counts and length info."""
        chunks = [
            Chunk(content="Short", metadata={"source_type": "text"}),
            Chunk(content="A bit longer text here", metadata={"source_type": "text"}),
            Chunk(content="Table content", metadata={"source_type": "table"}),
        ]
        stats = self.chunker.get_stats(chunks)
        assert stats["total_chunks"] == 3
        assert stats["by_source_type"]["text"] == 2
        assert stats["by_source_type"]["table"] == 1
        assert stats["min_chunk_length"] == 5
        assert stats["max_chunk_length"] == 22