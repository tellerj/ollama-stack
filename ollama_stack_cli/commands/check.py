import typer
import logging
from typing_extensions import Annotated

from ..context import AppContext
from ..schemas import CheckReport

log = logging.getLogger(__name__)


def run_environment_checks_logic(app_context: AppContext, fix: bool = False, verbose: bool = False) -> CheckReport:
    """Business logic for running environment checks."""
    return app_context.stack_manager.run_docker_environment_checks(fix=fix, verbose=verbose)


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
    report = run_environment_checks_logic(app_context, fix=fix, verbose=verbose)
    app_context.display.check_report(report)