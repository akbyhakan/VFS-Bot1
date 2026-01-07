FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN playwright install chromium
RUN playwright install-deps chromium

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

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/api/status')"

# Default command
CMD ["python", "main.py"]
