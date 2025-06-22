import typer
from typing_extensions import Annotated
from typing import Optional

from ..context import AppContext


def logs(
    ctx: typer.Context,
    service: Annotated[
        Optional[str],
        typer.Argument(help="The name of the service or extension to view logs for."),
    ] = None,
    follow: Annotated[
        bool,
        typer.Option("-f", "--follow", help="Follow log output."),
    ] = False,
    tail: Annotated[
        Optional[int],
        typer.Option("--tail", help="Number of lines to show from the end of the logs."),
    ] = None,
    level: Annotated[
        Optional[str],
        typer.Option("--level", help="Filter by log level."),
    ] = None,
    since: Annotated[
        Optional[str],
        typer.Option("--since", help="Show logs since a given timestamp (e.g., '2023-11-19T10:00:00')."),
    ] = None,
    until: Annotated[
        Optional[str],
        typer.Option("--until", help="Show logs before a given timestamp (e.g., '2023-11-19T11:00:00')."),
    ] = None,
):
    """Views logs from the core stack or a specific service/extension."""
    app_context: AppContext = ctx.obj
    
    app_context.stack_manager.stream_logs(
        service_or_extension=service,
        follow=follow,
        tail=tail,
        level=level,
        since=since,
        until=until,
    )