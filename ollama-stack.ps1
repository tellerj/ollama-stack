#!/usr/bin/env pwsh
# Ollama Stack - Unified CLI Tool (PowerShell)
# Combines stack management and extension management into a single interface

param(
    [Parameter(Position=0)]
    [string]$Command,
    
    [Parameter(Position=1, ValueFromRemainingArguments=$true)]
    [string[]]$Arguments
)

# Global variables
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$ExtensionsDir = Join-Path $ScriptDir "extensions"
$RegistryFile = Join-Path $ExtensionsDir "registry.json"

# Function to print colored output
function Write-ColorOutput {
    param(
        [string]$Message,
        [ConsoleColor]$ForegroundColor = [ConsoleColor]::White
    )
    Write-Host $Message -ForegroundColor $ForegroundColor
}

function Write-Header {
    param([string]$Message)
    Write-Host ""
    Write-ColorOutput "==== $Message ====" -ForegroundColor Cyan
}

function Write-Status {
    param([string]$Message)
    Write-ColorOutput "[*] $Message" -ForegroundColor Blue
}

function Write-Success {
    param([string]$Message)
    Write-ColorOutput "[+] $Message" -ForegroundColor Green
}

function Write-Error {
    param([string]$Message)
    Write-ColorOutput "[-] $Message" -ForegroundColor Red
}

function Write-Warning {
    param([string]$Message)
    Write-ColorOutput "[!] $Message" -ForegroundColor Yellow
}

# Platform detection
function Get-Platform {
    # Check for Apple Silicon
    if ($IsMacOS) {
        if ((uname -m) -eq "arm64") {
            return "apple"
        }
    }
    
    # Check for NVIDIA GPU
    if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) {
        try {
            $null = nvidia-smi 2>$null
            return "nvidia"
        } catch {
            # NVIDIA command failed, continue to CPU check
        }
    }
    
    # Default to CPU
    return "cpu"
}

# Check if Docker is running
function Test-DockerRunning {
    try {
        $null = docker info 2>$null
        return $true
    } catch {
        Write-Error "Docker is not running. Please start Docker and try again."
        exit 1
    }
}

# Wait for service health
function Wait-ForService {
    param(
        [string]$ServiceName,
        [string]$Url,
        [int]$MaxWaitSeconds = 120
    )
    
    Write-Status "Waiting for $ServiceName to be ready..."
    $elapsed = 0
    
    while ($elapsed -lt $MaxWaitSeconds) {
        try {
            $response = Invoke-WebRequest -Uri $Url -Method GET -TimeoutSec 5 -ErrorAction SilentlyContinue
            if ($response.StatusCode -eq 200) {
                Write-Success "$ServiceName ready!"
                return $true
            }
        } catch {
            # Service not ready yet
        }
        
        Start-Sleep -Seconds 5
        $elapsed += 5
        Write-ColorOutput "   Still waiting... ($elapsed/$MaxWaitSeconds seconds)" -ForegroundColor Gray
    }
    
    Write-Error "$ServiceName failed to start within $MaxWaitSeconds seconds"
    return $false
}

# Get compose files for platform
function Get-ComposeFiles {
    param([string]$Platform)
    
    $composeFiles = @("-f", "docker-compose.yml")
    
    switch ($Platform) {
        "nvidia" {
            $composeFiles += @("-f", "docker-compose.nvidia.yml")
        }
        "apple" {
            $composeFiles += @("-f", "docker-compose.apple.yml")
        }
    }
    
    return $composeFiles
}

# Extension management functions
function Get-Extensions {
    if (-not (Test-Path $RegistryFile)) {
        return @()
    }
    
    try {
        $data = Get-Content $RegistryFile | ConvertFrom-Json
        return $data.extensions.PSObject.Properties.Name
    } catch {
        return @()
    }
}

function Get-EnabledExtensions {
    if (-not (Test-Path $RegistryFile)) {
        return @()
    }
    
    try {
        $data = Get-Content $RegistryFile | ConvertFrom-Json
        return $data.enabled
    } catch {
        return @()
    }
}

function Test-ExtensionEnabled {
    param([string]$Extension)
    
    $enabled = Get-EnabledExtensions
    return $enabled -contains $Extension
}

