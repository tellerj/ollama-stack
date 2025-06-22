from typer.testing import CliRunner
from unittest.mock import MagicMock, patch
import pytest

from ollama_stack_cli.main import app

runner = CliRunner()

@patch('ollama_stack_cli.main.AppContext')
def test_verbose_flag(MockAppContext):
    """Tests that the verbose flag is correctly passed to the AppContext."""
    MockAppContext.return_value = MagicMock()
    
    runner.invoke(app, ["--verbose", "start"], catch_exceptions=False)
    MockAppContext.assert_called_once_with(verbose=True)
    
    MockAppContext.reset_mock()
    
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