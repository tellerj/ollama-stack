#!/bin/bash

# Ollama Stack CLI Installation Script
# Installs the ollama-stack command line tool

set -e

# Print ASCII art logo
echo ""
echo " ██████╗ ██╗     ██╗      █████╗ ███╗   ███╗ █████╗    ███████╗████████╗ █████╗  ██████╗██╗  ██╗"
echo "██╔═══██╗██║     ██║     ██╔══██╗████╗ ████║██╔══██╗   ██╔════╝╚══██╔══╝██╔══██╗██╔════╝██║ ██╔╝"
echo "██║   ██║██║     ██║     ███████║██╔████╔██║███████║   ███████╗   ██║   ███████║██║     █████╔╝ "
echo "██║   ██║██║     ██║     ██╔══██║██║╚██╔╝██║██╔══██║   ╚════██║   ██║   ██╔══██║██║     ██╔═██╗ "
echo "╚██████╔╝███████╗███████╗██║  ██║██║ ╚═╝ ██║██║  ██║   ███████║   ██║   ██║  ██║╚██████╗██║  ██╗"
echo " ╚═════╝ ╚══════╝╚══════╝╚═╝  ╚═╝╚═╝     ╚═╝╚═╝  ╚═╝   ╚══════╝   ╚═╝   ╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝"
echo ""

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

# Prompt user for installation type
echo ""
echo "📦 Installation Type Selection:"
echo ""
echo "🔧 Development Installation:"
echo "   - Creates a link to the source code"
echo "   - Changes to ./ollama_stack_cli/ modules will affect your installation"
echo "   - Perfect for developers or if you want to modify the tool"
echo ""
echo "🏭 Production Installation:"
echo "   - Creates a standalone copy of the tool"
echo "   - No link to source code - changes won't affect your installation"
echo "   - Recommended for most users"
echo ""
echo "🗑️  Uninstalling:"
echo "   - In either case, you can run 'ollama-stack uninstall' to clean up the tool's installation"
echo "   - Then use your system's package manager ('pip uninstall ollama-stack-cli') to completely remove it"
echo ""

while true; do
    read -p "Choose installation type (dev/prod) [default: prod]: " install_type
    install_type=${install_type:-prod}
    
    case $install_type in
        [Dd]ev|[Dd]evelopment|[Dd])
            echo "🔧 Installing in development mode..."
            install_cmd="python3 -m pip install -e . --user"
            break
            ;;
        [Pp]rod|[Pp]roduction|[Pp])
            echo "🏭 Installing in production mode..."
            install_cmd="python3 -m pip install . --user"
            break
            ;;
        *)
            echo "Please enter 'dev' or 'prod'"
            ;;
    esac
done

# Install the package
echo "📦 Installing ollama-stack CLI tool..."
$install_cmd

# Verify installation
if command -v ollama-stack &> /dev/null; then
    echo "✅ Installation successful!"
    echo ""
    echo "🎉 You can now use the 'ollama-stack' command:"
    echo "   ollama-stack install   # First-time setup and configuration"
    echo "   ollama-stack start     # Start the stack"
    echo "   ollama-stack status    # Check status"
    echo "   ollama-stack --help    # Show all commands"
else
    echo "⚠️  Installation completed, but 'ollama-stack' command not found in PATH."
    echo "   You may need to add ~/.local/bin to your PATH:"
    echo "   echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.bashrc"
    echo "   source ~/.bashrc"
fi

echo ""
echo "📖 Next steps:"
echo "   1. Ensure Docker is running"
echo "   2. Run 'ollama-stack install' to generate configuration and environment settings"
echo "   3. Run 'ollama-stack start' to start the stack"
echo "   4. Visit http://localhost:8080 for the web interface" 