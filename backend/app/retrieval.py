import os
import json
import math
from typing import List, Dict, Any, Tuple, Optional, Iterable

import numpy as np
from sentence_transformers import SentenceTransformer
import faiss

# Tune these defaults as needed
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
HNSW_M = 32
HNSW_EF_CONSTRUCTION = 200
BATCH_SIZE = 64


class FaissRetriever:
    """
    FAISS-only retriever using sentence-transformers embeddings and HNSW index.
    Documents must be dicts: {"id": str, "text": str, "metadata": {...}}
    """

    def __init__(self,
                 index_path: str = "indexes/faiss.index",
                 meta_path: str = "indexes/meta.json",
                 model_name: str = EMBEDDING_MODEL,
                 use_gpu: bool = False):
        self.index_path = index_path
        self.meta_path = meta_path
        self.model_name = model_name
        self.model = SentenceTransformer(self.model_name)
        self.index: Optional[faiss.Index] = None
        self.docs: List[Dict[str, Any]] = []
        self.ids: List[str] = []
        self.emb_dim: Optional[int] = None
        self.use_gpu = use_gpu

    # -------------------------
    # Index building / saving
    # -------------------------
    def build_index(self, docs: List[Dict[str, Any]], index_type: str = "hnsw"):
        """
        Build FAISS index from docs.
        - docs: list of {"id","text","metadata"}
        - index_type: 'hnsw' (default) or 'flat'
        """
        if not docs:
            raise ValueError("No documents provided to index.")

        self.docs = docs
        self.ids = [d["id"] for d in docs]
        texts = [d["text"] for d in docs]

        # Compute embeddings in batches
        embeddings = self._embed_batch(texts)

        # Normalize for cosine similarity
        faiss.normalize_L2(embeddings)
        self.emb_dim = embeddings.shape[1]

        # Create index
        if index_type == "hnsw":
            index = faiss.IndexHNSWFlat(self.emb_dim, HNSW_M)
            index.hnsw.efConstruction = HNSW_EF_CONSTRUCTION
        else:
            index = faiss.IndexFlatIP(self.emb_dim)

        # Add vectors
        index.add(embeddings)
        self.index = index

    def _embed_batch(self, texts: Iterable[str]) -> np.ndarray:
        """
        Embed texts in batches and return a numpy array (float32).
        """
        embs = []
        batch = []
        for t in texts:
            batch.append(t)
            if len(batch) >= BATCH_SIZE:
                e = self.model.encode(batch, convert_to_numpy=True, show_progress_bar=False)
                embs.append(e)
                batch = []
        if batch:
            e = self.model.encode(batch, convert_to_numpy=True, show_progress_bar=False)
            embs.append(e)
        if embs:
            return np.vstack(embs).astype("float32")
        return np.zeros((0, self.model.get_sentence_embedding_dimension()), dtype="float32")

    def save(self, index_dir: str = "indexes"):
        """
        Persist FAISS index and metadata to disk.
        """
        os.makedirs(index_dir, exist_ok=True)
        if self.index is None:
            raise RuntimeError("Index not built; nothing to save.")

        faiss.write_index(self.index, self.index_path)
        with open(self.meta_path, "w", encoding="utf-8") as f:
            json.dump(self.docs, f, ensure_ascii=False, indent=2)

    def load(self, index_dir: str = "indexes"):
        """
        Load FAISS index and metadata from disk.
        """
        if not os.path.exists(self.index_path) or not os.path.exists(self.meta_path):
            raise FileNotFoundError("Index or metadata not found on disk.")
        self.index = faiss.read_index(self.index_path)
        with open(self.meta_path, "r", encoding="utf-8") as f:
            self.docs = json.load(f)
        self.ids = [d["id"] for d in self.docs]
        # set emb_dim if possible
        if self.index is not None:
            self.emb_dim = self.index.d
        return self

    # -------------------------
    # Querying
    # -------------------------
    def query(self, query_text: str, top_k: int = 5, ef_search: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Query the FAISS index and return top_k results with metadata and scores.
        Returns list of {"id","score","metadata","text"} ordered by score desc.
        """
        if self.index is None:
            raise RuntimeError("Index not loaded or built.")

        q_emb = self.model.encode([query_text], convert_to_numpy=True).astype("float32")
        faiss.normalize_L2(q_emb)

        # If HNSW, tune efSearch for recall/latency tradeoff
        try:
            if ef_search is not None and isinstance(self.index, faiss.IndexHNSWFlat):
                self.index.hnsw.efSearch = ef_search
        except Exception:
            pass

        D, I = self.index.search(q_emb, top_k)
        results = []
        for score, idx in zip(D[0], I[0]):
            if idx < 0 or idx >= len(self.docs):
                continue
            doc = self.docs[idx]
            results.append({
                "id": doc.get("id"),
                "score": float(score),
                "metadata": doc.get("metadata", {}),
                "text": doc.get("text", "")
            })
        return results

    # -------------------------
    # Utilities
    # -------------------------
    def add_documents(self, docs: List[Dict[str, Any]]):
        """
        Add documents to an existing index (incremental indexing).
        Note: FAISS IndexFlat/HNSW supports add(); ensure embeddings computed with same model.
        """
        if not docs:
            return
        if self.index is None:
            # build fresh
            self.build_index(docs)
            return

        texts = [d["text"] for d in docs]
        embs = self._embed_batch(texts)
        faiss.normalize_L2(embs)
        self.index.add(embs)
        # append docs to metadata
        self.docs.extend(docs)
        self.ids.extend([d["id"] for d in docs])

    def info(self) -> Dict[str, Any]:
        """
        Return index stats for monitoring.
        """
        return {
            "num_docs": len(self.docs),
            "index_path": self.index_path,
            "meta_path": self.meta_path,
            "emb_dim": self.emb_dim,
            "index_type": type(self.index).__name__ if self.index is not None else None
        }
