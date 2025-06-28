import typer
import logging

from ..context import AppContext
from .start import start_services_logic
from .stop import stop_services_logic

log = logging.getLogger(__name__)


def restart_services_logic(app_context: AppContext, update: bool = False):
    """Business logic for restarting services."""
    log.info("Restarting Ollama Stack...")
    
    # Stop services first
    stop_services_logic(app_context)
    
    # Then start them again
    start_services_logic(app_context, update=update)
    
    log.info("Ollama Stack restarted successfully.")


def restart(ctx: typer.Context,
    update: bool = False,
):
    """Restarts the core Ollama Stack services."""
    app_context: AppContext = ctx.obj
    restart_services_logic(app_context, update=update) 