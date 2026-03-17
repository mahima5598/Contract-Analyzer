"""
Chat interface component for conversational Q&A over the contract.

This is the BONUS feature. Users can ask free-form questions like:
- "What does section 4.2 say about data retention?"
- "Are there any penalties for non-compliance?"
- "Summarize the encryption requirements"
"""
import streamlit as st
import requests
from typing import Optional


def render_chat_widget(api_base: str, document_id: Optional[str] = None):
    """Render the chat interface for document Q&A."""
    st.subheader("💬 Chat with the Contract")
    st.caption(
        "Ask any question about the uploaded contract. "
        "The AI will answer based on the document content."
    )

    if not document_id:
        st.warning("⚠️ Upload a document first to start chatting.")
        return

    # Initialize chat history
    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []

    # Suggested questions (starter prompts)
    if not st.session_state["chat_history"]:
        st.markdown("**💡 Try asking:**")
        suggestions = [
            "What are the key security obligations in this contract?",
            "Does the contract mention data encryption requirements?",
            "What are the termination conditions?",
            "Summarize the vendor's responsibilities for incident response.",
            "Are there any SLA guarantees mentioned?",
        ]

        cols = st.columns(2)
        for i, suggestion in enumerate(suggestions):
            col = cols[i % 2]
            if col.button(suggestion, key=f"suggestion_{i}", use_container_width=True):
                _send_message(suggestion, api_base, document_id)
                st.rerun()

    st.divider()

    # Display chat history
    for msg in st.session_state["chat_history"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

            # Show sources for assistant messages
            if msg["role"] == "assistant" and msg.get("source_quotes"):
                with st.expander("📖 Source References", expanded=False):
                    for j, quote in enumerate(msg["source_quotes"], 1):
                        st.markdown(f"**[{j}]** _{quote}_")
                    if msg.get("source_pages"):
                        st.caption(f"📄 Referenced pages: {msg['source_pages']}")

    # Chat input
    if prompt := st.chat_input("Ask a question about the contract..."):
        _send_message(prompt, api_base, document_id)
        st.rerun()

    # Clear chat button
    if st.session_state["chat_history"]:
        if st.button("🗑️ Clear Chat History", use_container_width=True):
            st.session_state["chat_history"] = []
            st.rerun()


def _send_message(user_message: str, api_base: str, document_id: str):
    """Send a message to the chat API and store the response."""
    # Add user message to history
    st.session_state["chat_history"].append({
        "role": "user",
        "content": user_message,
    })

    # Prepare history for API (only role + content, no metadata)
    api_history = [
        {"role": m["role"], "content": m["content"]}
        for m in st.session_state["chat_history"]
    ]

    try:
        response = requests.post(
            f"{api_base}/api/chat",
            json={
                "document_id": document_id,
                "message": user_message,
                "history": api_history[:-1],  # Exclude the message we just added
            },
            timeout=60,
        )

        if response.status_code == 200:
            data = response.json()
            st.session_state["chat_history"].append({
                "role": "assistant",
                "content": data["answer"],
                "source_quotes": data.get("source_quotes", []),
                "source_pages": data.get("source_pages", []),
            })
        else:
            st.session_state["chat_history"].append({
                "role": "assistant",
                "content": f"❌ Error: {response.json().get('detail', 'Unknown error')}",
            })

    except requests.exceptions.ConnectionError:
        st.session_state["chat_history"].append({
            "role": "assistant",
            "content": "❌ Cannot connect to backend. Is the server running?",
        })
    except requests.exceptions.Timeout:
        st.session_state["chat_history"].append({
            "role": "assistant",
            "content": "❌ Request timed out. Try a simpler question.",
        })