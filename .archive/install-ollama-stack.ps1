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

Usage: .\install-ollama-stack.ps1 [options]

Options:
  -Help            Show this help message

Examples:
  .\install-ollama-stack.ps1         # Install with automatic detection
"@
    exit 0
}

# Color output functions
function Write-Header {
    param([string]$Message)
    Write-Host ""
    Write-Host "==== $Message ====" -ForegroundColor White
}

function Write-Status {
    param([string]$Message)
    Write-Host "[*] $Message" -ForegroundColor Cyan
}

function Write-Success {
    param([string]$Message)
    Write-Host "[+] $Message" -ForegroundColor Green
}

function Write-Warning {
    param([string]$Message)
    Write-Host "[!] $Message" -ForegroundColor Yellow
}

function Write-Error {
    param([string]$Message)
    Write-Host "[-] $Message" -ForegroundColor Red
}

# Get script directory (now in project root)
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$ProjectDir = $ScriptDir
$ToolPath = Join-Path $ProjectDir "ollama-stack.ps1"

Write-Header "Ollama Stack CLI Installation (PowerShell)"

# Check if ollama-stack.ps1 exists
if (-not (Test-Path $ToolPath)) {
    Write-Error "ollama-stack.ps1 CLI tool not found at $ToolPath"
    exit 1
}

# Check for existing installations
$existingInstall = ""
try {
    $null = Get-Command ollama-stack -ErrorAction Stop
    $existingCommand = Get-Command ollama-stack
    $existingInstall = $existingCommand.Source
    Write-Warning "Found existing ollama-stack installation at: $existingInstall"
    
    Write-Host ""
    Write-Status "Current installation details:"
    Write-Status "  Command: $existingInstall"
    if ($existingCommand.CommandType -eq "Application") {
        $installDir = Split-Path $existingInstall
        Write-Status "  Install directory: $installDir"
    }
    
    Write-Host ""
    Write-Status "For most updates, you should use the update command instead:"
    Write-Success "  ollama-stack update    # Updates Docker images (Ollama, WebUI, etc.)"
    Write-Status "  ollama-stack --help    # See all available commands"
    
    Write-Host ""
    Write-Warning "The install script is only needed for CLI tool updates:"
    Write-Status "  • New ollama-stack script features"
    Write-Status "  • Updated docker-compose configurations"
    Write-Status "  • New extensions in the extensions/ directory"
    Write-Status "  • Bug fixes in the CLI tool itself"
    
    Write-Host ""
    Write-Warning "This will OVERWRITE the CLI installation files!"
    Write-Status "  • All scripts and compose files will be replaced"
    Write-Status "  • Extension configurations will be preserved"
    Write-Status "  • Running containers will NOT be affected"
    Write-Status "  • No backup will be created"
    
    Write-Host ""
    $response = Read-Host "Continue with CLI tool update? (y/N)"
    if ($response -notmatch "^[Yy]$") {
        Write-Status "CLI update cancelled."
        Write-Status "Run 'ollama-stack update' to update Docker images instead."
        exit 0
    }
    Write-Host ""
} catch {
    # Command not found - this is a new installation
}

# Determine installation method
$installMethod = ""
$installPath = ""
$projectInstallPath = ""

# Check for common installation directories
$userLocalSharePath = Join-Path $env:USERPROFILE ".local\share\ollama-stack"
$userBinPath = Join-Path $env:USERPROFILE ".local\bin"
$userScriptsPath = Join-Path $env:USERPROFILE "bin"

# Try different installation approaches
if (Test-Path $env:ProgramFiles) {
    # Try system installation (requires admin)
    try {
        $testFile = Join-Path $env:ProgramFiles "test-write"
        "test" | Out-File $testFile -ErrorAction Stop
        Remove-Item $testFile -ErrorAction SilentlyContinue
        
        $installMethod = "system"
        $installPath = Join-Path $env:ProgramFiles "ollama-stack\ollama-stack.bat"
        $projectInstallPath = Join-Path $env:ProgramFiles "ollama-stack"
    } catch {
        # Fall back to user installation
        $installMethod = "user"
        $installPath = Join-Path $userBinPath "ollama-stack.bat"
        $projectInstallPath = $userLocalSharePath
    }
} else {
    $installMethod = "user"
    $installPath = Join-Path $userBinPath "ollama-stack.bat"
    $projectInstallPath = $userLocalSharePath
}

