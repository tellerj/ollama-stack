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
    Write-ColorOutput "==== $Message ====" -ForegroundColor White
}

function Write-Status {
    param([string]$Message)
    Write-ColorOutput "[*] $Message" -ForegroundColor Cyan
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

# Check for available updates
function Test-ForUpdates {
    param([string]$Platform)
    
    # Simple check: if images are older than 7 days, suggest update
    $oldImages = @()
    
    # Check core images based on platform  
    $imagesToCheck = @()
    if ($Platform -ne "apple") {
        $imagesToCheck += "ollama/ollama:latest"
    }
    $imagesToCheck += "ghcr.io/open-webui/open-webui:main", "ghcr.io/open-webui/mcpo:main"
    
    foreach ($image in $imagesToCheck) {
        try {
            # Check if image is older than 7 days using CreatedSince
            $imageInfo = docker images --format "table {{.Repository}}:{{.Tag}}`t{{.CreatedSince}}" 2>$null | Where-Object { $_ -match [regex]::Escape($image) }
            if ($imageInfo -and ($imageInfo -match "[8-9] days ago|[1-9][0-9] days ago|[1-9] weeks ago|[1-9] months ago")) {
                $serviceName = ($image -split '/')[1..999] -join '/' -replace ':.*', ''
                $oldImages += $serviceName
            }
        } catch {
            # Ignore errors when checking for updates
        }
    }
    
    # Display simple notification if old images found
    if ($oldImages.Count -gt 0) {
        Write-Warning "Some images may have updates available"
        Write-Status "Run 'ollama-stack.ps1 update' to get the latest versions"
    }
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
        Write-Status "Still waiting... ($elapsed/$MaxWaitSeconds seconds)"
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
            Write-Status "Using NVIDIA GPU acceleration"
        }
        "apple" {
            Write-Status "Using Apple Silicon configuration"
            Write-Warning "Make sure native Ollama app is running!"
        }
        "cpu" {
            Write-Status "Using CPU-only configuration"
        }
    }
    
    # Start core stack
    Write-Status "Starting core stack..."
    
    # Pull latest images if update flag is set
    if ($autoUpdate) {
        Write-Status "Pulling latest images..."
        try {
            $pullCmd = @("docker", "compose") + $composeFiles + @("pull")
            & $pullCmd[0] $pullCmd[1..($pullCmd.Length-1)] 2>$null
        } catch {
            Write-Warning "Failed to pull some images, continuing with existing images..."
        }
    }
    
    $composeCmd = @("docker", "compose") + $composeFiles + @("up", "-d")
    $result = & $composeCmd[0] $composeCmd[1..($composeCmd.Length-1)] 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to start core stack: $result"
        exit 1
    }
    
    # Wait for services
    Write-Status "Waiting for core services..."
    
    # Always check Ollama health - it's required for Open WebUI
    if (-not (Wait-ForService -ServiceName "Ollama" -Url "http://localhost:11434")) {
        Write-Error "Ollama failed to start"
        exit 1
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
    Write-Status "Services:"
    Write-Success "  • Open WebUI: http://localhost:8080"
    Write-Success "  • Ollama API: http://localhost:11434"
    Write-Success "  • MCP Proxy: http://localhost:8200"
    Write-Success "  • MCP Docs: http://localhost:8200/docs"
    Write-Success "Ready! Visit http://localhost:8080 to get started."
    
    # Check for updates if we didn't just update
    if (-not $autoUpdate) {
        Test-ForUpdates -Platform $platform
    }
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
    
    # Check for zombie containers from other installations
    try {
        $currentContainers = @()
        $composeContainers = docker compose ps -q 2>$null
        if ($composeContainers) {
            foreach ($containerId in $composeContainers) {
                $containerName = docker inspect --format '{{.Name}}' $containerId 2>$null
                if ($containerName) {
                    $currentContainers += $containerName.TrimStart('/')
                }
            }
        }
        
        $allContainers = docker ps -a --format "{{.Names}}" 2>$null | Where-Object { $_ -match "(webui|ollama|mcp_proxy)" }
        $zombieContainers = @()
        
        foreach ($container in $allContainers) {
            if ($container -and $container -notin $currentContainers) {
                $zombieContainers += $container
            }
        }
        
        if ($zombieContainers.Count -gt 0) {
            Write-Warning "Found containers from other installations:"
            foreach ($container in $zombieContainers) {
                $status = docker ps -a --format "{{.Status}}" --filter "name=$container" 2>$null
                $ports = docker ps -a --format "{{.Ports}}" --filter "name=$container" 2>$null
                Write-Status "  • $container ($status) $ports"
            }
            Write-Status "Use 'ollama-stack.ps1 cleanup' to remove orphaned resources"
            Write-Host ""
        }
    } catch {
        # Ignore errors in zombie detection
    }
    
    # Check core services
    Write-Status "Core Services:"
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
    
    # Check for orphaned volumes
    try {
        $allOllamaVolumes = docker volume ls --format "{{.Name}}" 2>$null | Where-Object { $_ -match "(ollama|webui)" -and $_ -notmatch "ollama-stack-1" }
        if ($allOllamaVolumes.Count -gt 0) {
            Write-Warning "Found volumes from other installations:"
            $allOllamaVolumes | ForEach-Object { Write-Host "  $_" }
            Write-Status "Use 'ollama-stack.ps1 cleanup --volumes' to remove them"
            Write-Host ""
        }
    } catch {
        # Ignore errors in volume detection
    }
    
    # Check extensions
    Write-Status "Extensions:"
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
        $statusIcon = "[DISABLED]"
        $statusText = "disabled"
        
        if ($enabled) {
            $statusIcon = "[ENABLED]"
            $statusText = "enabled"
            
            # Check if running
            try {
                $runningContainers = docker ps --format "table {{.Names}}" 2>$null
                if ($runningContainers -match "^$extName$") {
                    $statusIcon = "[RUNNING]"
                    $statusText = "running"
                }
            } catch {
                # Ignore docker errors
            }
        }
        
        Write-Status "  $statusIcon $extName ($statusText)"
        
        # Get description
        $configFile = Join-Path $_.FullName "mcp-config.json"
        if (Test-Path $configFile) {
            try {
                $config = Get-Content $configFile | ConvertFrom-Json
                if ($config.description) {
                    Write-Status "      $($config.description)"
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
            
            Write-Status "Name: $($config.displayName)"
            Write-Status "Version: $($config.version)"
            Write-Status "Type: $($config.type)"
            Write-Status "Description: $($config.description)"
            
            # MCP info
            $mcp = $config.mcp
            $caps = $mcp.capabilities
            Write-Status "MCP Configuration:"
            Write-Status "  Server Name: $($mcp.serverName)"
            Write-Status "  Transport: $($mcp.transport)"
            Write-Status "  Tools: $(if ($caps.tools) { 'Yes' } else { 'No' })"
            Write-Status "  Resources: $(if ($caps.resources) { 'Yes' } else { 'No' })"
            Write-Status "  Prompts: $(if ($caps.prompts) { 'Yes' } else { 'No' })"
            
            # Platform support
            Write-Status "Platform Support:"
            $config.platforms.PSObject.Properties | ForEach-Object {
                $platform = $_.Name
                $info = $_.Value
                $supported = if ($info.supported) { 'Yes' } else { 'No' }
                $perf = $info.performance
                Write-Status "  $platform`: $supported (performance: $perf)"
            }
            
            # Requirements
            if ($config.requirements) {
                Write-Status "Requirements:"
                $config.requirements.PSObject.Properties | ForEach-Object {
                    $req = $_.Name
                    $desc = $_.Value
                    if ($desc -is [PSCustomObject] -and $desc.description) {
                        $reqText = $desc.description
                        $required = if ($desc.required) { " (required)" } else { "" }
                        Write-Status "  $req`: $reqText$required"
                    } else {
                        Write-Status "  $req`: $desc"
                    }
                }
            }
        } catch {
            Write-Error "Error reading config: $($_.Exception.Message)"
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
    
    Write-Status "Status:"
    Write-Status "  Enabled: $(if ($enabled) { 'Yes' } else { 'No' })"
    Write-Status "  Running: $(if ($running -eq 'Yes') { 'Yes' } else { 'No' })"
}

function Invoke-Uninstall {
    param([string[]]$Args)
    
    $force = $false
    $removeVolumes = $false
    $removeImages = $false
    
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
            "--remove-images" {
                $removeImages = $true
            }
            default {
                Write-Error "Unknown option: $($Args[$i])"
                Write-Host "Usage: ollama-stack.ps1 uninstall [--force] [--remove-volumes] [--remove-images]"
                exit 1
            }
        }
        $i++
    }
    
    Write-Header "Ollama Stack Uninstall"
    
    # Detect if we're running from an installed location
    $isInstalled = $false
    $installType = ""
    $installPath = ""
    $projectPath = ""
    
    # Check common installation locations
    $userLocalShare = Join-Path $env:USERPROFILE ".local\share\ollama-stack"
    $programFilesPath = Join-Path $env:ProgramFiles "ollama-stack"
    
    if ($ScriptDir -eq $userLocalShare -or $ScriptDir -eq $programFilesPath) {
        $isInstalled = $true
        $projectPath = $ScriptDir
        if ($ScriptDir -eq $programFilesPath) {
            $installType = "system"
            $installPath = Join-Path $env:ProgramFiles "ollama-stack\ollama-stack.bat"
        } else {
            $installType = "user"
            $installPath = Join-Path $env:USERPROFILE ".local\bin\ollama-stack.bat"
        }
    }
    
    if (-not $force) {
        Write-Warning "This will completely remove the Ollama Stack:"
        Write-Status "  • Stop all running containers"
        Write-Status "  • Remove all containers"
        if ($removeImages) {
            Write-Status "  • Remove all Docker images"
        } else {
            Write-Success "  • Keep Docker images (faster future installs)"
        }
        Write-Status "  • Remove Docker network"
        if ($removeVolumes) {
            Write-Error "  • Remove all volumes (DELETES ALL DATA!)"
        } else {
            Write-Success "  • Keep volumes (data preserved)"
        }
        Write-Status "  • Disable all extensions"
        
        if ($isInstalled) {
            Write-Status "  • Remove installation files"
            Write-Status "  • Remove ollama-stack command"
            Write-Status "  • Clean up PATH modifications"
        }
        
        $response = Read-Host "Are you sure you want to continue? (y/N)"
        if ($response -notmatch "^[Yy]$") {
            Write-Success "Uninstall cancelled."
            exit 0
        }
    }
    
    # Stop all services first
    Write-Status "Stopping all services..."
    Invoke-Stop @("--platform", "auto")
    
    # Stop and remove extension containers
    Write-Status "Stopping and removing extension containers..."
    $extensionDirs = Get-ChildItem $ExtensionsDir -Directory -ErrorAction SilentlyContinue
    foreach ($extensionDir in $extensionDirs) {
        $extension = $extensionDir.Name
        $dockerCompose = Join-Path $extensionDir.FullName "docker-compose.yml"
        if (Test-Path $dockerCompose) {
            Write-Status "  Removing extension: $extension"
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
            Update-Registry -Extension $extension -Action "disable"
        }
    }
    
    # Remove main stack containers
    Write-Status "Removing main stack containers..."
    try {
        docker compose down --remove-orphans 2>$null | Out-Null
    } catch {
        # Ignore errors
    }
    
    # Remove images if requested
    if ($removeImages) {
        Write-Status "Removing Docker images..."
        $imagesToRemove = @(
            "ollama/ollama",
            "ghcr.io/open-webui/open-webui",
            "ghcr.io/open-webui/mcpo"
        )
        
        foreach ($image in $imagesToRemove) {
            try {
                $existingImages = docker images --format "table {{.Repository}}:{{.Tag}}" 2>$null
                if ($existingImages -match "^$([regex]::Escape($image))") {
                    Write-Status "  Removing image: $image"
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
                    Write-Status "  Removing extension image: $extension"
                    $imageIds = docker images "$extension" -q 2>$null
                    if ($imageIds) {
                        docker rmi $imageIds 2>$null | Out-Null
                    }
                }
            } catch {
                # Ignore errors
            }
        }
    } else {
        Write-Status "Keeping Docker images for faster future installs..."
    }
    
    # Remove volumes
    if ($removeVolumes) {
        Write-Status "Removing volumes..."
        $volumesToRemove = @(
            "ollama_data",
            "webui_data"
        )
        
        foreach ($volume in $volumesToRemove) {
            try {
                $existingVolumes = docker volume ls --format "table {{.Name}}" 2>$null
                if ($existingVolumes -match "^$([regex]::Escape($volume))$") {
                    Write-Status "  Removing volume: $volume"
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
                        Write-Status "  Removing extension volume: $volume"
                        docker volume rm $volume.Trim() 2>$null | Out-Null
                    }
                }
            } catch {
                # Ignore errors
            }
        }
    }
    
    # Remove network
    Write-Status "Removing Docker network..."
    try {
        $existingNetworks = docker network ls --format "table {{.Name}}" 2>$null
        if ($existingNetworks -match "^ollama-stack-network$") {
            docker network rm ollama-stack-network 2>$null | Out-Null
        }
    } catch {
        # Ignore errors
    }
    
    # Clean up any remaining containers
    Write-Status "Cleaning up remaining containers..."
    try {
        docker container prune -f 2>$null | Out-Null
    } catch {
        # Ignore errors
    }
    
    # Clean up installation files if installed
    if ($isInstalled) {
        Write-Status "Removing installation files..."
        
        # Remove the wrapper batch file
        if (Test-Path $installPath) {
            Write-Status "  Removing command: $installPath"
            try {
                Remove-Item $installPath -Force -ErrorAction Stop
            } catch {
                Write-Warning "    Warning: Could not remove $installPath"
            }
        }
        
        # Clean up PATH modifications
        if ($installType -eq "user") {
            Write-Status "  Cleaning up PATH modifications"
            $userBinDir = Split-Path $installPath
            
            try {
                # Get current user PATH
                $currentPath = [Environment]::GetEnvironmentVariable('PATH', 'User')
                if ($currentPath -and $currentPath.Contains($userBinDir)) {
                    Write-Status "    Removing from user PATH"
                    $newPath = ($currentPath -split ';' | Where-Object { $_ -ne $userBinDir }) -join ';'
                    [Environment]::SetEnvironmentVariable('PATH', $newPath, 'User')
                }
                
                # Update current session PATH
                $env:PATH = ($env:PATH -split ';' | Where-Object { $_ -ne $userBinDir }) -join ';'
            } catch {
                Write-Warning "    Warning: Could not clean up PATH modifications"
            }
        }
        
        # Remove project files
        if (Test-Path $projectPath) {
            Write-Status "  Removing project files: $projectPath"
            
            # Create a cleanup script to remove the project directory after this script exits
            $cleanupScript = Join-Path $env:TEMP "ollama-stack-cleanup-$PID.bat"
            $cleanupContent = @"
@echo off
timeout /t 2 /nobreak >nul
rmdir /s /q "$projectPath" 2>nul
del "$cleanupScript" 2>nul
"@
            $cleanupContent | Set-Content $cleanupScript
            Start-Process -FilePath $cleanupScript -WindowStyle Hidden
        }
    }
    
    Write-Success "Ollama Stack uninstall completed!"
    if (-not $removeVolumes) {
        Write-Warning "Note: Data volumes were preserved. Use 'docker volume ls' to see them."
    }
    
    if ($isInstalled) {
        Write-Success "Installation files removed!"
        Write-Warning "Note: Restart your terminal to clear command cache."
    }
}

