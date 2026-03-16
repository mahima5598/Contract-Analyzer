# tools/reindex.py
"""
Rebuild FAISS index from saved docs JSON (indexes/docs.json).
Usage: python tools/reindex.py
"""
import os
import json
from backend.app.retrieval import FaissRetriever
from backend.app.indexer import load_docs_json

INDEX_DIR = "indexes"
DOCS_STORE = os.path.join(INDEX_DIR, "docs.json")

def main():
    if not os.path.exists(DOCS_STORE):
        print("Docs store not found at", DOCS_STORE)
        return
    docs = load_docs_json(DOCS_STORE)
    retriever = FaissRetriever(index_path=os.path.join(INDEX_DIR, "faiss.index"),
                               meta_path=os.path.join(INDEX_DIR, "meta.json"))
    print(f"Building index for {len(docs)} docs...")
    retriever.build_index(docs, index_type="hnsw")
    retriever.save(index_dir=INDEX_DIR)
    print("Index rebuilt and saved to", INDEX_DIR)

if __name__ == "__main__":
    main()