# Create directories if needed
if ($installMethod -eq "user") {
    try {
        New-Item -ItemType Directory -Path $userBinPath -Force -ErrorAction Stop | Out-Null
        New-Item -ItemType Directory -Path (Split-Path $projectInstallPath) -Force -ErrorAction Stop | Out-Null
    } catch {
        $installMethod = "manual"
    }
}

switch ($installMethod) {
    "system" {
        Write-Status "Installing to system directory: $env:ProgramFiles"
        
        try {
            # Create project directory
            New-Item -ItemType Directory -Path $projectInstallPath -Force -ErrorAction Stop | Out-Null
            
            # Copy project files
            Write-Status "Copying project files to $projectInstallPath"
            $filesToCopy = @("ollama-stack", "ollama-stack.ps1", "docker-compose.yml", "docker-compose.apple.yml", "docker-compose.nvidia.yml", "extensions", "tools")
            foreach ($file in $filesToCopy) {
                $sourcePath = Join-Path $ProjectDir $file
                if (Test-Path $sourcePath) {
                    Copy-Item $sourcePath $projectInstallPath -Recurse -Force -ErrorAction Stop
                }
            }
            
            # Create wrapper batch file
            $wrapperContent = @"
@echo off
cd /d "$projectInstallPath"
powershell.exe -ExecutionPolicy Bypass -File "$projectInstallPath\ollama-stack.ps1" %*
"@
            $wrapperContent | Set-Content $installPath
            
            Write-Success "Installed successfully!"
            Write-Status "Project files: $projectInstallPath"
            Write-Status "Command: ollama-stack"
        } catch {
            Write-Error "Failed to install to system directory: $($_.Exception.Message)"
            Write-Status "Try running as Administrator or use manual installation"
            exit 1
        }
    }
    "user" {
        Write-Status "Installing to user directory: $(Split-Path $installPath)"
        
        try {
            # Create project directory
            New-Item -ItemType Directory -Path $projectInstallPath -Force -ErrorAction Stop | Out-Null
            
            # Copy project files  
            Write-Status "Copying project files to $projectInstallPath"
            $filesToCopy = @("ollama-stack", "ollama-stack.ps1", "docker-compose.yml", "docker-compose.apple.yml", "docker-compose.nvidia.yml", "extensions", "tools")
            foreach ($file in $filesToCopy) {
                $sourcePath = Join-Path $ProjectDir $file
                if (Test-Path $sourcePath) {
                    Copy-Item $sourcePath $projectInstallPath -Recurse -Force -ErrorAction Stop
                }
            }
            
            # Create wrapper batch file
            $wrapperContent = @"
@echo off
cd /d "$projectInstallPath"
powershell.exe -ExecutionPolicy Bypass -File "$projectInstallPath\ollama-stack.ps1" %*
"@
            $wrapperContent | Set-Content $installPath
            
            Write-Success "Installed successfully!"
            Write-Status "Project files: $projectInstallPath"
            
            # Check if user bin is in PATH
            $pathDirs = $env:PATH -split ";" | Where-Object { $_ }
            $userBinDir = Split-Path $installPath
            if ($userBinDir -notin $pathDirs) {
                Write-Warning "$userBinDir is not in your PATH"
                
                # Check if already in user PATH environment variable (avoid duplicates)
                $userPath = [Environment]::GetEnvironmentVariable('PATH', 'User')
                $userPathDirs = $userPath -split ";" | Where-Object { $_ }
                
                if ($userBinDir -notin $userPathDirs) {
                    # Add to PATH automatically
                    try {
                        Write-Status "Adding $userBinDir to user PATH..."
                        $newUserPath = if ($userPath) { "$userPath;$userBinDir" } else { $userBinDir }
                        [Environment]::SetEnvironmentVariable('PATH', $newUserPath, 'User')
                        
                        # Update current session PATH
                        $env:PATH += ";$userBinDir"
                        
                                                Write-Success "Added $userBinDir to user PATH"
                        Write-Status "PATH updated for current and future sessions"
                    } catch {
                        Write-Warning "Failed to update PATH automatically: $($_.Exception.Message)"
                        Write-Status "Please add manually using one of these options:"
                        
                        Write-Status "Option 1 - PowerShell:"
                        Write-Status "[Environment]::SetEnvironmentVariable('PATH', `$env:PATH + ';$userBinDir', 'User')"
                        
                        Write-Status "Option 2 - GUI:"
                        Write-Status "1. Press Win+R, type 'sysdm.cpl', press Enter"
                        Write-Status "2. Click 'Environment Variables'"
                        Write-Status "3. In User variables, select 'Path' and click 'Edit'"
                        Write-Status "4. Click 'New' and add: $userBinDir"
                        Write-Status "5. Click OK on all dialogs"
                    }
                } else {
                    Write-Status "$userBinDir already in user PATH"
                }
            } else {
                Write-Status "You can now use 'ollama-stack' from any command prompt"
            }
        } catch {
            Write-Error "Failed to install to user directory: $($_.Exception.Message)"
            $installMethod = "manual"
        }
    }
    "manual" {
        Write-Warning "Could not find a suitable installation directory"
        Write-Status "Manual installation options:"
        
        Write-Status "Option 1 - Create user installation:"
        Write-Status "mkdir `$env:USERPROFILE\.local\share\ollama-stack"
        Write-Status "mkdir `$env:USERPROFILE\.local\bin"
        Write-Status "copy '$ProjectDir\*' `$env:USERPROFILE\.local\share\ollama-stack\ -Recurse"
        Write-Status "@'`ncd /d `$env:USERPROFILE\.local\share\ollama-stack`npowershell.exe -ExecutionPolicy Bypass -File ollama-stack.ps1 %*`n'@ | Set-Content `$env:USERPROFILE\.local\bin\ollama-stack.bat"
        Write-Status "`$env:PATH += `";`$env:USERPROFILE\.local\bin`""
        
        Write-Status "Option 2 - Run as Administrator:"
        Write-Status "Right-click PowerShell → 'Run as Administrator' → re-run this script"
        
        Write-Status "Option 3 - Use directly from project:"
        Write-Status "cd '$ProjectDir'"
        Write-Status ".\ollama-stack.ps1 start"
        
        Write-Error "Installation failed - manual steps required above"
        
        Write-Status "Until installed, use the tool directly from project directory:"
        Write-Status "  cd $ProjectDir"
        Write-Status "  .\ollama-stack.ps1 start"
        Write-Status "  .\ollama-stack.ps1 status"
        exit 1
    }
}

if ($installMethod -ne "manual") {
    Write-Header "Quick Start"
    Write-Status "ollama-stack start                          # Start the stack"
    Write-Status "ollama-stack update                         # Update Docker images"
    Write-Status "ollama-stack extensions enable dia-tts-mcp  # Enable TTS extension"
    Write-Status "ollama-stack extensions start dia-tts-mcp   # Start TTS extension"
    Write-Status "ollama-stack status                         # Check status"
    Write-Status "ollama-stack --help                         # Show help"

    # Check PowerShell execution policy
    $executionPolicy = Get-ExecutionPolicy
    if ($executionPolicy -eq "Restricted") {
        Write-Warning "PowerShell execution policy is set to 'Restricted'"
        Write-Status "You may need to change it to run scripts:"
        Write-Status "Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser"
    }

    Write-Success "Installation complete!"
} 