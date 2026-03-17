"""
Document chunking service.

Design decisions:
─────────────────
1. RecursiveCharacterTextSplitter is used because contracts have a natural
   hierarchy: sections → paragraphs → sentences. Recursive splitting
   respects these boundaries rather than cutting mid-sentence.

2. Chunk size of 1500 chars (~375 tokens) balances two tensions:
   - Too small → loses context, compliance criteria span multiple paragraphs
   - Too large → dilutes relevance, wastes LLM context window

3. Overlap of 200 chars ensures that if a compliance clause straddles two
   chunks, it appears fully in at least one of them.

4. Metadata (page number, source type) is attached to each chunk so the
   UI can show WHERE in the contract a quote came from.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from langchain_text_splitters import RecursiveCharacterTextSplitter


@dataclass
class Chunk:
    """A single chunk of document content with metadata."""
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def page_number(self) -> Optional[int]:
        return self.metadata.get("page_number")

    @property
    def source_type(self) -> str:
        return self.metadata.get("source_type", "text")


class DocumentChunker:
    """
    Splits extracted document content into chunks suitable for embedding.

    Handles three content types separately:
    - Page text (main body)
    - Tables (converted to markdown)
    """

    def __init__(
        self,
        chunk_size: int = 1500,
        chunk_overlap: int = 200,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

        # Primary splitter: respects section/paragraph/sentence boundaries
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=[
                "\n\n\n",   # Section breaks
                "\n\n",     # Paragraph breaks
                "\n",       # Line breaks
                ". ",       # Sentence boundaries
                "; ",       # Clause boundaries
                ", ",       # Sub-clause
                " ",        # Word boundaries (last resort)
            ],
            length_function=len,
        )

        # Table splitter: larger chunks because tables need full context
        self.table_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size * 2,  # Tables get double the chunk size
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", " "],
        )

    def chunk_document(self, extraction_result: Dict[str, Any]) -> List[Chunk]:
        """
        Process the full extraction result into a list of chunks.

        Args:
            extraction_result: Output from PDFExtractor.extract()

        Returns:
            List of Chunk objects with content and metadata
        """
        all_chunks: List[Chunk] = []

        # 1. Chunk page text
        all_chunks.extend(self._chunk_pages(extraction_result.get("pages", [])))

        # 2. Chunk tables (kept larger for structural integrity)
        all_chunks.extend(self._chunk_tables(extraction_result.get("tables", [])))


        return all_chunks

    def _chunk_pages(self, pages: List[Dict]) -> List[Chunk]:
        """Split page text into chunks, preserving page number metadata."""
        chunks = []

        for page in pages:
            text = page.get("text", "").strip()
            if not text:
                continue

            page_number = page.get("page_number", 0)

            # Split the page text
            splits = self.text_splitter.split_text(text)

            for i, split_text in enumerate(splits):
                chunks.append(Chunk(
                    content=split_text,
                    metadata={
                        "page_number": page_number,
                        "source_type": "text",
                        "chunk_index": i,
                        "total_chunks_on_page": len(splits),
                    },
                ))

        return chunks

    def _chunk_tables(self, tables: List[Dict]) -> List[Chunk]:
        """
        Split tables into chunks.

        Tables are prefixed with a header so the LLM knows it's
        looking at structured tabular data, not prose.
        """
        chunks = []

        for table in tables:
            markdown = table.get("markdown", "").strip()
            if not markdown:
                continue

            page_number = table.get("page_number", 0)
            prefixed = f"[TABLE on Page {page_number}]\n{markdown}"

            # Use larger chunks for tables to preserve row/column context
            splits = self.table_splitter.split_text(prefixed)

            for i, split_text in enumerate(splits):
                chunks.append(Chunk(
                    content=split_text,
                    metadata={
                        "page_number": page_number,
                        "source_type": "table",
                        "chunk_index": i,
                    },
                ))

        return chunks


    def get_texts_and_metadatas(
        self, chunks: List[Chunk]
    ) -> tuple[List[str], List[Dict]]:
        """
        Convenience method: unpack chunks into parallel lists
        that FAISS/LangChain expect.

        Returns:
            (texts, metadatas) tuple
        """
        texts = [c.content for c in chunks]
        metadatas = [c.metadata for c in chunks]
        return texts, metadatas

    def get_stats(self, chunks: List[Chunk]) -> Dict[str, Any]:
        """Return chunking statistics for logging/debugging."""
        source_counts = {}
        for c in chunks:
            st = c.source_type
            source_counts[st] = source_counts.get(st, 0) + 1

        lengths = [len(c.content) for c in chunks]

        return {
            "total_chunks": len(chunks),
            "by_source_type": source_counts,
            "avg_chunk_length": sum(lengths) / len(lengths) if lengths else 0,
            "min_chunk_length": min(lengths) if lengths else 0,
            "max_chunk_length": max(lengths) if lengths else 0,
        }