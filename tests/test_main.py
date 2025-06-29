from typer.testing import CliRunner
from unittest.mock import MagicMock, patch
import pytest

from ollama_stack_cli.main import app

runner = CliRunner()

@patch('ollama_stack_cli.main.AppContext')
def test_verbose_flag(MockAppContext):
    """Tests that the verbose flag is correctly passed to the AppContext."""
    # Create a mock app context with properly configured stack_manager
    mock_app_context = MagicMock()
    mock_app_context.config.fell_back_to_defaults = False
    mock_app_context.stack_manager.config.services = {}  # No services to start
    mock_app_context.stack_manager.get_running_services_summary.return_value = ([], [])  # Return tuple
    MockAppContext.return_value = mock_app_context
    
    runner.invoke(app, ["--verbose", "start"], catch_exceptions=False)
    MockAppContext.assert_called_once_with(verbose=True)
    
    MockAppContext.reset_mock()
    MockAppContext.return_value = mock_app_context  # Reset the return value too
    
    runner.invoke(app, ["start"], catch_exceptions=False)
    MockAppContext.assert_called_once_with(verbose=False)

def test_all_commands_are_registered():
    """Tests that all commands are registered by checking the --help output."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    help_text = result.stdout

    # List of all commands that should be registered
    commands = ["start", "stop", "restart", "status", "logs", "check"]

    for command in commands:
        assert command in help_text