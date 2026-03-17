"""
Lightweight API router — only defines the health-check endpoint.

All /upload, /analyze, /chat, /status, /results endpoints live in main.py
to avoid duplicate route registrations and split in-memory stores.
"""
import logging
from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health")
async def health_via_router():
    """Secondary health check available through the router."""
    return {"status": "healthy", "source": "router"}