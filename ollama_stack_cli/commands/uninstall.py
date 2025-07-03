"""
Uninstall command implementation for the Ollama Stack CLI.

This module handles the complete removal of all stack resources including Docker containers,
networks, images, volumes, and configuration files. The execution flow involves multiple phases
of resource discovery, service shutdown, and selective cleanup based on user preferences.

## Execution Flow Diagram

```mermaid
sequenceDiagram
    participant CLI as CLI
    participant Main as main.py<br/>(Typer App)
    participant Uninstall as uninstall.py<br/>(Command)
    participant Ctx as context.py<br/>(AppContext)
    participant Config as config.py<br/>(Config)
    participant SM as stack_manager.py<br/>(StackManager)
    participant DC as docker_client.py<br/>(DockerClient)
    participant OAC as ollama_api_client.py<br/>(OllamaApiClient)
    participant Docker as Docker API<br/>(subprocess)
    participant FS as Filesystem<br/>(shutil/pathlib)

    CLI->>Main: ollama-stack uninstall [--remove-volumes] [--remove-config] [--all] [--force]
    
    Note over Main: PHASE 1: CLI ENTRY & FRAMEWORK INITIALIZATION
    Main->>Main: @app.callback()
    Main->>Ctx: AppContext(verbose=verbose)
    Ctx->>Ctx: Display(verbose=verbose)
    Ctx->>Config: Config(display)
    Config->>Config: load_config() → (AppConfig, fell_back_to_defaults)
    Config->>Config: detect_platform() → "apple"/"nvidia"/"cpu"
    Ctx->>SM: StackManager(config.app_config, display)
    SM->>SM: detect_platform() → "apple"
    SM->>SM: configure_services_for_platform()
    Note over SM: ollama.type = "native-api" (Apple Silicon)
    SM->>DC: DockerClient(config, display)
    SM->>OAC: OllamaApiClient(display)
    
    Note over Main: PHASE 2: COMMAND EXECUTION LAYER
    Main->>Uninstall: uninstall(ctx, remove_volumes, remove_config, all_flag, force)
    Uninstall->>Uninstall: uninstall_logic(app_context, ...)
    
    Note over Uninstall: Flag Processing
    alt all_flag == True
        Uninstall->>Uninstall: remove_volumes = True, remove_config = True
        Uninstall->>Uninstall: log.debug("--all flag enabled")
    end
    
    Note over Uninstall: PHASE 3: STACKMANAGER ORCHESTRATION
    Uninstall->>SM: uninstall_stack(remove_volumes, remove_config, force)
    
    Note over SM: Warning Display Phase
    alt remove_volumes && remove_config
        SM->>SM: log.warning("⚠️ DESTRUCTIVE OPERATION: This will remove ALL...")
        SM->>SM: log.warning("• All AI models will be deleted...")
        SM->>SM: log.warning("• All chat conversations will be deleted...")
        SM->>SM: log.warning("• All configuration will be deleted")
    else remove_volumes only
        SM->>SM: log.warning("⚠️ DESTRUCTIVE OPERATION: This will remove all stack data!")
        SM->>SM: log.warning("• All AI models will be deleted...")
        SM->>SM: log.warning("• All chat conversations will be deleted...")
    else default
        SM->>SM: log.info("Removing stack resources (preserving data volumes and configuration)")
    end
    
    Note over SM: PHASE 4: RESOURCE DISCOVERY
    SM->>SM: log.info("Discovering stack resources...")
    SM->>SM: find_resources_by_label("ollama-stack.component")
    SM->>DC: client.containers.list(all=True, filters={"label": "ollama-stack.component"})
    DC->>Docker: docker.client.containers.list(all=True, filters=...)
    Docker-->>DC: containers[]
    SM->>DC: client.volumes.list(filters={"label": "ollama-stack.component"})
    DC->>Docker: docker.client.volumes.list(filters=...)
    Docker-->>DC: volumes[]
    SM->>DC: client.networks.list(filters={"label": "ollama-stack.component"})
    DC->>Docker: docker.client.networks.list(filters=...)
    Docker-->>DC: networks[]
    DC-->>SM: {"containers": [...], "volumes": [...], "networks": [...]}
    
    SM->>SM: total_resources = len(containers) + len(networks) + len(volumes)
    SM->>SM: log.info("Found X containers, Y networks, Z volumes")
    
    alt total_resources == 0 && !remove_config
        SM->>SM: log.info("No stack resources found to remove")
        SM-->>Uninstall: return True
        Uninstall-->>Main: success = True
        Main-->>CLI: exit_code = 0
    end
    
    Note over SM: PHASE 5: SERVICE SHUTDOWN
    SM->>SM: log.info("Stopping all running services...")
    SM->>SM: is_stack_running()
    SM->>DC: is_stack_running()
    DC->>Docker: docker.client.containers.list(filters={"label": "ollama-stack.component", "status": "running"})
    Docker-->>DC: running_containers[]
    DC-->>SM: stack_running = len(containers) > 0
    
    alt stack_running == True
        SM->>SM: docker_services = [name for name, conf in services.items() if conf.type == 'docker']
        SM->>SM: native_services = [name for name, conf in services.items() if conf.type == 'native-api']
        
        alt docker_services exists
            SM->>SM: stop_docker_services()
            SM->>SM: get_compose_files() → ["docker-compose.yml", "docker-compose.apple.yml"]
            SM->>DC: stop_services(compose_files)
            DC->>DC: _run_compose_command(["down"], compose_files)
            DC->>Docker: subprocess.run(["docker-compose", "-f", "docker-compose.yml", "-f", "docker-compose.apple.yml", "down"])
            Docker-->>DC: return_code = 0
            DC-->>SM: success
        end
        
        alt native_services exists
            SM->>SM: stop_native_services(native_services)
            SM->>OAC: stop_service()
            OAC->>OAC: shutil.which("ollama") → "/usr/local/bin/ollama"
            OAC->>OAC: is_service_running()
            OAC->>Docker: subprocess.run(["pgrep", "-f", "ollama serve"])
            Docker-->>OAC: return_code = 0 (process found)
            OAC->>Docker: subprocess.run(["pkill", "-f", "ollama serve"], timeout=10)
            Docker-->>OAC: return_code = 0 (success)
            OAC->>OAC: log.info("Ollama service stopped successfully.")
            OAC-->>SM: return True
        end
    end
    
    Note over SM: PHASE 6: RESOURCE REMOVAL
    SM->>SM: log.info("Removing containers and networks...")
    SM->>SM: cleanup_resources(remove_volumes=False, force=force)
    SM->>SM: find_resources_by_label("ollama-stack.component")
    
    Note over SM: Remove stopped containers
    SM->>SM: stopped_containers = [c for c in containers if c.status != "running"]
    loop for each stopped_container
        SM->>Docker: container.remove(force=force)
        Docker-->>SM: success
        SM->>SM: log.debug("Removed container: {name}")
    end
    
    Note over SM: Remove unused networks
    SM->>SM: unused_networks = [n for n in networks if n.name not in ['bridge', 'host', 'none']]
    loop for each unused_network
        SM->>Docker: network.remove()
        Docker-->>SM: success
        SM->>SM: log.debug("Removed network: {name}")
    end
    
    SM->>SM: log.info("Removing Docker images...")
    SM->>DC: remove_resources(remove_images=True, force=force)
    
    Note over DC: Remove labeled images
    DC->>Docker: client.images.list(filters={"label": "ollama-stack.component"})
    Docker-->>DC: images[]
    loop for each image
        DC->>Docker: client.images.remove(image.id, force=force)
        Docker-->>DC: success
        DC->>DC: log.debug("Removed image: {id}")
    end
    
    Note over DC: Remove via compose
    DC->>Docker: subprocess.run(["docker-compose", "-f", "docker-compose.yml", "down", "--rmi", "all"])
    Docker-->>DC: return_code = 0
    DC-->>SM: success
    
    Note over SM: PHASE 7: DATA VOLUME REMOVAL (if requested)
    alt remove_volumes == True
        alt force == False
            SM->>SM: log.warning("🚨 FINAL WARNING: About to delete all data volumes!")
        end
        
        SM->>SM: log.warning("Removing data volumes - THIS WILL DELETE ALL DATA!")
        SM->>SM: volumes = resources["volumes"]
        
        loop for each volume
            SM->>Docker: volume.remove(force=force)
            Docker-->>SM: success
            SM->>SM: log.debug("Removed volume: {name}")
        end
        
        SM->>SM: log.warning("Removed X data volumes")
    end
    
    Note over SM: PHASE 8: CONFIGURATION REMOVAL (if requested)
    alt remove_config == True
        SM->>SM: log.info("Removing configuration directory...")
        SM->>SM: from .config import DEFAULT_CONFIG_DIR
        
        alt DEFAULT_CONFIG_DIR.exists()
            SM->>FS: shutil.rmtree(DEFAULT_CONFIG_DIR)
            FS-->>SM: success
            SM->>SM: log.debug("Removed configuration directory: ~/.ollama-stack/")
        else
            SM->>SM: log.debug("Configuration directory not found")
        end
    end
    
    Note over SM: PHASE 9: COMPLETION & USER FEEDBACK
    SM->>SM: log.info("Stack uninstall completed successfully")
    
    alt remove_volumes && remove_config
        SM->>SM: log.info("All stack resources, data, and configuration have been removed")
    else remove_volumes only
        SM->>SM: log.info("All stack resources and data have been removed (configuration preserved)")
    else remove_config only
        SM->>SM: log.info("All stack resources and configuration have been removed (data volumes preserved)")
    else default
        SM->>SM: log.info("All stack resources have been removed (data and configuration preserved)")
    end
    
    SM->>SM: log.info("To remove the CLI tool itself, run: pip uninstall ollama-stack-cli")
    SM-->>Uninstall: return True
    
    Uninstall-->>Main: success = True
    Main-->>CLI: exit_code = 0
```

## Key Architecture Points

- **Multi-Phase Operation**: Structured execution through distinct phases (discovery, shutdown, cleanup)
- **Resource Discovery**: Uses Docker labels (`ollama-stack.component`) to find all stack resources
- **Platform Awareness**: StackManager configures service types based on detected platform
- **Safe Defaults**: Preserves data volumes and configuration unless explicitly requested
- **Progressive Warnings**: Multiple confirmation points for destructive operations
- **Comprehensive Cleanup**: Handles containers, networks, images, volumes, and configuration files
- **Error Resilience**: Continues cleanup operations even if individual steps fail
- **Service Type Filtering**: Separates Docker services from native services for appropriate shutdown
- **Docker API Integration**: Direct Docker client calls for resource management
- **Filesystem Operations**: Direct filesystem access for configuration directory removal

## Destructive Operations

⚠️ **WARNING**: The uninstall command can perform irreversible data destruction:

- `--remove-volumes`: Deletes all AI models, chat conversations, and database content
- `--remove-config`: Removes `~/.ollama-stack/` directory with all configuration
- `--all`: Equivalent to both flags above - complete stack removal
- `--force`: Skips all confirmation prompts for automation

## Resource Scope

**Always Removed:**
- Docker containers with `ollama-stack.component` label
- Docker networks with `ollama-stack.component` label  
- Docker images with `ollama-stack.component` label

**Conditionally Removed:**
- Docker volumes (with `--remove-volumes`)
- Configuration directory `~/.ollama-stack/` (with `--remove-config`)

**Never Removed:**
- The CLI tool itself (requires `pip uninstall ollama-stack-cli`)
- System-wide Docker installation
- Non-stack Docker resources
"""

