"""
Update command implementation for the Ollama Stack CLI.

This module handles updating Docker images for core services and enabled extensions.
The execution flow involves platform-aware image pulling with smart state management.

## Execution Flow Diagram

```mermaid
sequenceDiagram
    participant CLI as CLI
    participant Main as main.py
    participant Update as update.py
    participant Ctx as context.py<br/>(AppContext)
    participant Config as config.py<br/>(Config)
    participant SM as stack_manager.py<br/>(StackManager)
    participant DC as docker_client.py<br/>(DockerClient)
    participant Docker as subprocess<br/>(Docker API)
    
    CLI->>Main: ollama-stack update [--services|--extensions]
    Main->>Main: @app.callback()
    Main->>Ctx: AppContext(verbose=False)
    Ctx->>Ctx: Display(verbose=False)
    Ctx->>Config: Config(display)
    Config->>Config: load_config() → (AppConfig, fell_back_to_defaults)
    Config->>Config: detect_platform() → "apple"
    Ctx->>SM: StackManager(config.app_config, display)
    SM->>SM: detect_platform() → "apple"
    SM->>SM: configure_services_for_platform()
    Note over SM: ollama.type = "native-api" (Apple Silicon)
    SM->>DC: DockerClient(config, display)
    
    Main->>Update: update(ctx, services=False, extensions=False)
    Update->>Update: update_services_logic(app_context, services_only, extensions_only)
    
    Note over Update: VALIDATION PHASE
    Update->>Update: Validate flags (services_only && extensions_only = error)
    Update->>Update: update_core = not extensions_only
    Update->>Update: update_extensions = not services_only
    
    Note over Update: STATE DETECTION PHASE
    Update->>SM: is_stack_running()
    SM->>DC: is_stack_running()
    DC->>Docker: docker.client.containers.list(filters={"label": "ollama-stack.component"})
    Docker-->>DC: containers[]
    DC-->>SM: stack_running=True/False
    SM-->>Update: stack_running=True/False
    
    Note over Update: CONTEXT DETECTION
    Update->>Update: inspect.stack() → calling_functions[]
    Update->>Update: called_from_start_restart = any(["start_services_logic", "restart_services_logic"])
    
    alt stack_running && called_from_start_restart
        Update->>Update: log.info("Updating images for running services...")
        Note over Update: No restart needed - start/restart will handle
    else stack_running && !called_from_start_restart
        Update->>Update: display.info("Stack is currently running...")
        Update->>CLI: typer.confirm("Stop the stack to proceed?")
        CLI-->>Update: user_confirms=True/False
        alt user_confirms == True
            Update->>Update: log.info("Stopping stack...")
            Update->>SM: stop_stack()
            SM->>DC: stop_services(compose_files)
            DC->>Docker: subprocess.run(["docker-compose", "down"])
            Docker-->>DC: success
            DC-->>SM: success
            SM-->>Update: success
            Update->>Update: restart_after_update = True
        else user_confirms == False
            Update->>Update: log.info("Update cancelled")
            Update-->>Main: return False
        end
    end
    
    Note over Update: CORE SERVICES UPDATE PHASE
    alt update_core == True
        Update->>Update: log.info("Updating core stack services...")
        Update->>SM: pull_images()
        SM->>SM: get_compose_files() → ["docker-compose.yml", "docker-compose.apple.yml"]
        SM->>DC: pull_images(compose_files)
        DC->>DC: _run_compose_command(["pull"], compose_files)
        DC->>Docker: subprocess.run(["docker-compose", "-f", "docker-compose.yml", "-f", "docker-compose.apple.yml", "pull"])
        Docker-->>DC: return_code=0 (success)
        DC-->>SM: True
        SM-->>Update: True
        Update->>Update: log.info("Core services updated successfully")
    end
    
    Note over Update: EXTENSIONS UPDATE PHASE
    alt update_extensions == True
        Update->>Config: config.app_config.extensions.enabled
        Config-->>Update: enabled_extensions=["ext1", "ext2"]
        
        alt enabled_extensions exists
            Update->>Update: log.info("Updating X enabled extensions...")
            loop for each extension_name in enabled_extensions
                Update->>Update: log.info("Updating extension: {name}")
                Note over Update: TODO: Extension image pulling not yet implemented
                Update->>Update: log.warning("Extension update not yet implemented")
            end
            Update->>Update: log.info("All enabled extensions updated successfully")
        else no enabled_extensions
            Update->>Update: log.info("No extensions enabled, skipping extension updates")
        end
    end
    
    Note over Update: RESTART PHASE (if needed)
    alt restart_after_update == True
        Update->>Update: log.info("Restarting stack...")
        Update->>Update: from .start import start_services_logic
        Update->>Update: start_services_logic(ctx)
        Note over Update: Delegates to start command logic
        Update->>Update: log.info("Stack restarted successfully after update")
    end
    
    Note over Update: COMPLETION PHASE
    alt update_core && update_extensions
        Update->>Update: log.info("Update completed successfully - core services and extensions are up to date")
    else update_core only
        Update->>Update: log.info("Core services update completed successfully")
    else update_extensions only
        Update->>Update: log.info("Extension updates completed successfully")
    end
    
    Update-->>Main: return True (success)
    Main-->>CLI: exit_code=0
```

## Key Architecture Points

- **Thin Command Layer**: Handles CLI flags, user confirmation, and context detection
- **StackManager Orchestration**: Core update logic lives in StackManager.update_stack()
- **Context-Aware Execution**: Detects if called from start/restart to avoid double-prompting users  
- **Smart State Management**: Handles running vs stopped stack states intelligently
- **Platform Detection**: Uses detected platform (Apple/NVIDIA/CPU) for appropriate compose files
- **Extension Ready**: Framework in place for extension updates when extension manager is available
"""

