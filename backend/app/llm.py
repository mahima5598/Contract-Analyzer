# backend/app/llm.py
import os
import json
import time
from typing import List, Dict, Any, Tuple
import requests
from jsonschema import validate, ValidationError

SCHEMA_PATH = "tools/validators/json_schema.json"
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")

# Basic LLM call wrapper (abstracted). Extend for your provider.
def call_llm(prompt: str, max_tokens: int = 512, temperature: float = 0.0) -> str:
    """
    Minimal wrapper that calls an LLM provider.
    This implementation expects OpenAI-compatible REST API; adapt if using another provider.
    """
    if not LLM_API_KEY:
        raise RuntimeError("LLM_API_KEY not set in environment")

    if LLM_PROVIDER.lower() == "openai":
        url = "https://api.openai.com/v1/chat/completions"
        headers = {"Authorization": f"Bearer {LLM_API_KEY}", "Content-Type": "application/json"}
        payload = {
            "model": os.getenv("LLM_MODEL", "gpt-4o-mini"),
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        # adapt to provider response shape
        return data["choices"][0]["message"]["content"]
    else:
        raise NotImplementedError("LLM provider wrapper not implemented for: " + LLM_PROVIDER)


def _load_schema(path: str = SCHEMA_PATH) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _validate_json(candidate: Dict[str, Any], schema: Dict[str, Any]) -> Tuple[bool, str]:
    try:
        validate(instance=candidate, schema=schema)
        return True, ""
    except ValidationError as e:
        return False, str(e)


def _assemble_prompt(question: str, retrieved_docs: List[Dict[str, Any]], max_context_chars: int = 4000) -> str:
    """
    Build a prompt that includes:
      - short instructions and required output schema
      - top retrieved docs with provenance (id, metadata, snippet)
      - the user question
    """
    schema = _load_schema()
    schema_text = json.dumps(schema, indent=2)

    header = (
        "You are a compliance assistant. Answer the question using ONLY the provided evidence.\n"
        "Return a JSON object that conforms exactly to the provided JSON schema. Do not add extra fields.\n"
        "If you cannot determine an answer from the evidence, state Non-Compliant or Partially Compliant as appropriate and explain.\n\n"
    )

    evidence_parts = []
    total = 0
    for d in retrieved_docs:
        snippet = d.get("text", "")
        if not snippet:
            continue
        part = f"---\nID: {d.get('id')}\nMetadata: {json.dumps(d.get('metadata', {}))}\nText:\n{snippet}\n"
        total += len(part)
        if total > max_context_chars:
            break
        evidence_parts.append(part)

    evidence = "\n".join(evidence_parts) if evidence_parts else "No evidence provided."

    prompt = (
        f"{header}"
        f"JSON Schema:\n{schema_text}\n\n"
        f"Evidence (top results):\n{evidence}\n\n"
        f"Question: {question}\n\n"
        "Produce the JSON output now."
    )
    return prompt


def verify_provenance(result: Dict[str, Any], retrieved_docs: List[Dict[str, Any]]) -> List[str]:
    """
    Ensure each 'Relevant Quotes' entry appears in one of the retrieved docs' text.
    Returns list of provenance issues (empty if none).
    """
    issues = []
    texts = [d.get("text", "") for d in retrieved_docs]
    for q in result.get("Relevant Quotes", []):
        found = any(q.strip() in t for t in texts)
        if not found:
            issues.append(f"Quote not found in retrieved docs: {q[:120]}")
    return issues


def analyze_question(question: str, retrieved_docs: List[Dict[str, Any]], max_retries: int = 2) -> Dict[str, Any]:
    """
    Main orchestration:
      - assemble prompt
      - call LLM
      - validate JSON against schema
      - if invalid, attempt repair up to max_retries
      - verify provenance and attach provenance_issues if any
    Returns a dict with keys: result (the validated JSON or last attempt), validation_log, provenance_issues
    """
    schema = _load_schema()
    prompt = _assemble_prompt(question, retrieved_docs)
    validation_log = []
    last_candidate = None

    for attempt in range(0, max_retries + 1):
        try:
            raw = call_llm(prompt, max_tokens=1024, temperature=0.0)
        except Exception as e:
            validation_log.append({"attempt": attempt, "error": f"LLM call failed: {str(e)}"})
            break

        # Try to parse JSON from model output
        candidate = None
        try:
            # Some models return code fences; try to extract JSON
            text = raw.strip()
            if text.startswith("```"):
                # strip code fence
                text = "\n".join(text.splitlines()[1:-1])
            candidate = json.loads(text)
            last_candidate = candidate
        except Exception as e:
            validation_log.append({"attempt": attempt, "parse_error": str(e), "raw_output": raw})
            # prepare a repair prompt
            if attempt < max_retries:
                prompt = (
                    "The previous response could not be parsed as JSON or did not conform to the schema.\n"
                    "Please return a valid JSON object that conforms exactly to the schema provided earlier. "
                    "Do not include any explanatory text. Here is the previous output:\n\n"
                    f"{raw}\n\n"
                    "Return only the corrected JSON."
                )
                continue
            else:
                break

        # Validate candidate against schema
        ok, err = _validate_json(candidate, schema)
        if ok:
            # provenance check
            provenance_issues = verify_provenance(candidate, retrieved_docs)
            return {
                "result": candidate,
                "validation_log": validation_log,
                "provenance_issues": provenance_issues
            }
        else:
            validation_log.append({"attempt": attempt, "validation_error": err, "candidate": candidate})
            if attempt < max_retries:
                # ask model to repair using the failing validation message
                prompt = (
                    "The previous JSON did not validate against the schema. Validation error:\n"
                    f"{err}\n\n"
                    "Please return a corrected JSON object that conforms exactly to the schema. "
                    "Do not include any extra fields or explanatory text. Here is the previous JSON:\n\n"
                    f"{json.dumps(candidate, indent=2)}\n\n"
                    "Return only the corrected JSON."
                )
                continue
            else:
                break

    # If we reach here, return last candidate (if any) with logs and a note
    provenance_issues = verify_provenance(last_candidate or {}, retrieved_docs) if last_candidate else ["No candidate produced"]
    return {
        "result": last_candidate,
        "validation_log": validation_log,
        "provenance_issues": provenance_issues
    }
