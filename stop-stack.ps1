#!/usr/bin/env pwsh
# Ollama Stack Shutdown Script

param(
    [Parameter(HelpMessage="Operating system type: 'auto', 'cpu', 'nvidia', or 'apple'")]
    [ValidateSet("auto", "cpu", "nvidia", "apple")]
    [Alias("o")]
    [string]$OperatingSystem = "auto",
    
    [Parameter(HelpMessage="Also remove Docker volumes (WARNING: deletes all data)")]
    [switch]$RemoveVolumes = $false
)

# Color output functions
function Write-Status {
    param($Message)
    Write-Host "[*] $Message" -ForegroundColor Blue
}

function Write-Success {
    param($Message)
    Write-Host "[+] $Message" -ForegroundColor Green
}

function Write-Error {
    param($Message)
    Write-Host "[-] $Message" -ForegroundColor Red
}

function Write-Warning {
    param($Message)
    Write-Host "[!] $Message" -ForegroundColor Yellow
}

# Hardware detection function
function Get-OperatingSystem {
    if ($OperatingSystem -ne "auto") {
        return $OperatingSystem
    }
    
    # Check for Apple Silicon
    if ($IsMacOS) {
        if ((uname -m) -eq "arm64") {
            return "apple"
        }
    }
    
    # Check for NVIDIA GPU
    if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) {
        if (nvidia-smi 2>$null) {
            return "nvidia"
        }
    }
    
    # Default to CPU
    return "cpu"
}

# Stop stack function
function Stop-Stack {
    param($OperatingSystemType)
    
    Write-Status "Stopping Ollama Stack ($OperatingSystemType configuration)..."
    
    # Build compose file arguments
    $ComposeFiles = @("-f", "docker-compose.yml")
    
    switch ($OperatingSystemType) {
        "nvidia" { $ComposeFiles += @("-f", "docker-compose.nvidia.yml") }
        "apple" { $ComposeFiles += @("-f", "docker-compose.apple.yml") }
    }
    
    # Build docker compose command
    $ComposeCommand = @("docker", "compose") + $ComposeFiles
    
    if ($RemoveVolumes) {
        Write-Warning "Removing volumes (all data will be deleted)..."
        $ComposeCommand += @("down", "-v")
    }
    else {
        $ComposeCommand += @("down")
    }
    
    # Execute the command
    if (& $ComposeCommand[0] $ComposeCommand[1..($ComposeCommand.Length-1)]) {
        Write-Success "Stack stopped successfully"
        if ($RemoveVolumes) {
            Write-Success "Volumes removed successfully"
        }
    }
    else {
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
    docker info | Out-Null
}
catch {
    Write-Error "Docker is not running or accessible"
    exit 1
}

# Detect operating system
$DETECTED_OS = Get-OperatingSystem
Write-Status "Detected operating system: $DETECTED_OS"

# Stop the stack
Stop-Stack $DETECTED_OS

Write-Host ""
Write-Success "Ollama Stack shutdown complete!" 