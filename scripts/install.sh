#!/bin/bash
# Ollama Stack Installation Script
# Installs the ollama-stack CLI tool for system-wide access

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

print_color() {
    echo -e "${1}${2}${NC}"
}

print_success() {
    print_color $GREEN "[+] $1"
}

print_info() {
    print_color $BLUE "[*] $1"
}

print_warning() {
    print_color $YELLOW "[!] $1"
}

print_error() {
    print_color $RED "[-] $1"
}

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOOL_PATH="$SCRIPT_DIR/../ollama-stack"

print_info "Ollama Stack CLI Installation"
echo ""

# Check if ollama-stack exists
if [ ! -f "$TOOL_PATH" ]; then
    print_error "ollama-stack CLI tool not found at $TOOL_PATH"
    exit 1
fi

# Make sure it's executable
chmod +x "$TOOL_PATH"

# Determine installation method
install_method=""
install_path=""

# Check for common installation directories
if [ -d "/usr/local/bin" ] && [ -w "/usr/local/bin" ]; then
    install_method="system"
    install_path="/usr/local/bin/ollama-stack"
elif [ -d "$HOME/.local/bin" ]; then
    install_method="user"
    install_path="$HOME/.local/bin/ollama-stack"
    mkdir -p "$HOME/.local/bin"
elif [ -d "$HOME/bin" ]; then
    install_method="user"
    install_path="$HOME/bin/ollama-stack"
    mkdir -p "$HOME/bin"
else
    install_method="manual"
fi

case $install_method in
    system)
        print_info "Installing to system directory: /usr/local/bin"
        if cp "$TOOL_PATH" "/usr/local/bin/ollama-stack"; then
            print_success "Installed successfully!"
            print_info "You can now use 'ollama-stack' from anywhere"
        else
            print_error "Failed to install to /usr/local/bin"
            print_info "Try running with sudo: sudo $0"
            exit 1
        fi
        ;;
    user)
        print_info "Installing to user directory: $install_path"
        if cp "$TOOL_PATH" "$install_path"; then
            print_success "Installed successfully!"
            
            # Check if user bin is in PATH
            if [[ ":$PATH:" != *":$(dirname $install_path):"* ]]; then
                print_warning "$(dirname $install_path) is not in your PATH"
                print_info "Add this to your shell profile (.bashrc, .zshrc, etc.):"
                print_color $YELLOW "export PATH=\"$(dirname $install_path):\$PATH\""
                echo ""
                print_info "Or run: echo 'export PATH=\"$(dirname $install_path):\$PATH\"' >> ~/.$(basename $SHELL)rc"
                print_info "Then restart your terminal or run: source ~/.$(basename $SHELL)rc"
            else
                print_info "You can now use 'ollama-stack' from anywhere"
            fi
        else
            print_error "Failed to install to $install_path"
            exit 1
        fi
        ;;
    manual)
        print_warning "Could not find a suitable installation directory"
        print_info "Manual installation options:"
        echo ""
        print_info "Option 1 - Add to PATH:"
        print_color $YELLOW "export PATH=\"$SCRIPT_DIR:\$PATH\""
        echo ""
        print_info "Option 2 - Create symlink (requires sudo):"
        print_color $YELLOW "sudo ln -sf $TOOL_PATH /usr/local/bin/ollama-stack"
        echo ""
        print_info "Option 3 - Copy to user bin:"
        print_color $YELLOW "mkdir -p ~/.local/bin && cp $TOOL_PATH ~/.local/bin/ && export PATH=\"~/.local/bin:\$PATH\""
        echo ""
        print_info "Option 4 - Re-run with admin privileges:"
        print_color $YELLOW "sudo $0"
        echo ""
        print_error "Installation failed - manual steps required above"
        echo ""
        print_info "Until installed, use the tool directly from project directory:"
        print_color $BLUE "  ./ollama-stack start"
        print_color $BLUE "  ./ollama-stack status"
        exit 1
        ;;
esac

echo ""
print_info "Quick Start:"
print_color $BLUE "  ollama-stack start                    # Start the stack"
print_color $BLUE "  ollama-stack extensions enable dia-tts-mcp  # Enable TTS extension"
print_color $BLUE "  ollama-stack extensions start dia-tts-mcp   # Start TTS extension"
print_color $BLUE "  ollama-stack status                   # Check status"
print_color $BLUE "  ollama-stack --help                   # Show help"

echo ""
print_success "Installation complete!" 