#!/usr/bin/env pwsh
# Ollama Stack Startup Script
# This script handles a complete cold start of the Ollama Core Stack

param(
    [Parameter(HelpMessage="Hardware configuration: 'cpu', 'nvidia', or 'apple'")]
    [ValidateSet("cpu", "nvidia", "apple")]
    [string]$Hardware = "cpu",
    
    [Parameter(HelpMessage="Skip model download prompts")]
    [switch]$SkipModels = $false,

    [Parameter(HelpMessage="Automatically update to latest versions")]
    [switch]$Update = $false
)

Write-Host "Starting Ollama Core Stack..." -ForegroundColor Green
Write-Host "Hardware: $Hardware" -ForegroundColor Cyan
Write-Host ""

# Function to check if Docker is running
function Test-DockerRunning {
    try {
        docker info | Out-Null
        return $true
    }
    catch {
        return $false
    }
}

# Function to wait for service health
function Wait-ForService {
    param($ServiceName, $Url, $MaxWaitSeconds = 120)
    
    Write-Host "Waiting for $ServiceName..." -ForegroundColor Yellow
    $elapsed = 0
    
    while ($elapsed -lt $MaxWaitSeconds) {
        try {
            $response = Invoke-WebRequest -Uri $Url -Method GET -TimeoutSec 5 -ErrorAction SilentlyContinue
            if ($response.StatusCode -eq 200) {
                Write-Host "$ServiceName ready!" -ForegroundColor Green
                return $true
            }
        }
        catch {
            # Service not ready yet
        }
        
        Start-Sleep -Seconds 5
        $elapsed += 5
        Write-Host "   Still waiting... ($elapsed/$MaxWaitSeconds seconds)" -ForegroundColor Gray
    }
    
    Write-Host "$ServiceName failed to start within $MaxWaitSeconds seconds" -ForegroundColor Red
    return $false
}

# Function to check for updates
function Test-ForUpdates {
    $ComposeFiles = @("-f", "docker-compose.yml")
    
    switch ($Hardware) {
        "nvidia" { $ComposeFiles += @("-f", "docker-compose.nvidia.yml") }
        "apple" { $ComposeFiles += @("-f", "docker-compose.apple.yml") }
    }

    Write-Host "Checking for updates..." -ForegroundColor Blue
    
    # Get current image versions from docker-compose config
    $config = docker compose $ComposeFiles config
    $updates = @()
    
    foreach ($line in $config) {
        if ($line -match '^\s*image:\s*([^:]+):([^\s]+)') {
            $image = $matches[1]
            $currentTag = $matches[2]
            
            # Get latest tag
            try {
                $manifest = docker manifest inspect "$image`:latest" 2>$null
                $latestTag = ($manifest | Select-String -Pattern '"tag":"([^"]*)"' | Select-Object -First 1).Matches.Groups[1].Value
                
                if ($latestTag -and $latestTag -ne $currentTag) {
                    $updates += "$image`: $currentTag -> $latestTag"
                }
            }
            catch {
                # Image might not exist or manifest inspect failed
                continue
            }
        }
    }

    if ($updates.Count -eq 0) {
        Write-Host "All services are up to date!" -ForegroundColor Green
        return $false
    }

    Write-Host "Updates available for the following services:" -ForegroundColor Yellow
    foreach ($update in $updates) {
        Write-Host "  - $update" -ForegroundColor White
    }
    Write-Host ""

    if ($Update) {
        Write-Host "Auto-update enabled, proceeding with updates..." -ForegroundColor Green
        return $true
    }

    $response = Read-Host "Would you like to update before starting? [y/N]"
    return $response -match '^[yY]$'
}

# Function to pull updates
function Update-Stack {
    $ComposeFiles = @("-f", "docker-compose.yml")
    
    switch ($Hardware) {
        "nvidia" { $ComposeFiles += @("-f", "docker-compose.nvidia.yml") }
        "apple" { $ComposeFiles += @("-f", "docker-compose.apple.yml") }
    }

    Write-Host "Pulling latest images..." -ForegroundColor Blue
    $pullCommand = @("docker", "compose") + $ComposeFiles + @("pull")
    
    if (-not (& $pullCommand[0] $pullCommand[1..($pullCommand.Length-1)])) {
        Write-Host "Failed to pull updates" -ForegroundColor Red
        exit 1
    }
    
    Write-Host "Updates pulled successfully!" -ForegroundColor Green
}

# Check prerequisites
Write-Host "Checking prerequisites..." -ForegroundColor Blue

if (-not (Test-DockerRunning)) {
    Write-Host "Docker is not running. Please start Docker Desktop and try again." -ForegroundColor Red
    exit 1
}

if (-not (Test-Path "docker-compose.yml")) {
    Write-Host "docker-compose.yml not found. Please run this script from the ollama-stack directory." -ForegroundColor Red
    exit 1
}

Write-Host "Prerequisites check passed!" -ForegroundColor Green
Write-Host ""

# Determine Docker Compose command based on hardware
$ComposeCommand = @("docker", "compose")
$ComposeFiles = @("-f", "docker-compose.yml")

switch ($Hardware) {
    "nvidia" {
        $ComposeFiles += @("-f", "docker-compose.nvidia.yml")
        Write-Host "Using NVIDIA GPU acceleration" -ForegroundColor Magenta
    }
    "apple" {
        $ComposeFiles += @("-f", "docker-compose.apple.yml")
        Write-Host "Using Apple Silicon configuration" -ForegroundColor Magenta
        Write-Host "Make sure native Ollama app is running!" -ForegroundColor Yellow
    }
    "cpu" {
        Write-Host "Using CPU-only configuration" -ForegroundColor Magenta
    }
}

# Check for updates
if (Test-ForUpdates) {
    Update-Stack
}

# Start core stack
Write-Host "Starting core stack..." -ForegroundColor Blue
$StartCommand = $ComposeCommand + $ComposeFiles + @("up", "-d")
& $StartCommand[0] $StartCommand[1..($StartCommand.Length-1)]

if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to start core stack" -ForegroundColor Red
    exit 1
}

# Wait for core services
Write-Host ""
Write-Host "Waiting for core services to be ready..." -ForegroundColor Blue

if ($Hardware -ne "apple") {
    if (-not (Wait-ForService "Ollama" "http://localhost:11434")) {
        Write-Host "Ollama failed to start" -ForegroundColor Red
        exit 1
    }
}

if (-not (Wait-ForService "Open WebUI" "http://localhost:8080")) {
    Write-Host "Open WebUI failed to start" -ForegroundColor Red
    exit 1
}

if (-not (Wait-ForService "MCP Proxy" "http://localhost:8200/docs")) {
    Write-Host "MCP Proxy failed to start" -ForegroundColor Red
    exit 1
}

# Display status
Write-Host ""
Write-Host "Ollama Core Stack is running!" -ForegroundColor Green
Write-Host ""
Write-Host "Services:" -ForegroundColor Cyan
Write-Host "  Open WebUI: http://localhost:8080" -ForegroundColor White

if ($Hardware -ne "apple") {
    Write-Host "  Ollama API: http://localhost:11434" -ForegroundColor White
}

Write-Host "  MCP Proxy: http://localhost:8200" -ForegroundColor White
Write-Host "  MCP Docs: http://localhost:8200/docs" -ForegroundColor White
Write-Host ""
Write-Host "Ready! Visit http://localhost:8080 to get started." -ForegroundColor Green 