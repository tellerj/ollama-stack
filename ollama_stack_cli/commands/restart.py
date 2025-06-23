import typer

from ..context import AppContext


def restart(ctx: typer.Context,
    update: bool = False,
):
    """Restarts the core Ollama Stack services."""
    app_context: AppContext = ctx.obj
    app_context.display.info("Restarting Ollama Stack...")
    app_context.stack_manager.restart_services(update=update)
    app_context.display.success("Ollama Stack restarted successfully.") 