# Backend Dockerfile for FastAPI server
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY server.py .
COPY expressions.json .
COPY textgrid_to_timeline.py .
COPY start.sh .

# Make start script executable
RUN chmod +x start.sh

# Create necessary directories
RUN mkdir -p audio frames/sequences frames/endpoints

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health', timeout=2)"

# Run the server via start script (syncs manifests from S3 if enabled)
CMD ["./start.sh"]


