import typer
import logging
from typing_extensions import Annotated
from typing import Optional
from datetime import datetime

from ..context import AppContext

log = logging.getLogger(__name__)


def logs_services_logic(app_context: AppContext, service_or_extension: Optional[str], follow: bool, tail: Optional[int], level: Optional[str], since: Optional[str], until: Optional[str]):
    """
    Business logic for streaming logs with platform-aware service routing.
    
    This function routes log requests to the appropriate client based on service type:
    - Docker services → DockerClient.stream_logs()
    - Native services → OllamaApiClient.get_logs() (via StackManager)
    - Extensions → DockerClient.stream_logs() (treated as Docker services)
    - Unknown/All → DockerClient.stream_logs() (for all Docker services)
    """
    log.info("Streaming logs from services...")
    
    # Check if service_or_extension is a valid service name
    service_config = app_context.stack_manager.config.services.get(service_or_extension) if service_or_extension else None
    
    if service_or_extension and service_config:
        # We have a known service - route based on type
        service_type = service_config.type
        log.info(f"Service '{service_or_extension}' found with type: {service_type}")
        
        if service_type == 'docker':
            log.info(f"Streaming logs from Docker service: {service_or_extension}")
            yield from app_context.stack_manager.stream_docker_logs(service_or_extension, follow, tail, level, since, until)
            
        elif service_type == 'native-api':
            log.info(f"Streaming logs from native service: {service_or_extension}")
            yield from app_context.stack_manager.stream_native_logs(service_or_extension, follow, tail, level, since, until)
            
        elif service_type == 'remote-api':
            log.warning(f"Log streaming not supported for remote service: {service_or_extension}")
            log.info("Remote services run on external systems - check their own logging systems")
            
        else:
            log.error(f"Unknown service type '{service_type}' for service '{service_or_extension}'")
            
    elif service_or_extension:
        # Unknown service name - could be an extension or invalid service
        log.info(f"Unknown service '{service_or_extension}', treating as Docker service/extension")
        yield from app_context.stack_manager.stream_docker_logs(service_or_extension, follow, tail, level, since, until)
        
    else:
        # No specific service - stream all Docker services
        log.info("Streaming logs from all Docker services")
        
        # Check what types of services are configured
        services_config = app_context.stack_manager.config.services
        docker_services = [name for name, conf in services_config.items() if conf.type == 'docker']
        native_services = [name for name, conf in services_config.items() if conf.type == 'native-api']
        
        if docker_services and native_services:
            log.info(f"Found {len(docker_services)} Docker service(s) and {len(native_services)} native service(s)")
            log.info(f"Streaming logs from Docker services: {', '.join(docker_services)}")
            log.info("Use 'ollama-stack logs <service>' to view native service logs individually")
        elif docker_services:
            log.info(f"Found {len(docker_services)} Docker service(s) only")
        elif native_services:
            log.info(f"Found {len(native_services)} native service(s) only")
            log.info("No Docker services configured")
            log.info(f"Native services available: {', '.join(native_services)}")
            log.info("Use 'ollama-stack logs <service>' to view individual service logs")
            return
        else:
            log.info("No services configured in the stack")
            return
            
        yield from app_context.stack_manager.stream_docker_logs(None, follow, tail, level, since, until)


