# Ollama Stack CLI Installation Script for Windows
# Installs the ollama-stack command line tool

$ErrorActionPreference = "Stop"

# Print ASCII art logo
Write-Host ""
Write-Host " ██████╗ ██╗     ██╗      █████╗ ███╗   ███╗ █████╗    ███████╗████████╗ █████╗  ██████╗██╗  ██╗" -ForegroundColor Cyan
Write-Host "██╔═══██╗██║     ██║     ██╔══██╗████╗ ████║██╔══██╗   ██╔════╝╚══██╔══╝██╔══██╗██╔════╝██║ ██╔╝" -ForegroundColor Cyan
Write-Host "██║   ██║██║     ██║     ███████║██╔████╔██║███████║   ███████╗   ██║   ███████║██║     █████╔╝ " -ForegroundColor Cyan
Write-Host "██║   ██║██║     ██║     ██╔══██║██║╚██╔╝██║██╔══██║   ╚════██║   ██║   ██╔══██║██║     ██╔═██╗ " -ForegroundColor Cyan
Write-Host "╚██████╔╝███████╗███████╗██║  ██║██║ ╚═╝ ██║██║  ██║   ███████║   ██║   ██║  ██║╚██████╗██║  ██╗" -ForegroundColor Cyan
Write-Host " ╚═════╝ ╚══════╝╚══════╝╚═╝  ╚═╝╚═╝     ╚═╝╚═╝  ╚═╝   ╚══════╝   ╚═╝   ╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝" -ForegroundColor Cyan
Write-Host ""

Write-Host "🚀 Installing Ollama Stack CLI..." -ForegroundColor Green

# Check if we're in a virtual environment
if ($env:VIRTUAL_ENV) {
    Write-Host "⚠️  Warning: You are currently in a virtual environment ($env:VIRTUAL_ENV)" -ForegroundColor Yellow
    Write-Host "   This will install ollama-stack only within this virtual environment." -ForegroundColor Yellow
    Write-Host "   To install globally, please deactivate the virtual environment first:" -ForegroundColor Yellow
    Write-Host "   deactivate" -ForegroundColor Gray
    Write-Host ""
    $continueInVenv = Read-Host "Continue with virtual environment installation? (y/N)"
    if ($continueInVenv -notmatch "^[Yy]$") {
        Write-Host "Installation cancelled. Please deactivate the virtual environment and run again." -ForegroundColor Red
        exit 1
    }
}

# Check if Python is available
try {
    $null = Get-Command python -ErrorAction Stop
} catch {
    Write-Host "❌ Error: Python is required but not installed." -ForegroundColor Red
    Write-Host "   Please install Python 3.8 or later from https://python.org" -ForegroundColor Yellow
    Write-Host "   Make sure to check 'Add Python to PATH' during installation." -ForegroundColor Yellow
    exit 1
}

