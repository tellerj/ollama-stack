from unittest.mock import MagicMock, patch
import pytest
from rich.table import Table

from ollama_stack_cli.display import Display
from ollama_stack_cli.schemas import (
    StackStatus,
    ServiceStatus,
    ResourceUsage,
    CheckReport,
    EnvironmentCheck,
)

@patch('ollama_stack_cli.display.Console')
def test_display_basic_methods_call_console(MockConsole):
    """
    Tests that the basic Display methods call the underlying rich Console with expected strings.
    """
    mock_console_instance = MockConsole.return_value
    display = Display()

    # Test success
    display.success("It worked")
    mock_console_instance.print.assert_called_with("[bold green]Success:[/] It worked")

    # Test error
    display.error("It failed", suggestion="Try again")
    assert mock_console_instance.print.called
    panel_arg = mock_console_instance.print.call_args[0][0]
    assert "Error:" in panel_arg.renderable
    assert "It failed" in panel_arg.renderable
    assert "Suggestion:" in panel_arg.renderable
    assert "Try again" in panel_arg.renderable
    assert panel_arg.border_style == "red"

    # Test info
    display.info("Just so you know")
    mock_console_instance.print.assert_called_with("[bold blue]Info:[/] Just so you know")

    # Test warning
    display.warning("Look out")
    mock_console_instance.print.assert_called_with("[bold yellow]Warning:[/] Look out")

    # Test panel
    display.panel("Content", title="Title")
    panel_arg = mock_console_instance.print.call_args[0][0]
    assert panel_arg.title == "[bold]Title[/bold]"
    assert panel_arg.border_style == "blue"
    
    # Test verbose property
    assert not display.verbose
    verbose_display = Display(verbose=True)
    assert verbose_display.verbose

@patch('ollama_stack_cli.display.Console')
def test_display_status_renders_table(MockConsole):
    """Tests that the status method renders a table with correct data."""
    mock_console_instance = MockConsole.return_value
    display = Display()

    status = StackStatus(
        core_services=[
            ServiceStatus(
                name="ollama",
                is_running=True,
                status="running",
                health="healthy",
                ports={"11434/tcp": 11434},
                usage=ResourceUsage(cpu_percent=10.5, memory_mb=256.4)
            ),
            ServiceStatus(name="webui", is_running=False, status="exited", health="unhealthy")
        ],
        extensions=[]
    )

    display.status(status)

    mock_console_instance.print.assert_called_once()
    table_arg = mock_console_instance.print.call_args[0][0]
    assert isinstance(table_arg, Table)
    assert len(table_arg.rows) == 2
    # Just check a few key cells for correctness
    assert table_arg.rows[0].cells[0] == "[bold]ollama[/bold]"
    assert table_arg.rows[0].cells[1] == "✅"
    assert table_arg.rows[0].cells[3] == "healthy"
    assert table_arg.rows[1].cells[1] == "❌"
    assert table_arg.rows[1].cells[2] == "exited"


@patch('ollama_stack_cli.display.Console')
def test_display_status_empty_state(MockConsole):
    """Tests that the status method displays an info message when no services are present."""
    mock_console_instance = MockConsole.return_value
    display = Display()
    display.info = MagicMock() # Mock the info method to check if it's called
    
    status = StackStatus(core_services=[], extensions=[])
    display.status(status)

    display.info.assert_called_once_with("Ollama Stack is not running.")
    mock_console_instance.print.assert_not_called()


@patch('ollama_stack_cli.display.Console')
def test_display_check_report(MockConsole):
    """Tests that the check_report method prints a formatted list of checks."""
    mock_console_instance = MockConsole.return_value
    display = Display()
    
    report = CheckReport(checks=[
        EnvironmentCheck(name="Docker Running", passed=True, details="Docker is responsive."),
        EnvironmentCheck(name="Port 8080 Available", passed=False, details="Port in use.", suggestion="Stop the other process.")
    ])
    
    display.check_report(report)

    # Check that print was called for the report title and for each check
    assert mock_console_instance.print.call_count == 3
    
    # Check the "PASSED" line
    call_1_args = mock_console_instance.print.call_args_list[1][0][0]
    assert "[bold green]PASSED[/]" in call_1_args
    assert "Docker Running" in call_1_args
    
    # Check the "FAILED" line
    call_2_args = mock_console_instance.print.call_args_list[2][0][0]
    assert "[bold red]FAILED[/]" in call_2_args
    assert "Port 8080 Available" in call_2_args
    assert "Suggestion" in call_2_args


@patch('ollama_stack_cli.display.Console')
def test_display_log_message(MockConsole):
    """Tests that log_message simply prints the line given."""
    mock_console_instance = MockConsole.return_value
    display = Display()
    
    log_line = "This is a test log line."
    display.log_message(log_line)
    
    mock_console_instance.print.assert_called_once_with(log_line) 