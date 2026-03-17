import streamlit as st
import time
import requests
from components.upload import render_upload_widget, render_document_info
from components.results_display import render_results
from components.chat_widget import render_chat_widget
from utils import get_api_base, check_backend_health, run_analysis
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

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
    st.error("⚠️ Cannot connect to the backend API. Make sure the server is running.")
    st.stop()

# ── Sidebar: Upload ──
with st.sidebar:
    # render_upload_widget now returns immediately with 'processing' status
    render_upload_widget(API_BASE)
    
    # ── Polling for Upload Status ──
    if "document_id" in st.session_state and st.session_state.get("upload_status") != "ready":
        with st.status("🛠️ Processing Document...", expanded=True) as status:
            while True:
                try:
                    resp = requests.get(f"{API_BASE}/api/status/{st.session_state['document_id']}").json()
                    curr_status = resp.get("status")
                    
                    if curr_status == "ready":
                        st.session_state["upload_status"] = "ready"
                        status.update(label="✅ Document Ready!", state="complete")
                        st.rerun()
                        break
                    elif curr_status == "failed":
                        st.error(f"❌ Upload failed: {resp.get('error')}")
                        break
                    else:
                        st.write(f"Status: {curr_status.capitalize()}...")
                except Exception as e:
                    st.error(f"Connection error: {e}")
                    break
                time.sleep(2)

    render_document_info()

# ── Main Content ──
if "document_id" in st.session_state and st.session_state.get("upload_status") == "ready":
    tab_analysis, tab_chat = st.tabs(["📊 Compliance Analysis", "💬 Chat with Document"])

    # ── Tab 1: Compliance Analysis ──
    with tab_analysis:
        if "report" not in st.session_state:
            st.markdown("Click below to analyze the contract against **5 cybersecurity requirements**.")

            if st.button("▶️ Run Compliance Analysis", type="primary", use_container_width=True):
                # 1. Trigger the background analysis
                requests.post(f"{API_BASE}/api/analyze/{st.session_state['document_id']}")
                
                # 2. Polling for Analysis Results
                with st.status("🔍 Analyzing compliance...", expanded=True) as status:
                    while True:
                        resp = requests.get(f"{API_BASE}/api/status/{st.session_state['document_id']}").json()
                        curr_status = resp.get("status")
                        
                        if curr_status == "analysis_complete":
                            # Fetch final results from the results endpoint
                            report = requests.get(f"{API_BASE}/api/results/{st.session_state['document_id']}").json()
                            st.session_state["report"] = report
                            status.update(label="✅ Analysis Complete!", state="complete")
                            st.rerun()
                            break
                        elif curr_status == "failed":
                            st.error(f"❌ Analysis failed: {resp.get('error')}")
                            break
                        time.sleep(3)
        else:
            render_results(st.session_state["report"])
            if st.button("🔄 Re-run Analysis"):
                del st.session_state["report"]
                st.rerun()

    # ── Tab 2: Chat (Bonus) ──
    with tab_chat:
        render_chat_widget(API_BASE, st.session_state.get("document_id"))

else:
    # Landing page (Only shown if no document is uploaded or still processing)
    if "document_id" not in st.session_state:
        st.info("👈 **Upload a PDF contract** using the sidebar to get started.")
        # ... (rest of your landing page markdown)
    else:
        st.warning("⏳ **Processing your document...** Please wait for the sidebar status to show 'Ready'.")
