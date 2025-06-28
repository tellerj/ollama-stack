import typer
import logging
from typing_extensions import Annotated
from typing import Optional
from datetime import datetime

from ..context import AppContext

log = logging.getLogger(__name__)


def stream_logs_logic(app_context: AppContext, service_or_extension: Optional[str] = None, follow: bool = False, tail: Optional[int] = None, level: Optional[str] = None, since: Optional[str] = None, until: Optional[str] = None):
    """Business logic for streaming logs."""
    # Check if service is a native service that doesn't have container logs
    service_config = app_context.config.services.get(service_or_extension) if service_or_extension else None

    if service_config and service_config.type == "native-api":
        log.warning(f"'{service_or_extension}' runs as a native service. No container logs are available.")
        log.info(f"To view its logs, please consult the service's own logging mechanisms.")
        return
    
    # Stream logs from Docker containers via stack manager
    yield from app_context.stack_manager.stream_docker_logs(service_or_extension, follow, tail, level, since, until)


def logs(
    ctx: typer.Context,
    service: Optional[str] = typer.Argument(None, help="Name of the service to stream logs from."),
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow the logs as they are generated."),
    tail: Optional[int] = typer.Option(None, "--tail", "-t", help="Number of lines to show from the end of the logs."),
    level: Optional[str] = typer.Option(None, "--level", help="Log level (e.g., info, warning, error)."),
    since: Optional[datetime] = typer.Option(None, "--since", help="Show logs since a timestamp (e.g., 2023-06-18T10:30:00)."),
    until: Optional[datetime] = typer.Option(None, "--until", help="Show logs until a timestamp."),
):
    """Streams logs from a specific service or all services."""
    app_context: AppContext = ctx.obj
    try:
        log_stream = stream_logs_logic(
            app_context,
            service_or_extension=service,
            follow=follow,
            tail=tail,
            level=level,
            since=since,
            until=until,
        )
        for log_line in log_stream:
            app_context.display.log_message(log_line)
    except Exception as e:
        log.error(f"Failed to stream logs: {e}")
        raise typer.Exit(code=1)