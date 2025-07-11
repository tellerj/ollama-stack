from unittest.mock import MagicMock, patch, call
import pytest
import logging
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress

from ollama_stack_cli.display import Display
from ollama_stack_cli.schemas import (
    StackStatus,
    ServiceStatus,
    ResourceUsage,
    CheckReport,
    EnvironmentCheck,
    ExtensionStatus,
)


class TestDisplayInitialization:
    """Tests for Display constructor and initialization."""

    @patch('ollama_stack_cli.display.Console')
    @patch('ollama_stack_cli.display.logging')
    @patch('ollama_stack_cli.display.RichHandler')
    def test_init_default_verbose_false(self, MockRichHandler, mock_logging, MockConsole):
        """Test Display initialization with default verbose=False."""
        mock_console_instance = MagicMock()
        MockConsole.return_value = mock_console_instance
        
        mock_rich_handler = MagicMock()
        MockRichHandler.return_value = mock_rich_handler
        
        mock_root_logger = MagicMock()
        mock_logging.getLogger.return_value = mock_root_logger
        mock_root_logger.hasHandlers.return_value = True
        
        display = Display()
        
        # Verify console is created
        MockConsole.assert_called_once()
        assert display._console == mock_console_instance
        assert display._verbose is False
        
        # Verify logging setup
        mock_root_logger.handlers.clear.assert_called_once()
        mock_logging.basicConfig.assert_called_once()
        
        # Verify RichHandler configuration
        MockRichHandler.assert_called_once_with(
            console=mock_console_instance, 
            rich_tracebacks=True, 
            show_path=False, 
            show_level=False
        )
        
        # Verify logging config parameters
        config_call = mock_logging.basicConfig.call_args
        assert config_call[1]['level'] == "INFO"
        assert config_call[1]['format'] == "%(message)s"
        assert config_call[1]['datefmt'] == "[%X]"
        assert len(config_call[1]['handlers']) == 1
        assert config_call[1]['handlers'][0] == mock_rich_handler

    @patch('ollama_stack_cli.display.Console')
    @patch('ollama_stack_cli.display.logging')
    @patch('ollama_stack_cli.display.RichHandler')
    def test_init_verbose_true(self, MockRichHandler, mock_logging, MockConsole):
        """Test Display initialization with verbose=True."""
        mock_console_instance = MagicMock()
        MockConsole.return_value = mock_console_instance
        
        mock_rich_handler = MagicMock()
        MockRichHandler.return_value = mock_rich_handler
        
        mock_root_logger = MagicMock()
        mock_logging.getLogger.return_value = mock_root_logger
        mock_root_logger.hasHandlers.return_value = False
        
        display = Display(verbose=True)
        
        assert display._verbose is True
        
        # Verify logging setup for verbose mode
        mock_root_logger.handlers.clear.assert_not_called()  # No handlers to clear
        mock_logging.basicConfig.assert_called_once()
        
        # Verify RichHandler configuration in verbose mode
        MockRichHandler.assert_called_once_with(
            console=mock_console_instance, 
            rich_tracebacks=True, 
            show_path=True, 
            show_level=True
        )
        
        config_call = mock_logging.basicConfig.call_args
        assert config_call[1]['level'] == "DEBUG"
        assert config_call[1]['handlers'][0] == mock_rich_handler

    @patch('ollama_stack_cli.display.Console')
    @patch('ollama_stack_cli.display.logging')
    def test_init_no_existing_handlers(self, mock_logging, MockConsole):
        """Test Display initialization when no existing handlers."""
        mock_root_logger = MagicMock()
        mock_logging.getLogger.return_value = mock_root_logger
        mock_root_logger.hasHandlers.return_value = False
        
        Display()
        
        mock_root_logger.handlers.clear.assert_not_called()

    def test_verbose_property(self):
        """Test that verbose property returns correct value."""
        display_false = Display(verbose=False)
        display_true = Display(verbose=True)
        
        assert display_false.verbose is False
        assert display_true.verbose is True


