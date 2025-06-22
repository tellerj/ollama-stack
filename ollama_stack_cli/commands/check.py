import typer
from ..context import AppContext


def check(ctx: typer.Context):
    """Verifies environment requirements and Docker setup."""
    app_context: AppContext = ctx.obj
    report = app_context.stack_manager.run_environment_checks()
    app_context.display.check_report(report) 