def logs(
    ctx: typer.Context,
    service: Optional[str] = typer.Argument(None, help="Name of the service to stream logs from."),
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow the logs as they are generated."),
    tail: Optional[int] = typer.Option(None, "--tail", "-t", help="Number of lines to show from the end of the logs."),
    level: Optional[str] = typer.Option(None, "--level", help="Log level (e.g., info, warning, error)."),
    since: Optional[datetime] = typer.Option(None, "--since", help="Show logs since a timestamp (e.g., 2023-06-18T10:30:00)."),
    until: Optional[datetime] = typer.Option(None, "--until", help="Show logs until a timestamp."),
):
    """
    Streams logs from a specific service or all services with platform-aware routing.
    
    This command provides comprehensive log streaming for all service types in the stack:
    - Docker services (containers)
    - Native services (like Ollama on Apple Silicon)
    - Extensions (treated as Docker services)
    
    The command intelligently routes log requests based on service type and provides
    helpful information for native services where traditional container logs aren't available.
    
    ## Execution Flow Diagram
    
    ```mermaid
    sequenceDiagram
        participant User
        participant Typer as "Typer CLI"
        participant LogsCmd as "Logs Command"
        participant StackMgr as "StackManager"
        participant DockerClient as "DockerClient"
        participant OllamaClient as "OllamaApiClient"
        participant FileSystem as "~/.ollama/logs/"
        participant Display

        User->>Typer: ollama-stack logs [service] --follow --tail 100
        Typer->>Typer: Parse CLI arguments and convert datetime objects
        Typer->>LogsCmd: logs(ctx, service, follow=True, tail=100, ...)
        
        LogsCmd->>LogsCmd: Extract AppContext from ctx.obj
        LogsCmd->>LogsCmd: Convert datetime objects to ISO strings
        LogsCmd->>LogsCmd: logs_services_logic(app_context, service, ...)
        
        Note over LogsCmd: Service Type Detection & Routing
        LogsCmd->>StackMgr: config.services.get(service)
        StackMgr-->>LogsCmd: ServiceConfig with type
        
        alt Specific Service Requested
            alt Docker Service (Intel/AMD/NVIDIA)
                LogsCmd->>LogsCmd: log.info("Streaming logs from Docker service")
                LogsCmd->>StackMgr: stream_docker_logs(service, follow, tail, ...)
                StackMgr->>DockerClient: stream_logs(service, follow, tail, ...)
                DockerClient->>DockerClient: subprocess.Popen(docker-compose logs ...)
                loop For each log line
                    DockerClient-->>StackMgr: yield actual_log_line
                    StackMgr-->>LogsCmd: yield actual_log_line
                end
            end
            
            alt Native Service (Apple Silicon Ollama)
                LogsCmd->>LogsCmd: log.info("Streaming logs from native service")
                LogsCmd->>StackMgr: stream_native_logs(service, follow, tail, ...)
                StackMgr->>OllamaClient: get_logs(follow, tail, ...)
                OllamaClient->>OllamaClient: Check ollama installation & running status
                OllamaClient->>FileSystem: Access ~/.ollama/logs/server.log
                
                alt Follow Mode
                    OllamaClient->>FileSystem: subprocess.Popen(["tail", "-f", log_file])
                    loop Real-time streaming
                        FileSystem-->>OllamaClient: New log line from file
                        OllamaClient-->>StackMgr: yield log_line.strip()
                        StackMgr-->>LogsCmd: yield log_line
                    end
                end
                
                alt Static Mode
                    OllamaClient->>FileSystem: open(log_file, 'r').readlines()
                    FileSystem-->>OllamaClient: All log lines
                    OllamaClient->>OllamaClient: Apply tail limit if specified
                    loop For each log line
                        OllamaClient-->>StackMgr: yield log_line.strip()
                        StackMgr-->>LogsCmd: yield log_line
                    end
                end
            end
            
            alt Remote Service
                LogsCmd->>LogsCmd: log.warning("Log streaming not supported")
                LogsCmd->>LogsCmd: log.info("Check remote system logs")
                Note over LogsCmd: No yielded output - only logging messages
            end
            
            alt Unknown Service
                LogsCmd->>LogsCmd: log.info("Unknown service, treating as Docker")
                LogsCmd->>StackMgr: stream_docker_logs(service, ...)
                Note over DockerClient: May return docker-compose error if not found
            end
        end
        
        alt No Specific Service (All Services)
            LogsCmd->>LogsCmd: Categorize configured services by type
            
            alt Mixed or Docker-Only Services
                LogsCmd->>LogsCmd: log.info("Streaming logs from Docker services")
                LogsCmd->>LogsCmd: log.info("Use 'logs <service>' for native services")
                LogsCmd->>StackMgr: stream_docker_logs(None, ...)
                StackMgr->>DockerClient: stream_logs(None, ...)
                loop For each log line
                    DockerClient-->>LogsCmd: yield actual_log_line
                end
            end
            
            alt Only Native Services
                LogsCmd->>LogsCmd: log.info("No Docker services configured")
                LogsCmd->>LogsCmd: log.info("Native services available: [...]")
                LogsCmd->>LogsCmd: log.info("Use 'logs <service>' for individual logs")
                LogsCmd->>LogsCmd: return (no log streaming)
            end
            
            alt No Services
                LogsCmd->>LogsCmd: log.info("No services configured in the stack")
                LogsCmd->>LogsCmd: return (no log streaming)
            end
        end
        
        Note over LogsCmd: Main Command Loop
        LogsCmd->>LogsCmd: line_count = 0
        loop For each yielded log line
            LogsCmd->>LogsCmd: line_count += 1
            LogsCmd->>Display: log_message(log_line)
            Display->>User: Console output (actual log content)
        end
        
        alt Normal Completion
            LogsCmd->>LogsCmd: log.info(f"Streamed {line_count} log lines")
        end
        
        alt Keyboard Interrupt (Ctrl+C)
            LogsCmd->>LogsCmd: log.info("Log streaming interrupted")
        end
        
        alt Exception Handling
            LogsCmd->>LogsCmd: log.error(f"Failed to stream logs: {e}")
            LogsCmd->>Display: error(message, suggestion)
            LogsCmd->>LogsCmd: raise typer.Exit(code=1)
        end
    ```
    
    ## Key Architecture Points
    
    - **Platform-Aware Routing**: Automatically detects service type and routes appropriately
    - **Service Type Support**: Docker containers, native services, and remote services  
    - **Native Log File Access**: Direct access to ~/.ollama/logs/server.log on Apple Silicon
    - **Extension Support**: Treats extensions as Docker services for log streaming
    - **Error Resilience**: Graceful handling of missing services and connection failures
    - **Proper UI Separation**: Application messages via logging, actual log content via yielding
    
    ## Service Type Behaviors
    
    - **Docker Services**: Direct docker-compose logs streaming with all standard options
    - **Native Services**: Direct log file access with real-time following capability
    - **Remote Services**: Logging messages only (no yielded output) with guidance
    - **Extensions**: Treated as Docker services with fallback error handling
    - **Unknown Services**: Attempt Docker streaming with docker-compose error passthrough
    
    Args:
        ctx: Typer context containing AppContext
        service: Optional service name to stream logs from (streams all if not specified)
        follow: Continuously stream new log entries as they appear
        tail: Number of lines to show from the end of the logs
        level: Filter logs by level (info, warning, error, etc.)
        since: Show logs since this timestamp (ISO format)
        until: Show logs until this timestamp (ISO format)
        
    Examples:
        Stream all Docker service logs:
            ollama-stack logs
            
        Stream logs from specific service:
            ollama-stack logs ollama
            ollama-stack logs webui
            
        Follow logs in real-time:
            ollama-stack logs --follow
            ollama-stack logs ollama --follow
            
        Show last 50 lines:
            ollama-stack logs --tail 50
            
        Filter by log level:
            ollama-stack logs --level error
            
        Time-based filtering:
            ollama-stack logs --since 2023-06-18T10:30:00
    """
    app_context: AppContext = ctx.obj
    
    # Convert datetime objects to strings for Docker client compatibility
    since_str = since.isoformat() if since else None
    until_str = until.isoformat() if until else None
    
    try:
        log.info("Starting log streaming...")
        if service:
            log.info(f"Target service: {service}")
        else:
            log.info("Streaming logs from all services")
            
        log_stream = logs_services_logic(
            app_context,
            service_or_extension=service,
            follow=follow,
            tail=tail,
            level=level,
            since=since_str,
            until=until_str,
        )
        
        line_count = 0
        for log_line in log_stream:
            app_context.display.log_message(log_line)
            line_count += 1
            
        if line_count == 0:
            log.info("No log output received")
        else:
            log.info(f"Streamed {line_count} log lines")
            
    except Exception as e:
        log.error(f"Failed to stream logs: {e}")
        app_context.display.error(
            f"Unable to stream logs: {e}",
            "Check if Docker is running and the service name is correct."
        )
        raise typer.Exit(code=1)