function Update-Registry {
    param(
        [string]$Extension,
        [string]$Action  # enable or disable
    )
    
    try {
        if (Test-Path $RegistryFile) {
            $data = Get-Content $RegistryFile | ConvertFrom-Json
        } else {
            $data = @{
                version = "1.0"
                extensions = @{}
                enabled = @()
            }
        }
        
        $enabled = [System.Collections.ArrayList]$data.enabled
        
        if ($Action -eq "enable" -and $Extension -notin $enabled) {
            $null = $enabled.Add($Extension)
        } elseif ($Action -eq "disable" -and $Extension -in $enabled) {
            $null = $enabled.Remove($Extension)
        }
        
        $data.enabled = $enabled.ToArray()
        
        $data | ConvertTo-Json -Depth 10 | Set-Content $RegistryFile
    } catch {
        Write-Error "Failed to update registry: $($_.Exception.Message)"
    }
}

# Command implementations
function Invoke-Start {
    param([string[]]$Args)
    
    $platform = "auto"
    $skipModels = $false
    $autoUpdate = $false
    
    # Parse arguments
    for ($i = 0; $i -lt $Args.Length; $i++) {
        switch ($Args[$i]) {
            { $_ -in @("-p", "--platform") } {
                if ($i + 1 -lt $Args.Length) {
                    $platform = $Args[$i + 1]
                    if ($platform -notin @("auto", "cpu", "nvidia", "apple")) {
                        Write-Error "Platform must be 'auto', 'cpu', 'nvidia', or 'apple'"
                        exit 1
                    }
                    $i++
                } else {
                    Write-Error "Platform argument requires a value"
                    exit 1
                }
            }
            { $_ -in @("-s", "--skip-models") } {
                $skipModels = $true
            }
            { $_ -in @("-u", "--update") } {
                $autoUpdate = $true
            }
            default {
                Write-Error "Unknown option: $($Args[$i])"
                exit 1
            }
        }
    }
    
    Write-Header "Starting Ollama Stack"
    
    # Detect platform
    if ($platform -eq "auto") {
        $platform = Get-Platform
        Write-Status "Auto-detected platform: $platform"
    } else {
        Write-Status "Using specified platform: $platform"
    }
    
    Test-DockerRunning
    
    # Get compose files
    $composeFiles = Get-ComposeFiles -Platform $platform
    
    switch ($platform) {
        "nvidia" {
            Write-ColorOutput "Using NVIDIA GPU acceleration" -ForegroundColor Magenta
        }
        "apple" {
            Write-ColorOutput "Using Apple Silicon configuration" -ForegroundColor Magenta
            Write-Warning "Make sure native Ollama app is running!"
        }
        "cpu" {
            Write-ColorOutput "Using CPU-only configuration" -ForegroundColor Magenta
        }
    }
    
    # Start core stack
    Write-Status "Starting core stack..."
    $dockerCmd = @("docker", "compose") + $composeFiles + @("up", "-d")
    
    try {
        & $dockerCmd[0] $dockerCmd[1..($dockerCmd.Length-1)]
        if ($LASTEXITCODE -ne 0) {
            Write-Error "Failed to start core stack"
            exit 1
        }
    } catch {
        Write-Error "Failed to start core stack: $($_.Exception.Message)"
        exit 1
    }
    
    # Wait for services
    Write-Status "Waiting for core services..."
    
    if ($platform -ne "apple") {
        if (-not (Wait-ForService -ServiceName "Ollama" -Url "http://localhost:11434")) {
            Write-Error "Ollama failed to start"
            exit 1
        }
    }
    
    if (-not (Wait-ForService -ServiceName "Open WebUI" -Url "http://localhost:8080")) {
        Write-Error "Open WebUI failed to start"
        exit 1
    }
    
    if (-not (Wait-ForService -ServiceName "MCP Proxy" -Url "http://localhost:8200/docs")) {
        Write-Error "MCP Proxy failed to start"
        exit 1
    }
    
    Write-Header "Stack Started Successfully!"
    Write-ColorOutput "Services:" -ForegroundColor White
    Write-ColorOutput "  • Open WebUI: http://localhost:8080" -ForegroundColor Green
    if ($platform -ne "apple") {
        Write-ColorOutput "  • Ollama API: http://localhost:11434" -ForegroundColor Green
    }
    Write-ColorOutput "  • MCP Proxy: http://localhost:8200" -ForegroundColor Green
    Write-ColorOutput "  • MCP Docs: http://localhost:8200/docs" -ForegroundColor Green
    Write-Host ""
    Write-Success "Ready! Visit http://localhost:8080 to get started."
}

