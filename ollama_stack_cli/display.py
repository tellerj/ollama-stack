from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from typing import List, Optional

class Display:
    """A centralized display handler for all CLI output."""

    def __init__(self, verbose: bool = False):
        self._console = Console()
        self._verbose = verbose

    @property
    def verbose(self) -> bool:
        """Returns whether verbose mode is enabled."""
        return self._verbose

    def success(self, message: str):
        """Prints a success message."""
        self._console.print(f"[bold green]Success:[/] {message}")

    def error(self, message: str, suggestion: Optional[str] = None):
        """Prints an error message and an optional suggestion."""
        error_panel = Panel(
            f"[bold red]Error:[/] {message}\n"
            + (f"\n[bold]Suggestion:[/] {suggestion}" if suggestion else ""),
            border_style="red",
            expand=False,
        )
        self._console.print(error_panel)

    def warning(self, message: str):
        """Prints a warning message."""
        self._console.print(f"[bold yellow]Warning:[/] {message}")

    def info(self, message: str):
        """Prints an informational message."""
        self._console.print(f"[bold blue]Info:[/] {message}")

    def panel(self, content: str, title: str, border_style: str = "blue"):
        """Prints content within a styled panel."""
        self._console.print(
            Panel(
                content,
                title=f"[bold]{title}[/bold]",
                border_style=border_style,
                expand=False,
            )
        )

    def table(self, title: str, columns: List[str], rows: List[List[str]]):
        """Creates and prints a table."""
        table = Table(title=title)
        for column in columns:
            table.add_column(column, style="cyan")
        for row in rows:
            table.add_row(*row)
        self._console.print(table)

    def progress(self):
        """Returns a Rich Progress context manager."""
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=self._console,
            transient=True,
        )

    def print(self, *args, **kwargs):
        """A wrapper around rich.print for general output."""
        self._console.print(*args, **kwargs) 