class TestDisplayBasicMethods:
    """Tests for basic display methods."""

    @patch('ollama_stack_cli.display.Console')
    def test_success(self, MockConsole):
        """Test success message formatting."""
        mock_console_instance = MockConsole.return_value
        display = Display()
        
        display.success("Operation completed")
        
        mock_console_instance.print.assert_called_once_with(
            "[bold green]Success:[/] Operation completed"
        )

    @patch('ollama_stack_cli.display.Console')
    def test_error_with_suggestion(self, MockConsole):
        """Test error message with suggestion."""
        mock_console_instance = MockConsole.return_value
        display = Display()
        
        display.error("Something failed", suggestion="Try restarting")
        
        mock_console_instance.print.assert_called_once()
        panel_arg = mock_console_instance.print.call_args[0][0]
        
        assert isinstance(panel_arg, Panel)
        assert "Error:" in panel_arg.renderable
        assert "Something failed" in panel_arg.renderable
        assert "Suggestion:" in panel_arg.renderable
        assert "Try restarting" in panel_arg.renderable
        assert panel_arg.border_style == "red"
        assert panel_arg.expand is False

    @patch('ollama_stack_cli.display.Console')
    def test_error_without_suggestion(self, MockConsole):
        """Test error message without suggestion."""
        mock_console_instance = MockConsole.return_value
        display = Display()
        
        display.error("Something failed")
        
        mock_console_instance.print.assert_called_once()
        panel_arg = mock_console_instance.print.call_args[0][0]
        
        assert isinstance(panel_arg, Panel)
        assert "Error:" in panel_arg.renderable
        assert "Something failed" in panel_arg.renderable
        assert "Suggestion:" not in panel_arg.renderable

    @patch('ollama_stack_cli.display.Console')
    def test_panel_default_style(self, MockConsole):
        """Test panel with default border style."""
        mock_console_instance = MockConsole.return_value
        display = Display()
        
        display.panel("Test content", "Test Title")
        
        mock_console_instance.print.assert_called_once()
        panel_arg = mock_console_instance.print.call_args[0][0]
        
        assert isinstance(panel_arg, Panel)
        assert panel_arg.title == "[bold]Test Title[/bold]"
        assert panel_arg.border_style == "blue"
        assert panel_arg.expand is False

    @patch('ollama_stack_cli.display.Console')
    def test_panel_custom_style(self, MockConsole):
        """Test panel with custom border style."""
        mock_console_instance = MockConsole.return_value
        display = Display()
        
        display.panel("Test content", "Test Title", border_style="green")
        
        mock_console_instance.print.assert_called_once()
        panel_arg = mock_console_instance.print.call_args[0][0]
        
        assert isinstance(panel_arg, Panel)
        assert panel_arg.border_style == "green"

    @patch('ollama_stack_cli.display.Console')
    def test_table(self, MockConsole):
        """Test table creation and printing."""
        mock_console_instance = MockConsole.return_value
        display = Display()
        
        columns = ["Name", "Status", "Port"]
        rows = [
            ["service1", "running", "8080"],
            ["service2", "stopped", "8081"]
        ]
        
        display.table("Test Table", columns, rows)
        
        mock_console_instance.print.assert_called_once()
        table_arg = mock_console_instance.print.call_args[0][0]
        
        assert isinstance(table_arg, Table)
        assert table_arg.title == "Test Table"
        assert len(table_arg.columns) == 3
        assert len(table_arg.rows) == 2

    @patch('ollama_stack_cli.display.Console')
    def test_table_empty_rows(self, MockConsole):
        """Test table with empty rows."""
        mock_console_instance = MockConsole.return_value
        display = Display()
        
        display.table("Empty Table", ["Col1", "Col2"], [])
        
        mock_console_instance.print.assert_called_once()
        table_arg = mock_console_instance.print.call_args[0][0]
        
        assert isinstance(table_arg, Table)
        assert len(table_arg.rows) == 0

    @patch('ollama_stack_cli.display.Console')
    def test_json(self, MockConsole):
        """Test JSON output."""
        mock_console_instance = MockConsole.return_value
        display = Display()
        
        json_data = '{"key": "value", "number": 42}'
        display.json(json_data)
        
        mock_console_instance.print.assert_called_once_with(json_data)

    @patch('ollama_stack_cli.display.Console')
    def test_log_message(self, MockConsole):
        """Test log message output for Docker container logs."""
        mock_console_instance = MockConsole.return_value
        display = Display()
        
        # Use realistic Docker container log format (raw log line without level prefixes)
        log_line = "ollama-1  | time=2024-01-01T12:00:00.000Z level=INFO source=server.go:123 msg=Server started"
        display.log_message(log_line)
        
        mock_console_instance.print.assert_called_once_with(log_line)

    @patch('ollama_stack_cli.display.Console')
    def test_print(self, MockConsole):
        """Test print wrapper method."""
        mock_console_instance = MockConsole.return_value
        display = Display()
        
        display.print("test message", style="bold", end="")
        
        mock_console_instance.print.assert_called_once_with(
            "test message", style="bold", end=""
        )

    @patch('ollama_stack_cli.display.Console')
    def test_progress(self, MockConsole):
        """Test progress context manager creation."""
        mock_console_instance = MockConsole.return_value
        display = Display()
        
        progress = display.progress()
        
        assert isinstance(progress, Progress)
        # Verify console is passed to Progress
        assert progress.console == mock_console_instance
        # Verify progress has expected components (columns)
        assert len(progress.columns) == 4  # SpinnerColumn, TextColumn, BarColumn, TextColumn