import logging
import typer
from typing_extensions import Annotated

from ..context import AppContext

log = logging.getLogger(__name__)


def uninstall_logic(app_context: AppContext, remove_volumes: bool = False, remove_config: bool = False, all_flag: bool = False, force: bool = False) -> bool:
    """
    Business logic for uninstalling stack resources.
    """
    # Handle --all flag
    if all_flag:
        remove_volumes = True
        remove_config = True
        log.debug("--all flag enabled: setting remove_volumes=True, remove_config=True")
    
    # Call stack manager to perform uninstall
    return app_context.stack_manager.uninstall_stack(
        remove_volumes=remove_volumes,
        remove_config=remove_config, 
        force=force
    )


def uninstall(
    ctx: typer.Context,
    remove_volumes: Annotated[
        bool,
        typer.Option(
            "--remove-volumes",
            help="Also remove Docker volumes (destroys models, conversations, databases).",
        ),
    ] = False,
    remove_config: Annotated[
        bool,
        typer.Option(
            "--remove-config",
            help="Also remove configuration directory (~/.ollama-stack/).",
        ),
    ] = False,
    all_flag: Annotated[
        bool,
        typer.Option(
            "--all", "-a",
            help="Remove everything (equivalent to --remove-volumes --remove-config).",
        ),
    ] = False,
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            help="Skip all confirmation prompts.",
        ),
    ] = False,
):
    """Clean up all stack resources (containers, networks, images, and optionally volumes/config)."""
    app_context: AppContext = ctx.obj
    
    success = uninstall_logic(
        app_context, 
        remove_volumes=remove_volumes,
        remove_config=remove_config,
        all_flag=all_flag,
        force=force
    )
    
    if not success:
        raise typer.Exit(1) 