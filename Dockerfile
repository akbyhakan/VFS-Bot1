# Multi-stage build for smaller image size

# Stage 1: Build dependencies
FROM python:3.11-slim as builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install to /install
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim

WORKDIR /app

# Install only runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    fonts-liberation \
    libnss3 \
    libnspr4 \
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
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

# Copy Python dependencies from builder
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Install Playwright Chromium only
RUN playwright install chromium && \
    playwright install-deps chromium

# Copy application code
COPY . .

# Create non-root user
RUN useradd -m -u 1000 vfsbot && \
    chown -R vfsbot:vfsbot /app

# Create directories for logs and screenshots
RUN mkdir -p /app/logs /app/screenshots && \
    chown -R vfsbot:vfsbot /app/logs /app/screenshots

# Switch to non-root user
USER vfsbot

# Expose port for web dashboard
EXPOSE 8000

# Health check using new endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health').raise_for_status()" || exit 1

# Default command
CMD ["python", "main.py", "--mode", "both"]
