from typer.testing import CliRunner
from unittest.mock import MagicMock, patch
import pytest

from ollama_stack_cli.main import app
from ollama_stack_cli.schemas import StackStatus, CheckReport

runner = CliRunner()

@pytest.fixture
def mock_app_context():
    """Fixture to mock the AppContext and its components."""
    mock_context = MagicMock()
    mock_context.stack_manager = MagicMock()
    mock_context.display = MagicMock()
    return mock_context

# --- Command Tests ---

@patch('ollama_stack_cli.main.AppContext')
def test_start_command(MockAppContext, mock_app_context):
    """Tests that the 'start' command calls stack_manager.start_services."""
    MockAppContext.return_value = mock_app_context
    result = runner.invoke(app, ["start"])
    assert result.exit_code == 0
    mock_app_context.stack_manager.start_services.assert_called_once_with(update=False)

@patch('ollama_stack_cli.main.AppContext')
def test_start_command_with_update(MockAppContext, mock_app_context):
    """Tests that the 'start --update' command calls start_services with update=True."""
    MockAppContext.return_value = mock_app_context
    result = runner.invoke(app, ["start", "--update"])
    assert result.exit_code == 0
    mock_app_context.stack_manager.start_services.assert_called_once_with(update=True)

@patch('ollama_stack_cli.main.AppContext')
def test_stop_command(MockAppContext, mock_app_context):
    """Tests that the 'stop' command calls stack_manager.stop_services."""
    MockAppContext.return_value = mock_app_context
    result = runner.invoke(app, ["stop"])
    assert result.exit_code == 0
    mock_app_context.stack_manager.stop_services.assert_called_once()

@patch('ollama_stack_cli.main.AppContext')
def test_restart_command(MockAppContext, mock_app_context):
    """Tests that 'restart' calls stack_manager.restart_services."""
    MockAppContext.return_value = mock_app_context
    result = runner.invoke(app, ["restart"])
    assert result.exit_code == 0
    mock_app_context.stack_manager.restart_services.assert_called_once_with(update=False)

@patch('ollama_stack_cli.main.AppContext')
def test_restart_command_with_update(MockAppContext, mock_app_context):
    """Tests that 'restart --update' calls restart_services with update=True."""
    MockAppContext.return_value = mock_app_context
    result = runner.invoke(app, ["restart", "--update"])
    assert result.exit_code == 0
    mock_app_context.stack_manager.restart_services.assert_called_once_with(update=True)

@patch('ollama_stack_cli.main.AppContext')
def test_status_command(MockAppContext, mock_app_context):
    """Tests that the 'status' command calls the correct services."""
    MockAppContext.return_value = mock_app_context
    mock_stack_status = StackStatus(core_services=[], extensions=[])
    mock_app_context.stack_manager.get_stack_status.return_value = mock_stack_status
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    mock_app_context.stack_manager.get_stack_status.assert_called_once()
    mock_app_context.display.status.assert_called_once_with(mock_stack_status)

@patch('ollama_stack_cli.main.AppContext')
def test_check_command(MockAppContext, mock_app_context):
    """Tests that the 'check' command calls the correct services."""
    MockAppContext.return_value = mock_app_context
    mock_check_report = CheckReport(checks=[])
    mock_app_context.stack_manager.run_environment_checks.return_value = mock_check_report
    result = runner.invoke(app, ["check"])
    assert result.exit_code == 0
    mock_app_context.stack_manager.run_environment_checks.assert_called_once()
    mock_app_context.display.check_report.assert_called_once_with(mock_check_report)

@patch('ollama_stack_cli.main.AppContext')
def test_logs_command(MockAppContext, mock_app_context):
    """Tests the 'logs' command with default options."""
    MockAppContext.return_value = mock_app_context
    mock_logs = ["log line 1", "log line 2"]
    mock_app_context.stack_manager.stream_logs.return_value = iter(mock_logs)
    result = runner.invoke(app, ["logs"])
    assert result.exit_code == 0
    mock_app_context.stack_manager.stream_logs.assert_called_once_with(
        service_or_extension=None, follow=False, tail=None, level=None, since=None, until=None
    )
    assert mock_app_context.display.log_message.call_count == 2
    mock_app_context.display.log_message.assert_any_call("log line 1")
    mock_app_context.display.log_message.assert_any_call("log line 2")

@patch('ollama_stack_cli.main.AppContext')
def test_logs_command_with_options(MockAppContext, mock_app_context):
    """Tests the 'logs' command with all options."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.stream_logs.return_value = iter([])
    result = runner.invoke(app, ["logs", "ollama", "--follow", "--tail", "100", "--level", "info"])
    assert result.exit_code == 0
    mock_app_context.stack_manager.stream_logs.assert_called_once_with(
        service_or_extension="ollama", follow=True, tail=100, level="info", since=None, until=None
    )

@patch('ollama_stack_cli.main.AppContext')
def test_logs_command_empty_iterator(MockAppContext, mock_app_context):
    """Tests the 'logs' command handles an empty stream gracefully."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.stream_logs.return_value = iter([])
    result = runner.invoke(app, ["logs"])
    assert result.exit_code == 0
    mock_app_context.stack_manager.stream_logs.assert_called_once_with(
        service_or_extension=None, follow=False, tail=None, level=None, since=None, until=None
    )
    mock_app_context.display.log_message.assert_not_called() 