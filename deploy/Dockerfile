# ==============================================================================
# Privora — Private Document Intelligence Enterprise Container
# Multi-stage production build: Node 20 (Frontend) + Python 3.12 (Unified Backend)
# ==============================================================================

# Stage 1: Build Next.js Static Export
FROM node:20-bookworm-slim AS frontend-builder
WORKDIR /build

# Install dependencies with frozen lockfile where possible
COPY package.json package-lock.json* ./
RUN npm ci --silent || npm install --silent

# Copy source and build static export
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
ENV NODE_ENV=production
RUN npm run build

# Stage 2: Production Python Backend Runtime
FROM python:3.12-slim-bookworm AS runtime

LABEL maintainer="Privora Infrastructure Team <security@privora.workbench>"
LABEL description="Privora Private Document Intelligence Enterprise Runtime"

# Install minimal OS dependencies & curl for healthchecks
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create unprivileged application user
RUN groupadd -g 1000 privora && \
    useradd -u 1000 -g privora -s /bin/bash -m privora

WORKDIR /app

# Install Python dependencies
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /app/requirements.txt

# Copy backend application code
COPY backend/app /app/app
COPY backend/migrations /app/migrations 2>/dev/null || true

# Copy static frontend export from stage 1
COPY --from=frontend-builder /build/out /app/static

# Create persistent storage directories
RUN mkdir -p /app/data /app/data/documents /app/data/backups && \
    chown -R privora:privora /app

USER privora

# Runtime environment configuration
ENV DEPLOYMENT_MODE=server
ENV STATIC_DIR=/app/static
ENV DATA_DIR=/app/data
ENV DATABASE_PATH=/app/data/workbench.sqlite3
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

HEALTHCHECK --interval=20s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://127.0.0.1:8000/api/health || exit 1

ENTRYPOINT ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4", "--proxy-headers", "--forwarded-allow-ips", "*"]
