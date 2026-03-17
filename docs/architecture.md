# Architecture & Design Rationale

## System Architecture

```
┌─────────────────────┐     HTTP      ┌──────────────────────────────────────┐
│   Streamlit UI      │ ◄──────────►  │         FastAPI Backend              │
│   (Port 8501)       │               │         (Port 8000)                  │
│                     │               │                                      │
│  • PDF Upload       │               │  ┌──────────────────────────────┐    │
│  • Progress Status  │               │  │   PDF Extractor              │    │
│  • Results Table    │               │  │   • pdfplumber (text)        │    │
│  • Chat Interface   │               │  │   • camelot (tables)         │    │
│                     │               │  │   • pymupdf (images)         │    │
│                     │               │  │   • pytesseract (OCR)        │    │
│                     │               │  └──────────┬───────────────────┘    │
│                     │               │             ▼                        │
│                     │               │  ┌──────────────────────────────┐    │
│                     │               │  │   Chunker + Embeddings       │    │
│                     │               │  │   • RecursiveTextSplitter    │    │
│                     │               │  │   • OpenAI Embeddings        │    │
│                     │               │  └──────────┬───────────────────┘    │
│                     │               │             ▼                        │
│                     │               │  ┌──────────────────────────────┐    │
│                     │               │  │   FAISS Vector Store         │    │
│                     │               │  │   • Similarity search        │    │
│                     │               │  │   • Top-k retrieval          │    │
│                     │               │  └──────────┬───────────────────┘    │
│                     │               │             ▼                        │
│                     │               │  ┌──────────────────────────────┐    │
│                     │               │  │   LLM Compliance Evaluator   │    │
│                     │               │  │   • Per-question RAG chain   │    │
│                     │               │  │   • Structured JSON output   │    │
│                     │               │  │   • 5 compliance questions   │    │
│                     │               │  └──────────────────────────────┘    │
└─────────────────────┘               └──────────────────────────────────────┘
```

## Key Design Decisions

### 1. RAG over Direct Prompting
**Choice:** Retrieval-Augmented Generation  
**Why:** Contracts can be 50+ pages. Stuffing everything into a single prompt risks 
context window limits, increases cost, and reduces accuracy. RAG retrieves only the 
most relevant sections per question.  
**Tradeoff:** Adds indexing latency; retrieval quality depends on chunk size/overlap.

### 2. Per-Question Evaluation
**Choice:** Evaluate each of the 5 compliance questions independently  
**Why:** Each question has distinct criteria. Focused retrieval and prompting per 
question yields higher accuracy than a single mega-prompt.  
**Tradeoff:** 5x LLM calls instead of 1, but more accurate and debuggable.

### 3. FAISS over Cloud Vector DB
**Choice:** FAISS (local, in-memory)  
**Why:** No external dependencies, zero cost, fast for single-document analysis. 
A cloud vector DB (Pinecone, Weaviate) would be overkill for per-session indexing.  
**Tradeoff:** Not persistent across restarts; fine for a prototype.

### 4. Multi-Strategy PDF Extraction
**Choice:** pdfplumber → camelot → pymupdf → pytesseract  
**Why:** Contracts vary widely — some are digital-native, some scanned, some have 
complex tables. A layered approach handles all cases.  
**Tradeoff:** More dependencies, but better coverage.

### 5. GPT-4o as Default LLM
**Choice:** OpenAI GPT-4o  
**Why:** Best reasoning capability for compliance analysis. Strong JSON mode support.  
**Alternative:** Could swap for a local model via Ollama/vLLM if cost is a concern.

### 6. Streamlit for Frontend
**Choice:** Streamlit over React  
**Why:** Rapid prototyping, built-in components for file upload and data display, 
Python-native (same language as backend).  
**Tradeoff:** Less customizable than React, but faster to build for a prototype.

## Running the Application

### Docker (recommended):
```bash
cp .env.example .env     # Add your OpenAI API key
docker-compose up --build
# Frontend: http://localhost:8501
# Backend:  http://localhost:8000/docs
```

### Local:
```bash
cp .env.example .env
bash tools/run_local.sh
```