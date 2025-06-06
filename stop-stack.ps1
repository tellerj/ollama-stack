#!/usr/bin/env pwsh
# Ollama Stack Shutdown Script

param(
    [Parameter(Mandatory=$false)]
    [ValidateSet("auto", "cpu", "nvidia", "apple")]
    [string]$Platform = "auto",
    
    [Parameter(Mandatory=$false)]
    [switch]$RemoveVolumes,
    
    [Parameter(Mandatory=$false)]
    [switch]$Help
)

# Show help if requested
if ($Help) {
    Write-Host @"
Ollama Stack Shutdown Script

Usage: .\stop-stack.ps1 [options]

Options:
  -Platform TYPE    Platform type: auto, cpu, nvidia, apple (default: auto)
  -RemoveVolumes    Also remove Docker volumes (WARNING: deletes all data)
  -Help            Show this help message

Examples:
  .\stop-stack.ps1                      # Auto-detect and stop
  .\stop-stack.ps1 -Platform nvidia     # Force NVIDIA configuration
  .\stop-stack.ps1 -RemoveVolumes       # Stop and remove all data
"@
    exit 0
}

# Color output functions
function Write-Status {
    param([string]$Message)
    Write-Host "[*] $Message" -ForegroundColor Blue
}

function Write-Success {
    param([string]$Message)
    Write-Host "[+] $Message" -ForegroundColor Green
}

function Write-Error {
    param([string]$Message)
    Write-Host "[-] $Message" -ForegroundColor Red
}

function Write-Warning {
    param([string]$Message)
    Write-Host "[!] $Message" -ForegroundColor Yellow
}

# Platform detection function
function Get-Platform {
    if ($Platform -ne "auto") {
        return $Platform
    }
    
    # Check for Apple Silicon
    if ($IsMacOS) {
        if ((uname -m) -eq "arm64") {
            return "apple"
        }
    }
    
    # Check for NVIDIA GPU
    if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) {
        try {
            $null = nvidia-smi
            return "nvidia"
        } catch {
            # NVIDIA command failed, continue to CPU check
        }
    }
    
    # Default to CPU
    return "cpu"
}

# Function to stop native Ollama on Apple Silicon
function Stop-NativeOllama {
    Write-Status "Stopping native Ollama service..."
    
    # Try to stop using launchctl first (if installed via Homebrew)
    try {
        $ollamaService = launchctl list | Select-String "ollama"
        if ($ollamaService) {
            if (launchctl stop ollama) {
                Write-Success "Native Ollama service stopped successfully"
                return $true
            }
        }
    } catch {
        # launchctl command failed, continue to process check
    }
    
    # If launchctl fails or Ollama is not managed by it, try to kill the process
    try {
        $ollamaProcess = Get-Process -Name "ollama" -ErrorAction SilentlyContinue
        if ($ollamaProcess) {
            if (Stop-Process -Name "ollama" -Force) {
                Write-Success "Native Ollama process stopped successfully"
                return $true
            } else {
                Write-Error "Failed to stop native Ollama process"
                return $false
            }
        } else {
            Write-Status "Native Ollama is not running"
            return $true
        }
    } catch {
        Write-Error "Failed to stop native Ollama process"
        return $false
    }
}

# Stop stack function
function Stop-Stack {
    param(
        [string]$PlatformType
    )
    
    Write-Status "Stopping Ollama Stack ($PlatformType configuration)..."
    
    # Build compose file arguments
    $composeFiles = @("-f", "docker-compose.yml")
    
    switch ($PlatformType) {
        "nvidia" {
            $composeFiles += "-f", "docker-compose.nvidia.yml"
        }
        "apple" {
            $composeFiles += "-f", "docker-compose.apple.yml"
            # For Apple Silicon, we need to exclude the Ollama service
            $composeFiles += "--profile", "disabled-for-apple"
        }
    }
    
    # Build docker compose command
    $composeCmd = @("docker", "compose") + $composeFiles
    
    if ($RemoveVolumes) {
        Write-Warning "Removing volumes (all data will be deleted)..."
        $composeCmd += "down", "-v"
    } else {
        $composeCmd += "down"
    }
    
    # Execute the command
    try {
        & $composeCmd[0] $composeCmd[1..$composeCmd.Length]
        Write-Success "Stack stopped successfully"
        if ($RemoveVolumes) {
            Write-Success "Volumes removed successfully"
        }
    } catch {
        Write-Error "Failed to stop stack"
        exit 1
    }
}

# Main execution
Write-Host "OLLAMA STACK SHUTDOWN" -ForegroundColor Cyan
Write-Host ""

# Check if Docker is available and running
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error "Docker is not installed or not in PATH"
    exit 1
}

try {
    $null = docker info
} catch {
    Write-Error "Docker is not running or accessible"
    exit 1
}

# Detect platform if set to auto
$detectedPlatform = Get-Platform
if ($Platform -eq "auto") {
    $Platform = $detectedPlatform
    Write-Status "Auto-detected platform: $Platform"
} else {
    Write-Status "Using specified platform: $Platform"
}

# Stop the stack
Stop-Stack -PlatformType $Platform

# If on Apple Silicon, also stop the native Ollama service
if ($Platform -eq "apple") {
    Stop-NativeOllama
}

Write-Host ""
Write-Success "Ollama Stack shutdown complete!" 