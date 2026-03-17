# Contract Compliance Analyzer

An AI-powered system that analyzes vendor contracts and determines compliance with cybersecurity requirements using Retrieval-Augmented Generation (RAG).

## Features

- Extracts text, tables, and images from contracts
- Performs semantic search using embeddings
- Evaluates compliance against security requirements
- Returns structured results with supporting quotes
- Interactive Streamlit UI

## Architecture

Frontend: Streamlit  
Backend: FastAPI  
Vector DB: FAISS  
LLM: OpenAI / Local LLM  

## Quickstart
1. Copy `.env.example` to `.env` and set keys.
2. Backend: `pip install -r backend/requirements.txt` then `uvicorn backend.app.main:app --reload`.
3. Frontend: `pip install -r frontend/requirements.txt` then `streamlit run frontend/streamlit_app/app.py`.

## Repo layout
See `docs/architecture.md` for design rationale and run instructions.

## Contributing
Open issues and PRs. Include tests for new features.

