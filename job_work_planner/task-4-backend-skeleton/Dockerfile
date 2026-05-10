# ─────────────────────────────────────────────────────────────────────────────
# Project Roodha v1.5.7 — Production Dockerfile
# Account: 918172959197 (ap-south-1)
# Base : python:3.11-slim
# Serves: uvicorn app.main:app --host 0.0.0.0 --port 8000
# ─────────────────────────────────────────────────────────────────────────────

FROM python:3.11-slim

# Keeps Python output un-buffered for container log streaming
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# System dependencies (psycopg2-binary needs libpq, fpdf2 needs nothing extra)
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── Dependency layer (cached unless requirements.txt changes) ─────────────────
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# ── Application source ────────────────────────────────────────────────────────
COPY . .

# Expose the uvicorn port
EXPOSE 8000

# ── Runtime command ───────────────────────────────────────────────────────────
# Workers = 1 to stay stateless-friendly inside App Runner's single-container model.
# App Runner auto-scales horizontally, so multiple processes per container are unnecessary.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "1", "--log-level", "info"]
