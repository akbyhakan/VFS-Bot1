# Multi-stage build for smaller image size

# Stage 1: Build dependencies
FROM python:3.12-slim as builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install to /install
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Stage 2: Runtime
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
    && rm -rf /var/lib/apt/lists/*

# Create non-root user BEFORE copying dependencies
RUN useradd -m -u 1000 vfsbot

# Copy Python dependencies from builder to vfsbot's home
COPY --from=builder /root/.local /home/vfsbot/.local
ENV PATH=/home/vfsbot/.local/bin:$PATH

# Set Playwright browsers path to vfsbot-accessible location
ENV PLAYWRIGHT_BROWSERS_PATH=/home/vfsbot/.cache/ms-playwright

# Install Playwright Chromium as root and set ownership
RUN playwright install chromium && \
    chown -R vfsbot:vfsbot /home/vfsbot/.local /home/vfsbot/.cache

# Copy application code
COPY . .

# Set ownership of app directory
RUN chown -R vfsbot:vfsbot /app

# Create directories for logs and screenshots
RUN mkdir -p /app/logs /app/screenshots && \
    chown -R vfsbot:vfsbot /app/logs /app/screenshots

# Switch to non-root user
USER vfsbot

# Expose port for web dashboard
EXPOSE 8000

# Health check using httpx (available in requirements.txt)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health', timeout=5).raise_for_status()" || exit 1

# Default command
CMD ["python", "main.py", "--mode", "both"]
