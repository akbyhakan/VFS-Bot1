# Multi-stage build for smaller image size

# Stage 1: Frontend builder
FROM node:18-slim AS frontend-builder

WORKDIR /app/frontend

# Copy package files for dependency installation
COPY frontend/package.json frontend/package-lock.json ./

# Install dependencies with clean install for reproducibility
RUN npm ci

# Copy frontend source code
COPY frontend/ ./

# Build frontend (outputs to ../web/static/dist per vite.config.ts)
RUN npm run build

# Stage 2: Python dependencies builder
FROM python:3.12-slim AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy lockfile and install pinned dependencies for reproducible builds
# Production uses requirements.lock for deterministic, reproducible builds.
# If dependencies change, regenerate with: make lock
# See also: Dockerfile.dev (uses pyproject.toml for dev builds)
COPY requirements.lock .
RUN pip install --no-cache-dir --user -r requirements.lock

# Stage 3: Runtime
FROM python:3.12-slim

WORKDIR /app

# Install only runtime dependencies
RUN apt-get update && \
    (apt-get install -y --no-install-recommends libasound2t64 || \
     apt-get install -y --no-install-recommends libasound2) && \
    apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    fonts-liberation \
    fonts-noto-color-emoji \
    fonts-freefont-ttf \
    libglib2.0-0 \
    libnss3 \
    libnspr4 \
    libdbus-1-3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libatspi2.0-0 \
    libgtk-3-0 \
    libpango-1.0-0 \
    libcairo2 \
    libpq5 \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user BEFORE copying dependencies
RUN useradd -m -u 1000 vfsbot

# Copy Python dependencies from builder to vfsbot's home
COPY --from=builder /root/.local /home/vfsbot/.local

# Set Python user base and update PATH
ENV PYTHONUSERBASE=/home/vfsbot/.local
ENV PATH=/home/vfsbot/.local/bin:$PATH

# Set Playwright browsers path to vfsbot-accessible location
ENV PLAYWRIGHT_BROWSERS_PATH=/home/vfsbot/.cache/ms-playwright

# Bind to all interfaces in Docker container (overridable via docker run -e)
# Security: Default 127.0.0.1 in source code is intentional for local dev.
# In Docker, 0.0.0.0 is needed for port mapping to work.
ENV UVICORN_HOST=0.0.0.0

# Install Playwright Chromium and set ownership
RUN python3 -m playwright install chromium && \
    chown -R vfsbot:vfsbot /home/vfsbot/.local /home/vfsbot/.cache

# Copy application code
COPY . .

# Copy frontend build artifacts from frontend-builder (after COPY . . to override empty dist)
COPY --from=frontend-builder /app/web/static/dist /app/web/static/dist

# Set ownership of app directory
RUN chown -R vfsbot:vfsbot /app

# Create directories for logs and screenshots
RUN mkdir -p /app/logs /app/screenshots && \
    chown -R vfsbot:vfsbot /app/logs /app/screenshots

# Copy and set up entrypoint script
COPY scripts/docker-entrypoint.sh /app/scripts/docker-entrypoint.sh
RUN chmod +x /app/scripts/docker-entrypoint.sh

# Switch to non-root user
USER vfsbot

# Expose port for web dashboard
EXPOSE 8000

# Health check using curl
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Entrypoint for automatic migrations
ENTRYPOINT ["/app/scripts/docker-entrypoint.sh"]

# Default command
CMD ["--mode", "both"]
