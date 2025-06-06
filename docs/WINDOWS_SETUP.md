# Ollama Stack - Windows Setup Guide

This guide covers setting up and using the **Ollama Stack** on Windows with PowerShell.

## 🛠️ **Prerequisites**

### Required Software
1. **Docker Desktop for Windows**
   - Download from: https://docs.docker.com/desktop/install/windows/
   - Ensure WSL 2 backend is enabled
   - Start Docker Desktop before proceeding

2. **PowerShell 5.1+ or PowerShell Core 7+**
   - PowerShell 5.1 comes with Windows 10/11
   - For PowerShell Core: https://github.com/PowerShell/PowerShell

3. **Git for Windows** (if cloning the repository)
   - Download from: https://git-scm.com/download/win

### Optional but Recommended
- **Windows Terminal** for better PowerShell experience
- **HuggingFace Account** and token for AI model access

## 🚀 **Installation**

### Step 1: Get the Code
```powershell
# Clone the repository
git clone https://github.com/your-repo/ollama-stack-1.git
cd ollama-stack-1

# OR download and extract the ZIP file
```

### Step 2: Install the CLI Tool
```powershell
# Run the PowerShell installer
.\scripts\install.ps1

# The installer will:
# - Copy ollama-stack.ps1 to your user bin directory
# - Create a batch wrapper for easy access
# - Guide you through PATH configuration
```

### Step 3: Configure PowerShell Execution Policy (if needed)
```powershell
# Check current policy
Get-ExecutionPolicy

# If "Restricted", change it to allow script execution
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Confirm the change
Get-ExecutionPolicy
```

### Step 4: Verify Installation
```powershell
# Test the CLI tool
ollama-stack --help

# OR if PATH isn't configured yet:
.\ollama-stack.ps1 --help
```

## 🎯 **Quick Start**

### Complete Setup Workflow
```powershell
# 1. Set your HuggingFace token (required for AI models)
$env:HF_TOKEN = "your_huggingface_token_here"

# 2. Start the core stack
ollama-stack start

# 3. Enable the TTS extension
ollama-stack extensions enable dia-tts-mcp

# 4. Start the TTS extension
ollama-stack extensions start dia-tts-mcp

# 5. Check everything is running
ollama-stack status

# 6. Open your browser to http://localhost:8080
```

## 🔧 **Windows-Specific Commands**

### PowerShell Command Examples
```powershell
# Start with specific platform detection
ollama-stack start -p nvidia          # Force NVIDIA GPU
ollama-stack start -p cpu              # Force CPU-only

# View logs in real-time
ollama-stack logs -f

# Manage extensions
ollama-stack extensions list
ollama-stack extensions info dia-tts-mcp
ollama-stack extensions logs dia-tts-mcp -f

# Stop everything
ollama-stack stop

# Nuclear option (deletes all data)
ollama-stack stop --remove-volumes
```

### Using Without Installation
If you prefer not to install system-wide:
```powershell
# Use directly from the project directory
.\ollama-stack.ps1 start
.\ollama-stack.ps1 extensions enable dia-tts-mcp
.\ollama-stack.ps1 status
```

## 🔍 **Platform Detection on Windows**

The CLI automatically detects your hardware:

### NVIDIA GPU Detection
```powershell
# The script checks for nvidia-smi.exe
# If found and working, uses NVIDIA GPU acceleration
ollama-stack start  # Will auto-use GPU if available
```

### CPU Fallback
```powershell
# If no NVIDIA GPU detected, falls back to CPU
# This works on any Windows machine with Docker
```

### Force Platform Override
```powershell
# Override auto-detection if needed
ollama-stack start -p nvidia    # Force GPU even if not detected
ollama-stack start -p cpu       # Force CPU even with GPU available
```

## 🐳 **Docker Configuration**

### Windows-Specific Docker Settings

1. **WSL 2 Backend** (Recommended)
   - Better performance and compatibility
   - Required for some features

2. **Resource Allocation**
   - Increase memory limit in Docker Desktop settings
   - Recommended: 16GB+ for AI workloads

3. **File Sharing**
   - Ensure your project directory is accessible to Docker
   - Usually automatic with WSL 2

### Verify Docker Setup
```powershell
# Check Docker is running and accessible
docker info

# Test Docker Compose
docker compose version

# Check for NVIDIA GPU support (if applicable)
docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi
```

