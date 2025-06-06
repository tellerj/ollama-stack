#!/bin/bash
# Extension Management Script for Ollama Stack
# Manages MCP server extensions

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REGISTRY_FILE="$SCRIPT_DIR/registry.json"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

print_color() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

show_usage() {
    echo "Extension Management for Ollama Stack"
    echo ""
    echo "Usage: $0 <command> [extension] [options]"
    echo ""
    echo "Commands:"
    echo "  list                   List all available extensions"
    echo "  status                 Show status of all extensions" 
    echo "  enable <extension>     Enable an extension"
    echo "  disable <extension>    Disable an extension"
    echo "  start <extension>      Start an enabled extension"
    echo "  stop <extension>       Stop a running extension"
    echo "  restart <extension>    Restart an extension"
    echo "  logs <extension>       View extension logs"
    echo "  info <extension>       Show detailed extension information"
    echo ""
    echo "Options:"
    echo "  -p, --platform TYPE   Platform: auto, cpu, nvidia, apple (default: auto)"
    echo "  -f, --follow          Follow logs (for logs command)"
    echo ""
    echo "Examples:"
    echo "  $0 list"
    echo "  $0 enable dia-tts"
    echo "  $0 start dia-tts -p nvidia"
    echo "  $0 logs dia-tts -f"
}

