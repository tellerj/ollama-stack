import typer
import logging
from typing_extensions import Annotated

from ..context import AppContext

log = logging.getLogger(__name__)


def start_services_logic(app_context: AppContext, update: bool = False):
    """Business logic for starting services."""
    # Check if stack is already running
    if app_context.stack_manager.is_stack_running():
        log.info("Ollama Stack is already running.")
        return

    # Pull images if requested
    if update:
        app_context.stack_manager.pull_images()

    # Filter services by type
    docker_services = [name for name, conf in app_context.config.services.items() if conf.type == 'docker']
    native_services = [name for name, conf in app_context.config.services.items() if conf.type == 'native-api']

    # Start only Docker services
    if docker_services:
        log.info("Starting Docker-based services...")
        app_context.stack_manager.start_docker_services(docker_services)

    # Display info for non-docker services
    for service_name in native_services:
        log.info(f"Please ensure the native '{service_name}' service is running.")


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
    start_services_logic(app_context, update=update) 