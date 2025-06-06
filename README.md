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
   # Use the unified CLI tool (recommended)
   ./ollama-stack start

   # Or use legacy scripts
   ./scripts/start-stack.sh -p nvidia
   ```

3. Access the web interface at `http://localhost:8080`

## 📋 Documentation

- **[CLI Usage Guide](docs/CLI_USAGE.md)** - Complete CLI reference with examples
- **[Windows Setup](docs/WINDOWS_SETUP.md)** - Windows-specific installation and usage
- **[Project Structure](PROJECT_STRUCTURE.md)** - Organization and file layout guide
- **[Development Notes](docs/UNIFIED_CLI_SUMMARY.md)** - Technical implementation details

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
./ollama-stack start

# Force specific platform
./ollama-stack start -p nvidia
./ollama-stack start -p apple
./ollama-stack start -p cpu
```

### Environment Variables

Key environment variables can be configured in `.env`:

- `OLLAMA_HOST`: Ollama server host (default: `host.docker.internal`)
- `OLLAMA_PORT`: Ollama server port (default: `11434`)
- `QDRANT_HOST`: Qdrant server host (default: `qdrant`)
- `QDRANT_PORT`: Qdrant server port (default: `6333`)

## Usage

### Using the Unified CLI (Recommended)

```bash
# Start the stack
./ollama-stack start                    # Auto-detect platform
./ollama-stack start -p nvidia          # Force specific platform

# Manage extensions
./ollama-stack extensions list          # List all extensions
./ollama-stack extensions enable name   # Enable extension
./ollama-stack extensions start name    # Start extension

# Monitor and control
./ollama-stack status                   # Check status
./ollama-stack logs                     # View logs
./ollama-stack stop                     # Stop everything

# Get help
./ollama-stack --help
```

### Legacy Scripts (For Backwards Compatibility)

```bash
# Start with auto-detection
./scripts/start-stack.sh

# Stop with auto-detection
./scripts/stop-stack.sh

# Show help
./scripts/start-stack.sh -h
```

## Development

### Project Structure

```
.
├── README.md                   # This file
├── ollama-stack               # Main CLI tool (Unix/macOS)
├── ollama-stack.ps1           # Main CLI tool (Windows)
├── docker-compose*.yml        # Docker configurations
├── docs/                      # Documentation
│   ├── CLI_USAGE.md          # Detailed CLI usage guide
│   ├── WINDOWS_SETUP.md      # Windows-specific setup
│   └── UNIFIED_CLI_SUMMARY.md # Development notes
├── scripts/                   # Utility and legacy scripts
│   ├── install.sh            # Unix installer
│   ├── install.ps1           # Windows installer
│   ├── start-stack.sh        # Legacy start script
│   └── stop-stack.sh         # Legacy stop script
├── extensions/                # Extension system
└── tools/                     # Additional tools
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