function Invoke-Cleanup {
    param([string[]]$Args)
    
    $removeVolumes = $false
    $force = $false
    
    # Parse arguments
    $i = 0
    while ($i -lt $Args.Length) {
        switch ($Args[$i]) {
            "--volumes" {
                $removeVolumes = $true
            }
            { $_ -in @("-f", "--force") } {
                $force = $true
            }
            default {
                Write-Error "Unknown option: $($Args[$i])"
                Write-Host "Usage: ollama-stack.ps1 cleanup [--volumes] [--force]"
                exit 1
            }
        }
        $i++
    }
    
    Write-Header "Ollama Stack Cleanup"
    
    # Check Docker
    try {
        $null = docker info 2>$null
    } catch {
        Write-Error "Docker is not running"
        return
    }
    
    # Find all ollama-stack related containers (including stopped ones)
    $allContainers = docker ps -a --format "{{.Names}}" 2>$null | Where-Object { $_ -match "(webui|ollama|mcp_proxy)" }
    $currentContainers = @()
    
    try {
        $composeContainers = docker compose ps -q 2>$null
        if ($composeContainers) {
            foreach ($containerId in $composeContainers) {
                $containerName = docker inspect --format '{{.Name}}' $containerId 2>$null
                if ($containerName) {
                    $currentContainers += $containerName.TrimStart('/')
                }
            }
        }
    } catch {
        # Ignore errors
    }
    
    # Find zombie containers (not managed by current compose)
    $zombieContainers = @()
    foreach ($container in $allContainers) {
        if ($container -and $container -notin $currentContainers) {
            $zombieContainers += $container
        }
    }
    
    # Find orphaned volumes
    $orphanedVolumes = docker volume ls --format "{{.Name}}" 2>$null | Where-Object { $_ -match "(ollama|webui)" -and $_ -notmatch "ollama-stack-1" }
    
    # Find orphaned networks
    $orphanedNetworks = docker network ls --format "{{.Name}}" 2>$null | Where-Object { $_ -match "ollama" -and $_ -ne "ollama-stack-network" }
    
    if ($zombieContainers.Count -eq 0 -and $orphanedVolumes.Count -eq 0 -and $orphanedNetworks.Count -eq 0) {
        Write-Success "No orphaned ollama-stack resources found!"
        return
    }
    
    Write-Warning "Found orphaned ollama-stack resources:"
    
    if ($zombieContainers.Count -gt 0) {
        Write-Status "Containers from other installations:"
        foreach ($container in $zombieContainers) {
            $status = docker ps -a --format "{{.Status}}" --filter "name=$container" 2>$null
            Write-Status "  • $container ($status)"
        }
    }
    
    if ($orphanedVolumes.Count -gt 0 -and $removeVolumes) {
        Write-Error "Volumes to remove (THIS WILL DELETE DATA!):"
        foreach ($volume in $orphanedVolumes) {
            Write-Error "  • $volume"
        }
    } elseif ($orphanedVolumes.Count -gt 0) {
        Write-Status "Volumes found (use --volumes to remove):"
        foreach ($volume in $orphanedVolumes) {
            Write-Status "  • $volume"
        }
    }
    
    if ($orphanedNetworks.Count -gt 0) {
        Write-Status "Networks to remove:"
        foreach ($network in $orphanedNetworks) {
            Write-Status "  • $network"
        }
    }
    
    if (-not $force) {
        Write-Host ""
        $response = Read-Host "Remove these orphaned resources? (y/N)"
        if ($response -notmatch "^[Yy]$") {
            Write-Success "Cleanup cancelled."
            exit 0
        }
    }
    
    # Remove zombie containers
    if ($zombieContainers.Count -gt 0) {
        Write-Status "Removing orphaned containers..."
        foreach ($container in $zombieContainers) {
            Write-Status "  Stopping and removing: $container"
            try {
                docker stop $container 2>$null | Out-Null
                docker rm $container 2>$null | Out-Null
            } catch {
                # Ignore errors
            }
        }
    }
    
    # Remove orphaned volumes if requested
    if ($orphanedVolumes.Count -gt 0 -and $removeVolumes) {
        Write-Status "Removing orphaned volumes..."
        foreach ($volume in $orphanedVolumes) {
            Write-Status "  Removing volume: $volume"
            try {
                docker volume rm $volume 2>$null | Out-Null
            } catch {
                # Ignore errors
            }
        }
    }
    
    # Remove orphaned networks
    if ($orphanedNetworks.Count -gt 0) {
        Write-Status "Removing orphaned networks..."
        foreach ($network in $orphanedNetworks) {
            Write-Status "  Removing network: $network"
            try {
                docker network rm $network 2>$null | Out-Null
            } catch {
                # Ignore errors
            }
        }
    }
    
    Write-Success "Cleanup completed!"
    
    if ($orphanedVolumes.Count -gt 0 -and -not $removeVolumes) {
        Write-Warning "Note: Volumes were preserved. Use 'ollama-stack.ps1 cleanup --volumes' to remove them."
    }
}

