"""
Restart command implementation for the Ollama Stack CLI.

This module handles restarting services by performing a complete stop followed by a start.
The execution flow involves two phases: coordinated shutdown and then startup of all services.

## Execution Flow Diagram

```mermaid
sequenceDiagram
    participant CLI as CLI
    participant Main as main.py
    participant Restart as restart.py
    participant Stop as stop.py
    participant Start as start.py
    participant Ctx as context.py<br/>(AppContext)
    participant SM as stack_manager.py<br/>(StackManager)
    participant DC as docker_client.py<br/>(DockerClient)
    participant OAC as ollama_api_client.py<br/>(OllamaApiClient)
    participant Subprocess as subprocess

    CLI->>Main: ollama-stack restart [--update]
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
    
    Main->>Restart: restart(ctx, update=False)
    Restart->>Restart: restart_services_logic(app_context, update=False)
    Restart->>Restart: log.info("Restarting Ollama Stack...")
    
    Note over Restart: STOP PHASE
    Restart->>Stop: stop_services_logic(app_context)
    
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
        OAC->>OAC: shutil.which("ollama") → "/usr/local/bin/ollama"
        OAC->>OAC: is_service_running() → True
        OAC->>Subprocess: subprocess.run(["pkill", "-f", "ollama serve"], timeout=10)
        Subprocess-->>OAC: return_code=0 (success)
        OAC->>OAC: log.info("Ollama service stopped successfully.")
        OAC-->>SM: return True
        SM-->>Stop: return True
    end
    
    Stop-->>Restart: stop complete
    
    Note over Restart: START PHASE
    Restart->>Start: start_services_logic(app_context, update=False)
    
    Start->>SM: is_stack_running()
    SM->>DC: is_stack_running()
    DC->>Subprocess: docker.client.containers.list(filters={"label": "ollama-stack.component", "status": "running"})
    Subprocess-->>DC: containers=[]
    DC-->>SM: False
    SM-->>Start: False
    
    Note over Start: Filter services by type
    Start->>Start: config.services.items() → {"webui": docker, "ollama": native-api}
    Start->>Start: docker_services = ["webui"]
    Start->>Start: native_services = ["ollama"]
    
    alt docker_services exists
        Start->>SM: start_docker_services(["webui"])
        SM->>SM: get_compose_files() → ["docker-compose.yml", "docker-compose.apple.yml"]
        SM->>DC: start_services(["webui"], compose_files)
        DC->>DC: _run_compose_command(["up", "-d", "webui"], compose_files)
        DC->>Subprocess: subprocess.run(["docker-compose", "-f", "docker-compose.yml", "-f", "docker-compose.apple.yml", "up", "-d", "webui"])
        Subprocess-->>DC: return_code=0
        DC-->>SM: success
        SM-->>Start: success
    end
    
    alt native_services exists
        Start->>SM: start_native_services(["ollama"])
        SM->>OAC: start_service()
        OAC->>OAC: shutil.which("ollama") → "/usr/local/bin/ollama"
        OAC->>OAC: is_service_running() → False
        OAC->>OAC: log.info("Starting native Ollama service...")
        OAC->>Subprocess: subprocess.Popen(["ollama", "serve"], background=True)
        OAC->>OAC: log.info("Ollama service started successfully.")
        OAC-->>SM: return True
        SM-->>Start: return True
    end
    
    Start-->>Restart: start complete
    Restart->>Restart: log.info("Ollama Stack restarted successfully.")
```

## Key Architecture Points

- **Two-Phase Operation**: Complete stop followed by complete start ensures clean state transitions
- **Code Reuse**: Leverages existing stop_services_logic() and start_services_logic() functions
- **Atomic Context**: Single AppContext ensures consistent platform detection and service configuration
- **Service Type Filtering**: Same filtering logic applied in both phases for consistency
- **Platform Awareness**: StackManager maintains platform-specific service configurations throughout
- **Error Isolation**: Stop failures don't prevent start attempts, start failures are isolated
- **Update Flag**: --update only affects the start phase, enabling image updates during restart
- **State Management**: Ensures transition from fully-stopped to fully-started state
"""

import typer
import logging

from ..context import AppContext
from .start import start_services_logic
from .stop import stop_services_logic

log = logging.getLogger(__name__)


def restart_services_logic(app_context: AppContext, update: bool = False):
    """Business logic for restarting services."""
    log.info("Restarting Ollama Stack...")
    
    # Stop services first
    stop_services_logic(app_context)
    
    # Then start them again
    start_services_logic(app_context, update=update)
    
    log.info("Ollama Stack restarted successfully.")


def restart(ctx: typer.Context,
    update: bool = False,
):
    """Restarts the core Ollama Stack services."""
    app_context: AppContext = ctx.obj
    restart_services_logic(app_context, update=update) 