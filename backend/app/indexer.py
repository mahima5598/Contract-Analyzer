# backend/app/indexer.py
import hashlib
import json
import os
from typing import List, Dict, Any, Iterable, Optional

# Try to use tiktoken for token-aware chunking; fallback to char-based chunking
try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except Exception:
    TIKTOKEN_AVAILABLE = False

# Default chunking parameters tuned for semantic retrieval + LLM context
DEFAULT_TOKEN_CHUNK_SIZE = 500
DEFAULT_TOKEN_OVERLAP = 80
DEFAULT_CHAR_CHUNK_SIZE = 1200
DEFAULT_CHAR_OVERLAP = 200


def _make_id(prefix: str, text: str) -> str:
    """Stable short id for a chunk based on prefix and text hash."""
    h = hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}_{h}"


# -------------------------
# Chunking utilities
# -------------------------
def _tokenize(text: str, model_name: str = "gpt2"):
    """Return token ids using tiktoken if available, else None."""
    if not TIKTOKEN_AVAILABLE:
        return None
    enc = tiktoken.get_encoding(model_name)
    return enc.encode(text)


def chunk_text_token_aware(text: str,
                           chunk_size: int = DEFAULT_TOKEN_CHUNK_SIZE,
                           overlap: int = DEFAULT_TOKEN_OVERLAP,
                           model_name: str = "gpt2") -> List[str]:
    """
    Token-aware chunking using tiktoken. Returns list of text chunks.
    If tiktoken is not available, raises RuntimeError.
    """
    if not TIKTOKEN_AVAILABLE:
        raise RuntimeError("tiktoken not available for token-aware chunking.")
    enc = tiktoken.get_encoding(model_name)
    token_ids = enc.encode(text)
    chunks = []
    start = 0
    total = len(token_ids)
    while start < total:
        end = min(start + chunk_size, total)
        chunk_tokens = token_ids[start:end]
        chunk_text = enc.decode(chunk_tokens).strip()
        if chunk_text:
            chunks.append(chunk_text)
        if end == total:
            break
        start = end - overlap
    return chunks


def chunk_text_char_based(text: str,
                          chunk_size: int = DEFAULT_CHAR_CHUNK_SIZE,
                          overlap: int = DEFAULT_CHAR_OVERLAP) -> List[str]:
    """Fallback character-based chunking with overlap."""
    if not text:
        return []
    chunks = []
    start = 0
    length = len(text)
    while start < length:
        end = min(start + chunk_size, length)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end == length:
            break
        start = max(0, end - overlap)
    return chunks


def chunk_text(text: str,
               use_token_chunking: bool = True,
               token_chunk_size: int = DEFAULT_TOKEN_CHUNK_SIZE,
               token_overlap: int = DEFAULT_TOKEN_OVERLAP,
               char_chunk_size: int = DEFAULT_CHAR_CHUNK_SIZE,
               char_overlap: int = DEFAULT_CHAR_OVERLAP,
               model_name: str = "gpt2") -> List[str]:
    """
    Unified chunker: prefer token-aware chunking when available and requested,
    otherwise fall back to character-based chunking.
    """
    if use_token_chunking and TIKTOKEN_AVAILABLE:
        try:
            return chunk_text_token_aware(text, token_chunk_size, token_overlap, model_name)
        except Exception:
            # fallback to char-based if token chunking fails
            return chunk_text_char_based(text, char_chunk_size, char_overlap)
    else:
        return chunk_text_char_based(text, char_chunk_size, char_overlap)


