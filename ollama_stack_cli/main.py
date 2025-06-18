import typer
from typing_extensions import Annotated
from .context import AppContext
from .commands.start import start
from .commands.stop import stop
from .commands.restart import restart

app = typer.Typer(
    help="A CLI for managing the Ollama Stack.",
    add_completion=False,
)

app.command()(start)
app.command()(stop)
app.command()(restart)

@app.callback()
def main(
    ctx: typer.Context,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Enable verbose output for debugging.",
        ),
    ] = False,
):
    """
    Initialize the AppContext and attach it to the Typer context.
    """
    ctx.obj = AppContext(verbose=verbose)


@app.command()
def status(ctx: typer.Context):
    """Displays the status of the Ollama Stack services."""
    app_context: AppContext = ctx.obj
    statuses = app_context.docker_client.get_stack_status()
    
    if not statuses:
        app_context.display.info("Ollama Stack is not running.")
        return

    rows = [[s.name, s.status, s.ports, s.health] for s in statuses]
    app_context.display.table(
        title="Ollama Stack Status",
        columns=["Service", "Status", "Ports", "Health"],
        rows=rows,
    )

if __name__ == "__main__":
    app()
