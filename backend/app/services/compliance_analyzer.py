"""
Compliance analysis service using RAG.

Architecture decision: We use a per-question approach rather than a single
mega-prompt because:
1. Each question has distinct criteria → better accuracy with focused context
2. We can retrieve the most relevant chunks per question from FAISS
3. Easier to debug and iterate on individual question prompts
4. Avoids context window exhaustion on long contracts
"""
from datetime import datetime, timezone
from typing import List, Dict
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.vectorstores import FAISS
from langchain_classic.chains import RetrievalQA
from langchain_core.prompts import PromptTemplate
from backend.app.models.schemas import (
    ComplianceResult, ComplianceReport, ComplianceState
)
from backend.app.prompts.compliance_prompts import (
    COMPLIANCE_QUESTIONS, build_compliance_prompt
)
import json


class ComplianceAnalyzer:
    def __init__(self, model_name: str = "gpt-4o", temperature: float = 0.1):
        self.model_name = model_name
        self.llm = ChatOpenAI(model=model_name, temperature=temperature)
        self.embeddings = OpenAIEmbeddings()
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1500,
            chunk_overlap=200,
            separators=["\n\n", "\n", ". ", " "],
        )
        self.vectorstore = None

    def build_index(self, full_text: str) -> None:
        """Chunk the document and build a FAISS vector index."""
        chunks = self.text_splitter.split_text(full_text)
        self.vectorstore = FAISS.from_texts(chunks, self.embeddings)

    def analyze_compliance(self, contract_name: str) -> ComplianceReport:
        """Run all 5 compliance questions against the indexed document."""
        if not self.vectorstore:
            raise ValueError("Must call build_index() before analysis")

        results: List[ComplianceResult] = []

        for question_id, question_data in COMPLIANCE_QUESTIONS.items():
            result = self._evaluate_single_question(question_id, question_data)
            results.append(result)

        return ComplianceReport(
            contract_name=contract_name,
            analysis_timestamp=datetime.now(timezone.utc).isoformat(),
            results=results,
            model_used=self.model_name,
        )

    def _evaluate_single_question(
        self, question_id: str, question_data: Dict
    ) -> ComplianceResult:
        """Evaluate a single compliance question using RAG retrieval."""
        # Retrieve top-k most relevant chunks for this specific question
        retriever = self.vectorstore.as_retriever(
            search_type="similarity",
            search_kwargs={"k": 8},
        )

        prompt = build_compliance_prompt(question_data)

        chain = RetrievalQA.from_chain_type(
            llm=self.llm,
            chain_type="stuff",
            retriever=retriever,
            return_source_documents=True,
            chain_type_kwargs={"prompt": prompt},
        )

        response = chain.invoke({"query": question_data["question"]})
        parsed = self._parse_llm_response(response["result"], question_data)

        return parsed

    def _parse_llm_response(
        self, response_text: str, question_data: Dict
    ) -> ComplianceResult:
        """Parse the structured JSON response from the LLM."""
        try:
            data = json.loads(response_text)
            return ComplianceResult(
                compliance_question=question_data["title"],
                compliance_state=ComplianceState(data["compliance_state"]),
                confidence=float(data["confidence"]),
                relevant_quotes=data["relevant_quotes"],
                rationale=data["rationale"],
            )
        except (json.JSONDecodeError, KeyError, ValueError):
            # Fallback: if LLM didn't return valid JSON, wrap the raw text
            return ComplianceResult(
                compliance_question=question_data["title"],
                compliance_state=ComplianceState.NON_COMPLIANT,
                confidence=0.0,
                relevant_quotes=[],
                rationale=f"Failed to parse LLM response: {response_text[:500]}",
            )

    def chat(self, query: str, chat_history: list = None) -> Dict:
        """Bonus: chat over the document content."""
        if not self.vectorstore:
            raise ValueError("Must call build_index() before chatting")

        retriever = self.vectorstore.as_retriever(search_kwargs={"k": 5})
        docs = retriever.invoke(query)
        context = "\n\n".join([doc.page_content for doc in docs])

        messages = [
            {"role": "system", "content": (
                "You are a contract analysis assistant. Answer questions based "
                "on the provided contract content. Always cite specific sections "
                "or quotes from the contract. If the information is not in the "
                "contract, say so clearly."
            )},
            {"role": "user", "content": (
                f"Contract context:\n{context}\n\n"
                f"Question: {query}"
            )},
        ]

        response = self.llm.invoke(messages)
        source_quotes = [doc.page_content[:200] for doc in docs[:3]]

        return {
            "answer": response.content,
            "source_quotes": source_quotes,
        }