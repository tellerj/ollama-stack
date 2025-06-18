# Ollama Stack

Local AI stack with Ollama, Open WebUI, and MCP tool integration.

## Components

- **Ollama**: Local AI model server (port 11434)
- **Open WebUI**: Web interface for chat interactions (port 8080) 
- **MCP Proxy**: Tool integration server exposing MCP tools via REST (port 8200)
- **Extension System**: Modular extensions for additional AI capabilities

## Features

- Multi-platform support (CPU, NVIDIA GPU, Apple Silicon)
- Unified CLI tool for management
- Extension system for additional tools
- Docker-based deployment

## Prerequisites

- [Docker](https://www.docker.com/products/docker-desktop/)
- [Ollama](https://ollama.ai/) installed and running (Apple Silicon)
- For NVIDIA GPU support: NVIDIA drivers and NVIDIA Container Toolkit

## Quick Start

```bash
# Clone the repo
git clone https://github.com/tellerj/ollama-stack.git
cd ollama-stack

# Install the CLI tool
./install-ollama-stack.sh      # Unix/macOS
.\install-ollama-stack.ps1     # Windows
   
# Start the stack
ollama-stack start

# Enable an extension
ollama-stack extensions enable dia-tts-mcp
ollama-stack extensions start dia-tts-mcp

# Check status
ollama-stack status
```

Access the web interface at `http://localhost:8080`

## CLI Commands

```bash
ollama-stack start [--update]        # Start stack (add --update to pull latest images)
ollama-stack stop                    # Stop stack
ollama-stack restart                 # Restart stack
ollama-stack status                  # Show status
ollama-stack logs [service]          # View logs
ollama-stack extensions list         # List extensions
ollama-stack extensions enable <ext> # Enable extension
ollama-stack extensions start <ext>  # Start extension
ollama-stack --help                  # Show help
```


## Run via Script (no install)

```bash
# From project root
./ollama-stack start      # Unix/macOS
.\ollama-stack.ps1 start  # Windows
```

## Documentation

- [CLI Usage Guide](docs/CLI_USAGE.md)
- [Windows Setup](docs/WINDOWS_SETUP.md)
- [Project Structure](docs/PROJECT_STRUCTURE.md)

## Platform Support

The CLI auto-detects your hardware:

- **CPU**: Basic Docker configuration
- **NVIDIA**: GPU acceleration with CUDA
- **Apple Silicon**: Uses native Ollama app + Docker services

Force a specific platform: `./ollama-stack start -p nvidia`

## Project Structure

```
ollama-stack/
├── ollama-stack               # Main CLI (Unix/macOS)
├── ollama-stack.ps1           # Main CLI (Windows)  
├── docker-compose*.yml        # Service configurations
├── docs/                      # Documentation
├── install-ollama-stack.sh   # Unix/macOS installer
├── install-ollama-stack.ps1  # Windows installer
├── extensions/                # Extension system
└── tools/                     # Additional tools
```

## Troubleshooting

**Service not starting**: Check logs with `./ollama-stack logs <service>`
**GPU not detected**: Verify `nvidia-smi` works and NVIDIA Container Toolkit is installed
**Apple Silicon**: Ensure native Ollama app is running before starting stack

