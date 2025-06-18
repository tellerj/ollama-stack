import typer

from ..context import AppContext


def stop(ctx: typer.Context):
    """Stops the Ollama Stack."""
    app_context: AppContext = ctx.obj
    if not app_context.docker_client.stop_services():
        raise typer.Exit(1) 