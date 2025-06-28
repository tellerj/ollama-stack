import typer
import logging

from ..context import AppContext

log = logging.getLogger(__name__)


def stop_services_logic(app_context: AppContext):
    """Business logic for stopping services."""
    app_context.stack_manager.stop_docker_services()


def stop(ctx: typer.Context):
    """Stops the core Ollama Stack services."""
    app_context: AppContext = ctx.obj
    stop_services_logic(app_context) 