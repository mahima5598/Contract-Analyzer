# frontend/streamlit_app/live_results.py
import streamlit as st
import requests
import time

API_BASE = st.secrets.get("API_BASE", "http://localhost:8001/api")

st.title("Contract Analyzer — Live Analysis")

st.markdown("Upload a PDF and ask a compliance question. The backend will process and return a validated JSON answer.")

uploaded = st.file_uploader("Upload contract PDF", type=["pdf"])
question = st.text_input("Compliance question", value="Does the contract require MFA for admin access?")

if st.button("Submit for analysis"):
    if uploaded is None:
        st.warning("Please upload a PDF first.")
    elif not question.strip():
        st.warning("Please enter a question.")
    else:
        files = {"file": (uploaded.name, uploaded.getvalue(), "application/pdf")}
        # First build index (enqueue)
        resp = requests.post(f"{API_BASE}/index/build", files=files)
        if resp.status_code != 200:
            st.error(f"Index build failed: {resp.text}")
        else:
            data = resp.json()
            task_id = data.get("task_id")
            st.session_state["task_id"] = task_id
            st.success(f"Indexing started (task {task_id}). Will poll for completion and then run analysis.")
            st.experimental_rerun()

# If we have a task_id from indexing, poll it
task_id = st.session_state.get("task_id") if "task_id" in st.session_state else None
if task_id:
    st.info(f"Polling index build task: {task_id}")
    status_resp = requests.get(f"{API_BASE}/jobs/{task_id}/status")
    if status_resp.status_code == 200:
        status = status_resp.json()
        st.write(status)
        if status.get("state") == "SUCCESS" or status.get("state") == "done":
            st.success("Index built. Submitting analysis job...")
            # submit analysis
            q = question or "Does the contract require MFA for admin access?"
            a_resp = requests.post(f"{API_BASE}/analyze", data={"question": q})
            if a_resp.status_code == 200:
                a_data = a_resp.json()
                analysis_task = a_data.get("task_id")
                st.session_state["analysis_task"] = analysis_task
                st.experimental_rerun()
            else:
                st.error(f"Failed to start analysis: {a_resp.text}")
        else:
            st.write("Indexing in progress. Polling again in 3s...")
            time.sleep(3)
            st.experimental_rerun()
    else:
        st.error("Failed to fetch task status.")

# Poll analysis task if present
analysis_task = st.session_state.get("analysis_task") if "analysis_task" in st.session_state else None
if analysis_task:
    st.info(f"Polling analysis task: {analysis_task}")
    status_resp = requests.get(f"{API_BASE}/jobs/{analysis_task}/status")
    if status_resp.status_code == 200:
        status = status_resp.json()
        st.write(status)
        if status.get("state") == "SUCCESS" or status.get("state") == "done":
            # fetch results
            res = requests.get(f"{API_BASE}/jobs/{analysis_task}/results")
            if res.status_code == 200:
                st.subheader("Analysis result")
                st.json(res.json())
            else:
                st.error("Failed to fetch results.")
        else:
            st.write("Analysis in progress. Polling again in 3s...")
            time.sleep(3)
            st.experimental_rerun()
    else:
        st.error("Failed to fetch analysis task status.")
