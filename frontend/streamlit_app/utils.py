"""
Frontend utility functions.

Handles API communication and shared helpers for the Streamlit app.
"""
import os
import requests
from typing import Optional, Dict, Any


def get_api_base() -> str:
    """Get the backend API base URL from environment or default."""
    return os.getenv("API_BASE", "http://localhost:8000")


def check_backend_health(api_base: str) -> bool:
    """Check if the backend API is reachable."""
    try:
        response = requests.get(f"{api_base}/api/health", timeout=5)
        return response.status_code == 200
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        return False


def upload_document(api_base: str, file) -> Optional[Dict[str, Any]]:
    """Upload a PDF document to the backend."""
    try:
        files = {"file": (file.name, file.getvalue(), "application/pdf")}
        response = requests.post(f"{api_base}/api/upload", files=files, timeout=120)
        if response.status_code == 200:
            return response.json()
        return None
    except requests.exceptions.RequestException:
        return None


def run_analysis(api_base: str, document_id: str) -> Optional[Dict[str, Any]]:
    """Trigger compliance analysis on the backend."""
    try:
        response = requests.post(
            f"{api_base}/api/analyze/{document_id}",
            timeout=300,  # Analysis can take a few minutes
        )
        if response.status_code == 200:
            return response.json()
        return None
    except requests.exceptions.RequestException:
        return None


def send_chat_message(
    api_base: str,
    document_id: str,
    message: str,
    history: list = None,
) -> Optional[Dict[str, Any]]:
    """Send a chat message to the backend."""
    try:
        response = requests.post(
            f"{api_base}/api/chat",
            json={
                "document_id": document_id,
                "message": message,
                "history": history or [],
            },
            timeout=60,
        )
        if response.status_code == 200:
            return response.json()
        return None
    except requests.exceptions.RequestException:
        return None