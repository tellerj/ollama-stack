import typer
from typing_extensions import Annotated
from typing import Optional
from datetime import datetime

from ..context import AppContext


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
        log_stream = app_context.stack_manager.stream_logs(
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
        app_context.display.error(f"Failed to stream logs: {e}")
        raise typer.Exit(code=1)