# Ollama Stack CLI Installation Script for Windows
# Installs the ollama-stack command line tool

$ErrorActionPreference = "Stop"

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

# Install the package in editable mode
Write-Host "📦 Installing ollama-stack CLI tool..." -ForegroundColor Cyan
try {
    python -m pip install -e . --user
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
    Write-Host "   ollama-stack start    # Start the stack"
    Write-Host "   ollama-stack status   # Check status"
    Write-Host "   ollama-stack --help   # Show all commands"
} catch {
    Write-Host "⚠️  Installation completed, but 'ollama-stack' command not found in PATH." -ForegroundColor Yellow
    Write-Host "   You may need to restart your terminal or add the Scripts directory to your PATH." -ForegroundColor Yellow
    Write-Host "   The command is typically installed in: %APPDATA%\Python\Scripts\" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "📖 Next steps:" -ForegroundColor Cyan
Write-Host "   1. Ensure Docker Desktop is running"
Write-Host "   2. Run 'ollama-stack start' to start the stack"
Write-Host "   3. Visit http://localhost:8080 for the web interface" 