class TestDisplayStatus:
    """Tests for status display functionality."""

    @patch('ollama_stack_cli.display.Console')
    def test_status_with_core_services(self, MockConsole):
        """Test status display with core services."""
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
                    usage=ResourceUsage(cpu_percent=10.5, memory_mb=256.7)
                ),
                ServiceStatus(
                    name="webui",
                    is_running=False,
                    status="exited",
                    health="unhealthy",
                    ports={"8080/tcp": None},
                    usage=ResourceUsage(cpu_percent=None, memory_mb=None)
                )
            ],
            extensions=[]
        )

        display.status(status)

        mock_console_instance.print.assert_called_once()
        table_arg = mock_console_instance.print.call_args[0][0]
        
        assert isinstance(table_arg, Table)
        assert table_arg.title == "Ollama Stack Status"
        assert len(table_arg.rows) == 2
        
        # Check specific cell values
        assert table_arg.columns[0]._cells[0] == "[bold]ollama[/bold]"
        assert table_arg.columns[1]._cells[0] == "✅"
        assert table_arg.columns[2]._cells[0] == "running"
        assert table_arg.columns[3]._cells[0] == "healthy"
        assert table_arg.columns[4]._cells[0] == "11434"
        assert table_arg.columns[5]._cells[0] == "10.5"
        assert table_arg.columns[6]._cells[0] == "256.7"
        
        assert table_arg.columns[0]._cells[1] == "[bold]webui[/bold]"
        assert table_arg.columns[1]._cells[1] == "❌"
        assert table_arg.columns[2]._cells[1] == "exited"
        assert table_arg.columns[3]._cells[1] == "unhealthy"
        assert table_arg.columns[4]._cells[1] == "N/A"
        assert table_arg.columns[5]._cells[1] == "N/A"
        assert table_arg.columns[6]._cells[1] == "N/A"

    @patch('ollama_stack_cli.display.Console')
    def test_status_with_none_values(self, MockConsole):
        """Test status display with None values in service data."""
        mock_console_instance = MockConsole.return_value
        display = Display()

        status = StackStatus(
            core_services=[
                ServiceStatus(
                    name="test_service",
                    is_running=True,
                    status=None,
                    health=None,
                    ports={},
                    usage=ResourceUsage()
                )
            ],
            extensions=[]
        )

        display.status(status)

        table_arg = mock_console_instance.print.call_args[0][0]
        assert table_arg.columns[2]._cells[0] == "N/A"  # status
        assert table_arg.columns[3]._cells[0] == "N/A"  # health
        assert table_arg.columns[4]._cells[0] == "N/A"  # ports
        assert table_arg.columns[5]._cells[0] == "N/A"  # cpu
        assert table_arg.columns[6]._cells[0] == "N/A"  # memory

    @patch('ollama_stack_cli.display.Console')
    def test_status_with_multiple_ports(self, MockConsole):
        """Test status display with multiple ports."""
        mock_console_instance = MockConsole.return_value
        display = Display()

        status = StackStatus(
            core_services=[
                ServiceStatus(
                    name="multi_port_service",
                    is_running=True,
                    ports={"8080/tcp": 8080, "9090/tcp": 9090, "8443/tcp": None}
                )
            ],
            extensions=[]
        )

        display.status(status)

        table_arg = mock_console_instance.print.call_args[0][0]
        ports_cell = table_arg.columns[4]._cells[0]
        assert "8080" in ports_cell
        assert "9090" in ports_cell
        assert "8443" not in ports_cell  # None values should be filtered out

    @patch('ollama_stack_cli.display.Console')
    @patch('ollama_stack_cli.display.logging')
    def test_status_empty_state(self, mock_logging, MockConsole):
        """Test status display with no services."""
        mock_console_instance = MockConsole.return_value
        mock_logger = MagicMock()
        mock_logging.getLogger.return_value = mock_logger
        
        display = Display()
        status = StackStatus(core_services=[], extensions=[])
        
        display.status(status)

        mock_logger.info.assert_called_once_with("Ollama Stack is not running.")
        mock_console_instance.print.assert_not_called()

    @patch('ollama_stack_cli.display.Console')
    def test_status_with_extensions(self, MockConsole):
        """Test status display with extensions (future functionality)."""
        mock_console_instance = MockConsole.return_value
        display = Display()

        # Test with extensions present but no core services
        status = StackStatus(
            core_services=[],
            extensions=[
                ExtensionStatus(
                    name="test_extension",
                    is_running=True,
                    is_enabled=True,
                    status="running"
                )
            ]
        )

        display.status(status)

        # Currently extensions are not processed, so table should still be printed
        # when extensions exist (even if empty core_services)
        mock_console_instance.print.assert_called_once()


