import typer
import logging
import time
from typing_extensions import Annotated

from ..context import AppContext
from ..schemas import StackStatus

log = logging.getLogger(__name__)


def get_stack_status_logic(app_context: AppContext, extensions_only: bool = False) -> StackStatus:
    """
    Business logic for gathering comprehensive stack status.
    
    This function coordinates status gathering from all stack components:
    - Core services (Docker containers and native services)
    - Extensions (when supported)
    
    Execution Flow:
    ├── Service Configuration Check
    │   ├── Validate services are configured
    │   └── Categorize by type (docker/native-api)
    ├── Platform-Aware Status Gathering
    │   ├── Log service types being checked
    │   └── Delegate to StackManager.get_stack_status()
    ├── StackManager Orchestration
    │   ├── Docker Services → DockerClient.get_container_status()
    │   ├── Native Services → OllamaApiClient.get_status()
    │   └── Error handling for failed clients
    └── Summary Analysis
        ├── Count running vs total services
        └── Generate user-friendly status messages
    
    Args:
        app_context: Application context with configuration and clients
        extensions_only: If True, only check extension status
        
    Returns:
        StackStatus: Comprehensive status for all stack components
    """
    log.info("Gathering stack status...")
    
    # Check if any services are configured
    services_config = app_context.stack_manager.config.services
    if not services_config:
        log.info("No services configured")
        return app_context.stack_manager.get_stack_status(extensions_only=extensions_only)
    
    # Log what types of services we're checking
    docker_services = [name for name, conf in services_config.items() if conf.type == 'docker']
    native_services = [name for name, conf in services_config.items() if conf.type == 'native-api']
    
    if extensions_only:
        log.info("Checking extension status only...")
    else:
        service_summary = []
        if docker_services:
            service_summary.append(f"{len(docker_services)} Docker service{'s' if len(docker_services) > 1 else ''}")
        if native_services:
            service_summary.append(f"{len(native_services)} native service{'s' if len(native_services) > 1 else ''}")
        
        if service_summary:
            log.info(f"Checking status of {' and '.join(service_summary)}...")
        else:
            log.info("No core services configured")
    
    # Delegate to stack manager for comprehensive status gathering
    stack_status = app_context.stack_manager.get_stack_status(extensions_only=extensions_only)
    
    # Summary logging
    if not extensions_only and stack_status.core_services:
        running_count = sum(1 for service in stack_status.core_services if service.is_running)
        total_count = len(stack_status.core_services)
        
        if running_count == total_count:
            log.info(f"All services are running ({running_count}/{total_count})")
        elif running_count == 0:
            log.info(f"All services are stopped ({running_count}/{total_count})")
        else:
            log.info(f"Mixed service states: {running_count}/{total_count} running")
    
    return stack_status


def watch_status(app_context: AppContext, extensions_only: bool = False, json_output: bool = False, interval: int = 3):
    """Continuously monitor stack status with periodic updates."""
    log.info(f"Starting continuous status monitoring (refresh every {interval}s). Press Ctrl+C to stop...")
    
    try:
        while True:
            # Clear screen and show timestamp
            import os
            os.system('clear' if os.name == 'posix' else 'cls')
            
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            app_context.log.info(f"Stack Status - {timestamp} (refresh every {interval}s)")
            app_context.log.info("Press Ctrl+C to stop monitoring")
            print()
            
            # Get and display current status
            stack_status = get_stack_status_logic(app_context, extensions_only=extensions_only)
            
            if json_output:
                app_context.display.json(stack_status.model_dump_json())
            else:
                app_context.display.status(stack_status)
            
            # Wait for next refresh
            time.sleep(interval)
            
    except KeyboardInterrupt:
        log.info("Status monitoring stopped by user")
        app_context.log.info("\nStatus monitoring stopped.")


