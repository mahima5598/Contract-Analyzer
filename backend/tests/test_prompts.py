"""
Compliance prompt tests.

Run with: pytest backend/tests/test_prompts.py -v
"""
import pytest
from backend.app.prompts.compliance_prompts import (
    COMPLIANCE_QUESTIONS,
    build_compliance_prompt,
)


class TestComplianceQuestions:
    """Tests for the compliance question definitions."""

    def test_exactly_5_questions(self):
        """The assignment requires exactly 5 questions."""
        assert len(COMPLIANCE_QUESTIONS) == 5

    def test_all_questions_have_required_fields(self):
        """Each question must have title, question, and criteria."""
        for qid, qdata in COMPLIANCE_QUESTIONS.items():
            assert "title" in qdata, f"{qid} missing 'title'"
            assert "question" in qdata, f"{qid} missing 'question'"
            assert "criteria" in qdata, f"{qid} missing 'criteria'"
            assert len(qdata["criteria"]) > 0, f"{qid} has no criteria"

    def test_question_ids(self):
        """Questions should be Q1 through Q5."""
        expected = {"Q1", "Q2", "Q3", "Q4", "Q5"}
        assert set(COMPLIANCE_QUESTIONS.keys()) == expected

    def test_question_titles(self):
        """Verify all 5 question titles match the assignment."""
        titles = [q["title"] for q in COMPLIANCE_QUESTIONS.values()]
        assert "Password Management" in titles
        assert "IT Asset Management" in titles
        assert "Security Training & Background Checks" in titles
        assert "Data in Transit Encryption" in titles
        assert "Network Authentication & Authorization Protocols" in titles


class TestBuildCompliancePrompt:
    """Tests for the prompt builder."""

    def test_prompt_contains_question(self):
        """Built prompt should contain the compliance question."""
        qdata = COMPLIANCE_QUESTIONS["Q1"]
        prompt = build_compliance_prompt(qdata)
        # PromptTemplate stores partial variables, check the template
        assert "{context}" in prompt.template

    def test_prompt_is_langchain_template(self):
        """Should return a LangChain PromptTemplate."""
        from langchain_core.prompts import PromptTemplate
        qdata = COMPLIANCE_QUESTIONS["Q1"]
        prompt = build_compliance_prompt(qdata)
        assert isinstance(prompt, PromptTemplate)

    def test_prompt_has_json_instruction(self):
        """Prompt should instruct the LLM to return JSON."""
        qdata = COMPLIANCE_QUESTIONS["Q1"]
        prompt = build_compliance_prompt(qdata)
        assert "JSON" in prompt.template

    def test_prompt_enforces_three_states(self):
        """Prompt should list the three valid compliance states."""
        qdata = COMPLIANCE_QUESTIONS["Q1"]
        prompt = build_compliance_prompt(qdata)
        assert "Fully Compliant" in prompt.template
        assert "Partially Compliant" in prompt.template
        assert "Non-Compliant" in prompt.template