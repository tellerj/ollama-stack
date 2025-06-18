import typer

from ..context import AppContext


def restart(ctx: typer.Context):
    """Restarts the Ollama Stack."""
    app_context: AppContext = ctx.obj
    app_context.display.info("Restarting Ollama Stack...")
    if not app_context.docker_client.stop_services():
        app_context.display.error("Failed to stop the stack. Aborting restart.")
        raise typer.Exit(1)

    app_context.docker_client.start_services() 