# Ollama Stack - Unified CLI Guide

The **Ollama Stack** now features a unified command-line interface that combines all stack management and extension functionality into a single, powerful tool.

## 🚀 **Quick Start**

### Installation

**Unix/macOS:**
```bash
# Make the CLI tool system-wide accessible
./scripts/install.sh

# Or use directly from the project directory
./ollama-stack --help
```

**Windows (PowerShell):**
```powershell
# Make the CLI tool system-wide accessible
.\scripts\install.ps1

# Or use directly from the project directory
.\ollama-stack.ps1 --help
```

### Basic Usage

**Unix/macOS:**
```bash
# Start the entire stack (auto-detects your platform)
ollama-stack start

# Enable and start the TTS extension
ollama-stack extensions enable dia-tts-mcp
ollama-stack extensions start dia-tts-mcp

# Check status
ollama-stack status

# Stop everything
ollama-stack stop
```

**Windows (PowerShell):**
```powershell
# Start the entire stack (auto-detects your platform)
ollama-stack start
# OR: .\ollama-stack.ps1 start

# Enable and start the TTS extension
ollama-stack extensions enable dia-tts-mcp
ollama-stack extensions start dia-tts-mcp

# Check status
ollama-stack status

# Stop everything
ollama-stack stop
```

## 📋 **Complete Command Reference**

### **Core Stack Management**

#### `ollama-stack start`
Start the core Ollama stack with automatic platform detection.

**Options:**
- `-p, --platform TYPE` - Force platform: `auto`, `cpu`, `nvidia`, `apple` (default: auto)
- `-s, --skip-models` - Skip model download prompts
- `-u, --update` - Automatically update to latest versions

**Examples:**
```bash
ollama-stack start                    # Auto-detect platform
ollama-stack start -p nvidia          # Force NVIDIA GPU acceleration
ollama-stack start -p apple           # Force Apple Silicon config
ollama-stack start -u                 # Start with auto-updates
```

#### `ollama-stack stop`
Stop the core Ollama stack.

**Options:**
- `-p, --platform TYPE` - Platform type (usually auto-detected)
- `-v, --remove-volumes` - **WARNING:** Deletes all data including models and chat history

**Examples:**
```bash
ollama-stack stop                     # Normal shutdown
ollama-stack stop --remove-volumes   # Nuclear option - deletes everything
```

#### `ollama-stack status`
Show the current status of all services and extensions.

**Example Output:**
```
==== Ollama Stack Status ====
Core Services:
SERVICE     STATUS          PORTS
ollama      Up 2 minutes    0.0.0.0:11434->11434/tcp
webui       Up 2 minutes    0.0.0.0:8080->8080/tcp
mcp_proxy   Up 2 minutes    0.0.0.0:8200->8000/tcp

Extensions:
  🟢 dia-tts-mcp (running)
      High-quality dialogue generation using Nari Labs Dia model
```

#### `ollama-stack logs`
View logs from services.

**Options:**
- `-f, --follow` - Follow logs in real-time
- `[service]` - Specific service name (optional)

**Examples:**
```bash
ollama-stack logs                     # Show all logs
ollama-stack logs -f                  # Follow all logs
ollama-stack logs webui               # Show only WebUI logs
ollama-stack logs ollama -f           # Follow Ollama logs
```

### **Extension Management**

#### `ollama-stack extensions list`
List all available extensions with their status.

**Aliases:** `ext list`, `extensions ls`

**Example Output:**
```
  🟢 dia-tts-mcp (running)
      High-quality dialogue generation using Nari Labs Dia model
  ❌ future-extension (disabled)
      Description of future extension
```

#### `ollama-stack extensions enable <name>`
Enable an extension (makes it available to start).

**Examples:**
```bash
ollama-stack extensions enable dia-tts-mcp
ollama-stack ext enable dia-tts-mcp        # Short alias
```

#### `ollama-stack extensions disable <name>`
Disable an extension (stops it if running and marks as disabled).

**Examples:**
```bash
ollama-stack extensions disable dia-tts-mcp
```

#### `ollama-stack extensions start <name>`
Start an enabled extension.

**Options:**
- `-p, --platform TYPE` - Platform: `auto`, `cpu`, `nvidia`, `apple` (default: auto)

**Examples:**
```bash
ollama-stack extensions start dia-tts-mcp           # Auto-detect platform
ollama-stack extensions start dia-tts-mcp -p nvidia # Force NVIDIA
```

#### `ollama-stack extensions stop <name>`
Stop a running extension.

**Examples:**
```bash
ollama-stack extensions stop dia-tts-mcp
```

#### `ollama-stack extensions restart <name>`
Restart an extension (stop + start).

**Options:**
- `-p, --platform TYPE` - Platform for restart

**Examples:**
```bash
ollama-stack extensions restart dia-tts-mcp
ollama-stack extensions restart dia-tts-mcp -p apple
```

#### `ollama-stack extensions logs <name>`
View logs from a specific extension.

**Options:**
- `-f, --follow` - Follow logs in real-time

**Examples:**
```bash
ollama-stack extensions logs dia-tts-mcp
ollama-stack extensions logs dia-tts-mcp -f
```

#### `ollama-stack extensions info <name>`
Show detailed information about an extension.

