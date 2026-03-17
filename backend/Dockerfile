FROM python:3.12-slim

# Install system dependencies (Adding poppler-utils for pdf2image)
# install system deps needed by camelot and other imaging libs
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ghostscript \
    libxml2-dev \
    libxslt1-dev \
    libjpeg-dev \
    zlib1g-dev \
    libgl1 \
    libsm6 \
    libxrender1 \
    libxext6 \
    tcl \
    tk \
    && rm -rf /var/lib/apt/lists/*


WORKDIR /app

# Pre-install major libraries to prevent resolution loops
RUN pip install --upgrade pip && \
    pip install --no-cache-dir "numpy<2.0" "pydantic>=2.0" "fastapi>=0.100"

# Copy and install Python requirements
COPY backend/requirements.txt ./backend/requirements.txt
COPY frontend/requirements.txt ./frontend/requirements.txt

RUN pip install --no-cache-dir \
    -r ./backend/requirements.txt \
    -r ./frontend/requirements.txt

COPY . .
ENV PYTHONPATH=/app

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]