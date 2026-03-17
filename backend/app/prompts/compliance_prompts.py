"""
Compliance question definitions and prompt templates.

Design decision: We define each question with its specific sub-criteria
so the LLM knows exactly what to look for. The prompt enforces JSON output
with the exact schema required by the assignment.
"""
from langchain_core.prompts import PromptTemplate

COMPLIANCE_QUESTIONS = {
    "Q1": {
        "title": "Password Management",
        "question": (
            "The contract must require a documented password standard covering "
            "password length/strength, prohibition of default and known-compromised "
            "passwords, secure storage (no plaintext; salted hashing if stored), "
            "brute-force protections (lockout/rate limiting), prohibition on password "
            "sharing, vaulting of privileged credentials/recovery codes, and time-based "
            "rotation for break-glass credentials. Based on the contract language and "
            "exhibits, what is the compliance state for Password Management?"
        ),
        "criteria": [
            "Password length/strength requirements",
            "Prohibition of default and known-compromised passwords",
            "Secure storage (no plaintext; salted hashing)",
            "Brute-force protections (lockout/rate limiting)",
            "Prohibition on password sharing",
            "Vaulting of privileged credentials/recovery codes",
            "Time-based rotation for break-glass credentials",
        ],
    },
    "Q2": {
        "title": "IT Asset Management",
        "question": (
            "The contract must require an in-scope asset inventory (including cloud "
            "accounts/subscriptions, workloads, databases, security tooling), define "
            "minimum inventory fields, require at least quarterly reconciliation/review, "
            "and require secure configuration baselines with drift remediation and "
            "prohibition of insecure defaults. Based on the contract language and "
            "exhibits, what is the compliance state for IT Asset Management?"
        ),
        "criteria": [
            "In-scope asset inventory (cloud accounts, workloads, databases, security tooling)",
            "Minimum inventory fields defined",
            "Quarterly reconciliation/review",
            "Secure configuration baselines",
            "Drift remediation",
            "Prohibition of insecure defaults",
        ],
    },
    "Q3": {
        "title": "Security Training & Background Checks",
        "question": (
            "The contract must require security awareness training on hire and at "
            "least annually, and background screening for personnel with access to "
            "Company Data to the extent permitted by law, including maintaining a "
            "screening policy and attestation/evidence. Based on the contract language "
            "and exhibits, what is the compliance state for Security Training and "
            "Background Checks?"
        ),
        "criteria": [
            "Security awareness training on hire",
            "Annual security training",
            "Background screening for personnel with data access",
            "Screening policy maintained",
            "Attestation/evidence of compliance",
        ],
    },
    "Q4": {
        "title": "Data in Transit Encryption",
        "question": (
            "The contract must require encryption of Company Data in transit using "
            "TLS 1.2+ (preferably TLS 1.3 where feasible) for Company-to-Service "
            "traffic, administrative access pathways, and applicable "
            "Service-to-Subprocessor transfers, with certificate management and "
            "avoidance of insecure cipher suites. Based on the contract language and "
            "exhibits, what is the compliance state for Data in Transit Encryption?"
        ),
        "criteria": [
            "TLS 1.2+ required (TLS 1.3 preferred)",
            "Company-to-Service traffic encrypted",
            "Administrative access pathways encrypted",
            "Service-to-Subprocessor transfers encrypted",
            "Certificate management",
            "Avoidance of insecure cipher suites",
        ],
    },
    "Q5": {
        "title": "Network Authentication & Authorization Protocols",
        "question": (
            "The contract must specify the authentication mechanisms (e.g., SAML SSO "
            "for users, OAuth/token-based for APIs), require MFA for "
            "privileged/production access, require secure admin pathways "
            "(bastion/secure gateway) with session logging, and require RBAC "
            "authorization. Based on the contract language and exhibits, what is the "
            "compliance state for Network Authentication and Authorization Protocols?"
        ),
        "criteria": [
            "Authentication mechanisms specified (SAML SSO, OAuth, etc.)",
            "MFA for privileged/production access",
            "Secure admin pathways (bastion/secure gateway)",
            "Session logging",
            "RBAC authorization",
        ],
    },
}

COMPLIANCE_PROMPT_TEMPLATE = """You are a cybersecurity contract compliance analyst. 
Your task is to evaluate a vendor contract against a specific compliance requirement.

COMPLIANCE REQUIREMENT:
{question}

SPECIFIC CRITERIA TO EVALUATE:
{criteria}

RELEVANT CONTRACT CONTENT:
{context}

INSTRUCTIONS:
1. Carefully review the contract content against EACH specific criterion listed above.
2. Determine the compliance state:
   - "Fully Compliant": ALL criteria are explicitly addressed in the contract
   - "Partially Compliant": SOME but not all criteria are addressed
   - "Non-Compliant": NONE or almost none of the criteria are addressed
3. Provide your confidence as a percentage (0-100).
4. Extract EXACT quotes from the contract that support your assessment.
5. Explain your rationale, specifically noting which criteria are met and which are missing.

You MUST respond with ONLY valid JSON in this exact format:
{{
    "compliance_state": "Fully Compliant" | "Partially Compliant" | "Non-Compliant",
    "confidence": <number 0-100>,
    "relevant_quotes": ["<exact quote 1>", "<exact quote 2>", ...],
    "rationale": "<detailed explanation of which criteria are met/unmet>"
}}

Respond with ONLY the JSON object, no additional text."""


def build_compliance_prompt(question_data: dict) -> PromptTemplate:
    """Build a LangChain PromptTemplate for a compliance question."""
    criteria_str = "\n".join(
        f"  - {c}" for c in question_data["criteria"]
    )

    return PromptTemplate(
        template=COMPLIANCE_PROMPT_TEMPLATE,
        input_variables=["context"],
        partial_variables={
            "question": question_data["question"],
            "criteria": criteria_str,
        },
    )