def status(
    ctx: typer.Context,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output in JSON format."),
    ] = False,
    extensions_only: Annotated[
        bool,
        typer.Option("--extensions", help="Show only extension status."),
    ] = False,
    watch: Annotated[
        bool,
        typer.Option(
            "--watch",
            help="Continuously monitor stack status.",
        ),
    ] = False,
):
    """
    Displays comprehensive stack status for all stack components.
    
    This command provides detailed status information for Docker containers,
    native services, and extensions. It follows the lightweight delegation
    pattern where the command coordinates execution while StackManager
    orchestrates the actual status gathering.
    
    ## Execution Flow Diagram
    
    ```mermaid
    sequenceDiagram
        participant User
        participant Typer as "Typer CLI"
        participant StatusCmd as "Status Command"
        participant StackMgr as "StackManager"
        participant DockerClient as "DockerClient"
        participant OllamaClient as "OllamaApiClient"
        participant Display

        User->>Typer: ollama-stack status --json --extensions
        Typer->>Typer: Parse CLI arguments<br/>(json_output=True, extensions_only=True)
        Typer->>StatusCmd: status(ctx, json_output=True, extensions_only=True, watch=False)
        
        StatusCmd->>StatusCmd: Extract AppContext from ctx.obj
        
        alt Watch Mode Check
            StatusCmd->>StatusCmd: if watch: call watch_status() and return
        end
        
        StatusCmd->>StatusCmd: get_stack_status_logic(app_context, extensions_only=True)
        
        Note over StatusCmd: Business Logic Layer
        StatusCmd->>StatusCmd: log.info("Gathering stack status...")
        StatusCmd->>StackMgr: Access config.services
        StackMgr-->>StatusCmd: services configuration
        
        alt No Services Configured
            StatusCmd->>StatusCmd: log.info("No services configured")
        else Services Exist
            StatusCmd->>StatusCmd: Categorize services (docker vs native)
            StatusCmd->>StatusCmd: log.info("Checking extension status only...")
        end
        
        StatusCmd->>StackMgr: get_stack_status(extensions_only=True)
        
        Note over StackMgr: StackManager Orchestration
        StackMgr->>StackMgr: Initialize core_services=[], extensions=[]
        
        alt extensions_only=False
            StackMgr->>StackMgr: Filter docker_services by type='docker'
            StackMgr->>StackMgr: log.debug("Getting status for Docker services...")
            
            opt Docker Services Exist
                StackMgr->>DockerClient: get_container_status(docker_services)
                DockerClient->>DockerClient: Check Docker containers via API
                DockerClient-->>StackMgr: List[ServiceStatus] for Docker services
                StackMgr->>StackMgr: core_services.extend(docker_statuses)
            end
            
            StackMgr->>StackMgr: Filter native_services by type='native-api'
            
            loop For each native service
                StackMgr->>StackMgr: log.debug("Getting status for native service...")
                StackMgr->>StackMgr: get_native_service_status(service_name)
                
                alt service_name == "ollama"
                    StackMgr->>OllamaClient: get_status()
                    OllamaClient->>OllamaClient: Check Ollama API health
                    OllamaClient-->>StackMgr: ServiceStatus for Ollama
                else Unknown Native Service
                    StackMgr->>StackMgr: Return generic ServiceStatus<br/>(status="unknown")
                end
                
                StackMgr->>StackMgr: core_services.append(service_status)
            end
        end
        
        Note over StackMgr: TODO: Extensions support (currently empty)
        StackMgr->>StackMgr: extensions = []
        
        StackMgr-->>StatusCmd: StackStatus(core_services, extensions)
        
        Note over StatusCmd: Summary Analysis
        StatusCmd->>StatusCmd: Count running vs total services
        
        alt All Services Running
            StatusCmd->>StatusCmd: log.info("All services are running (X/Y)")
        else Mixed States
            StatusCmd->>StatusCmd: log.info("Mixed service states: X/Y running")
        else All Stopped
            StatusCmd->>StatusCmd: log.info("All services are stopped (0/Y)")
        end
        
        StatusCmd-->>StatusCmd: return StackStatus
        
        Note over StatusCmd: Output Routing
        alt JSON Output
            StatusCmd->>Display: json(stack_status.model_dump_json())
            Display->>Display: Serialize and print JSON
        else Table Output
            StatusCmd->>Display: status(stack_status)
            Display->>Display: Render Rich table format
        end
        
        Display-->>User: Status output (JSON or table)
        
        Note over User,Display: Watch Mode Flow (if --watch)
        rect rgb(240, 248, 255)
            Note over StatusCmd: watch_status() implementation
            StatusCmd->>StatusCmd: while True loop
            StatusCmd->>StatusCmd: Clear screen + timestamp
            StatusCmd->>StatusCmd: Call get_stack_status_logic()
            StatusCmd->>StatusCmd: Display results
            StatusCmd->>StatusCmd: time.sleep(3)
            StatusCmd->>StatusCmd: Handle Ctrl+C → break
        end
    ```
    
    ## Key Architecture Points
    
    - **Lightweight Command Pattern**: Status command acts as coordinator, not implementer
    - **Delegation Hierarchy**: Command → StackManager → Clients → Display  
    - **Platform Awareness**: StackManager routes to appropriate clients based on service types
    - **Error Resilience**: Each client interaction is wrapped with proper error handling
    - **Display Abstraction**: All output goes through Display module for consistency
    - **Watch Mode**: Continuous monitoring with graceful exit handling
    
    ## Critical Decision Points
    
    - **Watch Mode Check**: Early exit if `--watch` flag is set
    - **Extensions Only Filter**: Skips core services if `--extensions` flag is used  
    - **Service Type Routing**: Docker services → DockerClient, Native services → OllamaApiClient
    - **Output Format**: JSON vs Rich table based on `--json` flag
    
    Args:
        ctx: Typer context containing AppContext
        json_output: Output results in JSON format instead of table
        extensions_only: Only check extension status, skip core services
        watch: Enable continuous monitoring with periodic refresh
        
    Examples:
        Basic status check:
            ollama-stack status
            
        JSON output:
            ollama-stack status --json
            
        Extensions only:
            ollama-stack status --extensions
            
        Continuous monitoring:
            ollama-stack status --watch
    """
    app_context: AppContext = ctx.obj
    
    if watch:
        watch_status(app_context, extensions_only=extensions_only, json_output=json_output)
        return
    
    try:
        # Get status information
        stack_status = get_stack_status_logic(app_context, extensions_only=extensions_only)
        
        # Display results
        if json_output:
            app_context.display.json(stack_status.model_dump_json())
        else:
            app_context.display.status(stack_status)
            
    except Exception as e:
        log.error(f"Failed to get stack status: {e}")
        app_context.display.error(
            f"Unable to retrieve stack status: {e}",
            "Check if Docker is running and services are properly configured."
        )
        raise typer.Exit(1)