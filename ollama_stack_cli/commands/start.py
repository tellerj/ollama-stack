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
    participant Config as config.py<br/>(Config)
    participant SM as stack_manager.py<br/>(StackManager)
    participant DC as docker_client.py<br/>(DockerClient)
    participant OAC as ollama_api_client.py<br/>(OllamaApiClient)
    participant Docker as subprocess
    
    CLI->>Main: ollama-stack start [--update]
    Main->>Main: @app.callback()
    Main->>Ctx: AppContext(verbose)
    Ctx->>Config: Config(display)
    Config->>Config: load_config() → (AppConfig, fell_back_to_defaults)
    Note over Config: Tracks if config fell back to defaults
    Ctx->>SM: StackManager(config.app_config, display)
    SM->>SM: detect_platform() → "apple"
    SM->>SM: configure_services_for_platform()
    Note over SM: ollama.type = "native-api"
    SM->>DC: DockerClient(config, display)
    SM->>OAC: OllamaApiClient(display)
    
    Main->>Start: start(ctx, update)
    Start->>Start: start_services_logic(app_context, update)
    
    Start->>Config: config.fell_back_to_defaults
    Config-->>Start: True/False
    alt fell_back_to_defaults == True
        Start->>Start: log.info("Configuration file appears to be empty or corrupted...")
    end
    
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
    Start->>SM: stack_manager.config.services
    SM-->>Start: {"webui": {type: "docker"}, "mcp_proxy": {type: "docker"}, "ollama": {type: "native-api"}}
    Note over Start: docker_services = ["webui", "mcp_proxy"]<br/>native_services = ["ollama"]
    
    alt docker_services exists
        Start->>SM: start_docker_services(["webui", "mcp_proxy"])
        SM->>SM: get_compose_files() → ["docker-compose.yml", "docker-compose.apple.yml"]
        SM->>DC: start_services(["webui", "mcp_proxy"], compose_files)
        DC->>DC: _run_compose_command(["up", "-d", "webui", "mcp_proxy"], compose_files)
        DC->>Docker: subprocess.Popen(["docker-compose", "-f", "docker-compose.yml", "-f", "docker-compose.apple.yml", "up", "-d", "webui", "mcp_proxy"])
    end
    
    alt native_services exists
        Start->>SM: start_native_services(["ollama"])
        SM->>OAC: start_service()
        OAC->>OAC: shutil.which("ollama") → "/usr/local/bin/ollama"
        OAC->>OAC: subprocess.run(["pgrep", "-f", "ollama serve"]) → not running
        OAC->>Docker: subprocess.Popen(["ollama", "serve"], background=True)
        OAC->>OAC: log.info("Ollama service started successfully.")
        OAC-->>SM: return True
        SM-->>Start: return True
    end
```

## Key Architecture Points

- **Config Fallback Detection**: Config tracks and exposes when it fell back to defaults
- **User-Friendly Messaging**: Start command shows config fallback message only when needed  
- **Platform Detection**: StackManager detects Apple Silicon, NVIDIA, or CPU platform at startup
- **Service Configuration**: Platform-specific service types (Apple: ollama becomes native-api)
- **Service Filtering**: Commands access services through stack_manager.config.services
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
    # Check if config fell back to defaults and inform user
    if app_context.config.fell_back_to_defaults:
        log.info("Configuration file appears to be empty or corrupted. Using default settings.")
    
    # Filter services by type - access through stack_manager's config
    services_config = app_context.stack_manager.config.services
    docker_services = [name for name, conf in services_config.items() if conf.type == 'docker']
    native_services = [name for name, conf in services_config.items() if conf.type == 'native-api']

    # Check what's already running
    running_docker, running_native = app_context.stack_manager.get_running_services_summary()
    
    # Determine what needs to be started
    docker_to_start = [svc for svc in docker_services if svc not in running_docker]
    native_to_start = [svc for svc in native_services if svc not in running_native]
    
    # Show info about already running services
    all_running = running_docker + running_native
    if all_running:
        if len(all_running) == 1:
            log.info(f"Service already running: {all_running[0]}")
        else:
            running_display = []
            if running_docker:
                running_display.extend(running_docker)
            if running_native:
                running_display.extend([f"{name} (native)" for name in running_native])
            log.info(f"Services already running: {', '.join(running_display)}")
    
    # If everything is already running, we're done
    if not docker_to_start and not native_to_start:
        log.info("All services are already running.")
        return

    # Pull images if requested
    if update:
        app_context.stack_manager.pull_images()

    # Start Docker services that aren't running
    if docker_to_start:
        log.info(f"Starting Docker services: {', '.join(docker_to_start)}")
        app_context.stack_manager.start_docker_services(docker_to_start)

    # Start native services that aren't running
    if native_to_start:
        log.info(f"Starting native services: {', '.join(native_to_start)}")
        app_context.stack_manager.start_native_services(native_to_start)


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