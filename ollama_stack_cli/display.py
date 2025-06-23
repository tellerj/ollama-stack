import logging
from rich.logging import RichHandler
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from typing import List, Optional

from .schemas import StackStatus, CheckReport

class Display:
    """A centralized display handler for all CLI output."""

    def __init__(self, verbose: bool = False):
        self._console = Console()
        self._verbose = verbose

        # Clear any existing handlers to avoid duplicate logs
        root_logger = logging.getLogger()
        if root_logger.hasHandlers():
            root_logger.handlers.clear()

        # Configure logging to use RichHandler
        logging.basicConfig(
            level="DEBUG" if verbose else "INFO",
            format="%(message)s",
            datefmt="[%X]",
            handlers=[RichHandler(console=self._console, rich_tracebacks=True, show_path=verbose, show_level=verbose)]
        )
        self.log = logging.getLogger(__name__)

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
        self.log.warning(message)

    def info(self, message: str):
        """Prints an informational message."""
        self.log.info(message)

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

    def status(self, stack_status: StackStatus):
        """Displays the formatted status of the stack."""
        table = Table(title="Ollama Stack Status")
        table.add_column("Service", style="cyan")
        table.add_column("Running", style="magenta")
        table.add_column("Status", style="yellow")
        table.add_column("Health", style="green")
        table.add_column("Ports", style="blue")
        table.add_column("CPU %", style="red")
        table.add_column("Memory (MB)", style="red")

        if not stack_status.core_services and not stack_status.extensions:
            self.info("Ollama Stack is not running.")
            return

        for service in stack_status.core_services:
            table.add_row(
                f"[bold]{service.name}[/bold]",
                "✅" if service.is_running else "❌",
                service.status or "N/A",
                service.health or "N/A",
                ", ".join(str(p) for p in service.ports.values() if p) or "N/A",
                str(service.usage.cpu_percent) if service.usage.cpu_percent is not None else "N/A",
                str(service.usage.memory_mb) if service.usage.memory_mb is not None else "N/A",
            )
        
        # Add extension processing here later if needed

        self._console.print(table)

    def json(self, data: str):
        """Prints pre-formatted JSON to the console."""
        self._console.print(data)

    def check_report(self, report: CheckReport):
        """Displays the results of an environment check."""
        self.info("Running environment checks...")
        for check in report.checks:
            status = "[bold green]PASSED[/]" if check.passed else "[bold red]FAILED[/]"
            self._console.print(f"{status}: {check.name}")
            if not check.passed and check.details:
                self._console.print(f"  [cyan]Details:[/] {check.details}")
            if not check.passed and check.suggestion:
                self._console.print(f"  [cyan]Suggestion:[/] {check.suggestion}")

    def log_message(self, message: str):
        """Prints a single log line."""
        # Simple print for now, can add formatting later
        self.log.info(message)

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