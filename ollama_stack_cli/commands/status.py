import typer
import logging
from typing_extensions import Annotated

from ..context import AppContext
from ..schemas import StackStatus

log = logging.getLogger(__name__)


def get_stack_status_logic(app_context: AppContext, extensions_only: bool = False) -> StackStatus:
    """Business logic for gathering stack status."""
    core_services = []
    if not extensions_only:
        # Group services by type for efficient processing - access through stack_manager's config
        services_config = app_context.stack_manager.config.services
        docker_services = [name for name, conf in services_config.items() if conf.type == 'docker']
        api_services = {name: conf for name, conf in services_config.items() if conf.type == 'native-api'}

        # Get status for all Docker services in one call
        if docker_services:
            core_services.extend(app_context.stack_manager.get_docker_services_status(docker_services))

        # Get status for individual API-based services
        for name, config in api_services.items():
            if name == 'ollama': # This could be a registry of clients in the future
                core_services.append(app_context.stack_manager.get_ollama_status())
    
    return StackStatus(core_services=core_services, extensions=[])


def status(
    ctx: typer.Context,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output in JSON format."),
    ] = False,
    extensions_only: Annotated[
        bool,
        typer.Option("--extensions", help="Show only extension status."),
    ] = False,
    watch: Annotated[
        bool,
        typer.Option(
            "--watch",
            help="Continuously monitor stack status.",
        ),
    ] = False,
):
    """Displays comprehensive stack status."""
    app_context: AppContext = ctx.obj
    
    # Filter services by type - access through stack_manager's config
    services_config = app_context.stack_manager.config.services
    docker_services = [name for name, conf in services_config.items() if conf.type == 'docker']
    api_services = {name: conf for name, conf in services_config.items() if conf.type == 'native-api'}

    stack_status = get_stack_status_logic(app_context, extensions_only=extensions_only)
    
    if json_output:
        app_context.display.json(stack_status.model_dump_json())
    else:
        app_context.display.status(stack_status)