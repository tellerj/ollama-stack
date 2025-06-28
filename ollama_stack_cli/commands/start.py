"""
Start command implementation for the Ollama Stack CLI.

This module handles starting Docker-based services and automatically starts native services when possible.
The execution flow involves platform detection, service filtering, and orchestrated startup.

## Execution Flow Diagram

```mermaid
sequenceDiagram
    participant CLI as CLI
    participant Main as main.py
    participant Start as start.py
    participant Ctx as context.py<br/>(AppContext)
    participant SM as stack_manager.py<br/>(StackManager)
    participant DC as docker_client.py<br/>(DockerClient)
    participant OAC as ollama_api_client.py<br/>(OllamaApiClient)
    participant Docker as subprocess
    
    CLI->>Main: ollama-stack start [--update]
    Main->>Main: @app.callback()
    Main->>Ctx: AppContext(verbose)
    Ctx->>SM: StackManager(config, display)
    SM->>SM: detect_platform() → "apple"
    SM->>SM: configure_services_for_platform()
    Note over SM: ollama.type = "native-api"
    SM->>DC: DockerClient(config, display)
    
    Main->>Start: start(ctx, update)
    Start->>Start: start_services_logic(app_context, update)
    
    Start->>SM: is_stack_running()
    SM->>DC: is_stack_running()
    DC->>Docker: docker.client.containers.list()
    Docker-->>DC: containers[]
    DC-->>SM: False
    SM-->>Start: False
    
    alt update == True
        Start->>SM: pull_images()
        SM->>SM: get_compose_files() → ["docker-compose.yml", "docker-compose.apple.yml"]
        SM->>DC: pull_images(compose_files)
        DC->>DC: _run_compose_command(["pull"], compose_files)
        DC->>Docker: subprocess.Popen(["docker-compose", "-f", "docker-compose.yml", "-f", "docker-compose.apple.yml", "pull"])
    end
    
    Note over Start: Filter services by type
    Note over Start: docker_services = ["webui", "mcp_proxy"]<br/>native_services = ["ollama"]
    
    Start->>SM: start_docker_services(["webui", "mcp_proxy"])
    SM->>SM: get_compose_files() → ["docker-compose.yml", "docker-compose.apple.yml"]
    SM->>DC: start_services(["webui", "mcp_proxy"], compose_files)
    DC->>DC: _run_compose_command(["up", "-d", "webui", "mcp_proxy"], compose_files)
    DC->>Docker: subprocess.Popen(["docker-compose", "-f", "docker-compose.yml", "-f", "docker-compose.apple.yml", "up", "-d", "webui", "mcp_proxy"])
    
    Note over Start: Start native services
    Start->>SM: start_native_services(["ollama"])
    SM->>OAC: start_service()
    OAC->>OAC: shutil.which("ollama") → "/usr/local/bin/ollama"
    OAC->>OAC: subprocess.run(["pgrep", "-f", "ollama serve"]) → not running
    OAC->>Docker: subprocess.Popen(["ollama", "serve"], background=True)
    OAC->>OAC: log.info("Ollama service started successfully.")
    OAC-->>SM: return True
    SM-->>Start: return True
```

## Key Architecture Points

- **Platform Detection**: StackManager detects Apple Silicon, NVIDIA, or CPU platform at startup
- **Service Configuration**: Platform-specific service types (Apple: ollama becomes native-api)
- **Service Filtering**: Commands separate docker services from native services
- **Compose File Layering**: Platform-specific compose files are layered (e.g., base + apple)
- **Clean Delegation**: Each module has a specific responsibility in the execution chain
"""

import typer
import logging
from typing_extensions import Annotated

from ..context import AppContext

log = logging.getLogger(__name__)


def start_services_logic(app_context: AppContext, update: bool = False):
    """Business logic for starting services."""
    # Check if stack is already running
    if app_context.stack_manager.is_stack_running():
        log.info("Ollama Stack is already running.")
        return

    # Pull images if requested
    if update:
        app_context.stack_manager.pull_images()

    # Filter services by type
    docker_services = [name for name, conf in app_context.config.services.items() if conf.type == 'docker']
    native_services = [name for name, conf in app_context.config.services.items() if conf.type == 'native-api']

    # Start Docker services
    if docker_services:
        log.info("Starting Docker-based services...")
        app_context.stack_manager.start_docker_services(docker_services)

    # Start native services
    if native_services:
        app_context.stack_manager.start_native_services(native_services)


def start(
    ctx: typer.Context,
    update: Annotated[
        bool,
        typer.Option(
            "--update",
            help="Pull the latest Docker images before starting.",
        ),
    ] = False,
):
    """Starts the core Ollama Stack services."""
    app_context: AppContext = ctx.obj
    start_services_logic(app_context, update=update) 