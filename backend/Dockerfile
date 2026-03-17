FROM python:3.10-slim

# 1. Install all system dependencies in ONE go (Better for speed/size)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libmagic-dev \
    tesseract-ocr \
    poppler-utils \
    ghostscript \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 2. Pre-install the "Heavy" libraries
RUN pip install --upgrade pip && \
    pip install --no-cache-dir "numpy<2.0" "pydantic>=2.0" "fastapi>=0.100" "langchain>=0.1.0" "openai" "faiss-cpu" && \
    pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# 3. Copy Requirement files
COPY backend/requirements.txt ./backend/requirements.txt
COPY frontend/requirements.txt ./frontend/requirements.txt

# 4. Install remaining app requirements
RUN pip install --no-cache-dir \
    -r ./backend/requirements.txt \
    -r ./frontend/requirements.txt

# 5. Copy App Code
COPY . .

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