**Example Output:**
```
==== Extension Information: dia-tts-mcp ====
Name: Dia TTS
Version: 1.0.0
Type: mcp-server
Description: High-quality dialogue generation using Nari Labs Dia model

MCP Configuration:
  Server Name: dia-tts
  Transport: stdio
  Tools: ✅
  Resources: ✅
  Prompts: ✅

Platform Support:
  cpu: ✅ (performance: slow)
  nvidia: ✅ (performance: optimal)
  apple: ✅ (performance: good)

Requirements:
  hf_token: HuggingFace token for accessing Dia model (required)
  memory: 16GB
  gpu_memory: 10GB (recommended for optimal performance)

Status:
  Enabled: ✅ Yes
  Running: 🟢 Yes
```

## 🔄 **Common Workflows**

### **Complete Setup from Scratch**
```bash
# 1. Install CLI tool
./install.sh

# 2. Set required environment variables
export HF_TOKEN="your_huggingface_token_here"

# 3. Start everything
ollama-stack start

# 4. Enable and start TTS extension
ollama-stack extensions enable dia-tts-mcp
ollama-stack extensions start dia-tts-mcp

# 5. Verify everything is working
ollama-stack status
```

### **Daily Usage**
```bash
# Morning: Start your AI stack
ollama-stack start

# Work with your AI...

# Evening: Clean shutdown
ollama-stack stop
```

### **Development/Testing**
```bash
# Start with specific platform
ollama-stack start -p nvidia

# Monitor logs while developing
ollama-stack extensions logs dia-tts-mcp -f

# Restart extension after changes
ollama-stack extensions restart dia-tts-mcp

# Check what's running
ollama-stack status
```

### **Maintenance**
```bash
# Update all images and start
ollama-stack start -u

# Nuclear reset (deletes all data!)
ollama-stack stop --remove-volumes
ollama-stack start
```

## 🌐 **Access Points**

After starting with `ollama-stack start`, these services are available:

| Service | URL | Description |
|---------|-----|-------------|
| **Open WebUI** | http://localhost:8080 | Main chat interface |
| **Ollama API** | http://localhost:11434 | Direct model API (except Apple Silicon) |
| **MCP Proxy** | http://localhost:8200 | Extension proxy |
| **MCP Docs** | http://localhost:8200/docs | API documentation |

## 🔧 **Platform-Specific Behavior**

### **Apple Silicon (M1/M2/M3)**
- Uses native Ollama app (must be installed separately)
- Optimizes extensions for Metal Performance Shaders
- WebUI connects to host machine's Ollama

### **NVIDIA GPU**
- Enables CUDA acceleration for all services
- Best performance for AI workloads
- Requires nvidia-docker runtime

### **CPU-Only**
- Universal compatibility
- Slower performance but works everywhere
- Good for development and testing

## 🆚 **Migration from Old Scripts**

If you were using the old separate scripts, here's the migration:

| Old Command | New Command |
|-------------|-------------|
| `./start-stack.sh` | `ollama-stack start` |
| `./start-stack.sh -p nvidia` | `ollama-stack start -p nvidia` |
| `./stop-stack.sh` | `ollama-stack stop` |
| `./stop-stack.sh --remove-volumes` | `ollama-stack stop --remove-volumes` |
| `cd extensions && ./manage.sh list` | `ollama-stack extensions list` |
| `./manage.sh enable dia-tts-mcp` | `ollama-stack extensions enable dia-tts-mcp` |
| `./manage.sh start dia-tts-mcp` | `ollama-stack extensions start dia-tts-mcp` |
| `./manage.sh logs dia-tts-mcp -f` | `ollama-stack extensions logs dia-tts-mcp -f` |
| `docker compose ps` | `ollama-stack status` |

## 💡 **Tips & Tricks**

### **Aliases for Power Users**
Add these to your shell profile for even faster access:
```bash
alias os='ollama-stack'
alias ose='ollama-stack extensions'
alias oss='ollama-stack status'
alias osl='ollama-stack logs -f'
```

Then use:
```bash
os start              # Start stack
ose enable dia-tts-mcp # Enable extension
oss                   # Check status
osl                   # Follow all logs
```

### **Environment Setup**
```bash
# Create a startup script
cat > ~/start-ai.sh << 'EOF'
#!/bin/bash
export HF_TOKEN="your_token_here"
ollama-stack start
ollama-stack extensions start dia-tts-mcp
echo "🚀 AI Stack is ready at http://localhost:8080"
EOF

chmod +x ~/start-ai.sh
```

### **Monitoring**
```bash
# Watch status in real-time
watch -n 5 'ollama-stack status'

# Follow all logs with timestamps
ollama-stack logs -f | while read line; do echo "$(date): $line"; done
```

## 🔍 **Troubleshooting**

### **Common Issues**

**"Docker is not running"**
```bash
# Start Docker Desktop first, then:
ollama-stack start
```

**"Extension won't start"**
```bash
# Check if it's enabled first:
ollama-stack extensions info dia-tts-mcp

# Enable if needed:
ollama-stack extensions enable dia-tts-mcp

# Check logs for errors:
ollama-stack extensions logs dia-tts-mcp
```

**"Service failed to start"**
```bash
# Check overall status:
ollama-stack status

# View specific logs:
ollama-stack logs webui
ollama-stack logs ollama
```

### **Getting Help**
```bash
ollama-stack --help                    # General help
ollama-stack extensions --help         # Extension help (if implemented)
ollama-stack start --help              # Command-specific help (if implemented)
```

## 🎯 **Next Steps**

1. **Install the CLI:** Run `./install.sh`
2. **Set up environment:** Export your `HF_TOKEN`
3. **Start the stack:** `ollama-stack start`
4. **Enable extensions:** `ollama-stack extensions enable dia-tts-mcp`
5. **Start building:** Visit http://localhost:8080

The unified CLI makes managing your local AI stack effortless while maintaining all the powerful features of the individual scripts! 