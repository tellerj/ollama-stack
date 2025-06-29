"""
Check command implementation for the Ollama Stack CLI.

This module handles environment validation for the Ollama Stack by delegating
to the StackManager for comprehensive checks.

## Key Validation Areas

- **Docker Environment**: Daemon availability, runtime configuration
- **Port Availability**: Required ports for stack services
- **Platform Requirements**: NVIDIA runtime, native Ollama installation  
- **Configuration**: Config files existence and validity
- **Compose Files**: Docker compose file availability for current platform

## Fix Functionality

The --fix flag attempts to resolve common issues automatically where possible.

## Execution Flow Diagram

```mermaid
sequenceDiagram
    participant CLI as CLI
    participant Main as main.py
    participant Check as check.py
    participant Ctx as context.py<br/>(AppContext)
    participant Config as config.py<br/>(Config)
    participant SM as stack_manager.py<br/>(StackManager)
    participant DC as docker_client.py<br/>(DockerClient)
    participant OAC as ollama_api_client.py<br/>(OllamaApiClient)
    participant Display as display.py<br/>(Display)

    CLI->>Main: ollama-stack check --fix
    Main->>Main: @app.callback() - Initialize context
    Main->>Ctx: AppContext(verbose=False)
    
    Note over Ctx: Initialize core services
    Ctx->>Display: Display(verbose=False)
    Ctx->>Config: Config(display)
    Config->>Config: load_config() → (AppConfig, fell_back_to_defaults)
    Ctx->>SM: StackManager(config.app_config, display)
    
    Note over SM: Platform detection and service configuration
    SM->>SM: detect_platform() → "apple"
    SM->>SM: configure_services_for_platform()
    Note over SM: ollama.type = "native-api" (Apple Silicon)
    SM->>DC: DockerClient(config, display)
    SM->>OAC: OllamaApiClient(display)
    
    Main->>Check: check(ctx, fix=True)
    Check->>Check: check_environment_logic(app_context, fix=True)
    
    Note over Check: Handle configuration fallback
    Check->>Config: config.fell_back_to_defaults
    Config-->>Check: True/False
    alt fell_back_to_defaults == True AND fix == True
        Check->>Config: config.save()
        Config-->>Check: Create default config files
    end
    
    Note over Check: Delegate comprehensive checks
    Check->>SM: run_environment_checks(fix=True)
    SM->>SM: log.debug("Running comprehensive environment checks...")
    
    Note over SM: Docker environment checks
    SM->>DC: run_environment_checks(fix=True, platform="apple")
    
    Note over DC: 1. Docker Daemon Check
    DC->>DC: client.ping()
    DC->>DC: EnvironmentCheck("Docker Daemon Running", passed=True)
    
    Note over DC: 2. Port Availability Checks
    DC->>DC: _check_required_ports()
    DC->>DC: _is_port_available(11434) → True
    DC->>DC: _is_port_available(8080) → True  
    DC->>DC: _is_port_available(8200) → True
    DC->>DC: EnvironmentCheck("Port 11434 Available", passed=True)
    DC->>DC: EnvironmentCheck("Port 8080 Available", passed=True)
    DC->>DC: EnvironmentCheck("Port 8200 Available", passed=True)
    
    Note over DC: 3. Skip NVIDIA checks (apple platform)
    
    Note over DC: 4. Compose File Checks
    DC->>DC: _check_compose_files(fix=True)
    DC->>DC: Path("docker-compose.yml").exists() → True
    DC->>DC: EnvironmentCheck("Compose File: docker-compose.yml", passed=True)
    
    Note over DC: 5. Docker Images Check (fix=True)
    DC->>DC: _check_and_pull_images()
    DC->>DC: pull_images()
    DC->>DC: _run_compose_command(["pull"])
    DC->>DC: EnvironmentCheck("Docker Images", passed=True)
    
    DC-->>SM: CheckReport(docker_checks)
    
    Note over SM: Platform-specific native checks
    alt platform == "apple"
        SM->>OAC: run_environment_checks(fix=True)
        
        Note over OAC: Check Ollama installation
        OAC->>OAC: shutil.which("ollama") → "/usr/local/bin/ollama"
        OAC->>OAC: EnvironmentCheck("Ollama Installation (Native)", passed=True)
        
        OAC-->>SM: List[EnvironmentCheck]
        SM->>SM: report.checks.extend(native_checks)
    end
    
    SM-->>Check: CheckReport(all_checks)
    
    Note over Check: Summary logging
    Check->>Check: passed_count = sum(check.passed for check in report.checks)
    Check->>Check: log.info("All environment checks passed (8/8)")
    
    Check-->>Check: return report
    Check->>Display: display.check_report(report)
    
    Note over Display: Format and display results
    Display->>Display: log.info("Running environment checks...")
    loop for each check in report.checks
        Display->>Display: console.print("[bold green]PASSED[/]: {check.name}")
        alt check.passed == False
            Display->>Display: console.print("Details: {check.details}")
            Display->>Display: console.print("Suggestion: {check.suggestion}")
        end
    end
```

## Key Architecture Points

- **Platform Detection**: StackManager detects platform and configures service types accordingly
- **Clean Delegation**: Command coordinates, StackManager orchestrates, clients implement
- **Configuration Recovery**: Handles config fallback scenarios with optional automatic fixing
- **Comprehensive Validation**: Docker daemon, ports, platform requirements, compose files, images
- **Platform-Aware Checks**: Different validation paths for Apple Silicon vs NVIDIA vs CPU platforms
- **Error Recovery**: Individual check failures don't stop the validation process
- **Centralized Display**: All output routed through consistent display system
"""

import typer
import logging
from typing_extensions import Annotated

from ..context import AppContext

log = logging.getLogger(__name__)


def check_environment_logic(app_context: AppContext, fix: bool = False):
    """Business logic for running environment checks."""
    log.info("Running environment checks...")
    
    # Check if config fell back to defaults and inform user
    if app_context.config.fell_back_to_defaults:
        log.info("Configuration file appears to be empty or corrupted. Using default settings.")
        if fix:
            try:
                app_context.config.save()
                log.info("Created default configuration files")
            except Exception as e:
                log.error(f"Failed to create configuration files: {e}")
    
    # Delegate comprehensive environment checks to stack manager
    report = app_context.stack_manager.run_environment_checks(fix=fix)
    
    # Summary logging
    passed_count = sum(1 for check in report.checks if check.passed)
    total_count = len(report.checks)
    
    if passed_count == total_count:
        log.info(f"All environment checks passed ({passed_count}/{total_count})")
    else:
        failed_count = total_count - passed_count
        log.warning(f"Environment check results: {passed_count} passed, {failed_count} failed")
    
    return report


def check(
    ctx: typer.Context,
    fix: Annotated[
        bool,
        typer.Option("--fix", help="Attempt to fix issues where possible."),
    ] = False,
):
    """Verifies environment requirements and Docker setup."""
    app_context: AppContext = ctx.obj
    report = check_environment_logic(app_context, fix=fix)
    app_context.display.check_report(report)