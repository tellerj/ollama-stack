import typer

from ..context import AppContext


def stop(ctx: typer.Context):
    """Stops the core Ollama Stack services."""
    app_context: AppContext = ctx.obj
    app_context.stack_manager.stop_services() 