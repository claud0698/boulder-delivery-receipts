# Use official Python runtime
# Explicitly use AMD64 for Cloud Run compatibility
FROM --platform=linux/amd64 python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/

# Create credentials directory
RUN mkdir -p credentials

# Expose port (Cloud Run uses PORT env var, default 8080)
ENV PORT=8080
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:$PORT/health')" || exit 1

# Run with Gunicorn for production
# Timeout set to 300s (5 min) to handle long OCR processing and network delays
# Using 1 worker with NO THREADS - async event loop handles concurrency
# UvicornWorker handles async natively, threads cause SSL/segfault issues
CMD ["sh", "-c", "exec gunicorn --bind :$PORT --workers 1 --worker-class uvicorn.workers.UvicornWorker --timeout 300 --graceful-timeout 30 --keep-alive 75 --worker-tmp-dir /dev/shm --access-logfile - --error-logfile - --log-level info src.main:app"]
