import os
import json
from datetime import datetime, timezone
from typing import List, Dict

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.chains import RetrievalQA                        # ← FIXED
from langchain_core.prompts import PromptTemplate
from langchain_text_splitters import RecursiveCharacterTextSplitter

from backend.app.models.schemas import (
    ComplianceResult, ComplianceReport, ComplianceState
)
from backend.app.prompts.compliance_prompts import (
    COMPLIANCE_QUESTIONS, build_compliance_prompt
)


class ComplianceAnalyzer:
    def __init__(self, model_name: str = "gemini-1.5-flash", temperature: float = 0.1):
        self.model_name = model_name
        self.llm = ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=os.getenv("GOOGLE_API_KEY"),
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
        chunks = self.text_splitter.split_text(full_text)
        self.vectorstore = FAISS.from_texts(chunks, self.embeddings)

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