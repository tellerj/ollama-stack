#!/usr/bin/env pwsh

param(
    [string]$Hardware = "auto",
    [switch]$RemoveVolumes = $false,
    [switch]$Help = $false
)

if ($Help) {
    Write-Host @"
Ollama Stack Shutdown Script

Usage: .\stop-stack.ps1 [options]

Options:
  -Hardware <type>     Hardware type: auto, cpu, nvidia, apple (default: auto)
  -RemoveVolumes       Also remove Docker volumes (WARNING: deletes all data)
  -Help               Show this help message

Examples:
  .\stop-stack.ps1                    # Auto-detect and stop
  .\stop-stack.ps1 -Hardware nvidia   # Stop NVIDIA configuration
  .\stop-stack.ps1 -RemoveVolumes     # Stop and remove all data
"@
    exit 0
}

function Write-Status {
    param([string]$Message, [string]$Color = "White")
    Write-Host "[*] $Message" -ForegroundColor $Color
}

function Write-Success {
    param([string]$Message)
    Write-Host "[+] $Message" -ForegroundColor Green
}

function Write-Error {
    param([string]$Message)
    Write-Host "[-] $Message" -ForegroundColor Red
}

function Get-Hardware {
    if ($Hardware -ne "auto") {
        return $Hardware
    }
    
    if ($IsWindows -or $env:OS -eq "Windows_NT") {
        try {
            $gpu = Get-WmiObject -Class Win32_VideoController | Where-Object { $_.Name -like "*NVIDIA*" }
            if ($gpu) { return "nvidia" }
        } catch {}
    } elseif ($IsMacOS -or (uname -s) -eq "Darwin") {
        $arch = uname -m
        if ($arch -eq "arm64") { return "apple" }
    } else {
        try {
            if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) { 
                nvidia-smi *>$null
                return "nvidia" 
            }
        } catch {}
    }
    
    return "cpu"
}

function Stop-Stack {
    param([string]$HardwareType)
    
    Write-Status "Stopping Ollama Stack ($HardwareType configuration)..."
    
    $composeFiles = @("docker-compose.yml")
    
    switch ($HardwareType) {
        "nvidia" { $composeFiles += "docker-compose.nvidia.yml" }
        "apple" { $composeFiles += "docker-compose.apple.yml" }
    }
    
    $composeArgs = @()
    foreach ($file in $composeFiles) {
        $composeArgs += "-f"
        $composeArgs += $file
    }
    
    if ($RemoveVolumes) {
        $composeArgs += "down"
        $composeArgs += "-v"
        Write-Host "[!] Removing volumes (all data will be deleted)..." -ForegroundColor Yellow
    } else {
        $composeArgs += "down"
    }
    
    try {
        & docker compose @composeArgs
        if ($LASTEXITCODE -eq 0) {
            Write-Success "Stack stopped successfully"
            if ($RemoveVolumes) {
                Write-Success "Volumes removed successfully"
            }
        } else {
            Write-Error "Failed to stop stack (exit code: $LASTEXITCODE)"
            exit 1
        }
    } catch {
        Write-Error "Error stopping stack: $_"
        exit 1
    }
}

# Main execution
Write-Host "OLLAMA STACK SHUTDOWN" -ForegroundColor Cyan
Write-Host ""

# Check Docker
try {
    docker info | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Docker is not running or accessible"
        exit 1
    }
} catch {
    Write-Error "Docker is not installed or accessible"
    exit 1
}

$detectedHardware = Get-Hardware
Write-Status "Detected hardware: $detectedHardware"

Stop-Stack -HardwareType $detectedHardware

Write-Host ""
Write-Success "Ollama Stack shutdown complete!" 