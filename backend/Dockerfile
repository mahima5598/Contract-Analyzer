# Use a slim Linux Python base
FROM python:3.12-slim

# Avoid running as root in container
ARG APP_USER=app
ARG APP_UID=1000
RUN groupadd -g ${APP_UID} ${APP_USER} && \
    useradd -m -u ${APP_UID} -g ${APP_UID} ${APP_USER}

WORKDIR /app

# Install system deps needed by native libs (adjust as needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential git curl ca-certificates libsndfile1 libgl1 \
    && rm -rf /var/lib/apt/lists/*

# copy runtime requirements
# copy runtime requirements
COPY backend/requirements.txt /app/backend-requirements.txt
RUN pip install --upgrade pip \
 && pip install --no-cache-dir -r /app/backend-requirements.txt
# optionally copy frontend runtime requirements if you created one
# copy runtime requirements
COPY frontend/requirements.txt /app/frontend-requirements.txt
RUN pip install --upgrade pip \
 && pip install --no-cache-dir -r /app/frontend-requirements.txt

# Copy project
COPY . /app

# Ensure python imports find backend package
ENV PYTHONPATH=/app

# Use non-root user
USER ${APP_USER}

# Default entrypoint (overridden by docker-compose or kubernetes)
COPY backend/docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

ENTRYPOINT ["/app/docker-entrypoint.sh"]

