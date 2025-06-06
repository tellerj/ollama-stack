#!/usr/bin/env pwsh
# Ollama Stack Installation Script (PowerShell)
# Installs the ollama-stack CLI tool for system-wide access on Windows

param(
    [switch]$Help
)

# Show help if requested
if ($Help) {
    Write-Host @"
Ollama Stack CLI Installation Script

Usage: .\install.ps1 [options]

Options:
  -Help            Show this help message

Examples:
  .\install.ps1                      # Install with automatic detection
"@
    exit 0
}

# Color output functions
function Write-Success {
    param([string]$Message)
    Write-Host "[+] $Message" -ForegroundColor Green
}

function Write-Info {
    param([string]$Message)
    Write-Host "[*] $Message" -ForegroundColor Blue
}

function Write-Warning {
    param([string]$Message)
    Write-Host "[!] $Message" -ForegroundColor Yellow
}

function Write-Error {
    param([string]$Message)
    Write-Host "[-] $Message" -ForegroundColor Red
}

# Get script directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$ToolPath = Join-Path (Split-Path -Parent $ScriptDir) "ollama-stack.ps1"

Write-Info "Ollama Stack CLI Installation (PowerShell)"
Write-Host ""

# Check if ollama-stack.ps1 exists
if (-not (Test-Path $ToolPath)) {
    Write-Error "ollama-stack.ps1 CLI tool not found at $ToolPath"
    exit 1
}

# Determine installation method
$installMethod = ""
$installPath = ""

# Check for PowerShell modules directory (user scope)
$userModulesPath = Join-Path $env:USERPROFILE "Documents\PowerShell\Modules\OllamaStack"
$systemModulesPath = Join-Path $env:ProgramFiles "PowerShell\Modules\OllamaStack"

# Check for common script directories
$userScriptsPath = Join-Path $env:USERPROFILE "bin"
$localBinPath = Join-Path $env:USERPROFILE ".local\bin"

# Determine best installation approach
if ($env:PATH -split ";" | Where-Object { $_ -like "*PowerShell*" }) {
    # PowerShell is in PATH, try module installation
    $installMethod = "module"
    $installPath = $userModulesPath
} elseif (Test-Path $userScriptsPath) {
    $installMethod = "script"
    $installPath = $userScriptsPath
} else {
    # Try to create user bin directory
    try {
        $installMethod = "script"
        $installPath = $userScriptsPath
        New-Item -ItemType Directory -Path $userScriptsPath -Force | Out-Null
    } catch {
        $installMethod = "manual"
    }
}

