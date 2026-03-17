# Contract Analyzer Architecture

## System Overview
- **Frontend**: Streamlit UI for contract upload and compliance results
- **Backend**: FastAPI server handling document processing and RAG pipeline
- **Vector Store**: FAISS for semantic search on contract embeddings
- **LLM**: OpenAI API (with local LLM fallback option)

## Data Flow
1. User uploads contract (PDF)
2. Backend extracts text/tables/images using pdfplumber/PyMuPDF
3. Text chunked and embedded using LangChain
4. Embeddings stored in FAISS vector DB
5. User query triggers semantic search + LLM evaluation
6. Results with supporting quotes returned to frontend

## Tech Stack Details
- Python 3.10+
- FastAPI: REST API framework
- Streamlit: Interactive frontend
- LangChain: LLM orchestration
- FAISS: Vector similarity search
- pdfplumber/PyMuPDF: PDF processing

PDF
 ├─ text extraction (pymupdf4llm)
 ├─ image extraction + OCR
 ├─ table extraction
 ↓
document builder
 ↓
embedding
 ↓
FAISS index
 ↓
retrieval
 ↓
LLM analysis