# -------------------------
# Document builders
# -------------------------
def docs_from_pages(pages: List[Dict[str, Any]],
                    source_filename: str = None,
                    use_token_chunking: bool = True) -> List[Dict[str, Any]]:
    """
    Convert page-level text into retrieval documents (chunked).
    Each doc: {"id": str, "text": str, "metadata": {...}}
    Metadata includes: type, page, chunk_index, source_filename
    """
    docs = []
    for p in pages:
        page_num = p.get("page")
        text = p.get("text", "") or ""
        chunks = chunk_text(text, use_token_chunking=use_token_chunking)
        for i, c in enumerate(chunks, start=1):
            prefix = f"page{page_num}_chunk{i}"
            doc_id = _make_id(prefix, c[:200])
            metadata = {
                "type": "page_chunk",
                "page": page_num,
                "chunk_index": i
            }
            if source_filename:
                metadata["source"] = source_filename
            docs.append({
                "id": doc_id,
                "text": c,
                "metadata": metadata
            })
    return docs


def docs_from_tables(tables: List[Dict[str, Any]],
                     source_filename: str = None,
                     rows_per_chunk: int = 20) -> List[Dict[str, Any]]:
    """
    Convert table artifacts into row-based chunks for retrieval.
    Each table dict expected to have 'table_id', 'page', 'text' (plain text rendering) and optionally 'csv'.
    Metadata includes: type, table_id, page, row_start, row_count, source
    """
    docs = []
    for t in tables:
        table_id = t.get("table_id")
        page = t.get("page")
        text = t.get("text", "") or ""
        rows = [r for r in text.splitlines() if r.strip()]
        if not rows:
            continue
        for i in range(0, len(rows), rows_per_chunk):
            chunk_rows = rows[i:i + rows_per_chunk]
            chunk_text = "\n".join(chunk_rows)
            prefix = f"{table_id}_r{i//rows_per_chunk+1}"
            doc_id = _make_id(prefix, chunk_text[:200])
            metadata = {
                "type": "table_chunk",
                "table_id": table_id,
                "page": page,
                "row_start": i + 1,
                "row_count": len(chunk_rows)
            }
            if source_filename:
                metadata["source"] = source_filename
            docs.append({
                "id": doc_id,
                "text": chunk_text,
                "metadata": metadata
            })
    return docs


def docs_from_images(images: List[Dict[str, Any]],
                     source_filename: str = None) -> List[Dict[str, Any]]:
    """
    Convert image OCR text into documents.
    Each image dict expected to have 'image_id', 'page', 'ocr_text', 'path'
    Metadata includes: type, image_id, page, path, source
    """
    docs = []
    for img in images:
        img_id = img.get("image_id")
        page = img.get("page")
        ocr = img.get("ocr_text", "") or ""
        # If OCR empty, include a placeholder referencing the image path so it can be retrieved by metadata
        if not ocr:
            text = f"[image: {img.get('path')}]"
        else:
            text = ocr
        prefix = f"img_{img_id}"
        doc_id = _make_id(prefix, text[:200])
        metadata = {
            "type": "image_ocr",
            "image_id": img_id,
            "page": page,
            "path": img.get("path")
        }
        if source_filename:
            metadata["source"] = source_filename
        docs.append({
            "id": doc_id,
            "text": text,
            "metadata": metadata
        })
    return docs


def build_documents(ingest_result: Dict[str, Any],
                    source_filename: Optional[str] = None,
                    use_token_chunking: bool = True) -> List[Dict[str, Any]]:
    """
    Given the output of extract_all (pages, tables, images), produce a flat list of docs for indexing.
    """
    pages = ingest_result.get("pages", [])
    tables = ingest_result.get("tables", [])
    images = ingest_result.get("images", [])

    docs = []
    docs.extend(docs_from_pages(pages, source_filename=source_filename, use_token_chunking=use_token_chunking))
    docs.extend(docs_from_tables(tables, source_filename=source_filename))
    docs.extend(docs_from_images(images, source_filename=source_filename))
    return docs


# -------------------------
# Persistence helpers
# -------------------------
def save_docs_json(docs: List[Dict[str, Any]], path: str):
    """Save docs metadata/text to a JSONL or JSON file for later reindexing."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    # Save as JSON array for simplicity
    with open(path, "w", encoding="utf-8") as f:
        json.dump(docs, f, ensure_ascii=False, indent=2)


def load_docs_json(path: str) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
