# Ollama Stack

A focused local AI stack with Ollama, Open WebUI, and MCP tool integration. Everything runs locally for privacy.

## Features

- **Local AI Processing**: Run AI models locally using Ollama
- **Modern Web Interface**: Clean, responsive UI for interacting with AI models
- **Vector Database**: Store and search embeddings with Qdrant
- **Document Processing**: Upload and process documents with Unstructured
- **Multi-Platform Support**: Works on CPU, NVIDIA GPU, and Apple Silicon
- **Privacy-Focused**: All processing happens locally on your machine

## Prerequisites

- [Docker](https://www.docker.com/products/docker-desktop/) and Docker Compose
- [Ollama](https://ollama.ai/) installed and running
- For NVIDIA GPU support: NVIDIA drivers and NVIDIA Container Toolkit
- For Apple Silicon: Docker Desktop for Mac with Apple Silicon support

## Quick Start

1. Clone this repository:
   ```bash
   git clone https://github.com/yourusername/ollama-stack.git
   cd ollama-stack
   ```

2. Start the stack:
   ```bash
   # Auto-detect platform (default)
   ./start-stack.sh

   # Force specific platform
   ./start-stack.sh -p cpu
   ./start-stack.sh -p nvidia
   ./start-stack.sh -p apple
   ```

3. Access the web interface at `http://localhost:3000`

## Components

### Core Services

- **Ollama**: Local AI model server
- **Web UI**: Modern interface for interacting with AI models
- **MCP Proxy**: Tool integration server that exposes MCP tools via REST API

### Optional Services

- **Monitoring**: 
- **Logging**: 

## Configuration

### Platform Selection

The stack supports different hardware configurations and will auto-detect the appropriate platform by default:

- **Auto-detect** (default): Automatically detects the best platform for your system
- **CPU**: Basic configuration for systems without GPU
- **NVIDIA**: Optimized for NVIDIA GPUs
- **Apple**: Optimized for Apple Silicon

You can override the auto-detection by specifying a platform:

```bash
# Auto-detect platform (default)
./start-stack.sh

# Force specific platform
./start-stack.sh -p nvidia
./start-stack.sh -p apple
./start-stack.sh -p cpu
```

### Environment Variables

Key environment variables can be configured in `.env`:

- `OLLAMA_HOST`: Ollama server host (default: `host.docker.internal`)
- `OLLAMA_PORT`: Ollama server port (default: `11434`)
- `QDRANT_HOST`: Qdrant server host (default: `qdrant`)
- `QDRANT_PORT`: Qdrant server port (default: `6333`)

## Usage

### Starting the Stack

```bash
# Start with auto-detection (recommended)
./start-stack.sh

# Start with specific platform
./start-stack.sh -p nvidia

# Start with verbose output
./start-stack.sh -v

# Show help
./start-stack.sh -h
```

### Stopping the Stack

```bash
# Stop with auto-detection (recommended)
./stop-stack.sh

# Stop with specific platform
./stop-stack.sh -p nvidia

# Stop and remove volumes
./stop-stack.sh -v
```

### Updating the Stack

```bash
# Update with auto-detection (recommended)
./update-stack.sh

# Update with specific platform
./update-stack.sh -p nvidia
```

## Development

### Project Structure

```
.
├── docker-compose.yml          # Base Docker Compose configuration
├── docker-compose.nvidia.yml   # NVIDIA-specific overrides
├── docker-compose.apple.yml    # Apple Silicon-specific overrides
├── start-stack.sh             # Start script for Unix-like systems
├── start-stack.ps1            # Start script for Windows
├── stop-stack.sh              # Stop script for Unix-like systems
└── stop-stack.ps1             # Stop script for Windows
```

### Adding New Services

1. Add service configuration to `docker-compose.yml`
2. Add platform-specific overrides if needed
3. Update start/stop scripts to handle the new service

## Troubleshooting

### Common Issues

1. **Ollama Connection Issues**
   - Ensure Ollama is running
   - Check `OLLAMA_HOST` and `OLLAMA_PORT` in `.env`

2. **GPU Not Detected**
   - Verify NVIDIA drivers are installed
   - Check NVIDIA Container Toolkit installation
   - Use `nvidia-smi` to verify GPU detection

3. **Apple Silicon Issues**
   - Ensure Docker Desktop is configured for Apple Silicon
   - Check Rosetta 2 installation if needed

### Logs

View service logs:
```bash
# All services
docker compose logs

# Specific service
docker compose logs web-ui
```

