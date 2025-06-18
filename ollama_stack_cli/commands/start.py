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
    """Starts the Ollama Stack."""
    app_context: AppContext = ctx.obj
    app_context.docker_client.start_services(update=update) 