function Invoke-Stop {
    param([string[]]$Args)
    
    $platform = "auto"
    $removeVolumes = $false
    
    # Parse arguments
    for ($i = 0; $i -lt $Args.Length; $i++) {
        switch ($Args[$i]) {
            { $_ -in @("-p", "--platform") } {
                if ($i + 1 -lt $Args.Length) {
                    $platform = $Args[$i + 1]
                    $i++
                } else {
                    Write-Error "Platform argument requires a value"
                    exit 1
                }
            }
            { $_ -in @("-v", "--remove-volumes") } {
                $removeVolumes = $true
            }
            default {
                Write-Error "Unknown option: $($Args[$i])"
                exit 1
            }
        }
    }
    
    Write-Header "Stopping Ollama Stack"
    
    if ($platform -eq "auto") {
        $platform = Get-Platform
    }
    
    Test-DockerRunning
    
    # Get compose files
    $composeFiles = Get-ComposeFiles -Platform $platform
    
    # Build command
    $dockerCmd = @("docker", "compose") + $composeFiles
    
    if ($removeVolumes) {
        Write-Warning "Removing volumes (all data will be deleted)..."
        $dockerCmd += @("down", "-v")
    } else {
        $dockerCmd += @("down")
    }
    
    # Execute
    try {
        & $dockerCmd[0] $dockerCmd[1..($dockerCmd.Length-1)]
        if ($LASTEXITCODE -eq 0) {
            Write-Success "Stack stopped successfully"
            if ($removeVolumes) {
                Write-Success "Volumes removed successfully"
            }
        } else {
            Write-Error "Failed to stop stack"
            exit 1
        }
    } catch {
        Write-Error "Failed to stop stack: $($_.Exception.Message)"
        exit 1
    }
}

function Invoke-Status {
    Write-Header "Ollama Stack Status"
    
    # Check Docker
    try {
        $null = docker info 2>$null
    } catch {
        Write-Error "Docker is not running"
        return
    }
    
    # Check core services
    Write-ColorOutput "Core Services:" -ForegroundColor Cyan
    try {
        $services = docker compose ps --format "table {{.Service}}`t{{.Status}}`t{{.Ports}}" 2>$null
        if ($services) {
            $services | ForEach-Object { Write-Host $_ }
        } else {
            Write-Warning "No core services running"
        }
    } catch {
        Write-Warning "Failed to get service status"
    }
    
    # Check extensions
    Write-Host ""
    Write-ColorOutput "Extensions:" -ForegroundColor Cyan
    Invoke-ExtensionsList
}

function Invoke-Logs {
    param([string[]]$Args)
    
    $service = ""
    $follow = $false
    
    # Parse arguments
    for ($i = 0; $i -lt $Args.Length; $i++) {
        switch ($Args[$i]) {
            { $_ -in @("-f", "--follow") } {
                $follow = $true
            }
            default {
                $service = $Args[$i]
            }
        }
    }
    
    if ([string]::IsNullOrEmpty($service)) {
        # Show all logs
        if ($follow) {
            docker compose logs -f
        } else {
            docker compose logs
        }
    } else {
        # Show specific service logs
        if ($follow) {
            docker compose logs -f $service
        } else {
            docker compose logs $service
        }
    }
}

function Invoke-Extensions {
    param([string[]]$Args)
    
    if ($Args.Length -eq 0) {
        Write-Error "Extension subcommand required"
        Show-ExtensionsHelp
        exit 1
    }
    
    $subcommand = $Args[0]
    $remainingArgs = $Args[1..($Args.Length-1)]
    
    switch ($subcommand) {
        { $_ -in @("list", "ls") } {
            Invoke-ExtensionsList $remainingArgs
        }
        "enable" {
            Invoke-ExtensionsEnable $remainingArgs
        }
        "disable" {
            Invoke-ExtensionsDisable $remainingArgs
        }
        "start" {
            Invoke-ExtensionsStart $remainingArgs
        }
        "stop" {
            Invoke-ExtensionsStop $remainingArgs
        }
        "restart" {
            Invoke-ExtensionsRestart $remainingArgs
        }
        "logs" {
            Invoke-ExtensionsLogs $remainingArgs
        }
        "info" {
            Invoke-ExtensionsInfo $remainingArgs
        }
        default {
            Write-Error "Unknown extensions subcommand: $subcommand"
            Show-ExtensionsHelp
            exit 1
        }
    }
}

