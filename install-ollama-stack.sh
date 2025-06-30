#!/bin/bash

# Ollama Stack CLI Installation Script
# Installs the ollama-stack command line tool

set -e

echo "🚀 Installing Ollama Stack CLI..."

# Check if Python 3 is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: Python 3 is required but not installed."
    echo "   Please install Python 3.8 or later from https://python.org"
    exit 1
fi

# Check Python version
PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
MIN_VERSION="3.8"

if [[ $(echo -e "$MIN_VERSION\n$PYTHON_VERSION" | sort -V | head -n1) != "$MIN_VERSION" ]]; then
    echo "❌ Error: Python $MIN_VERSION or later is required (found $PYTHON_VERSION)"
    exit 1
fi

# Check if pip is available
if ! python3 -m pip --version &> /dev/null; then
    echo "❌ Error: pip is required but not available."
    echo "   Please install pip or ensure Python was installed with pip."
    exit 1
fi

# Install the package in editable mode
echo "📦 Installing ollama-stack CLI tool..."
python3 -m pip install -e . --user

# Verify installation
if command -v ollama-stack &> /dev/null; then
    echo "✅ Installation successful!"
    echo ""
    echo "🎉 You can now use the 'ollama-stack' command:"
    echo "   ollama-stack start    # Start the stack"
    echo "   ollama-stack status   # Check status"
    echo "   ollama-stack --help   # Show all commands"
else
    echo "⚠️  Installation completed, but 'ollama-stack' command not found in PATH."
    echo "   You may need to add ~/.local/bin to your PATH:"
    echo "   echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.bashrc"
    echo "   source ~/.bashrc"
fi

echo ""
echo "📖 Next steps:"
echo "   1. Ensure Docker is running"
echo "   2. Run 'ollama-stack start' to start the stack"
echo "   3. Visit http://localhost:8080 for the web interface" 