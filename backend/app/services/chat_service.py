"""
Chat service for conversational Q&A over contract documents.

This is the BONUS feature from the assignment. It lets users ask
free-form questions about the uploaded contract.

Design decisions:
─────────────────
1. Conversational memory: We pass chat history into the prompt so the
   LLM can handle follow-up questions like "What about section 5?"
   without the user re-stating the full context.

2. Context-aware retrieval: The user's question is combined with
   recent chat context to improve retrieval relevance. For example,
   if the user previously asked about "encryption" and now asks
   "what version?", the retriever searches for both terms.

3. Source attribution: Every answer includes the source chunks so
   the user can verify claims against the actual contract text.

4. Guardrails: The system prompt restricts the LLM to only answer
   based on the contract content, preventing hallucination.
"""
from typing import List, Dict, Optional
from langchain_openai import ChatOpenAI
from langchain import HumanMessage, SystemMessage, AIMessage
from backend.app.services.embeddings import EmbeddingService
from backend.app.config import settings


CHAT_SYSTEM_PROMPT = """You are a contract analysis assistant. Your role is to answer 
questions about the uploaded vendor contract based ONLY on the provided contract content.

Rules:
1. ONLY answer based on the contract content provided in the context.
2. If the information is not in the contract, clearly state: "This information is not 
   found in the provided contract."
3. Always cite specific sections, clauses, or page numbers when possible.
4. Use direct quotes from the contract to support your answers.
5. If a question is ambiguous, ask for clarification.
6. Be precise and professional — this is a legal/compliance context.
"""


class ChatService:
    """Handles conversational Q&A over an indexed contract document."""

    def __init__(
        self,
        embedding_service: EmbeddingService,
        model_name: Optional[str] = None,
        temperature: float = 0.2,
        max_history_turns: int = 10,
    ):
        self.embedding_service = embedding_service
        self.model_name = model_name or settings.model_name
        self.llm = ChatOpenAI(
            model=self.model_name,
            temperature=temperature,
        )
        self.max_history_turns = max_history_turns

    def chat(
        self,
        user_message: str,
        chat_history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict:
        """
        Process a user message and return an answer grounded in the contract.

        Args:
            user_message: The user's question
            chat_history: List of {"role": "user"|"assistant", "content": "..."}

        Returns:
            Dict with 'answer', 'source_quotes', and 'source_pages'
        """
        if not self.embedding_service.is_indexed:
            raise ValueError("No document has been indexed yet.")

        chat_history = chat_history or []

        # Step 1: Enhance the retrieval query with conversation context
        retrieval_query = self._build_retrieval_query(user_message, chat_history)

        # Step 2: Retrieve relevant chunks from the vector store
        search_results = self.embedding_service.similarity_search(
            retrieval_query, k=6
        )

        # Step 3: Format the context for the LLM
        context = self._format_context(search_results)

        # Step 4: Build the full message list with history
        messages = self._build_messages(user_message, context, chat_history)

        # Step 5: Get LLM response
        response = self.llm.invoke(messages)

        # Step 6: Extract source information
        source_quotes = [r["content"][:300] for r in search_results[:3]]
        source_pages = list(set(
            r["metadata"].get("page_number", 0)
            for r in search_results
            if r["metadata"].get("page_number")
        ))
        source_pages.sort()

        return {
            "answer": response.content,
            "source_quotes": source_quotes,
            "source_pages": source_pages,
        }

    def _build_retrieval_query(
        self,
        user_message: str,
        chat_history: List[Dict[str, str]],
    ) -> str:
        """
        Combine the current question with recent history to improve retrieval.

        Example:
            History: "Tell me about encryption requirements"
            Current: "What specific versions are mentioned?"
            Enhanced: "What specific versions are mentioned regarding encryption requirements"

        For simple questions with no ambiguity, we just use the question as-is.
        """
        if not chat_history:
            return user_message

        # Take the last few user messages for context
        recent_user_msgs = [
            m["content"]
            for m in chat_history[-4:]
            if m["role"] == "user"
        ]

        # If the current question seems like a follow-up (short, uses pronouns)
        follow_up_indicators = [
            "it", "that", "this", "those", "they", "them",
            "what about", "how about", "and ", "also",
            "more", "else", "other",
        ]

        is_follow_up = (
            len(user_message.split()) < 8
            or any(user_message.lower().startswith(ind) for ind in follow_up_indicators)
        )

        if is_follow_up and recent_user_msgs:
            # Combine with previous context for better retrieval
            context_snippet = recent_user_msgs[-1]
            return f"{user_message} (context: {context_snippet})"

        return user_message

    def _format_context(self, search_results: List[Dict]) -> str:
        """Format retrieved chunks into a context block for the prompt."""
        parts = []
        for i, result in enumerate(search_results, 1):
            page = result["metadata"].get("page_number", "?")
            source = result["metadata"].get("source_type", "text")
            parts.append(
                f"[Reference {i} — Page {page}, Source: {source}]\n"
                f"{result['content']}"
            )
        return "\n\n---\n\n".join(parts)

    def _build_messages(
        self,
        user_message: str,
        context: str,
        chat_history: List[Dict[str, str]],
    ) -> list:
        """
        Build the full message list for the LLM.

        Structure:
          1. System prompt (role + rules)
          2. Truncated chat history (last N turns)
          3. Current user question with retrieved context
        """
        messages = [SystemMessage(content=CHAT_SYSTEM_PROMPT)]

        # Add truncated history
        recent_history = chat_history[-(self.max_history_turns * 2):]
        for msg in recent_history:
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                messages.append(AIMessage(content=msg["content"]))

        # Add the current question with retrieved context
        user_prompt = (
            f"Based on the following contract content, answer my question.\n\n"
            f"CONTRACT CONTENT:\n{context}\n\n"
            f"QUESTION: {user_message}"
        )
        messages.append(HumanMessage(content=user_prompt))

        return messages