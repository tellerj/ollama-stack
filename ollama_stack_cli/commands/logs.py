import typer
import logging
from typing_extensions import Annotated
from typing import Optional
from datetime import datetime

from ..context import AppContext

log = logging.getLogger(__name__)


def logs_services_logic(app_context: AppContext, service_or_extension: Optional[str], follow: bool, tail: Optional[int], level: Optional[str], since: Optional[str], until: Optional[str]):
    """Business logic for streaming logs."""
    # Check if service_or_extension is a valid service name - access through stack_manager's config
    service_config = app_context.stack_manager.config.services.get(service_or_extension) if service_or_extension else None
    
    if service_or_extension and service_config and service_config.type == 'docker':
        # Stream logs for a specific Docker service
        yield from app_context.stack_manager.stream_docker_logs(service_or_extension, follow, tail, level, since, until)
    elif service_or_extension:
        # Could be an extension or invalid service name
        yield from app_context.stack_manager.stream_docker_logs(service_or_extension, follow, tail, level, since, until)
    else:
        # Stream logs for all services
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
    """Streams logs from a specific service or all services."""
    app_context: AppContext = ctx.obj
    try:
        log_stream = logs_services_logic(
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