#!/bin/bash
# Ollama Stack Startup Script
# This script handles a complete cold start of the Ollama Core Stack

set -e

# Default values
HARDWARE="cpu"
SKIP_MODELS=false

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
GRAY='\033[0;37m'
NC='\033[0m' # No Color

# Function to print colored output
print_color() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

# Function to show usage
show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -h, --hardware HARDWARE    Hardware configuration: cpu, nvidia, or apple (default: cpu)"
    echo "  -s, --skip-models         Skip model download prompts"
    echo "  --help                    Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                        # Start with CPU-only configuration"
    echo "  $0 -h nvidia             # Start with NVIDIA GPU acceleration"
    echo "  $0 -h apple -s           # Start Apple Silicon config, skip model prompts"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--hardware)
            HARDWARE="$2"
            if [[ ! "$HARDWARE" =~ ^(cpu|nvidia|apple)$ ]]; then
                print_color $RED "Error: Hardware must be 'cpu', 'nvidia', or 'apple'"
                exit 1
            fi
            shift 2
            ;;
        -s|--skip-models)
            SKIP_MODELS=true
            shift
            ;;
        --help)
            show_usage
            exit 0
            ;;
        *)
            print_color $RED "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

print_color $GREEN "Starting Ollama Core Stack..."
print_color $CYAN "Hardware: $HARDWARE"
echo ""

# Function to check if Docker is running
check_docker() {
    if ! docker info >/dev/null 2>&1; then
        return 1
    fi
    return 0
}

# Function to wait for service health
wait_for_service() {
    local service_name=$1
    local url=$2
    local max_wait=${3:-120}
    
    print_color $YELLOW "Waiting for $service_name to be ready..."
    local elapsed=0
    
    while [ $elapsed -lt $max_wait ]; do
        if curl -s -f "$url" >/dev/null 2>&1; then
            print_color $GREEN "$service_name ready!"
            return 0
        fi
        
        sleep 5
        elapsed=$((elapsed + 5))
        print_color $GRAY "   Still waiting... ($elapsed/$max_wait seconds)"
    done
    
    print_color $RED "$service_name failed to start within $max_wait seconds"
    return 1
}

# Check prerequisites
print_color $BLUE "Checking prerequisites..."

if ! check_docker; then
    print_color $RED "Docker is not running. Please start Docker and try again."
    exit 1
fi

if [ ! -f "docker-compose.yml" ]; then
    print_color $RED "docker-compose.yml not found. Please run this script from the ollama-stack directory."
    exit 1
fi

print_color $GREEN "Prerequisites check passed!"
echo ""

# Determine Docker Compose command based on hardware
COMPOSE_FILES=("-f" "docker-compose.yml")

case $HARDWARE in
    nvidia)
        COMPOSE_FILES+=("-f" "docker-compose.nvidia.yml")
        print_color $MAGENTA "Using NVIDIA GPU acceleration"
        ;;
    apple)
        COMPOSE_FILES+=("-f" "docker-compose.apple.yml")
        print_color $MAGENTA "Using Apple Silicon configuration"
        print_color $YELLOW "Make sure native Ollama app is running!"
        ;;
    cpu)
        print_color $MAGENTA "Using CPU-only configuration"
        ;;
esac

# Start core stack
print_color $BLUE "Starting core stack..."
if ! docker compose "${COMPOSE_FILES[@]}" up -d; then
    print_color $RED "Failed to start core stack"
    exit 1
fi

# Wait for core services
echo ""
print_color $BLUE "Waiting for core services to be ready..."

if [ "$HARDWARE" != "apple" ]; then
    if ! wait_for_service "Ollama" "http://localhost:11434"; then
        print_color $RED "Ollama failed to start"
        exit 1
    fi
fi

if ! wait_for_service "Open WebUI" "http://localhost:8080"; then
    print_color $RED "Open WebUI failed to start"
    exit 1
fi

if ! wait_for_service "MCP Proxy" "http://localhost:8200/docs"; then
    print_color $RED "MCP Proxy failed to start"
    exit 1
fi

# Display status
echo ""
print_color $GREEN "Ollama Core Stack is running!"
echo ""
print_color $CYAN "Services:"
print_color $WHITE "  Open WebUI: http://localhost:8080"

if [ "$HARDWARE" != "apple" ]; then
    print_color $WHITE "  Ollama API: http://localhost:11434"
fi

print_color $WHITE "  MCP Proxy: http://localhost:8200"
print_color $WHITE "  MCP Docs: http://localhost:8200/docs"
echo ""
print_color $GREEN "Ready! Visit http://localhost:8080 to get started." 