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

# Check if we're in a virtual environment
if [[ "$VIRTUAL_ENV" != "" ]]; then
    echo "⚠️  Warning: You are currently in a virtual environment ($VIRTUAL_ENV)"
    echo "   This will install ollama-stack only within this virtual environment."
    echo "   To install globally, please deactivate the virtual environment first:"
    echo "   deactivate"
    echo ""
    read -p "Continue with virtual environment installation? (y/N): " continue_in_venv
    if [[ ! "$continue_in_venv" =~ ^[Yy]$ ]]; then
        echo "Installation cancelled. Please deactivate the virtual environment and run again."
        exit 1
    fi
fi

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

# Check if this is an externally managed environment
EXTERNALLY_MANAGED=false
if python3 -c "import sys; sys.exit(0 if hasattr(sys, 'base_prefix') or hasattr(sys, 'real_prefix') else 1)" 2>/dev/null; then
    # Not in a virtual environment, check for externally managed
    if python3 -c "import sys; sys.exit(0 if hasattr(sys, 'stdlib_dir') and 'site-packages' in sys.stdlib_dir else 1)" 2>/dev/null; then
        EXTERNALLY_MANAGED=true
    fi
fi

# Check if pipx is available
if command -v pipx &> /dev/null; then
    USE_PIPX=true
else
    USE_PIPX=false
fi

# Determine installation method
if [[ "$EXTERNALLY_MANAGED" == "true" && "$USE_PIPX" == "false" ]]; then
    echo "⚠️  Detected externally managed Python environment."
    echo "   This system prevents system-wide pip installations for safety."
    echo ""
    echo "   Options:"
    echo "   1. Install pipx (recommended): brew install pipx"
    echo "   2. Force installation (not recommended): Use --break-system-packages"
    echo "   3. Use virtual environment"
    echo ""
    read -p "Install pipx first? (Y/n): " install_pipx
    if [[ ! "$install_pipx" =~ ^[Nn]$ ]]; then
        echo "📦 Installing pipx..."
        if command -v brew &> /dev/null; then
            brew install pipx
            USE_PIPX=true
        else
            echo "❌ Error: Homebrew not found. Please install Homebrew first:"
            echo "   /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
            exit 1
        fi
    else
        echo "⚠️  Proceeding with forced installation (not recommended)..."
    fi
fi

# Prompt user for installation type (only if not using pipx)
if [[ "$USE_PIPX" == "false" ]]; then
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
                if [[ "$EXTERNALLY_MANAGED" == "true" ]]; then
                    install_cmd="python3 -m pip install -e . --user --break-system-packages"
                else
                    install_cmd="python3 -m pip install -e . --user"
                fi
                break
                ;;
            [Pp]rod|[Pp]roduction|[Pp])
                echo "🏭 Installing in production mode..."
                if [[ "$EXTERNALLY_MANAGED" == "true" ]]; then
                    install_cmd="python3 -m pip install . --user --break-system-packages"
                else
                    install_cmd="python3 -m pip install . --user"
                fi
                break
                ;;
            *)
                echo "Please enter 'dev' or 'prod'"
                ;;
        esac
    done
else
    echo "📦 Using pipx for isolated installation..."
    install_cmd="pipx install ."
fi

# Install the package
echo "📦 Installing ollama-stack CLI tool..."
$install_cmd

# Check if installation was successful
if python3 -m pip show ollama-stack-cli &> /dev/null || command -v ollama-stack &> /dev/null || pipx list | grep -q ollama-stack-cli; then
    echo "✅ Package installed successfully!"
else
    echo "❌ Package installation failed!"
    exit 1
fi

# Verify installation and provide PATH guidance
if command -v ollama-stack &> /dev/null; then
    echo "✅ Installation successful! 'ollama-stack' command is available."
else
    echo "⚠️  Installation completed, but 'ollama-stack' command not found in PATH."
    
    # Check if it's in ~/.local/bin
    if [[ -f "$HOME/.local/bin/ollama-stack" ]]; then
        echo "   The command is installed at: $HOME/.local/bin/ollama-stack"
        echo "   You need to add ~/.local/bin to your PATH."
        
        # Detect shell and provide appropriate command
        if [[ "$SHELL" == *"zsh"* ]]; then
            echo "   For zsh, run these commands:"
            echo "   echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.zshrc"
            echo "   source ~/.zshrc"
        elif [[ "$SHELL" == *"bash"* ]]; then
            echo "   For bash, run these commands:"
            echo "   echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.bashrc"
            echo "   source ~/.bashrc"
        else
            echo "   Add ~/.local/bin to your PATH in your shell configuration file."
        fi
        
        # Offer to add to PATH automatically
        read -p "Add ~/.local/bin to PATH automatically? (Y/n): " add_to_path
        if [[ ! "$add_to_path" =~ ^[Nn]$ ]]; then
            if [[ "$SHELL" == *"zsh"* ]]; then
                echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
                export PATH="$HOME/.local/bin:$PATH"
                echo "✅ Added to ~/.zshrc and current session"
            elif [[ "$SHELL" == *"bash"* ]]; then
                echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
                export PATH="$HOME/.local/bin:$PATH"
                echo "✅ Added to ~/.bashrc and current session"
            fi
        fi
    else
        echo "   The command was not found in expected locations."
        echo "   Please check the installation and try again."
    fi
fi

echo ""
echo "📖 Next steps:"
echo "   1. Ensure Docker is running"
echo "   2. Run 'ollama-stack install' to generate configuration and environment settings"
echo "   3. Run 'ollama-stack start' to start the stack"
echo "   4. Visit http://localhost:8080 for the web interface" 