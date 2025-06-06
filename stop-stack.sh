#!/bin/bash

set -e

# Default values
PLATFORM="auto"
REMOVE_VOLUMES=false
SHOW_HELP=false

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -p|--platform)
            PLATFORM="$2"
            if [[ ! "$PLATFORM" =~ ^(auto|cpu|nvidia|apple)$ ]]; then
                echo -e "\033[31mError: Platform must be 'auto', 'cpu', 'nvidia', or 'apple'\033[0m"
                exit 1
            fi
            shift 2
            ;;
        -v|--remove-volumes)
            REMOVE_VOLUMES=true
            shift
            ;;
        -h|--help)
            SHOW_HELP=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

if [ "$SHOW_HELP" = true ]; then
    cat << EOF
Ollama Stack Shutdown Script

Usage: ./stop-stack.sh [options]

Options:
  -p, --platform TYPE    Platform type: auto, cpu, nvidia, apple (default: auto)
  -v, --remove-volumes   Also remove Docker volumes (WARNING: deletes all data)
  -h, --help            Show this help message

Examples:
  ./stop-stack.sh                      # Auto-detect and stop
  ./stop-stack.sh -p nvidia            # Force NVIDIA configuration
  ./stop-stack.sh --remove-volumes     # Stop and remove all data
EOF
    exit 0
fi

# Color output functions
print_status() {
    echo -e "\033[34m[*] $1\033[0m"
}

print_success() {
    echo -e "\033[32m[+] $1\033[0m"
}

print_error() {
    echo -e "\033[31m[-] $1\033[0m"
}

print_warning() {
    echo -e "\033[33m[!] $1\033[0m"
}

# Platform detection function
detect_platform() {
    if [ "$PLATFORM" != "auto" ]; then
        echo "$PLATFORM"
        return
    fi
    
    # Check for Apple Silicon
    if [[ "$OSTYPE" == "darwin"* ]]; then
        if [[ $(uname -m) == "arm64" ]]; then
            echo "apple"
            return
        fi
    fi
    
    # Check for NVIDIA GPU
    if command -v nvidia-smi >/dev/null 2>&1; then
        if nvidia-smi >/dev/null 2>&1; then
            echo "nvidia"
            return
        fi
    fi
    
    # Default to CPU
    echo "cpu"
}

# Stop stack function
stop_stack() {
    local platform_type=$1
    
    print_status "Stopping Ollama Stack ($platform_type configuration)..."
    
    # Build compose file arguments
    local compose_files=("-f" "docker-compose.yml")
    
    case $platform_type in
        nvidia)
            compose_files+=("-f" "docker-compose.nvidia.yml")
            ;;
        apple)
            compose_files+=("-f" "docker-compose.apple.yml")
            ;;
    esac
    
    # Build docker compose command
    local compose_cmd=("docker" "compose" "${compose_files[@]}")
    
    if [ "$REMOVE_VOLUMES" = true ]; then
        print_warning "Removing volumes (all data will be deleted)..."
        compose_cmd+=("down" "-v")
    else
        compose_cmd+=("down")
    fi
    
    # Execute the command
    if "${compose_cmd[@]}"; then
        print_success "Stack stopped successfully"
        if [ "$REMOVE_VOLUMES" = true ]; then
            print_success "Volumes removed successfully"
        fi
    else
        print_error "Failed to stop stack"
        exit 1
    fi
}

# Main execution
echo -e "\033[36mOLLAMA STACK SHUTDOWN\033[0m"
echo ""

# Check if Docker is available and running
if ! command -v docker >/dev/null 2>&1; then
    print_error "Docker is not installed or not in PATH"
    exit 1
fi

if ! docker info >/dev/null 2>&1; then
    print_error "Docker is not running or accessible"
    exit 1
fi

# Detect platform if set to auto
DETECTED_PLATFORM=$(detect_platform)
if [ "$PLATFORM" = "auto" ]; then
    PLATFORM=$DETECTED_PLATFORM
    print_status "Auto-detected platform: $PLATFORM"
else
    print_status "Using specified platform: $PLATFORM"
fi

# Stop the stack
stop_stack "$PLATFORM"

echo ""
print_success "Ollama Stack shutdown complete!" 