function Invoke-ExtensionsList {
    if (-not (Test-Path $ExtensionsDir)) {
        Write-Warning "Extensions directory not found"
        return
    }
    
    Get-ChildItem $ExtensionsDir -Directory | ForEach-Object {
        $extName = $_.Name
        
        # Skip non-extension directories
        if ($extName -in @("manage.sh", "registry.json")) {
            return
        }
        
        $enabled = Test-ExtensionEnabled $extName
        $statusIcon = "❌"
        $statusText = "disabled"
        
        if ($enabled) {
            $statusIcon = "✅"
            $statusText = "enabled"
            
            # Check if running
            try {
                $runningContainers = docker ps --format "table {{.Names}}" 2>$null
                if ($runningContainers -match "^$extName$") {
                    $statusIcon = "🟢"
                    $statusText = "running"
                }
            } catch {
                # Ignore docker errors
            }
        }
        
        Write-ColorOutput "  $statusIcon $extName ($statusText)" -ForegroundColor White
        
        # Get description
        $configFile = Join-Path $_.FullName "mcp-config.json"
        if (Test-Path $configFile) {
            try {
                $config = Get-Content $configFile | ConvertFrom-Json
                if ($config.description) {
                    Write-ColorOutput "      $($config.description)" -ForegroundColor Gray
                }
            } catch {
                # Ignore JSON errors
            }
        }
    }
}

function Invoke-ExtensionsEnable {
    param([string[]]$Args)
    
    if ($Args.Length -eq 0) {
        Write-Error "Extension name required"
        exit 1
    }
    
    $extension = $Args[0]
    
    if (-not (Test-Path (Join-Path $ExtensionsDir $extension))) {
        Write-Error "Extension '$extension' not found"
        exit 1
    }
    
    if (Test-ExtensionEnabled $extension) {
        Write-Warning "Extension '$extension' is already enabled"
        return
    }
    
    Update-Registry -Extension $extension -Action "enable"
    Write-Success "Extension '$extension' enabled"
}

function Invoke-ExtensionsDisable {
    param([string[]]$Args)
    
    if ($Args.Length -eq 0) {
        Write-Error "Extension name required"
        exit 1
    }
    
    $extension = $Args[0]
    
    if (-not (Test-ExtensionEnabled $extension)) {
        Write-Warning "Extension '$extension' is already disabled"
        return
    }
    
    # Stop if running
    try {
        $runningContainers = docker ps --format "table {{.Names}}" 2>$null
        if ($runningContainers -match "^$extension$") {
            Invoke-ExtensionsStop @($extension)
        }
    } catch {
        # Ignore docker errors
    }
    
    Update-Registry -Extension $extension -Action "disable"
    Write-Success "Extension '$extension' disabled"
}

