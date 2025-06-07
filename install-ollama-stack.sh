#!/bin/bash
# Ollama Stack Installation Script
# Installs the ollama-stack CLI tool for system-wide access

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
WHITE='\033[1;37m'
NC='\033[0m'
CYAN='\033[0;36m'

print_color() {
    echo -e "${1}${2}${NC}"
}

print_header() {
    local message=$1
    echo ""
    print_color $WHITE "==== $message ===="
}

print_status() {
    print_color $CYAN "[*] $1"
}

print_success() {
    print_color $GREEN "[+] $1"
}

print_warning() {
    print_color $YELLOW "[!] $1"
}

print_error() {
    print_color $RED "[-] $1"
}

# Get script directory (now in project root)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR"
TOOL_PATH="$PROJECT_DIR/ollama-stack"

print_header "Ollama Stack CLI Installation"

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
project_install_path=""

# Check for common installation directories
if [ -d "/usr/local/bin" ] && [ -w "/usr/local/bin" ] && [ -w "/usr/local" ]; then
    install_method="system"
    install_path="/usr/local/bin/ollama-stack"
    project_install_path="/usr/local/share/ollama-stack"
elif [ -d "$HOME/.local/bin" ]; then
    install_method="user"
    install_path="$HOME/.local/bin/ollama-stack"
    project_install_path="$HOME/.local/share/ollama-stack"
    mkdir -p "$HOME/.local/bin"
    mkdir -p "$HOME/.local/share"
elif [ -d "$HOME/bin" ]; then
    install_method="user"
    install_path="$HOME/bin/ollama-stack"
    project_install_path="$HOME/.ollama-stack"
    mkdir -p "$HOME/bin"
else
    install_method="manual"
fi

case $install_method in
    system)
        print_status "Installing to system directory: /usr/local"
        
        # Create project directory
        if ! mkdir -p "$project_install_path"; then
            print_error "Failed to create project directory $project_install_path"
            print_status "Try running with sudo: sudo $0"
            exit 1
        fi
        
        # Copy project files
        print_status "Copying project files to $project_install_path"
        if ! cp -r "$PROJECT_DIR"/{ollama-stack,ollama-stack.ps1,docker-compose*.yml,extensions,tools} "$project_install_path/"; then
            print_error "Failed to copy project files"
            exit 1
        fi
        
        # Make scripts executable
        chmod +x "$project_install_path/ollama-stack"
        chmod +x "$project_install_path/ollama-stack.ps1"
        
        # Create wrapper script
        cat > "$install_path" << 'EOF'
#!/bin/bash
# Ollama Stack wrapper script
OLLAMA_STACK_DIR="/usr/local/share/ollama-stack"
cd "$OLLAMA_STACK_DIR"
exec "$OLLAMA_STACK_DIR/ollama-stack" "$@"
EOF
        chmod +x "$install_path"
        
        print_success "Installed successfully!"
        print_status "Project files: $project_install_path"
        print_status "Command: ollama-stack"
        ;;
    user)
        print_status "Installing to user directory: $(dirname $install_path)"
        
        # Create project directory  
        if ! mkdir -p "$project_install_path"; then
            print_error "Failed to create project directory $project_install_path"
            exit 1
        fi
        
        # Copy project files
        print_status "Copying project files to $project_install_path"
        if ! cp -r "$PROJECT_DIR"/{ollama-stack,ollama-stack.ps1,docker-compose*.yml,extensions,tools} "$project_install_path/"; then
            print_error "Failed to copy project files"
            exit 1
        fi
        
        # Make scripts executable
        chmod +x "$project_install_path/ollama-stack"
        chmod +x "$project_install_path/ollama-stack.ps1"
        
        # Create wrapper script
        cat > "$install_path" << EOF
#!/bin/bash
# Ollama Stack wrapper script
OLLAMA_STACK_DIR="$project_install_path"
cd "\$OLLAMA_STACK_DIR"
exec "\$OLLAMA_STACK_DIR/ollama-stack" "\$@"
EOF
        chmod +x "$install_path"
        
        print_success "Installed successfully!"
        print_status "Project files: $project_install_path"
        
        # Check if user bin is in PATH
        bin_dir=$(dirname $install_path)
        if [[ ":$PATH:" != *":$bin_dir:"* ]]; then
            print_warning "$bin_dir is not in your PATH"
            
            # Determine shell config file
            shell_config=""
            case $(basename "$SHELL") in
                bash) shell_config="$HOME/.bashrc" ;;
                zsh) shell_config="$HOME/.zshrc" ;;
                *) shell_config="$HOME/.profile" ;;
            esac
            
            # Add to PATH automatically
            path_export="export PATH=\"$bin_dir:\$PATH\""
            if [ -f "$shell_config" ] && ! grep -q "$bin_dir" "$shell_config"; then
                echo "" >> "$shell_config"
                echo "# Added by ollama-stack installer" >> "$shell_config"
                echo "$path_export" >> "$shell_config"
                print_success "Added $bin_dir to PATH in $shell_config"
                print_status "Restart your terminal or run: source $shell_config"
            elif [ ! -f "$shell_config" ]; then
                echo "# Added by ollama-stack installer" > "$shell_config"
                echo "$path_export" >> "$shell_config"
                print_success "Created $shell_config and added $bin_dir to PATH"
                print_status "Restart your terminal or run: source $shell_config"
            else
                print_status "$bin_dir already in $shell_config"
            fi
            
            # Also export for current session
            export PATH="$bin_dir:$PATH"
            print_status "PATH updated for current session"
        else
            print_status "You can now use 'ollama-stack' from anywhere"
        fi
        ;;
    manual)
        print_warning "Could not find a suitable installation directory"
        print_status "Manual installation options:"
        
        print_status "Option 1 - Add to PATH:"
        print_status "export PATH=\"$PROJECT_DIR:\$PATH\""
        
        print_status "Option 2 - Create symlink (requires sudo):"
        print_status "sudo mkdir -p /usr/local/share/ollama-stack"
        print_status "sudo cp -r $PROJECT_DIR/* /usr/local/share/ollama-stack/"
        print_status "sudo ln -sf /usr/local/share/ollama-stack/ollama-stack /usr/local/bin/ollama-stack"
        
        print_status "Option 3 - Copy to user directory:"
        print_status "mkdir -p ~/.local/share/ollama-stack ~/.local/bin"
        print_status "cp -r $PROJECT_DIR/* ~/.local/share/ollama-stack/"
        print_status "echo '#!/bin/bash\ncd ~/.local/share/ollama-stack\nexec ~/.local/share/ollama-stack/ollama-stack \"\$@\"' > ~/.local/bin/ollama-stack"
        print_status "chmod +x ~/.local/bin/ollama-stack"
        print_status "export PATH=\"~/.local/bin:\$PATH\""
        
        print_status "Option 4 - Re-run with admin privileges:"
        print_status "sudo $0"
        
        print_error "Installation failed - manual steps required above"
        
        print_status "Until installed, use the tool directly from project directory:"
        print_status "  cd $PROJECT_DIR"
        print_status "  ./ollama-stack start"
        print_status "  ./ollama-stack status"
        exit 1
        ;;
esac

print_header "Quick Start"
print_status "ollama-stack start                          # Start the stack"
print_status "ollama-stack extensions enable dia-tts-mcp  # Enable TTS extension"
print_status "ollama-stack extensions start dia-tts-mcp   # Start TTS extension"
print_status "ollama-stack status                         # Check status"
print_status "ollama-stack --help                         # Show help"
print_success "Installation complete!" 