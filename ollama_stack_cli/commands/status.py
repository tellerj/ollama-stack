import typer
from typing_extensions import Annotated

from ..context import AppContext


def status(
    ctx: typer.Context,
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
    stack_status = app_context.stack_manager.get_stack_status()
    app_context.display.status(stack_status) 