switch ($installMethod) {
    "module" {
        Write-Info "Installing as PowerShell module: $installPath"
        
        # Create module directory
        New-Item -ItemType Directory -Path $installPath -Force | Out-Null
        
        # Copy the script
        $moduleScript = Join-Path $installPath "ollama-stack.ps1"
        Copy-Item $ToolPath $moduleScript -Force
        
        # Create module manifest
        $manifestPath = Join-Path $installPath "OllamaStack.psd1"
        $manifestContent = @"
@{
    RootModule = 'ollama-stack.ps1'
    ModuleVersion = '1.0.0'
    GUID = 'a1b2c3d4-e5f6-7890-abcd-ef1234567890'
    Author = 'Ollama Stack Team'
    Description = 'Unified CLI tool for managing Ollama Stack and extensions'
    PowerShellVersion = '5.1'
    FunctionsToExport = @()
    CmdletsToExport = @()
    VariablesToExport = @()
    AliasesToExport = @()
}
"@
        $manifestContent | Set-Content $manifestPath
        
        Write-Success "Installed successfully as PowerShell module!"
        Write-Info "You can now use 'ollama-stack' from any PowerShell session"
        Write-Info "Usage: ollama-stack start"
    }
    "script" {
        Write-Info "Installing to user scripts directory: $installPath"
        
        # Copy the script
        $targetScript = Join-Path $installPath "ollama-stack.ps1"
        Copy-Item $ToolPath $targetScript -Force
        
        # Create a wrapper batch file for easier access
        $wrapperBat = Join-Path $installPath "ollama-stack.bat"
        $wrapperContent = @"
@echo off
powershell.exe -ExecutionPolicy Bypass -File "$targetScript" %*
"@
        $wrapperContent | Set-Content $wrapperBat
        
        Write-Success "Installed successfully!"
        
        # Check if user scripts path is in PATH
        $pathDirs = $env:PATH -split ";"
        if ($installPath -notin $pathDirs) {
            Write-Warning "$installPath is not in your PATH"
            Write-Info "To use 'ollama-stack' from anywhere, add it to your PATH:"
            Write-Host ""
            Write-Host "Option 1 - Temporary (current session):" -ForegroundColor Yellow
            Write-Host "`$env:PATH += `";$installPath`"" -ForegroundColor Yellow
            Write-Host ""
            Write-Host "Option 2 - Permanent (all sessions):" -ForegroundColor Yellow
            Write-Host "[Environment]::SetEnvironmentVariable('PATH', `$env:PATH + ';$installPath', 'User')" -ForegroundColor Yellow
            Write-Host ""
            Write-Host "Option 3 - GUI (recommended):" -ForegroundColor Yellow
            Write-Host "1. Press Win+R, type 'sysdm.cpl', press Enter" -ForegroundColor Yellow
            Write-Host "2. Click 'Environment Variables'" -ForegroundColor Yellow
            Write-Host "3. In User variables, select 'Path' and click 'Edit'" -ForegroundColor Yellow
            Write-Host "4. Click 'New' and add: $installPath" -ForegroundColor Yellow
            Write-Host "5. Click OK on all dialogs" -ForegroundColor Yellow
        } else {
            Write-Info "You can now use 'ollama-stack' from any command prompt"
        }
        
        Write-Info "Usage examples:"
        Write-Host "  ollama-stack.ps1 start" -ForegroundColor Cyan
        Write-Host "  ollama-stack start" -ForegroundColor Cyan -NoNewline
        Write-Host " (if PATH is configured)" -ForegroundColor Gray
    }
    "manual" {
        Write-Warning "Could not find a suitable installation directory"
        Write-Info "Manual installation options:"
        Write-Host ""
        Write-Info "Option 1 - Create user bin and add to PATH:"
        Write-Host "mkdir `$env:USERPROFILE\bin" -ForegroundColor Yellow
        Write-Host "copy `"$ToolPath`" `$env:USERPROFILE\bin\" -ForegroundColor Yellow
        Write-Host "`$env:PATH += `";`$env:USERPROFILE\bin`"" -ForegroundColor Yellow
        Write-Host ""
        Write-Info "Option 2 - Run as Administrator:"
        Write-Host "Right-click PowerShell → 'Run as Administrator' → re-run this script" -ForegroundColor Yellow
        Write-Host ""
        Write-Info "Option 3 - Use directly from project:"
        Write-Host ".\ollama-stack.ps1 start" -ForegroundColor Yellow
        Write-Host ""
        Write-Error "Installation failed - manual steps required above"
        Write-Host ""
        Write-Info "Until installed, use the tool directly from project directory:"
        Write-Host "  .\ollama-stack.ps1 start" -ForegroundColor Blue
        Write-Host "  .\ollama-stack.ps1 status" -ForegroundColor Blue
        exit 1
    }
}

Write-Host ""
Write-Info "Quick Start:"
Write-Host "  ollama-stack start                          # Start the stack" -ForegroundColor Blue
Write-Host "  ollama-stack extensions enable dia-tts-mcp  # Enable TTS extension" -ForegroundColor Blue
Write-Host "  ollama-stack extensions start dia-tts-mcp   # Start TTS extension" -ForegroundColor Blue
Write-Host "  ollama-stack status                         # Check status" -ForegroundColor Blue
Write-Host "  ollama-stack --help                         # Show help" -ForegroundColor Blue

# Check PowerShell execution policy
$executionPolicy = Get-ExecutionPolicy
if ($executionPolicy -eq "Restricted") {
    Write-Host ""
    Write-Warning "PowerShell execution policy is set to 'Restricted'"
    Write-Info "You may need to change it to run the ollama-stack script:"
    Write-Host "Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser" -ForegroundColor Yellow
    Write-Info "Or run with bypass: powershell -ExecutionPolicy Bypass -File ollama-stack.ps1"
}

Write-Host ""
Write-Success "Installation complete!"
Write-Info "Test the installation by running: ollama-stack --help" 