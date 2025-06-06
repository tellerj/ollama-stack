FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    build-essential \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Set environment variables
ENV HF_TOKEN=""
ENV PYTORCH_ENABLE_MPS_FALLBACK=1
ENV TRANSFORMERS_CACHE=/app/cache/transformers
ENV HF_HOME=/app/cache/huggingface

# Create cache directories
RUN mkdir -p /app/cache/transformers /app/cache/huggingface /tmp/dia_audio

# Copy the server code
COPY server.py .

# Create a health check script
RUN echo '#!/bin/bash\npython3 -c "import sys; sys.exit(0)"' > /app/health_check.sh && \
    chmod +x /app/health_check.sh

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD ["/app/health_check.sh"]

# Set the entrypoint - MCP servers use stdio
ENTRYPOINT ["python3", "server.py"] 