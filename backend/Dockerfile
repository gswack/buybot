# FastAPI price-comparison backend (app.main:app).
# NOTE: this replaces the old Node server.js image. The real backend the
# frontend talks to is this Python/FastAPI app, serving /api/search/*,
# /api/users/*, /api/classify, /api/coupons on port 8000.
FROM python:3.11-slim

WORKDIR /app

# System deps: libpq for asyncpg builds, plus build tooling for any wheels
# that need compiling (kept minimal; CLIP/torch are NOT used by the live routes).
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first for better layer caching
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy the FastAPI application package. main.py imports as `app.main:app`,
# so the package directory must be named `app` at the working dir root.
COPY app/ ./app/

# FastAPI/uvicorn listens on 8000; the reverse proxy on the public VM
# forwards /api to this port over the VNet.
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