class TestDisplayCheckReport:
    """Tests for check report display functionality."""

    @patch('ollama_stack_cli.display.Console')
    @patch('ollama_stack_cli.display.logging')
    def test_check_report_mixed_results(self, mock_logging, MockConsole):
        """Test check report with mixed passed/failed checks."""
        mock_console_instance = MockConsole.return_value
        mock_logger = MagicMock()
        mock_logging.getLogger.return_value = mock_logger
        
        display = Display()
        
        report = CheckReport(checks=[
            EnvironmentCheck(
                name="Docker Running", 
                passed=True, 
                details="Docker is responsive"
            ),
            EnvironmentCheck(
                name="Port Available", 
                passed=False, 
                details="Port 8080 in use", 
                suggestion="Stop the conflicting process"
            )
        ])
        
        display.check_report(report)
        
        mock_logger.info.assert_called_once_with("Running environment checks...")
        
        # Verify all print calls
        print_calls = mock_console_instance.print.call_args_list
        assert len(print_calls) == 4  # Status + details + suggestion + status
        
        all_output = "".join(str(call[0][0]) for call in print_calls)
        assert "[bold green]PASSED[/]: Docker Running" in all_output
        assert "[bold red]FAILED[/]: Port Available" in all_output
        assert "Details:[/] Port 8080 in use" in all_output
        assert "Suggestion:[/] Stop the conflicting process" in all_output

    @patch('ollama_stack_cli.display.Console')
    @patch('ollama_stack_cli.display.logging')
    def test_check_report_all_passed(self, mock_logging, MockConsole):
        """Test check report with all checks passed."""
        mock_console_instance = MockConsole.return_value
        mock_logger = MagicMock()
        mock_logging.getLogger.return_value = mock_logger
        
        display = Display()
        
        report = CheckReport(checks=[
            EnvironmentCheck(name="Check 1", passed=True),
            EnvironmentCheck(name="Check 2", passed=True, details="All good")
        ])
        
        display.check_report(report)
        
        print_calls = mock_console_instance.print.call_args_list
        assert len(print_calls) == 2  # Only status messages, no details/suggestions
        
        all_output = "".join(str(call[0][0]) for call in print_calls)
        assert "[bold green]PASSED[/]: Check 1" in all_output
        assert "[bold green]PASSED[/]: Check 2" in all_output
        assert "Details:" not in all_output
        assert "Suggestion:" not in all_output

    @patch('ollama_stack_cli.display.Console')
    @patch('ollama_stack_cli.display.logging')
    def test_check_report_all_failed(self, mock_logging, MockConsole):
        """Test check report with all checks failed."""
        mock_console_instance = MockConsole.return_value
        mock_logger = MagicMock()
        mock_logging.getLogger.return_value = mock_logger
        
        display = Display()
        
        report = CheckReport(checks=[
            EnvironmentCheck(
                name="Check 1", 
                passed=False, 
                details="Error details"
            ),
            EnvironmentCheck(
                name="Check 2", 
                passed=False, 
                suggestion="Fix suggestion"
            )
        ])
        
        display.check_report(report)
        
        all_output = "".join(str(call[0][0]) for call in mock_console_instance.print.call_args_list)
        assert "[bold red]FAILED[/]: Check 1" in all_output
        assert "[bold red]FAILED[/]: Check 2" in all_output
        assert "Details:[/] Error details" in all_output
        assert "Suggestion:[/] Fix suggestion" in all_output

    @patch('ollama_stack_cli.display.Console')
    @patch('ollama_stack_cli.display.logging')
    def test_check_report_empty(self, mock_logging, MockConsole):
        """Test check report with no checks."""
        mock_console_instance = MockConsole.return_value
        mock_logger = MagicMock()
        mock_logging.getLogger.return_value = mock_logger
        
        display = Display()
        
        report = CheckReport(checks=[])
        
        display.check_report(report)
        
        mock_logger.info.assert_called_once_with("Running environment checks...")
        # Only the initial log message, no check results
        assert len(mock_console_instance.print.call_args_list) == 0

    @patch('ollama_stack_cli.display.Console')
    @patch('ollama_stack_cli.display.logging')
    def test_check_report_failed_without_details_or_suggestion(self, mock_logging, MockConsole):
        """Test check report with failed check but no details or suggestion."""
        mock_console_instance = MockConsole.return_value
        mock_logger = MagicMock()
        mock_logging.getLogger.return_value = mock_logger
        
        display = Display()
        
        report = CheckReport(checks=[
            EnvironmentCheck(name="Simple Fail", passed=False)
        ])
        
        display.check_report(report)
        
        print_calls = mock_console_instance.print.call_args_list
        assert len(print_calls) == 1  # Only status message
        
        all_output = str(print_calls[0][0][0])
        assert "[bold red]FAILED[/]: Simple Fail" in all_output