## 🔧 **Troubleshooting**

### Common Windows Issues

#### PowerShell Execution Policy
**Problem:** "Execution of scripts is disabled on this system"
```powershell
# Solution: Change execution policy
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

#### PATH Not Updated
**Problem:** "ollama-stack" command not found
```powershell
# Solution 1: Add to PATH temporarily
$env:PATH += ";$env:USERPROFILE\bin"

# Solution 2: Add to PATH permanently
[Environment]::SetEnvironmentVariable('PATH', $env:PATH + ";$env:USERPROFILE\bin", 'User')

# Solution 3: Use full path
.\ollama-stack.ps1 start
```

#### Docker Not Running
**Problem:** "Docker is not running"
```powershell
# Solution: Start Docker Desktop manually
# Check system tray for Docker icon
# Wait for Docker to fully start before running commands
```

#### Port Conflicts
**Problem:** "Port already in use"
```powershell
# Check what's using the ports
netstat -ano | findstr :8080
netstat -ano | findstr :11434

# Stop conflicting services or change ports in docker-compose.yml
```

#### WSL/Docker Integration Issues
**Problem:** Docker can't access files or has permission issues
```powershell
# Solution: Use WSL 2 and ensure Docker Desktop integration is enabled
# In Docker Desktop: Settings > Resources > WSL Integration
```

### Getting Help
```powershell
# Built-in help
ollama-stack --help
ollama-stack extensions --help

# Check logs for errors
ollama-stack logs
ollama-stack extensions logs dia-tts-mcp

# Verify system status
ollama-stack status
docker compose ps
```

## 🎨 **PowerShell Profile Integration**

### Add Aliases to Your Profile
```powershell
# Edit your PowerShell profile
notepad $PROFILE

# Add these lines for convenience:
Set-Alias os ollama-stack
Set-Alias ose 'ollama-stack extensions'
function oss { ollama-stack status }
function osl { ollama-stack logs -f }

# Save and reload profile
. $PROFILE
```

### Environment Variables
```powershell
# Add to your PowerShell profile for persistence
$env:HF_TOKEN = "your_token_here"

# Or set permanently
[Environment]::SetEnvironmentVariable('HF_TOKEN', 'your_token_here', 'User')
```

## 📊 **Performance Tips**

### Windows-Specific Optimizations

1. **Use NVIDIA GPU** if available
   ```powershell
   ollama-stack start -p nvidia
   ```

2. **Increase Docker Resources**
   - Memory: 16GB+ recommended
   - CPU: All available cores
   - Disk: SSD recommended

3. **Close Unnecessary Applications**
   - AI workloads are resource-intensive
   - Close browsers/games while using the stack

4. **Monitor Resource Usage**
   ```powershell
   # Check Docker stats
   docker stats

   # Check Windows performance
   Get-Counter "\Processor(_Total)\% Processor Time"
   ```

## 🔄 **Windows Service Integration** (Advanced)

### Running as Windows Service
For production use, you can run the stack as a Windows service:

```powershell
# Install NSSM (Non-Sucking Service Manager)
# Download from: https://nssm.cc/

# Create service (run as Administrator)
nssm install OllamaStack powershell.exe
nssm set OllamaStack Arguments "-ExecutionPolicy Bypass -File C:\path\to\ollama-stack.ps1 start"
nssm set OllamaStack DisplayName "Ollama Stack"
nssm set OllamaStack Description "Local AI Stack with Ollama and Extensions"

# Start the service
nssm start OllamaStack
```

## 🎯 **Next Steps**

1. **Complete the Quick Start** section above
2. **Install AI models** through the web interface at http://localhost:8080
3. **Explore extensions** with `ollama-stack extensions list`
4. **Read the main CLI_USAGE.md** for advanced features

## 🆘 **Getting Support**

### Before Asking for Help
1. Check Docker Desktop is running
2. Verify PowerShell execution policy
3. Try the direct script path: `.\ollama-stack.ps1`
4. Check logs: `ollama-stack logs`

### Information to Include
- Windows version
- PowerShell version (`$PSVersionTable`)
- Docker version (`docker version`)
- Error messages from logs
- Hardware specs (CPU, GPU, RAM)

The Windows PowerShell version provides the same powerful functionality as the Unix version with Windows-specific optimizations and troubleshooting! 