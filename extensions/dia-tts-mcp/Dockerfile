FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Set environment variables
ENV HF_TOKEN=""
ENV PYTORCH_ENABLE_MPS_FALLBACK=1

# Copy the server code
COPY server.py .

# Expose the port (MCP typically uses stdio, but this is for health checks)
EXPOSE 8000

# Set the entrypoint
CMD ["python", "server.py"] 