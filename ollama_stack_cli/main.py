import typer
from typing_extensions import Annotated
from .context import AppContext
from .commands.start import start
from .commands.stop import stop
from .commands.restart import restart
from .commands.status import status
from .commands.logs import logs
from .commands.check import check
from .commands.update import update

app = typer.Typer(
    help="A CLI for managing the Ollama Stack.",
    add_completion=False,
)

app.command()(start)
app.command()(stop)
app.command()(restart)
app.command()(status)
app.command()(logs)
app.command()(check)
app.command()(update)

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


if __name__ == "__main__":
    app()