function Invoke-ExtensionsStart {
    param([string[]]$Args)
    
    if ($Args.Length -eq 0) {
        Write-Error "Extension name required"
        exit 1
    }
    
    $extension = $Args[0]
    $platform = "auto"
    
    # Parse remaining arguments
    for ($i = 1; $i -lt $Args.Length; $i++) {
        switch ($Args[$i]) {
            { $_ -in @("-p", "--platform") } {
                if ($i + 1 -lt $Args.Length) {
                    $platform = $Args[$i + 1]
                    $i++
                } else {
                    Write-Error "Platform argument requires a value"
                    exit 1
                }
            }
            default {
                Write-Error "Unknown option: $($Args[$i])"
                exit 1
            }
        }
    }
    
    if (-not (Test-Path (Join-Path $ExtensionsDir $extension))) {
        Write-Error "Extension '$extension' not found"
        exit 1
    }
    
    if (-not (Test-ExtensionEnabled $extension)) {
        Write-Error "Extension '$extension' is not enabled. Enable it first with: ollama-stack extensions enable $extension"
        exit 1
    }
    
    # Detect platform
    if ($platform -eq "auto") {
        $platform = Get-Platform
    }
    
    Write-Status "Starting extension '$extension' with $platform configuration..."
    
    # Change to extension directory
    $originalLocation = Get-Location
    try {
        Set-Location (Join-Path $ExtensionsDir $extension)
        
        # Get compose files
        $composeFiles = @("-f", "docker-compose.yml")
        switch ($platform) {
            "nvidia" {
                if (Test-Path "docker-compose.nvidia.yml") {
                    $composeFiles += @("-f", "docker-compose.nvidia.yml")
                }
            }
            "apple" {
                if (Test-Path "docker-compose.apple.yml") {
                    $composeFiles += @("-f", "docker-compose.apple.yml")
                }
            }
        }
        
        # Start extension
        $dockerCmd = @("docker", "compose") + $composeFiles + @("up", "-d")
        
        & $dockerCmd[0] $dockerCmd[1..($dockerCmd.Length-1)]
        if ($LASTEXITCODE -eq 0) {
            Write-Success "Extension '$extension' started successfully"
        } else {
            Write-Error "Failed to start extension '$extension'"
            exit 1
        }
    } finally {
        Set-Location $originalLocation
    }
}

function Invoke-ExtensionsStop {
    param([string[]]$Args)
    
    if ($Args.Length -eq 0) {
        Write-Error "Extension name required"
        exit 1
    }
    
    $extension = $Args[0]
    
    Write-Status "Stopping extension '$extension'..."
    
    $originalLocation = Get-Location
    try {
        Set-Location (Join-Path $ExtensionsDir $extension)
        
        docker compose down
        if ($LASTEXITCODE -eq 0) {
            Write-Success "Extension '$extension' stopped successfully"
        } else {
            Write-Error "Failed to stop extension '$extension'"
            exit 1
        }
    } finally {
        Set-Location $originalLocation
    }
}

function Invoke-ExtensionsRestart {
    param([string[]]$Args)
    
    if ($Args.Length -eq 0) {
        Write-Error "Extension name required"
        exit 1
    }
    
    $extension = $Args[0]
    $remainingArgs = $Args[1..($Args.Length-1)]
    
    Invoke-ExtensionsStop @($extension)
    Invoke-ExtensionsStart (@($extension) + $remainingArgs)
}

function Invoke-ExtensionsLogs {
    param([string[]]$Args)
    
    if ($Args.Length -eq 0) {
        Write-Error "Extension name required"
        exit 1
    }
    
    $extension = $Args[0]
    $follow = $false
    
    # Parse remaining arguments
    for ($i = 1; $i -lt $Args.Length; $i++) {
        switch ($Args[$i]) {
            { $_ -in @("-f", "--follow") } {
                $follow = $true
            }
            default {
                Write-Error "Unknown option: $($Args[$i])"
                exit 1
            }
        }
    }
    
    $originalLocation = Get-Location
    try {
        Set-Location (Join-Path $ExtensionsDir $extension)
        
        if ($follow) {
            docker compose logs -f
        } else {
            docker compose logs
        }
    } finally {
        Set-Location $originalLocation
    }
}

