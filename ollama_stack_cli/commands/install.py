"""
Install command implementation for the Ollama Stack CLI.

This module handles fresh stack initialization, creating configuration files
and preparing the environment for first use.

## Execution Flow Diagram

```mermaid
sequenceDiagram
    participant CLI as CLI
    participant Main as main.py
    participant Install as install.py
    participant Ctx as context.py<br/>(AppContext)
    participant Config as config.py<br/>(Config)
    participant SM as stack_manager.py<br/>(StackManager)
    participant FS as File System<br/>(~/.ollama-stack/)
    
    CLI->>Main: ollama-stack install [--force]
    Main->>Main: @app.callback()
    Main->>Ctx: AppContext(verbose)
    Ctx->>Config: Config(display)
    Config->>Config: load_config() → (AppConfig, fell_back_to_defaults)
    Ctx->>SM: StackManager(config.app_config, display)
    SM->>SM: detect_platform() → "apple"/"nvidia"/"cpu"
    SM->>SM: configure_services_for_platform()
    
    Main->>Install: install(ctx, force)
    Install->>Install: install_logic(app_context, force)
    
    Install->>SM: install_stack(force=force)
    SM->>SM: Check if ~/.ollama-stack/ exists
    
    alt Directory exists AND force=False AND config files exist
        SM->>CLI: typer.confirm("Overwrite existing configuration?")
        CLI-->>SM: User response (True/False)
        alt User declines
            SM-->>Install: return False
            Install->>CLI: "Installation cancelled by user"
        end
    end
    
    SM->>FS: DEFAULT_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    FS-->>SM: Directory created
    
    SM->>SM: _generate_secure_key() → 64-char secure key
    SM->>SM: Create AppConfig with platform configurations
    SM->>Config: save_config(app_config, config_file, env_file)
    Config->>FS: Write ~/.ollama-stack/.ollama-stack.json
    Config->>FS: Write ~/.ollama-stack/.env
    FS-->>Config: Files created
    
    SM->>SM: run_environment_checks(fix=False)
    SM->>SM: Generate CheckReport with validation results
    SM->>SM: display.check_report(check_report)
    
    alt All checks pass
        SM->>CLI: "Environment validation completed - all checks passed!"
    else Some checks fail
        SM->>CLI: "Some environment checks failed. Run `ollama-stack check --fix`"
    end
    
    SM-->>Install: return True
    Install->>CLI: "Installation completed successfully!"
    Install->>CLI: "Run `ollama-stack start` to begin using the stack"
```

## Key Architecture Points

- **Fresh Installation**: Creates new configuration in ~/.ollama-stack/ directory
- **User Confirmation**: Prompts before overwriting existing configuration (unless --force)
- **Secure Key Generation**: Creates cryptographically secure 64-character WebUI secret key
- **Platform Awareness**: Generates platform-specific configurations (apple/nvidia/cpu)
- **Environment Validation**: Runs comprehensive checks after configuration creation
- **User Guidance**: Provides clear next steps and handles failed validation gracefully

## Artifacts Created

- **~/.ollama-stack/.ollama-stack.json**: Main configuration with services, platform configs
- **~/.ollama-stack/.env**: Environment variables including PROJECT_NAME and WEBUI_SECRET_KEY
"""

import logging as log
import typer
from ..context import AppContext


def install_logic(app_context: AppContext, force: bool = False) -> bool:
    """
    Business logic for the install command.
    
    Args:
        app_context: The application context containing config, display, and stack_manager
        force: Whether to overwrite existing configuration without prompting
        
    Returns:
        bool: True if installation succeeded, False otherwise
    """
    log.info("Starting fresh stack installation...")
    
    try:
        # Delegate to stack manager for the actual installation logic
        success = app_context.stack_manager.install_stack(force=force)
        
        if success:
            app_context.display.success("Installation completed successfully!")
            app_context.display.panel(
                "Run `ollama-stack start` to begin using the stack",
                "Next Steps",
                border_style="green"
            )
            log.info("Installation completed successfully")
        else:
            app_context.display.error("Installation failed - check logs for details")
            log.error("Installation failed")
            
        return success
        
    except Exception as e:
        error_msg = f"Installation failed: {str(e)}"
        app_context.display.error(error_msg)
        log.error(error_msg, exc_info=True)
        return False


def install(
    ctx: typer.Context,
    force: bool = typer.Option(False, "--force", help="Overwrite existing configuration files without prompting")
):
    """
    Initialize fresh stack configuration and prepare environment for first use.
    
    This command creates a new installation in ~/.ollama-stack/ with default
    configuration files and runs environment checks to validate the setup.
    """
    app_context: AppContext = ctx.obj
    install_logic(app_context, force) 