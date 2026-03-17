"""
Contract Compliance Analyzer — Streamlit Frontend

This is the main entry point. It composes the modular components:
  - upload.py       → PDF upload sidebar
  - results_display → Compliance results rendering
  - chat_widget     → Bonus chat interface
  - utils           → Backend API communication
"""
import streamlit as st
from components.upload import render_upload_widget, render_document_info
from components.results_display import render_results
from components.chat_widget import render_chat_widget
from utils import get_api_base, check_backend_health, run_analysis

# ── Page Configuration ──
st.set_page_config(
    page_title="Contract Compliance Analyzer",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded",
)

API_BASE = get_api_base()

# ── Header ──
st.title("📋 Contract Compliance Analyzer")
st.markdown(
    "*AI-powered cybersecurity compliance analysis for vendor contracts "
    "using Retrieval-Augmented Generation (RAG)*"
)

# ── Backend Health Check ──
if not check_backend_health(API_BASE):
    st.error(
        "⚠️ Cannot connect to the backend API. "
        "Make sure the server is running on port 8000.\n\n"
        "Start it with: `uvicorn backend.app.main:app --reload`"
    )
    st.stop()

# ── Sidebar: Upload ──
with st.sidebar:
    render_upload_widget(API_BASE)
    render_document_info()

# ── Main Content ──
if "document_id" in st.session_state:
    # Two tabs: Analysis + Chat
    tab_analysis, tab_chat = st.tabs(["📊 Compliance Analysis", "💬 Chat with Document"])

    # ── Tab 1: Compliance Analysis ──
    with tab_analysis:
        if "report" not in st.session_state:
            st.markdown(
                "Click the button below to analyze the contract against "
                "**5 cybersecurity compliance requirements**."
            )

            if st.button(
                "▶️ Run Compliance Analysis",
                type="primary",
                use_container_width=True,
            ):
                with st.spinner("🔍 Analyzing contract for compliance... This may take 1-2 minutes."):
                    report = run_analysis(API_BASE, st.session_state["document_id"])

                if report:
                    st.session_state["report"] = report
                    st.rerun()
                else:
                    st.error("❌ Analysis failed. Check the backend logs for details.")

        else:
            render_results(st.session_state["report"])

    # ── Tab 2: Chat (Bonus) ──
    with tab_chat:
        render_chat_widget(API_BASE, st.session_state.get("document_id"))

else:
    # Landing page when no document is uploaded
    st.info("👈 **Upload a PDF contract** using the sidebar to get started.")

    st.markdown("---")
    st.markdown("### How it works")

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.markdown("**1. Upload**\n\n📄 Upload a vendor contract PDF")
    col2.markdown("**2. Extract**\n\n🔍 Text, tables & images are extracted")
    col3.markdown("**3. Index**\n\n📊 Content is embedded into a vector store")
    col4.markdown("**4. Analyze**\n\n🤖 AI evaluates 5 compliance requirements")
    col5.markdown("**5. Report**\n\n📋 Structured results with quotes & rationale")

    st.markdown("---")
    st.markdown("### Compliance Requirements Evaluated")
    st.markdown("""
    | # | Requirement | What's Checked |
    |---|---|---|
    | 1 | **Password Management** | Strength, storage, brute-force protection, rotation |
    | 2 | **IT Asset Management** | Inventory, reconciliation, secure baselines |
    | 3 | **Security Training & Background Checks** | Annual training, screening policies |
    | 4 | **Data in Transit Encryption** | TLS 1.2+, certificate management, cipher suites |
    | 5 | **Network Auth & Authorization** | SSO, MFA, bastion hosts, RBAC |
    """)