detect_platform() {
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

get_extensions() {
    if [ ! -f "$REGISTRY_FILE" ]; then
        echo "[]"
        return
    fi
    python3 -c "
import json
try:
    with open('$REGISTRY_FILE', 'r') as f:
        data = json.load(f)
    print(json.dumps(list(data.get('extensions', {}).keys())))
except:
    print('[]')
"
}

get_enabled_extensions() {
    if [ ! -f "$REGISTRY_FILE" ]; then
        echo "[]"
        return
    fi
    python3 -c "
import json
try:
    with open('$REGISTRY_FILE', 'r') as f:
        data = json.load(f)
    print(json.dumps(data.get('enabled', [])))
except:
    print('[]')
"
}

is_extension_enabled() {
    local extension=$1
    local enabled_list=$(get_enabled_extensions)
    echo "$enabled_list" | python3 -c "
import json, sys
enabled = json.load(sys.stdin)
print('true' if '$extension' in enabled else 'false')
"
}

extension_exists() {
    local extension=$1
    [ -d "$SCRIPT_DIR/$extension" ]
}

update_registry() {
    local extension=$1
    local action=$2  # enable or disable
    
    python3 -c "
import json
try:
    with open('$REGISTRY_FILE', 'r') as f:
        data = json.load(f)
except:
    data = {'version': '1.0', 'extensions': {}, 'enabled': []}

enabled = data.get('enabled', [])
if '$action' == 'enable' and '$extension' not in enabled:
    enabled.append('$extension')
elif '$action' == 'disable' and '$extension' in enabled:
    enabled.remove('$extension')

data['enabled'] = enabled

with open('$REGISTRY_FILE', 'w') as f:
    json.dump(data, f, indent=2)
"
}

list_extensions() {
    print_color $CYAN "Available Extensions:"
    echo ""
    
    for ext_dir in "$SCRIPT_DIR"/*/; do
        if [ -d "$ext_dir" ]; then
            local ext_name=$(basename "$ext_dir")
            local enabled=$(is_extension_enabled "$ext_name")
            local status_icon="❌"
            local status_text="disabled"
            
            if [ "$enabled" = "true" ]; then
                status_icon="✅"
                status_text="enabled"
            fi
            
            # Check if running
            if docker ps --format "table {{.Names}}" | grep -q "$ext_name"; then
                status_icon="🟢"
                status_text="running"
            fi
            
            print_color $WHITE "  $status_icon $ext_name ($status_text)"
            
            # Try to get description from config
            if [ -f "$ext_dir/mcp-config.json" ]; then
                local desc=$(python3 -c "
import json
try:
    with open('$ext_dir/mcp-config.json', 'r') as f:
        data = json.load(f)
    print(data.get('description', ''))
except:
    pass
" 2>/dev/null)
                if [ -n "$desc" ]; then
                    print_color $GRAY "      $desc"
                fi
            fi
        fi
    done
    echo ""
}

enable_extension() {
    local extension=$1
    
    if ! extension_exists "$extension"; then
        print_color $RED "Extension '$extension' not found"
        exit 1
    fi
    
    if [ "$(is_extension_enabled "$extension")" = "true" ]; then
        print_color $YELLOW "Extension '$extension' is already enabled"
        return 0
    fi
    
    print_color $GREEN "Enabling extension: $extension"
    update_registry "$extension" "enable"
    print_color $GREEN "Extension '$extension' enabled successfully"
    print_color $CYAN "Use '$0 start $extension' to start the extension"
}

disable_extension() {
    local extension=$1
    
    if ! extension_exists "$extension"; then
        print_color $RED "Extension '$extension' not found"
        exit 1
    fi
    
    if [ "$(is_extension_enabled "$extension")" = "false" ]; then
        print_color $YELLOW "Extension '$extension' is already disabled"
        return 0
    fi
    
    # Stop if running
    stop_extension "$extension" 2>/dev/null || true
    
    print_color $GREEN "Disabling extension: $extension"
    update_registry "$extension" "disable"
    print_color $GREEN "Extension '$extension' disabled successfully"
}

start_extension() {
    local extension=$1
    local platform=${2:-$(detect_platform)}
    
    if ! extension_exists "$extension"; then
        print_color $RED "Extension '$extension' not found"
        exit 1
    fi
    
    if [ "$(is_extension_enabled "$extension")" = "false" ]; then
        print_color $RED "Extension '$extension' is not enabled. Enable it first with: $0 enable $extension"
        exit 1
    fi
    
    local ext_dir="$SCRIPT_DIR/$extension"
    if [ ! -f "$ext_dir/docker-compose.yml" ]; then
        print_color $RED "No docker-compose.yml found for extension '$extension'"
        exit 1
    fi
    
    # Create shared network if it doesn't exist
    docker network create ollama-stack-network 2>/dev/null || true
    
    print_color $GREEN "Starting extension: $extension (platform: $platform)"
    
    cd "$ext_dir"
    
    # Build compose file arguments
    local compose_files=("-f" "docker-compose.yml")
    
    case $platform in
        nvidia)
            if [ -f "docker-compose.nvidia.yml" ]; then
                compose_files+=("-f" "docker-compose.nvidia.yml")
                print_color $BLUE "Using NVIDIA GPU acceleration"
            fi
            ;;
        apple)
            if [ -f "docker-compose.apple.yml" ]; then
                compose_files+=("-f" "docker-compose.apple.yml")
                print_color $BLUE "Using Apple Silicon optimizations"
            fi
            ;;
    esac
    
    if ! docker compose "${compose_files[@]}" up -d; then
        print_color $RED "Failed to start extension '$extension'"
        exit 1
    fi
    
    print_color $GREEN "Extension '$extension' started successfully"
}

stop_extension() {
    local extension=$1
    
    if ! extension_exists "$extension"; then
        print_color $RED "Extension '$extension' not found"
        exit 1
    fi
    
    local ext_dir="$SCRIPT_DIR/$extension"
    if [ ! -f "$ext_dir/docker-compose.yml" ]; then
        print_color $YELLOW "No docker-compose.yml found for extension '$extension'"
        return 0
    fi
    
    print_color $GREEN "Stopping extension: $extension"
    
    cd "$ext_dir"
    
    if ! docker compose down; then
        print_color $RED "Failed to stop extension '$extension'"
        exit 1
    fi
    
    print_color $GREEN "Extension '$extension' stopped successfully"
}

show_logs() {
    local extension=$1
    local follow=${2:-false}
    
    if ! extension_exists "$extension"; then
        print_color $RED "Extension '$extension' not found"
        exit 1
    fi
    
    local ext_dir="$SCRIPT_DIR/$extension"
    cd "$ext_dir"
    
    if [ "$follow" = "true" ]; then
        docker compose logs -f
    else
        docker compose logs
    fi
}

show_info() {
    local extension=$1
    
    if ! extension_exists "$extension"; then
        print_color $RED "Extension '$extension' not found"
        exit 1
    fi
    
    local ext_dir="$SCRIPT_DIR/$extension"
    
    print_color $CYAN "Extension Information: $extension"
    echo ""
    
    if [ -f "$ext_dir/mcp-config.json" ]; then
        python3 -c "
import json
try:
    with open('$ext_dir/mcp-config.json', 'r') as f:
        data = json.load(f)
    
    print(f\"Name: {data.get('displayName', data.get('name', 'N/A'))}\")
    print(f\"Version: {data.get('version', 'N/A')}\")
    print(f\"Type: {data.get('type', 'N/A')}\")
    print(f\"Description: {data.get('description', 'N/A')}\")
    print()
    
    if 'mcp' in data:
        mcp = data['mcp']
        print('MCP Configuration:')
        print(f\"  Server Name: {mcp.get('serverName', 'N/A')}\")
        print(f\"  Transport: {mcp.get('transport', 'N/A')}\")
        if 'capabilities' in mcp:
            caps = mcp['capabilities']
            print(f\"  Tools: {'✅' if caps.get('tools') else '❌'}\")
            print(f\"  Resources: {'✅' if caps.get('resources') else '❌'}\")
            print(f\"  Prompts: {'✅' if caps.get('prompts') else '❌'}\")
        print()
    
    if 'platforms' in data:
        print('Platform Support:')
        for platform, info in data['platforms'].items():
            supported = '✅' if info.get('supported') else '❌'
            perf = info.get('performance', 'unknown')
            print(f\"  {platform}: {supported} (performance: {perf})\")
        print()
    
    if 'requirements' in data:
        print('Requirements:')
        reqs = data['requirements']
        for key, value in reqs.items():
            if isinstance(value, dict):
                req_text = value.get('description', str(value))
                required = '(required)' if value.get('required') else '(optional)'
                print(f\"  {key}: {req_text} {required}\")
            else:
                print(f\"  {key}: {value}\")
    
except Exception as e:
    print(f'Error reading config: {e}')
"
    else
        print_color $YELLOW "No mcp-config.json found for this extension"
    fi
    
    # Show status
    local enabled=$(is_extension_enabled "$extension")
    local running="false"
    if docker ps --format "table {{.Names}}" | grep -q "$extension"; then
        running="true"
    fi
    
    echo ""
    print_color $CYAN "Status:"
    print_color $WHITE "  Enabled: $([ "$enabled" = "true" ] && echo "✅ Yes" || echo "❌ No")"
    print_color $WHITE "  Running: $([ "$running" = "true" ] && echo "🟢 Yes" || echo "🔴 No")"
}

# Parse arguments
COMMAND=""
EXTENSION=""
PLATFORM="auto"
FOLLOW=false

while [[ $# -gt 0 ]]; do
    case $1 in
        list|status|enable|disable|start|stop|restart|logs|info)
            COMMAND=$1
            shift
            ;;
        -p|--platform)
            PLATFORM="$2"
            shift 2
            ;;
        -f|--follow)
            FOLLOW=true
            shift
            ;;
        -h|--help)
            show_usage
            exit 0
            ;;
        -*)
            print_color $RED "Unknown option: $1"
            show_usage
            exit 1
            ;;
        *)
            if [ -z "$EXTENSION" ]; then
                EXTENSION=$1
            else
                print_color $RED "Unexpected argument: $1"
                show_usage
                exit 1
            fi
            shift
            ;;
    esac
done

# Validate platform
if [[ ! "$PLATFORM" =~ ^(auto|cpu|nvidia|apple)$ ]]; then
    print_color $RED "Invalid platform: $PLATFORM"
    exit 1
fi

# Auto-detect platform if needed
if [ "$PLATFORM" = "auto" ]; then
    PLATFORM=$(detect_platform)
fi

# Execute command
case $COMMAND in
    list|status)
        list_extensions
        ;;
    enable)
        if [ -z "$EXTENSION" ]; then
            print_color $RED "Extension name required for enable command"
            show_usage
            exit 1
        fi
        enable_extension "$EXTENSION"
        ;;
    disable)
        if [ -z "$EXTENSION" ]; then
            print_color $RED "Extension name required for disable command"
            show_usage
            exit 1
        fi
        disable_extension "$EXTENSION"
        ;;
    start)
        if [ -z "$EXTENSION" ]; then
            print_color $RED "Extension name required for start command"
            show_usage
            exit 1
        fi
        start_extension "$EXTENSION" "$PLATFORM"
        ;;
    stop)
        if [ -z "$EXTENSION" ]; then
            print_color $RED "Extension name required for stop command"
            show_usage
            exit 1
        fi
        stop_extension "$EXTENSION"
        ;;
    restart)
        if [ -z "$EXTENSION" ]; then
            print_color $RED "Extension name required for restart command"
            show_usage
            exit 1
        fi
        stop_extension "$EXTENSION"
        sleep 2
        start_extension "$EXTENSION" "$PLATFORM"
        ;;
    logs)
        if [ -z "$EXTENSION" ]; then
            print_color $RED "Extension name required for logs command"
            show_usage
            exit 1
        fi
        show_logs "$EXTENSION" "$FOLLOW"
        ;;
    info)
        if [ -z "$EXTENSION" ]; then
            print_color $RED "Extension name required for info command"
            show_usage
            exit 1
        fi
        show_info "$EXTENSION"
        ;;
    "")
        print_color $RED "No command specified"
        show_usage
        exit 1
        ;;
    *)
        print_color $RED "Unknown command: $COMMAND"
        show_usage
        exit 1
        ;;
esac
