import typer
from typing_extensions import Annotated

from ..context import AppContext


def check(
    ctx: typer.Context,
    fix: Annotated[
        bool,
        typer.Option("--fix", help="Attempt to fix issues where possible."),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", help="Show detailed information."),
    ] = False,
):
    """Verifies environment requirements and Docker setup."""
    app_context: AppContext = ctx.obj
    report = app_context.stack_manager.run_environment_checks(fix=fix, verbose=verbose)
    app_context.display.check_report(report)