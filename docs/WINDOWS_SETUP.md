# Windows Setup Guide

Windows setup for Ollama Stack with PowerShell.

## Prerequisites

### Required
- Docker Desktop for Windows (WSL 2 backend enabled)
- PowerShell 5.1+ (included with Windows 10/11)
- Git for Windows (if cloning repository)

### Optional
- Windows Terminal
- HuggingFace token for AI model access

## Installation

### 1. Get the Code
```powershell
git clone https://github.com/your-repo/ollama-stack-1.git
cd ollama-stack-1
```

### 2. Install CLI Tool
```powershell
.\scripts\install.ps1
```

### 3. Configure PowerShell (if needed)
```powershell
# Check current policy
Get-ExecutionPolicy

# If "Restricted", change it
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### 4. Verify Installation
```powershell
ollama-stack --help
# OR: .\ollama-stack.ps1 --help
```

## Quick Start

```powershell
# Optional: Set HuggingFace token
$env:HF_TOKEN = "your_token_here"

# Start the stack
ollama-stack start

# Enable and start extension
ollama-stack extensions enable dia-tts-mcp
ollama-stack extensions start dia-tts-mcp

# Check status
ollama-stack status
```

Access web interface at http://localhost:8080

## Commands

### Platform Options
```powershell
ollama-stack start              # Auto-detect platform
ollama-stack start -p nvidia    # Force NVIDIA GPU
ollama-stack start -p cpu       # Force CPU-only
```

### Extension Management
```powershell
ollama-stack extensions list
ollama-stack extensions enable dia-tts-mcp
ollama-stack extensions start dia-tts-mcp
ollama-stack extensions logs dia-tts-mcp -f
```

### Using Without Installation
```powershell
.\ollama-stack.ps1 start
.\ollama-stack.ps1 extensions enable dia-tts-mcp
.\ollama-stack.ps1 status
```

## Platform Detection

The CLI automatically detects your hardware:
- Checks for `nvidia-smi.exe` → uses NVIDIA GPU acceleration
- Falls back to CPU if no GPU detected
- Override with `-p nvidia` or `-p cpu` if needed

## Docker Configuration

### Recommended Settings
- Use WSL 2 backend for better performance
- Increase memory limit to 16GB+ for AI workloads
- File sharing is usually automatic with WSL 2

### Verify Setup
```powershell
docker info
docker compose version
# For NVIDIA: docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi
```

## Troubleshooting

### Common Issues

**"Execution of scripts is disabled"**
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

**"ollama-stack command not found"**
```powershell
# Use full path or add to PATH
.\ollama-stack.ps1 start
$env:PATH += ";$env:USERPROFILE\bin"
```

**"Docker is not running"**
- Start Docker Desktop and wait for it to fully initialize

**Port conflicts**
```powershell
netstat -ano | findstr :8080  # Check what's using ports
```

### Getting Help
```powershell
ollama-stack --help
ollama-stack logs
ollama-stack status
``` 