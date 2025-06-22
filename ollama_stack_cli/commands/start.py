import typer
from typing_extensions import Annotated

from ..context import AppContext


def start(
    ctx: typer.Context,
    update: Annotated[
        bool,
        typer.Option(
            "--update",
            help="Pull the latest Docker images before starting.",
        ),
    ] = False,
):
    """Starts the core Ollama Stack services."""
    app_context: AppContext = ctx.obj
    app_context.stack_manager.start_services(update=update) 