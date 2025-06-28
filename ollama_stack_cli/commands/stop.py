"""
Stop command implementation for the Ollama Stack CLI.

This module handles stopping both Docker-based services and native services.
The execution flow involves service filtering and coordinated shutdown operations.

## Execution Flow Diagram

```mermaid
sequenceDiagram
    participant CLI as CLI
    participant Main as main.py
    participant Stop as stop.py
    participant Ctx as context.py<br/>(AppContext)
    participant SM as stack_manager.py<br/>(StackManager)
    participant DC as docker_client.py<br/>(DockerClient)
    participant OAC as ollama_api_client.py<br/>(OllamaApiClient)
    participant Subprocess as subprocess

    CLI->>Main: ollama-stack stop
    Main->>Main: @app.callback() - Initialize context
    Main->>Ctx: AppContext(verbose=False)
    Ctx->>Ctx: Display(verbose=False)
    Ctx->>Ctx: Config(display)
    Ctx->>SM: StackManager(config.app_config, display)
    SM->>SM: detect_platform() → "apple"
    SM->>SM: configure_services_for_platform()
    Note over SM: ollama.type = "native-api" (Apple Silicon)
    SM->>DC: DockerClient(config, display)
    SM->>OAC: OllamaApiClient(display)
    
    Main->>Stop: stop(ctx)
    Stop->>Stop: stop_services_logic(app_context)
    
    Note over Stop: Filter services by type
    Stop->>Stop: config.services.items() → {"webui": docker, "ollama": native-api}
    Stop->>Stop: docker_services = ["webui"]
    Stop->>Stop: native_services = ["ollama"]
    
    alt docker_services exists
        Stop->>SM: stop_docker_services()
        SM->>SM: get_compose_files() → ["docker-compose.yml", "docker-compose.apple.yml"]
        SM->>DC: stop_services(compose_files)
        DC->>DC: _run_compose_command(["down"], compose_files)
        DC->>Subprocess: subprocess.run(["docker-compose", "-f", "docker-compose.yml", "-f", "docker-compose.apple.yml", "down"])
        Subprocess-->>DC: return_code=0
        DC-->>SM: success
        SM-->>Stop: success
    end
    
    alt native_services exists
        Stop->>SM: stop_native_services(["ollama"])
        SM->>OAC: stop_service()
        
        Note over OAC: Validate ollama installation
        OAC->>OAC: shutil.which("ollama") → "/usr/local/bin/ollama"
        
        Note over OAC: Check if service is running
        OAC->>OAC: is_service_running()
        OAC->>Subprocess: subprocess.run(["pgrep", "-f", "ollama serve"])
        Subprocess-->>OAC: return_code=0 (process found)
        OAC-->>OAC: return True
        
        Note over OAC: Stop the service
        OAC->>Subprocess: subprocess.run(["pkill", "-f", "ollama serve"], timeout=10)
        Subprocess-->>OAC: return_code=0 (success)
        OAC->>OAC: log.info("Ollama service stopped successfully.")
        OAC-->>SM: return True
        SM-->>Stop: return True
    end
```

## Key Architecture Points

- **Service Type Filtering**: Commands separate docker services from native services based on platform configuration
- **Docker Services**: Stopped via docker-compose down with platform-specific compose files
- **Native Services**: Stopped via process management with validation and error handling
- **Platform Awareness**: StackManager configures service types based on detected platform (Apple Silicon → native-api)
- **Graceful Validation**: OllamaApiClient validates installation and running state before attempting operations
- **Error Recovery**: Comprehensive error handling with fallback messaging for manual intervention
"""

import typer
import logging

from ..context import AppContext

log = logging.getLogger(__name__)


def stop_services_logic(app_context: AppContext):
    """Business logic for stopping services."""
    # Filter services by type
    docker_services = [name for name, conf in app_context.config.services.items() if conf.type == 'docker']
    native_services = [name for name, conf in app_context.config.services.items() if conf.type == 'native-api']

    # Stop Docker services
    if docker_services:
        app_context.stack_manager.stop_docker_services()

    # Stop native services
    if native_services:
        app_context.stack_manager.stop_native_services(native_services)


def stop(ctx: typer.Context):
    """Stops the core Ollama Stack services."""
    app_context: AppContext = ctx.obj
    stop_services_logic(app_context) 