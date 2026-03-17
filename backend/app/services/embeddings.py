"""
Embedding and vector store service.

Design decisions:
─────────────────
1. OpenAI text-embedding-3-small is used by default:
   - 1536 dimensions, strong semantic quality
   - Much cheaper than text-embedding-3-large
   - Can swap to a local model (e.g. sentence-transformers) via config

2. FAISS is chosen over cloud vector DBs (Pinecone, Weaviate) because:
   - Zero external dependency / cost
   - We index ONE document at a time, not millions
   - In-memory speed is more than sufficient
   - No network latency for retrieval

3. Metadata is preserved in the FAISS docstore so we can trace
   retrieved chunks back to their page numbers and source types.

4. The retriever supports both similarity search and MMR (Maximal
   Marginal Relevance) to reduce redundant chunk retrieval.
"""
from typing import List, Dict, Any, Optional
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain import Document
from backend.app.services.chunker import Chunk, DocumentChunker
from backend.app.config import settings


class EmbeddingService:
    """Manages document embedding and FAISS vector store."""

    def __init__(
        self,
        model_name: Optional[str] = None,
    ):
        self.model_name = model_name or settings.embedding_model
        self.embeddings = OpenAIEmbeddings(model=self.model_name)
        self.vectorstore: Optional[FAISS] = None
        self.chunker = DocumentChunker(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
        )

    def index_document(self, extraction_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Full pipeline: chunk the extracted document → embed → build FAISS index.

        Args:
            extraction_result: Output from PDFExtractor.extract()

        Returns:
            Chunking/indexing statistics
        """
        # Step 1: Chunk the document
        chunks = self.chunker.chunk_document(extraction_result)

        if not chunks:
            raise ValueError("No content could be chunked from the document")

        # Step 2: Convert to LangChain Documents (preserves metadata)
        documents = [
            Document(
                page_content=chunk.content,
                metadata=chunk.metadata,
            )
            for chunk in chunks
        ]

        # Step 3: Build FAISS index from documents
        self.vectorstore = FAISS.from_documents(documents, self.embeddings)

        # Return stats for logging / UI
        return self.chunker.get_stats(chunks)

    def get_retriever(
        self,
        search_type: str = "similarity",
        k: int = None,
        fetch_k: int = 20,
        lambda_mult: float = 0.7,
    ):
        """
        Get a LangChain retriever from the vector store.

        Args:
            search_type: "similarity" or "mmr"
                - similarity: pure cosine similarity, best for focused questions
                - mmr: Maximal Marginal Relevance, reduces redundancy in results
            k: Number of chunks to retrieve (default from settings)
            fetch_k: Number of candidates to consider for MMR
            lambda_mult: MMR diversity parameter (0=max diversity, 1=max relevance)

        Returns:
            LangChain retriever object
        """
        if not self.vectorstore:
            raise ValueError("No index built. Call index_document() first.")

        k = k or settings.retrieval_k

        if search_type == "mmr":
            return self.vectorstore.as_retriever(
                search_type="mmr",
                search_kwargs={
                    "k": k,
                    "fetch_k": fetch_k,
                    "lambda_mult": lambda_mult,
                },
            )
        else:
            return self.vectorstore.as_retriever(
                search_type="similarity",
                search_kwargs={"k": k},
            )

    def similarity_search(
        self,
        query: str,
        k: int = None,
    ) -> List[Dict[str, Any]]:
        """
        Direct similarity search — useful for chat and debugging.

        Returns:
            List of dicts with 'content', 'metadata', and 'score' keys
        """
        if not self.vectorstore:
            raise ValueError("No index built. Call index_document() first.")

        k = k or settings.retrieval_k

        results = self.vectorstore.similarity_search_with_score(query, k=k)

        return [
            {
                "content": doc.page_content,
                "metadata": doc.metadata,
                "score": float(score),  # Lower = more similar in FAISS L2
            }
            for doc, score in results
        ]

    def get_relevant_context(
        self,
        query: str,
        k: int = None,
        include_metadata: bool = True,
    ) -> str:
        """
        Retrieve relevant chunks and format them as a single context string.

        This is useful for passing directly into a prompt template.
        """
        results = self.similarity_search(query, k=k)

        parts = []
        for r in results:
            if include_metadata:
                source = r["metadata"].get("source_type", "text")
                page = r["metadata"].get("page_number", "?")
                header = f"[Source: {source}, Page {page}]"
                parts.append(f"{header}\n{r['content']}")
            else:
                parts.append(r["content"])

        return "\n\n---\n\n".join(parts)

    @property
    def is_indexed(self) -> bool:
        """Check if a document has been indexed."""
        return self.vectorstore is not None