import typer

from ..context import AppContext


def restart(ctx: typer.Context,
    update: bool = False,
):
    """Restarts the core Ollama Stack services."""
    app_context: AppContext = ctx.obj
    app_context.stack_manager.restart_services(update=update)

    app_context.display.info("Restarting Ollama Stack...")
    if not app_context.docker_client.stop_services():
        app_context.display.error("Failed to stop the stack. Aborting restart.")
        raise typer.Exit(1)

    app_context.docker_client.start_services() 