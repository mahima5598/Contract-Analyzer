"""
PDF upload component for Streamlit.

Handles:
- File upload with validation
- Upload progress feedback
- API call to backend /api/upload
- Session state management for the uploaded document
"""
import streamlit as st
import requests
from typing import Optional, Dict


def render_upload_widget(api_base: str) -> Optional[Dict]:
    """
    Render the PDF upload sidebar widget.

    Returns:
        Upload response dict if a document is uploaded, None otherwise
    """
    st.header("📄 Upload Contract")

    uploaded_file = st.file_uploader(
        "Choose a PDF contract",
        type=["pdf"],
        help="Upload a vendor contract PDF to analyze for cybersecurity compliance.",
        key="pdf_uploader",
    )

    if uploaded_file is not None:
        # Show file info
        file_size_mb = uploaded_file.size / (1024 * 1024)
        st.caption(f"📎 {uploaded_file.name} ({file_size_mb:.1f} MB)")

        # Validate file size (max 50MB)
        if file_size_mb > 50:
            st.error("❌ File too large. Maximum size is 50 MB.")
            return None

        # Only upload if not already uploaded (check session state)
        if (
            "document_id" not in st.session_state
            or st.session_state.get("filename") != uploaded_file.name
        ):
            if st.button("📤 Upload & Process", type="primary", use_container_width=True):
                return _upload_file(uploaded_file, api_base)
        else:
            st.success(f"✅ Already uploaded: {uploaded_file.name}")
            return {
                "document_id": st.session_state["document_id"],
                "filename": st.session_state["filename"],
                "page_count": st.session_state["page_count"],
                "status": "ready",
            }

    return None


def _upload_file(uploaded_file, api_base: str) -> Optional[Dict]:
    """Upload the file to the backend API and process it."""
    progress_bar = st.progress(0, text="Uploading PDF...")

    try:
        # Step 1: Upload
        progress_bar.progress(20, text="Uploading PDF...")
        files = {
            "file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")
        }
        response = requests.post(
            f"{api_base}/api/upload",
            files=files,
            timeout=120,
        )

        progress_bar.progress(60, text="Extracting text, tables, and images...")

        if response.status_code != 200:
            st.error(f"❌ Upload failed: {response.json().get('detail', response.text)}")
            progress_bar.empty()
            return None

        data = response.json()

        # Step 2: Store in session state
        progress_bar.progress(90, text="Building search index...")
        st.session_state["document_id"] = data["document_id"]
        st.session_state["filename"] = data["filename"]
        st.session_state["page_count"] = data["page_count"]

        progress_bar.progress(100, text="Ready!")
        st.success(
            f"✅ Uploaded: **{data['filename']}** — "
            f"{data['page_count']} pages extracted"
        )

        return data

    except requests.exceptions.ConnectionError:
        st.error("❌ Cannot connect to backend. Is the server running on port 8000?")
        progress_bar.empty()
        return None
    except requests.exceptions.Timeout:
        st.error("❌ Upload timed out. The PDF may be too large.")
        progress_bar.empty()
        return None


def render_document_info():
    """Show info about the currently uploaded document in the sidebar."""
    if "document_id" in st.session_state:
        st.divider()
        st.subheader("📋 Current Document")
        st.markdown(f"**File:** {st.session_state['filename']}")
        st.markdown(f"**Pages:** {st.session_state['page_count']}")
        st.markdown(f"**ID:** `{st.session_state['document_id'][:8]}...`")

        if st.button("🗑️ Clear & Upload New", use_container_width=True):
            for key in ["document_id", "filename", "page_count", "report", "chat_history"]:
                st.session_state.pop(key, None)
            st.rerun()