function Invoke-Update {
    param([string[]]$Args)
    
    $platform = "auto"
    $force = $false
    
    # Parse arguments
    $i = 0
    while ($i -lt $Args.Length) {
        switch ($Args[$i]) {
            { $_ -in @("-p", "--platform") } {
                if ($i + 1 -ge $Args.Length) {
                    Write-Error "Platform option requires a value"
                    exit 1
                }
                $platform = $Args[$i + 1]
                if ($platform -notin @("auto", "cpu", "nvidia", "apple")) {
                    Write-Error "Platform must be 'auto', 'cpu', 'nvidia', or 'apple'"
                    exit 1
                }
                $i += 2
            }
            { $_ -in @("-f", "--force") } {
                $force = $true
                $i++
            }
            default {
                Write-Error "Unknown option: $($Args[$i])"
                Write-Host "Usage: ollama-stack.ps1 update [-p|--platform TYPE] [-f|--force]"
                exit 1
            }
        }
    }
    
    Write-Header "Updating Ollama Stack"
    
    # Detect platform
    if ($platform -eq "auto") {
        $platform = Get-Platform
        Write-Status "Auto-detected platform: $platform"
    } else {
        Write-Status "Using specified platform: $platform"
    }
    
    Test-DockerRunning
    
    # Get compose files
    $composeFiles = Get-ComposeFiles $platform
    
    # Check if stack is running
    $runningContainers = 0
    try {
        $psCmd = @("docker", "compose") + $composeFiles + @("ps", "-q")
        $runningOutput = & $psCmd[0] $psCmd[1..($psCmd.Length-1)] 2>$null
        if ($runningOutput) {
            $runningContainers = ($runningOutput | Measure-Object).Count
        }
    } catch {
        # Ignore errors
    }
    
    $wasRunning = $runningContainers -gt 0
    
    if ($wasRunning) {
        if (-not $force) {
            Write-Warning "The stack is currently running. This update will:"
            Write-Status "  • Stop all running containers"
            Write-Status "  • Pull latest Docker images"
            Write-Status "  • Restart with updated images"
            Write-Success "  • Keep all data volumes (no data loss)"
            
            $response = Read-Host "Continue with update? (y/N)"
            if ($response -notmatch "^[Yy]$") {
                Write-Success "Update cancelled."
                exit 0
            }
        }
        
        Write-Status "Stopping running containers..."
        $downCmd = @("docker", "compose") + $composeFiles + @("down")
        & $downCmd[0] $downCmd[1..($downCmd.Length-1)] 2>$null | Out-Null
    }
    
    # Pull latest images
    Write-Status "Pulling latest images..."
    $imagesToUpdate = @(
        "ollama/ollama:latest",
        "ghcr.io/open-webui/open-webui:main",
        "ghcr.io/open-webui/mcpo:main"
    )
    
    $pullFailed = $false
    foreach ($image in $imagesToUpdate) {
        Write-Status "  Pulling $image..."
        try {
            docker pull $image 2>$null | Out-Null
            if ($LASTEXITCODE -ne 0) {
                Write-Warning "Failed to pull $image"
                $pullFailed = $true
            }
        } catch {
            Write-Warning "Failed to pull $image"
            $pullFailed = $true
        }
    }
    
    # Also pull using compose (in case there are platform-specific overrides)
    Write-Status "Pulling images via compose..."
    try {
        $pullCmd = @("docker", "compose") + $composeFiles + @("pull")
        & $pullCmd[0] $pullCmd[1..($pullCmd.Length-1)] 2>$null | Out-Null
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "Some compose images failed to pull, continuing with available images..."
        }
    } catch {
        Write-Warning "Some compose images failed to pull, continuing with available images..."
    }
    
    # Update extensions if any are enabled
    Write-Status "Updating enabled extensions..."
    $extensionDirs = Get-ChildItem $ExtensionsDir -Directory -ErrorAction SilentlyContinue
    foreach ($extensionDir in $extensionDirs) {
        $extension = $extensionDir.Name
        $dockerCompose = Join-Path $extensionDir.FullName "docker-compose.yml"
        if ((Test-Path $dockerCompose) -and (Test-ExtensionEnabled $extension)) {
            Write-Status "  Updating extension: $extension"
            $originalLocation = Get-Location
            try {
                Set-Location $extensionDir.FullName
                docker compose pull 2>$null | Out-Null
                if ($LASTEXITCODE -ne 0) {
                    Write-Warning "Failed to pull $extension images"
                }
            } catch {
                Write-Warning "Failed to pull $extension images"
            } finally {
                Set-Location $originalLocation
            }
        }
    }
    
    if ($wasRunning) {
        Write-Status "Restarting stack with updated images..."
        $upCmd = @("docker", "compose") + $composeFiles + @("up", "-d")
        $result = & $upCmd[0] $upCmd[1..($upCmd.Length-1)] 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-Error "Failed to restart stack after update: $result"
            exit 1
        }
        
        # Wait for services to be ready
        Write-Status "Waiting for services to be ready..."
        
        # Always check Ollama health - it's required for Open WebUI
        Wait-ForService "Ollama" "http://localhost:11434"
        
        Wait-ForService "Open WebUI" "http://localhost:8080"
        Wait-ForService "MCP Proxy" "http://localhost:8200/docs"
        
        # Restart enabled extensions
        foreach ($extensionDir in $extensionDirs) {
            $extension = $extensionDir.Name
            $dockerCompose = Join-Path $extensionDir.FullName "docker-compose.yml"
            if ((Test-Path $dockerCompose) -and (Test-ExtensionEnabled $extension)) {
                Write-Status "  Restarting extension: $extension"
                $originalLocation = Get-Location
                try {
                    Set-Location $extensionDir.FullName
                    docker compose up -d 2>$null | Out-Null
                    if ($LASTEXITCODE -ne 0) {
                        Write-Warning "Failed to restart $extension"
                    }
                } catch {
                    Write-Warning "Failed to restart $extension"
                } finally {
                    Set-Location $originalLocation
                }
            }
        }
    }
    
    Write-Success "Update completed successfully!"
    
    if ($pullFailed) {
        Write-Warning "Note: Some images failed to update. Check your internet connection and try again."
    }
    
    if ($wasRunning) {
        Write-Status "Updated services are now running:"
        Write-Success "  • Open WebUI: http://localhost:8080"
        Write-Success "  • Ollama API: http://localhost:11434"
        Write-Success "  • MCP Proxy: http://localhost:8200"
    } else {
        Write-Status "Images updated. Run 'ollama-stack.ps1 start' to use the updated stack."
    }
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
    update               Update to latest versions
    cleanup              Remove orphaned containers and resources
    uninstall            Completely remove the stack and installation

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

    update:
        -p, --platform TYPE      Platform: auto, cpu, nvidia, apple (default: auto)
        -f, --force             Skip confirmation prompt

    cleanup:
        --volumes               Also remove orphaned volumes (DELETES DATA!)
        -f, --force             Skip confirmation prompt

    uninstall:
        -f, --force             Skip confirmation prompt
        --remove-volumes        Remove data volumes (deletes all data)
        --remove-images         Remove Docker images (forces re-download)
                               Note: Also removes installation files and PATH modifications

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
    .\ollama-stack.ps1 start --update                 # Start and update to latest versions
    .\ollama-stack.ps1 stop --remove-volumes          # Stop and delete all data
    .\ollama-stack.ps1 update                         # Update to latest versions
    .\ollama-stack.ps1 update --force                 # Update without confirmation
    .\ollama-stack.ps1 cleanup                        # Remove orphaned containers/networks
    .\ollama-stack.ps1 cleanup --volumes              # Also remove orphaned volumes (DANGER!)
    .\ollama-stack.ps1 status                         # Show current status
    .\ollama-stack.ps1 logs -f                        # Follow all logs
    .\ollama-stack.ps1 logs webui                     # Show WebUI logs only
    .\ollama-stack.ps1 uninstall                      # Remove stack and installation (keeps data and images)
    .\ollama-stack.ps1 uninstall --remove-volumes     # Remove everything including all data (keeps images)
    .\ollama-stack.ps1 uninstall --remove-images      # Remove stack, installation, and Docker images
    .\ollama-stack.ps1 uninstall --remove-volumes --remove-images  # Remove everything completely

    .\ollama-stack.ps1 extensions list               # List all extensions
    .\ollama-stack.ps1 extensions enable dia-tts-mcp # Enable TTS extension
    .\ollama-stack.ps1 extensions start dia-tts-mcp  # Start TTS extension
    .\ollama-stack.ps1 extensions logs dia-tts-mcp -f # Follow TTS logs

ACCESS POINTS:
    Open WebUI: http://localhost:8080
    Ollama API: http://localhost:11434
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
        "update" {
            Invoke-Update $Arguments
        }
        "cleanup" {
            Invoke-Cleanup $Arguments
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