function Invoke-ExtensionsInfo {
    param([string[]]$Args)
    
    if ($Args.Length -eq 0) {
        Write-Error "Extension name required"
        exit 1
    }
    
    $extension = $Args[0]
    
    if (-not (Test-Path (Join-Path $ExtensionsDir $extension))) {
        Write-Error "Extension '$extension' not found"
        exit 1
    }
    
    Write-Header "Extension Information: $extension"
    
    # Read MCP config
    $configFile = Join-Path $ExtensionsDir $extension "mcp-config.json"
    if (Test-Path $configFile) {
        try {
            $config = Get-Content $configFile | ConvertFrom-Json
            
            Write-Host "Name: $($config.displayName)"
            Write-Host "Version: $($config.version)"
            Write-Host "Type: $($config.type)"
            Write-Host "Description: $($config.description)"
            Write-Host ""
            
            # MCP info
            $mcp = $config.mcp
            $caps = $mcp.capabilities
            Write-Host "MCP Configuration:"
            Write-Host "  Server Name: $($mcp.serverName)"
            Write-Host "  Transport: $($mcp.transport)"
            Write-Host "  Tools: $(if ($caps.tools) { '✅' } else { '❌' })"
            Write-Host "  Resources: $(if ($caps.resources) { '✅' } else { '❌' })"
            Write-Host "  Prompts: $(if ($caps.prompts) { '✅' } else { '❌' })"
            Write-Host ""
            
            # Platform support
            Write-Host "Platform Support:"
            $config.platforms.PSObject.Properties | ForEach-Object {
                $platform = $_.Name
                $info = $_.Value
                $supported = if ($info.supported) { '✅' } else { '❌' }
                $perf = $info.performance
                Write-Host "  $platform`: $supported (performance: $perf)"
            }
            Write-Host ""
            
            # Requirements
            if ($config.requirements) {
                Write-Host "Requirements:"
                $config.requirements.PSObject.Properties | ForEach-Object {
                    $req = $_.Name
                    $desc = $_.Value
                    if ($desc -is [PSCustomObject] -and $desc.description) {
                        $reqText = $desc.description
                        $required = if ($desc.required) { " (required)" } else { "" }
                        Write-Host "  $req`: $reqText$required"
                    } else {
                        Write-Host "  $req`: $desc"
                    }
                }
                Write-Host ""
            }
        } catch {
            Write-Host "Error reading config: $($_.Exception.Message)"
        }
    }
    
    # Status
    $enabled = Test-ExtensionEnabled $extension
    $running = "No"
    try {
        $runningContainers = docker ps --format "table {{.Names}}" 2>$null
        if ($runningContainers -match "^$extension$") {
            $running = "Yes"
        }
    } catch {
        # Ignore docker errors
    }
    
    Write-ColorOutput "Status:" -ForegroundColor Cyan
    Write-ColorOutput "  Enabled: $(if ($enabled) { '✅ Yes' } else { '❌ No' })" -ForegroundColor White
    Write-ColorOutput "  Running: $(if ($running -eq 'Yes') { '🟢 Yes' } else { '🔴 No' })" -ForegroundColor White
}

