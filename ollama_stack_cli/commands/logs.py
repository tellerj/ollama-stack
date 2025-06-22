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
):
    """Views logs from the core stack or a specific service/extension."""
    app_context: AppContext = ctx.obj
    
    for line in app_context.stack_manager.stream_logs(
        service_or_extension=service,
        follow=follow,
        tail=tail,
    ):
        app_context.display.log_message(line) 