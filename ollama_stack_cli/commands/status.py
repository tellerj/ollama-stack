import typer
from typing_extensions import Annotated

from ..context import AppContext


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
    # The display logic will be handled by the display module later.
    # For now, we fetch the data and print it simply.
    stack_status = app_context.stack_manager.get_stack_status(
        extensions_only=extensions_only
    )
    
    if json_output:
        app_context.display.json(stack_status.model_dump_json())
    else:
        app_context.display.status(stack_status)