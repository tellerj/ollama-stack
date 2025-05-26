# Ollama Stack

A focused local AI stack with Ollama, Open WebUI, and MCP tool integration. Everything runs locally for complete privacy.

## 🚀 Quick Start

### Simple Start
```bash
git clone <repository_url>
cd ollama-stack
docker compose up -d
```

### Using Startup Scripts
```bash
# Linux/macOS
./start-stack.sh

# Windows PowerShell
.\start-stack.ps1

# With hardware acceleration
./start-stack.sh -h nvidia
.\start-stack.ps1 -Hardware nvidia
```

### Hardware-Optimized
```bash
# NVIDIA GPU acceleration
docker compose -f docker-compose.yml -f docker-compose.nvidia.yml up -d

# Apple Silicon (requires native Ollama app running first)
docker compose -f docker-compose.yml -f docker-compose.apple.yml up -d
```

### Access Services
- **Open WebUI**: http://localhost:8080 (Main interface)
- **Ollama API**: http://localhost:11434 (LLM engine)
- **MCP Proxy**: http://localhost:8200 (Tool integration)
- **MCP Docs**: http://localhost:8200/docs (Interactive API docs)

### First Steps
1. **Download a model**: Open WebUI → model selector → type `llama3.1` or `phi3`
2. **Explore MCP tools**: Visit http://localhost:8200/docs
3. **Start chatting**: Built-in tools appear automatically in conversations

## Core Services

### Ollama (`localhost:11434`)
- Runs large language models locally
- Supports CPU and GPU acceleration
- Compatible with 100+ open-source models

### Open WebUI (`localhost:8080`)
- Modern chat interface for Ollama
- Built-in RAG, document upload, and tool integration
- Includes RAG Optimizer and Document Manager tools

### MCP Proxy (`localhost:8200`)
- Exposes MCP tools via REST API
- Auto-generates OpenAPI documentation
- Default time server with timezone/date tools
- Easily extensible with additional MCP servers

## Prerequisites

- Docker and Docker Compose
- **NVIDIA GPU**: NVIDIA drivers + Container Toolkit
- **Apple Silicon**: Native Ollama macOS app installed

## Getting Started

### Download Models

**Via WebUI (Recommended):**
1. Open http://localhost:8080
2. Click model selector → type model name (`llama3.1`, `mistral`, `phi3`)
3. Wait for download

**Via Command Line:**
```bash
# Dockerized Ollama
docker exec ollama ollama pull llama3.1

# Native Ollama (Apple Silicon)
ollama pull llama3.1
```

### Hardware Configurations

| Configuration | Command | Use Case |
|---------------|---------|----------|
| **CPU Only** | `docker compose up -d` | Testing, light usage |
| **NVIDIA GPU** | `docker compose -f docker-compose.yml -f docker-compose.nvidia.yml up -d` | Heavy usage, faster inference |
| **Apple Silicon** | `docker compose -f docker-compose.yml -f docker-compose.apple.yml up -d` | M1/M2/M3 Macs (requires native Ollama) |

## Using MCP Tools

### Built-in Time Server
- Current time and timezone conversions
- Date calculations and formatting
- Test at http://localhost:8200/docs

### Adding MCP Servers
Modify the `mcp_proxy` service in `docker-compose.yml`:
```yaml
command: ["--port", "8000", "--api-key", "mcp-proxy-key", "--", "uvx", "your-mcp-server"]
```

Or use a config file approach. See [MCP documentation](https://docs.openwebui.com/openapi-servers/mcp/) for details.

### Integration
- **REST API**: Make HTTP requests to `http://localhost:8200`
- **Open WebUI**: Tools appear automatically in conversations
- **Custom Apps**: Use OpenAPI spec from `/docs` endpoint

## Extensions

Additional features are available as extensions in `./extensions/`:
- **Apache Tika**: Advanced document processing (1000+ formats)
- **TTS Services**: Text-to-speech capabilities
- **API Bridges**: OpenAI compatibility layers

This modular approach keeps the core stack lean while allowing you to add only what you need.

## Advanced Configuration

### Volumes
- `ollama_data`: Model storage (Docker Ollama only)
- `webui_data`: Open WebUI configuration and data

### Environment Variables
```yaml
# MCP Proxy
MCP_API_KEY: "your-api-key"

# Open WebUI
OLLAMA_API_BASE_URL: "http://ollama:11434"
```

### Resource Limits
Adjust in `docker-compose.yml`:
```yaml
ollama:
  mem_limit: 16g
  cpus: 8.0
```

## Troubleshooting

### Services Won't Start
```bash
docker info                    # Check Docker is running
docker compose logs           # Check service logs
docker compose restart webui  # Restart specific service
```

### MCP Proxy Issues
```bash
curl http://localhost:8200/docs     # Check health
docker compose logs mcp_proxy       # Check logs
docker compose restart mcp_proxy    # Restart service
```

### Models Not Downloading
1. Check internet connection
2. Try smaller models (`phi3:mini`)
3. Check disk space
4. Restart Ollama: `docker compose restart ollama`

### Apple Silicon Issues
- Ensure native Ollama app is running first
- Check connection: `curl http://localhost:11434`
- Models are stored in `~/.ollama/models`

## Integration with Development Tools

### Cursor IDE
1. Settings → Models
2. Base URL: `http://localhost:11434`
3. API Key: Leave blank

### Other Tools
Many AI tools support Ollama's API format. For OpenAI compatibility, check `./extensions/` for bridge services.

## Stopping the Stack

```bash
# Stop services
docker compose down

# Stop with hardware acceleration
docker compose -f docker-compose.yml -f docker-compose.nvidia.yml down

# Remove volumes too
docker compose down -v
```

---

**Ready to start?** Run `docker compose up -d` and visit http://localhost:8080!
