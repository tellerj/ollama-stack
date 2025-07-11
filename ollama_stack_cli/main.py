import typer
from typing_extensions import Annotated
from .context import AppContext
from .commands.start import start
from .commands.stop import stop
from .commands.restart import restart
from .commands.status import status
from .commands.logs import logs
from .commands.check import check
from .commands.install import install
from .commands.update import update
from .commands.uninstall import uninstall
from .commands.backup import backup
from .commands.restore import restore
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
app.command()(install)
app.command()(update)
app.command()(uninstall)
app.command()(backup)
app.command()(restore)

@app.callback(invoke_without_command=True)
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
    # Only print the logo if no subcommand and no options (bare invocation)
    if ctx.invoked_subcommand is None and not ctx.args:
        from rich.console import Console
        import subprocess
        import sys
        console = Console()
        logo = """
 ██████╗ ██╗     ██╗      █████╗ ███╗   ███╗ █████╗    ███████╗████████╗ █████╗  ██████╗██╗  ██╗
██╔═══██╗██║     ██║     ██╔══██╗████╗ ████║██╔══██╗   ██╔════╝╚══██╔══╝██╔══██╗██╔════╝██║ ██╔╝
██║   ██║██║     ██║     ███████║██╔████╔██║███████║   ███████╗   ██║   ███████║██║     █████╔╝ 
██║   ██║██║     ██║     ██╔══██║██║╚██╔╝██║██╔══██║   ╚════██║   ██║   ██╔══██║██║     ██╔═██╗ 
╚██████╔╝███████╗███████╗██║  ██║██║ ╚═╝ ██║██║  ██║   ███████║   ██║   ██║  ██║╚██████╗██║  ██╗
 ╚═════╝ ╚══════╝╚══════╝╚═╝  ╚═╝╚═╝     ╚═╝╚═╝  ╚═╝   ╚══════╝   ╚═╝   ╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝
"""
        console.print(logo, style="cyan")
        console.print(
            "\nA complete local AI development environment with privacy-focused, locally-hosted AI capabilities.",
            style="dim",
        )
        console.print(
            "Manage Ollama, Open WebUI, MCP Proxy, and extensions with a unified CLI interface.\n",
            style="dim",
        )
        # Invoke help command
        subprocess.run([sys.executable, "-m", "ollama_stack_cli.main", "--help"])
        raise typer.Exit()

if __name__ == "__main__":
    app()