import typer
import logging
from typing import Optional
from ..context import AppContext

log = logging.getLogger(__name__)


def update_services_logic(
    app_context: AppContext, 
    services_only: bool = False, 
    extensions_only: bool = False
) -> tuple[bool, bool]:
    """
    Business logic for updating services and extensions.
    
    Args:
        app_context: The application context containing all services
        services_only: Only update core stack services
        extensions_only: Only update enabled extensions
        
    Returns:
        tuple[bool, bool]: (success, user_cancelled)
            - success: True if update succeeded, False if failed
            - user_cancelled: True if user cancelled, False otherwise
    """
    ctx = app_context
    
    # Check current stack status
    stack_running = ctx.stack_manager.is_stack_running()
    force_restart = False
    
    # Handle running stack state with CLI-specific logic
    if stack_running:
        # When called directly (not from start/restart), prompt for confirmation
        log.info("Stack is currently running. Updates require stopping services.")
        if typer.confirm("Stop the stack to proceed with update?"):
            log.info("Proceeding with update...")
            force_restart = True
        else:
            log.info("Update cancelled")
            return False, True  # Failed due to user cancellation
    
    # Check for version transitions and handle them appropriately
    current_version = ctx.config.app_config.version
    latest_version = "0.4.0"  # This would come from a version registry in the future
    
    if current_version != latest_version:
        log.info(f"Detected version transition: {current_version} → {latest_version}")
        
        # For major version updates, create automatic backup
        if _is_major_version_update(current_version, latest_version):
            log.info("Major version update detected - creating automatic backup...")
            if not _create_version_update_backup(ctx):
                log.error("Failed to create backup before version update")
                if not typer.confirm("Continue without backup?"):
                    log.info("Update cancelled")
                    return False, True  # Failed due to user cancellation
    
    # Delegate to StackManager for orchestration
    success = ctx.stack_manager.update_stack(
        services_only=services_only,
        extensions_only=extensions_only, 
        force_restart=force_restart,
        called_from_start_restart=False  # Always False when called directly
    )
    
    # Update version if update was successful
    if success and current_version != latest_version:
        log.info(f"Updating stack version from {current_version} to {latest_version}")
        ctx.config.app_config.version = latest_version
        # Save the updated config
        from ..config import save_config
        save_config(ctx.display, ctx.config.app_config)
    
    return success, False  # Success or failure, but not user cancellation


def _is_major_version_update(current_version: str, target_version: str) -> bool:
    """Check if this is a major version update that requires backup."""
    try:
        current_major = int(current_version.split('.')[0])
        target_major = int(target_version.split('.')[0])
        return target_major > current_major
    except (ValueError, IndexError):
        # If version parsing fails, assume it's a major update to be safe
        return True


def _create_version_update_backup(ctx: AppContext) -> bool:
    """Create a backup before version update."""
    import datetime
    from pathlib import Path
    
    backup_dir = Path(ctx.config.app_config.backup_directory) / f"pre-version-update-{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}"
    
    log.info(f"Creating backup at: {backup_dir}")
    return ctx.stack_manager.create_backup(backup_dir)


def update(
    ctx: typer.Context,
    services: bool = typer.Option(
        False, 
        "--services", 
        help="Only update core stack services"
    ),
    extensions: bool = typer.Option(
        False, 
        "--extensions", 
        help="Only update enabled extensions"
    )
):
    """
    Pull the latest Docker images for the core stack and all enabled extensions.
    
    This command will:
    1. Check if the stack is running and prompt for confirmation before stopping
    2. Detect version transitions and create automatic backups for major updates
    3. Pull latest images for core services (ollama, open-webui, mcp-proxy) 
    4. Pull latest images for all enabled extensions
    5. Update the stack version if a version transition is detected
    6. Restart the stack if it was running before the update
    
    Use --services to only update core services, or --extensions to only update extensions.
    """
    app_context: AppContext = ctx.obj
    
    # Validate conflicting flags
    if services and extensions:
        log.error("Cannot use both --services and --extensions flags together")
        raise typer.Exit(2)
    
    success, user_cancelled = update_services_logic(
        app_context, 
        services_only=services, 
        extensions_only=extensions
    )
    
    if user_cancelled:
        # User cancelled - this is normal, exit with code 0
        return
    
    if not success:
        raise typer.Exit(1) 