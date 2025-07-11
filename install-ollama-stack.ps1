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

# Prompt user for installation type
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
            $installCmd = "python -m pip install -e . --user"
            $validChoice = $true
        }
        { $_ -in @("prod", "production", "p") } {
            Write-Host "🏭 Installing in production mode..." -ForegroundColor Green
            $installCmd = "python -m pip install . --user"
            $validChoice = $true
        }
        default {
            Write-Host "Please enter 'dev' or 'prod'" -ForegroundColor Red
            $validChoice = $false
        }
    }
} while (-not $validChoice)

# Install the package
Write-Host "📦 Installing ollama-stack CLI tool..." -ForegroundColor Cyan
try {
    Invoke-Expression $installCmd
} catch {
    Write-Host "❌ Error: Failed to install ollama-stack" -ForegroundColor Red
    Write-Host "   Make sure you're running this script from the ollama-stack directory." -ForegroundColor Yellow
    exit 1
}

# Verify installation
try {
    $null = Get-Command ollama-stack -ErrorAction Stop
    Write-Host "✅ Installation successful!" -ForegroundColor Green
    Write-Host ""
    Write-Host "🎉 You can now use the 'ollama-stack' command:" -ForegroundColor Green
    Write-Host "   ollama-stack install   # First-time setup and configuration" -ForegroundColor Gray
    Write-Host "   ollama-stack start     # Start the stack" -ForegroundColor Gray
    Write-Host "   ollama-stack status    # Check status" -ForegroundColor Gray
    Write-Host "   ollama-stack --help    # Show all commands" -ForegroundColor Gray
} catch {
    Write-Host "⚠️  Installation completed, but 'ollama-stack' command not found in PATH." -ForegroundColor Yellow
    Write-Host "   You may need to restart your terminal or add the Scripts directory to your PATH." -ForegroundColor Yellow
    Write-Host "   The command is typically installed in: %APPDATA%\Python\Scripts\" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "📖 Next steps:" -ForegroundColor Cyan
Write-Host "   1. Ensure Docker Desktop is running" -ForegroundColor Gray
Write-Host "   2. Run 'ollama-stack install' to generate configuration and environment settings" -ForegroundColor Gray
Write-Host "   3. Run 'ollama-stack start' to start the stack" -ForegroundColor Gray
Write-Host "   4. Visit http://localhost:8080 for the web interface" -ForegroundColor Gray 