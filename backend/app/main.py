from fastapi import FastAPI
from .api import router as api_router
from .api_index import router as index_router

app = FastAPI(title="Contract Analyzer API")

# This is for the basic "Upload and Extract" logic
app.include_router(api_router, prefix="/api/v1") 

# This is for the "Search and Indexing" logic
app.include_router(index_router, prefix="/api/index") 