function Invoke-Uninstall {
    param([string[]]$Args)
    
    $force = $false
    $removeVolumes = $false
    
    # Parse arguments
    $i = 0
    while ($i -lt $Args.Length) {
        switch ($Args[$i]) {
            { $_ -in @("-f", "--force") } {
                $force = $true
            }
            "--remove-volumes" {
                $removeVolumes = $true
            }
            default {
                Write-Error "Unknown option: $($Args[$i])"
                Write-Host "Usage: ollama-stack.ps1 uninstall [--force] [--remove-volumes]"
                exit 1
            }
        }
        $i++
    }
    
    Write-Header "Ollama Stack Uninstall"
    
    if (-not $force) {
        Write-ColorOutput "This will completely remove the Ollama Stack:" -ForegroundColor Yellow
        Write-ColorOutput "  • Stop all running containers" -ForegroundColor White
        Write-ColorOutput "  • Remove all containers" -ForegroundColor White
        Write-ColorOutput "  • Remove all Docker images" -ForegroundColor White
        Write-ColorOutput "  • Remove Docker network" -ForegroundColor White
        if ($removeVolumes) {
            Write-ColorOutput "  • Remove all volumes (DELETES ALL DATA!)" -ForegroundColor Red
        } else {
            Write-ColorOutput "  • Keep volumes (data preserved)" -ForegroundColor Green
        }
        Write-ColorOutput "  • Disable all extensions" -ForegroundColor White
        Write-Host ""
        
        $response = Read-Host "Are you sure you want to continue? (y/N)"
        if ($response -notmatch "^[Yy]$") {
            Write-ColorOutput "Uninstall cancelled." -ForegroundColor Green
            exit 0
        }
    }
    
    # Stop all services first
    Write-ColorOutput "Stopping all services..." -ForegroundColor Cyan
    Invoke-Stop @("--platform", "auto")
    
    # Stop and remove extension containers
    Write-ColorOutput "Stopping and removing extension containers..." -ForegroundColor Cyan
    $extensionDirs = Get-ChildItem $ExtensionsDir -Directory -ErrorAction SilentlyContinue
    foreach ($extensionDir in $extensionDirs) {
        $extension = $extensionDir.Name
        $dockerCompose = Join-Path $extensionDir.FullName "docker-compose.yml"
        if (Test-Path $dockerCompose) {
            Write-ColorOutput "  Removing extension: $extension" -ForegroundColor White
            $originalLocation = Get-Location
            try {
                Set-Location $extensionDir.FullName
                docker compose down --remove-orphans 2>$null | Out-Null
            } catch {
                # Ignore errors
            } finally {
                Set-Location $originalLocation
            }
            
            # Disable extension
            Disable-Extension $extension
        }
    }
    
    # Remove main stack containers
    Write-ColorOutput "Removing main stack containers..." -ForegroundColor Cyan
    try {
        docker compose down --remove-orphans 2>$null | Out-Null
    } catch {
        # Ignore errors
    }
    
    # Remove images
    Write-ColorOutput "Removing Docker images..." -ForegroundColor Cyan
    $imagesToRemove = @(
        "ollama/ollama",
        "ghcr.io/open-webui/open-webui",
        "ghcr.io/open-webui/mcpo"
    )
    
    foreach ($image in $imagesToRemove) {
        try {
            $existingImages = docker images --format "table {{.Repository}}:{{.Tag}}" 2>$null
            if ($existingImages -match "^$([regex]::Escape($image))") {
                Write-ColorOutput "  Removing image: $image" -ForegroundColor White
                $imageIds = docker images "$image" -q 2>$null
                if ($imageIds) {
                    docker rmi $imageIds 2>$null | Out-Null
                }
            }
        } catch {
            # Ignore errors
        }
    }
    
    # Remove extension images
    foreach ($extensionDir in $extensionDirs) {
        $extension = $extensionDir.Name
        try {
            $existingImages = docker images --format "table {{.Repository}}:{{.Tag}}" 2>$null
            if ($existingImages -match "^$([regex]::Escape($extension))") {
                Write-ColorOutput "  Removing extension image: $extension" -ForegroundColor White
                $imageIds = docker images "$extension" -q 2>$null
                if ($imageIds) {
                    docker rmi $imageIds 2>$null | Out-Null
                }
            }
        } catch {
            # Ignore errors
        }
    }
    
    # Remove volumes
    if ($removeVolumes) {
        Write-ColorOutput "Removing volumes..." -ForegroundColor Cyan
        $volumesToRemove = @(
            "ollama_data",
            "webui_data"
        )
        
        foreach ($volume in $volumesToRemove) {
            try {
                $existingVolumes = docker volume ls --format "table {{.Name}}" 2>$null
                if ($existingVolumes -match "^$([regex]::Escape($volume))$") {
                    Write-ColorOutput "  Removing volume: $volume" -ForegroundColor White
                    docker volume rm $volume 2>$null | Out-Null
                }
            } catch {
                # Ignore errors
            }
        }
        
        # Remove extension volumes
        foreach ($extensionDir in $extensionDirs) {
            $extension = $extensionDir.Name
            try {
                $existingVolumes = docker volume ls --format "table {{.Name}}" 2>$null
                $extensionVolumes = $existingVolumes | Where-Object { $_ -match "^$([regex]::Escape($extension))" }
                foreach ($volume in $extensionVolumes) {
                    if ($volume -and $volume.Trim()) {
                        Write-ColorOutput "  Removing extension volume: $volume" -ForegroundColor White
                        docker volume rm $volume.Trim() 2>$null | Out-Null
                    }
                }
            } catch {
                # Ignore errors
            }
        }
    }
    
    # Remove network
    Write-ColorOutput "Removing Docker network..." -ForegroundColor Cyan
    try {
        $existingNetworks = docker network ls --format "table {{.Name}}" 2>$null
        if ($existingNetworks -match "^ollama-stack-network$") {
            docker network rm ollama-stack-network 2>$null | Out-Null
        }
    } catch {
        # Ignore errors
    }
    
    # Clean up any remaining containers
    Write-ColorOutput "Cleaning up remaining containers..." -ForegroundColor Cyan
    try {
        docker container prune -f 2>$null | Out-Null
    } catch {
        # Ignore errors
    }
    
    Write-ColorOutput "✅ Ollama Stack uninstall completed!" -ForegroundColor Green
    if (-not $removeVolumes) {
        Write-ColorOutput "Note: Data volumes were preserved. Use 'docker volume ls' to see them." -ForegroundColor Yellow
    }
    
    Write-Host ""
    Write-ColorOutput "To remove Docker completely, run:" -ForegroundColor White
    Write-ColorOutput "  docker system prune -a --volumes" -ForegroundColor White
}