class TestDisplayEdgeCases:
    """Tests for edge cases and error scenarios."""

    @patch('ollama_stack_cli.display.Console')
    def test_empty_strings(self, MockConsole):
        """Test display methods with empty strings."""
        mock_console_instance = MockConsole.return_value
        display = Display()
        
        display.success("")
        display.error("")
        display.panel("", "")
        display.json("")
        display.log_message("")
        
        # Should not crash and should call console.print for each
        assert mock_console_instance.print.call_count == 5

    @patch('ollama_stack_cli.display.Console')
    def test_special_characters(self, MockConsole):
        """Test display methods with special characters."""
        mock_console_instance = MockConsole.return_value
        display = Display()
        
        special_text = "Test with éñöügh spécial chars & symbols [bold]markup[/bold]"
        
        display.success(special_text)
        display.error(special_text, suggestion=special_text)
        display.panel(special_text, special_text)
        
        # Should handle special characters without crashing
        assert mock_console_instance.print.call_count == 3

    @patch('ollama_stack_cli.display.Console')
    def test_large_data_structures(self, MockConsole):
        """Test display methods with large data structures."""
        mock_console_instance = MockConsole.return_value
        display = Display()
        
        # Large table
        columns = [f"Column {i}" for i in range(10)]
        rows = [[f"Cell {i},{j}" for j in range(10)] for i in range(100)]
        
        display.table("Large Table", columns, rows)
        
        table_arg = mock_console_instance.print.call_args[0][0]
        assert len(table_arg.columns) == 10
        assert len(table_arg.rows) == 100

    @patch('ollama_stack_cli.display.Console')
    def test_status_with_very_long_service_names(self, MockConsole):
        """Test status display with very long service names."""
        mock_console_instance = MockConsole.return_value
        display = Display()
        
        very_long_name = "a" * 100
        status = StackStatus(
            core_services=[
                ServiceStatus(
                    name=very_long_name,
                    is_running=True
                )
            ],
            extensions=[]
        )
        
        display.status(status)
        
        table_arg = mock_console_instance.print.call_args[0][0]
        assert f"[bold]{very_long_name}[/bold]" == table_arg.columns[0]._cells[0] 