# Check Python version
try {
    $pythonVersion = python -c "import sys; print('.'.join(map(str, sys.version_info[:2])))"
    $minVersion = [Version]"3.8"
    $currentVersion = [Version]$pythonVersion
    
    if ($currentVersion -lt $minVersion) {
        Write-Host "❌ Error: Python 3.8 or later is required (found $pythonVersion)" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "❌ Error: Unable to determine Python version" -ForegroundColor Red
    exit 1
}

# Check if pip is available
try {
    $null = python -m pip --version 2>$null
} catch {
    Write-Host "❌ Error: pip is required but not available." -ForegroundColor Red
    Write-Host "   Please ensure Python was installed with pip." -ForegroundColor Yellow
    exit 1
}

# Check if this is an externally managed environment
$externallyManaged = $false
try {
    # Check if we're not in a virtual environment and if it's externally managed
    $venvCheck = python -c "import sys; sys.exit(0 if hasattr(sys, 'base_prefix') or hasattr(sys, 'real_prefix') else 1)" 2>$null
    if ($LASTEXITCODE -eq 1) {
        # Not in a virtual environment, check for externally managed
        $externallyManagedCheck = python -c "import sys; sys.exit(0 if hasattr(sys, 'stdlib_dir') and 'site-packages' in sys.stdlib_dir else 1)" 2>$null
        if ($LASTEXITCODE -eq 1) {
            $externallyManaged = $true
        }
    }
} catch {
    # Assume not externally managed if we can't determine
    $externallyManaged = $false
}

# Check if pipx is available
$usePipx = $false
try {
    $null = Get-Command pipx -ErrorAction Stop
    $usePipx = $true
} catch {
    $usePipx = $false
}

# Determine installation method
if ($externallyManaged -and -not $usePipx) {
    Write-Host "⚠️  Detected externally managed Python environment." -ForegroundColor Yellow
    Write-Host "   This system prevents system-wide pip installations for safety." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "   Options:" -ForegroundColor Cyan
    Write-Host "   1. Install pipx (recommended): pip install --user pipx" -ForegroundColor Gray
    Write-Host "   2. Force installation (not recommended): Use --break-system-packages" -ForegroundColor Gray
    Write-Host "   3. Use virtual environment" -ForegroundColor Gray
    Write-Host ""
    $installPipx = Read-Host "Install pipx first? (Y/n)"
    if ($installPipx -notmatch "^[Nn]$") {
        Write-Host "📦 Installing pipx..." -ForegroundColor Cyan
        try {
            python -m pip install --user pipx
            $usePipx = $true
        } catch {
            Write-Host "❌ Error: Failed to install pipx" -ForegroundColor Red
            exit 1
        }
    } else {
        Write-Host "⚠️  Proceeding with forced installation (not recommended)..." -ForegroundColor Yellow
    }
}

# Prompt user for installation type (only if not using pipx)
if (-not $usePipx) {
    Write-Host ""
    Write-Host "📦 Installation Type Selection:" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "🔧 Development Installation:" -ForegroundColor Yellow
    Write-Host "   - Creates a link to the source code" -ForegroundColor Gray
    Write-Host "   - Changes to ./ollama_stack_cli/ modules will affect your installation" -ForegroundColor Gray
    Write-Host "   - Perfect for developers or if you want to modify the tool" -ForegroundColor Gray
    Write-Host ""
    Write-Host "🏭 Production Installation:" -ForegroundColor Yellow
    Write-Host "   - Creates a standalone copy of the tool" -ForegroundColor Gray
    Write-Host "   - No link to source code - changes won't affect your installation" -ForegroundColor Gray
    Write-Host "   - Recommended for most users" -ForegroundColor Gray
    Write-Host ""
    Write-Host "🗑️  Uninstalling:" -ForegroundColor Yellow
    Write-Host "   - In either case, you can run 'ollama-stack uninstall' to clean up the tool's installation" -ForegroundColor Gray
    Write-Host "   - Then use your system's package manager ('pip uninstall ollama-stack-cli') to completely remove it" -ForegroundColor Gray
    Write-Host ""

    do {
        $installType = Read-Host "Choose installation type (dev/prod) [default: prod]"
        if ([string]::IsNullOrWhiteSpace($installType)) {
            $installType = "prod"
        }
        
        switch ($installType.ToLower()) {
            { $_ -in @("dev", "development", "d") } {
                Write-Host "🔧 Installing in development mode..." -ForegroundColor Green
                if ($externallyManaged) {
                    $installCmd = "python -m pip install -e . --user --break-system-packages"
                } else {
                    $installCmd = "python -m pip install -e . --user"
                }
                $validChoice = $true
            }
            { $_ -in @("prod", "production", "p") } {
                Write-Host "🏭 Installing in production mode..." -ForegroundColor Green
                if ($externallyManaged) {
                    $installCmd = "python -m pip install . --user --break-system-packages"
                } else {
                    $installCmd = "python -m pip install . --user"
                }
                $validChoice = $true
            }
            default {
                Write-Host "Please enter 'dev' or 'prod'" -ForegroundColor Red
                $validChoice = $false
            }
        }
    } while (-not $validChoice)
} else {
    Write-Host "📦 Using pipx for isolated installation..." -ForegroundColor Cyan
    $installCmd = "pipx install ."
}

# Install the package
Write-Host "📦 Installing ollama-stack CLI tool..." -ForegroundColor Cyan
try {
    if ($usePipx) {
        Invoke-Expression $installCmd
    } else {
        Invoke-Expression $installCmd
    }
} catch {
    Write-Host "❌ Error: Failed to install ollama-stack" -ForegroundColor Red
    Write-Host "   Make sure you're running this script from the ollama-stack directory." -ForegroundColor Yellow
    exit 1
}

# Check if installation was successful
$installationSuccess = $false
try {
    if ($usePipx) {
        $pipxList = pipx list 2>$null
        if ($pipxList -match "ollama-stack-cli") {
            $installationSuccess = $true
        }
    } else {
        $null = python -m pip show ollama-stack-cli 2>$null
        $installationSuccess = $true
    }
} catch {
    $installationSuccess = $false
}

if (-not $installationSuccess) {
    Write-Host "❌ Package installation failed!" -ForegroundColor Red
    exit 1
}

# Verify installation and provide PATH guidance
try {
    $null = Get-Command ollama-stack -ErrorAction Stop
    Write-Host "✅ Installation successful! 'ollama-stack' command is available." -ForegroundColor Green
} catch {
    Write-Host "⚠️  Installation completed, but 'ollama-stack' command not found in PATH." -ForegroundColor Yellow
    
    # Check if it's in the expected location
    $expectedPaths = @(
        "$env:APPDATA\Python\Scripts\ollama-stack.exe",
        "$env:LOCALAPPDATA\Programs\Python\Scripts\ollama-stack.exe",
        "$env:USERPROFILE\.local\bin\ollama-stack.exe"
    )
    
    $foundPath = $null
    foreach ($path in $expectedPaths) {
        if (Test-Path $path) {
            $foundPath = $path
            break
        }
    }
    
    if ($foundPath) {
        Write-Host "   The command is installed at: $foundPath" -ForegroundColor Gray
        Write-Host "   You need to add the Scripts directory to your PATH." -ForegroundColor Yellow
        
        $scriptsDir = Split-Path $foundPath -Parent
        Write-Host "   Add this directory to your PATH: $scriptsDir" -ForegroundColor Gray
        
        # Offer to add to PATH automatically
        $addToPath = Read-Host "Add Scripts directory to PATH automatically? (Y/n)"
        if ($addToPath -notmatch "^[Nn]$") {
            try {
                $currentPath = [Environment]::GetEnvironmentVariable("PATH", "User")
                if ($currentPath -notlike "*$scriptsDir*") {
                    $newPath = "$currentPath;$scriptsDir"
                    [Environment]::SetEnvironmentVariable("PATH", $newPath, "User")
                    $env:PATH = "$env:PATH;$scriptsDir"
                    Write-Host "✅ Added to PATH and current session" -ForegroundColor Green
                } else {
                    Write-Host "✅ Already in PATH" -ForegroundColor Green
                }
            } catch {
                Write-Host "⚠️  Failed to update PATH automatically. Please add manually." -ForegroundColor Yellow
            }
        }
    } else {
        Write-Host "   The command was not found in expected locations." -ForegroundColor Yellow
        Write-Host "   Please check the installation and try again." -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "📖 Next steps:" -ForegroundColor Cyan
Write-Host "   1. Ensure Docker Desktop is running" -ForegroundColor Gray
Write-Host "   2. Run 'ollama-stack install' to generate configuration and environment settings" -ForegroundColor Gray
Write-Host "   3. Run 'ollama-stack start' to start the stack" -ForegroundColor Gray
Write-Host "   4. Visit http://localhost:8080 for the web interface" -ForegroundColor Gray 