function Show-ExtensionsHelp {
    Write-Host @"
Available extension subcommands:
  list, ls       List all extensions
  enable <ext>   Enable an extension
  disable <ext>  Disable an extension
  start <ext>    Start an extension
  stop <ext>     Stop an extension
  restart <ext>  Restart an extension
  logs <ext>     View extension logs
  info <ext>     Show extension information
"@
}

function Show-Help {
    Write-Host @"
Ollama Stack - Unified CLI Tool

USAGE:
    ollama-stack.ps1 <COMMAND> [OPTIONS]

COMMANDS:
    start                Start the core stack
    stop                 Stop the core stack
    status               Show stack and extension status
    logs [service]       View logs (all services or specific service)
    extensions           Manage extensions
    uninstall            Completely remove the stack

STACK OPTIONS:
    start:
        -p, --platform TYPE      Platform: auto, cpu, nvidia, apple (default: auto)
        -s, --skip-models        Skip model download prompts
        -u, --update            Automatically update to latest versions

    stop:
        -p, --platform TYPE      Platform: auto, cpu, nvidia, apple (default: auto)
        -v, --remove-volumes     Remove volumes (WARNING: deletes all data)

    logs:
        -f, --follow            Follow logs in real-time

    uninstall:
        -f, --force             Skip confirmation prompt
        --remove-volumes        Remove data volumes (deletes all data)

EXTENSION COMMANDS:
    extensions list             List all extensions
    extensions enable <name>    Enable an extension
    extensions disable <name>   Disable an extension
    extensions start <name>     Start an extension
    extensions stop <name>      Stop an extension
    extensions restart <name>   Restart an extension
    extensions logs <name>      View extension logs
    extensions info <name>      Show extension information

EXTENSION OPTIONS:
    start/restart:
        -p, --platform TYPE      Platform: auto, cpu, nvidia, apple (default: auto)

    logs:
        -f, --follow            Follow logs in real-time

EXAMPLES:
    .\ollama-stack.ps1 start                          # Start with auto-detected platform
    .\ollama-stack.ps1 start -p nvidia                # Force NVIDIA GPU acceleration
    .\ollama-stack.ps1 stop --remove-volumes          # Stop and delete all data
    .\ollama-stack.ps1 status                         # Show current status
    .\ollama-stack.ps1 logs -f                        # Follow all logs
    .\ollama-stack.ps1 logs webui                     # Show WebUI logs only
    .\ollama-stack.ps1 uninstall                      # Remove stack (keeps data)
    .\ollama-stack.ps1 uninstall --remove-volumes     # Remove stack and delete all data

    .\ollama-stack.ps1 extensions list               # List all extensions
    .\ollama-stack.ps1 extensions enable dia-tts-mcp # Enable TTS extension
    .\ollama-stack.ps1 extensions start dia-tts-mcp  # Start TTS extension
    .\ollama-stack.ps1 extensions logs dia-tts-mcp -f # Follow TTS logs

ACCESS POINTS:
    Open WebUI: http://localhost:8080
    Ollama API: http://localhost:11434 (except Apple Silicon)
    MCP Proxy:  http://localhost:8200
    MCP Docs:   http://localhost:8200/docs

For more information, visit: https://github.com/your-repo/ollama-stack
"@
}

# Main command dispatcher
function Main {
    # Change to script directory
    Set-Location $ScriptDir
    
    if ([string]::IsNullOrEmpty($Command)) {
        Show-Help
        return
    }
    
    switch ($Command) {
        "start" {
            Invoke-Start $Arguments
        }
        "stop" {
            Invoke-Stop $Arguments
        }
        "status" {
            Invoke-Status
        }
        "logs" {
            Invoke-Logs $Arguments
        }
        { $_ -in @("extensions", "ext") } {
            Invoke-Extensions $Arguments
        }
        "uninstall" {
            Invoke-Uninstall $Arguments
        }
        { $_ -in @("help", "--help", "-h") } {
            Show-Help
        }
        default {
            Write-Error "Unknown command: $Command"
            Write-Host ""
            Show-Help
            exit 1
        }
    }
}

# Run main function
Main 