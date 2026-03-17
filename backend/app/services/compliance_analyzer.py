import os
import json
from datetime import datetime, timezone
from typing import List, Dict

from langchain_groq import ChatGroq                              # ← CHANGED
from langchain_community.embeddings import HuggingFaceEmbeddings # ← stays local, no API key needed
from langchain_community.vectorstores import FAISS
from langchain_classic.chains.retrieval_qa.base import RetrievalQA
from langchain_core.prompts import PromptTemplate
from langchain_text_splitters import RecursiveCharacterTextSplitter

from backend.app.models.schemas import (
    ComplianceResult, ComplianceReport, ComplianceState
)
from backend.app.prompts.compliance_prompts import (
    COMPLIANCE_QUESTIONS, build_compliance_prompt
)


class ComplianceAnalyzer:
    def __init__(self, model_name: str = "llama-3.1-8b-instant", temperature: float = 0.1):
        self.model_name = model_name

        api_key = os.getenv("GROQ_API_KEY", "")
        if not api_key:
            raise ValueError("GROQ_API_KEY is not set")

        self.llm = ChatGroq(
            model=model_name,
            api_key=api_key,
            temperature=temperature,
        )
        self.embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2"
        )
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1500,
            chunk_overlap=200,
            separators=["\n\n", "\n", ". ", " "],
        )
        self.vectorstore = None

    def build_index(self, full_text: str) -> None:
    # Anchor section/exhibit headers so they stay attached to their content.
    # This prevents "Section 6.7" from being split into a separate chunk
    # away from the text it governs — so the LLM can always cite the source.
        anchored_text = self._anchor_section_headers(full_text)
        chunks = self.text_splitter.split_text(anchored_text)
        self.vectorstore = FAISS.from_texts(chunks, self.embeddings)

    def _anchor_section_headers(self, text: str) -> str:
        """
        Prevent section/exhibit headers from being separated from their content.
        
        Replaces the newline AFTER a header line with a space so the splitter
        keeps the header glued to the first sentence of the section.
        
        Matches patterns like:
        - "Section 6.7 Authentication..."
        - "6.7 Authentication..."  
        - "Exhibit G13"
        - "Exhibit A"
        - "SECTION 4 -"
        """
        import re
        # Glue "Section X.Y Heading\n" → "Section X.Y Heading: "
        # so it stays in the same chunk as its content
        text = re.sub(
            r'((?:Section|SECTION|Exhibit|EXHIBIT)\s[\d\w\.]+[^\n]*)\n',
            r'\1 — ',
            text
        )
        # Also glue bare numbered headers like "6.7 Title\n"
        text = re.sub(
            r'(\n\d+\.\d+[\s][^\n]{3,60})\n',
            r'\1 — ',
            text
        )
        return text

    def analyze_compliance(self, contract_name: str) -> ComplianceReport:
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

    def _evaluate_single_question(self, question_id: str, question_data: Dict) -> ComplianceResult:
        retriever = self.vectorstore.as_retriever(
            search_type="similarity", search_kwargs={"k": 8},
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
        return self._parse_llm_response(response["result"], question_data)

    def _parse_llm_response(self, response_text: str, question_data: Dict) -> ComplianceResult:
        try:
            clean_json = response_text.replace("```json", "").replace("```", "").strip()
            data = json.loads(clean_json)
            return ComplianceResult(
                compliance_question=question_data["title"],
                compliance_state=ComplianceState(data["compliance_state"]),
                confidence=float(data["confidence"]),
                relevant_quotes=data["relevant_quotes"],
                rationale=data["rationale"],
            )
        except Exception as e:
            return ComplianceResult(
                compliance_question=question_data["title"],
                compliance_state=ComplianceState.NON_COMPLIANT,
                confidence=0.0,
                relevant_quotes=[],
                rationale=f"Analysis engine error: {str(e)}",
            )

    def chat(self, query: str, chat_history: list = None) -> Dict:
        if not self.vectorstore:
            raise ValueError("Must call build_index() before chatting")

        retriever = self.vectorstore.as_retriever(search_kwargs={"k": 5})
        docs = retriever.invoke(query)
        context = "\n\n".join([doc.page_content for doc in docs])

        system_instruction = (
            "You are a contract analysis assistant. Answer questions based "
            "on the provided contract content. Always cite specific sections "
            "or quotes. If the information is not in the contract, say so clearly."
        )
        user_input = f"Contract context:\n{context}\n\nQuestion: {query}"
        response = self.llm.invoke(f"{system_instruction}\n\n{user_input}")

        return {
            "answer": response.content,
            "source_quotes": [doc.page_content[:200] for doc in docs[:3]],
        }