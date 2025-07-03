from typer.testing import CliRunner
from unittest.mock import MagicMock, patch
import pytest

from ollama_stack_cli.main import app
from ollama_stack_cli.schemas import StackStatus, ServiceStatus

runner = CliRunner()


# --- Status Command Tests ---

@patch('ollama_stack_cli.main.AppContext')
def test_status_command(MockAppContext, mock_app_context):
    """Tests that the 'status' command calls the correct services."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.config.services = {'webui': MagicMock(type='docker'), 'ollama': MagicMock(type='native-api')}
    
    # Mock return values - now using get_stack_status method
    mock_stack_status = StackStatus(
        core_services=[
            ServiceStatus(name='webui', is_running=True),
            ServiceStatus(name='ollama', is_running=True)
        ],
        extensions=[]
    )
    mock_app_context.stack_manager.get_stack_status.return_value = mock_stack_status
    
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    mock_app_context.stack_manager.get_stack_status.assert_called_once_with(extensions_only=False)
    mock_app_context.display.status.assert_called_once_with(mock_stack_status)

@patch('ollama_stack_cli.main.AppContext')
def test_status_command_extensions_only(MockAppContext, mock_app_context):
    """Tests that the 'status --extensions' command filters to extensions only."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.config.services = {'webui': MagicMock(type='docker')}
    
    mock_stack_status = StackStatus(core_services=[], extensions=[])
    mock_app_context.stack_manager.get_stack_status.return_value = mock_stack_status
    
    result = runner.invoke(app, ["status", "--extensions"])
    assert result.exit_code == 0
    mock_app_context.stack_manager.get_stack_status.assert_called_once_with(extensions_only=True)
    mock_app_context.display.status.assert_called_once_with(mock_stack_status)

@patch('ollama_stack_cli.main.AppContext')
def test_status_command_json_output(MockAppContext, mock_app_context):
    """Tests that the 'status --json' command outputs JSON format."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.config.services = {'ollama': MagicMock(type='native-api')}
    
    mock_stack_status = StackStatus(
        core_services=[ServiceStatus(name='ollama', is_running=False)],
        extensions=[]
    )
    mock_app_context.stack_manager.get_stack_status.return_value = mock_stack_status
    
    result = runner.invoke(app, ["status", "--json"])
    assert result.exit_code == 0
    mock_app_context.stack_manager.get_stack_status.assert_called_once_with(extensions_only=False)
    mock_app_context.display.json.assert_called_once_with(mock_stack_status.model_dump_json())

@patch('ollama_stack_cli.main.AppContext')
def test_status_command_no_services_configured(MockAppContext, mock_app_context):
    """Tests status command when no services are configured."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.config.services = {}
    
    mock_stack_status = StackStatus(core_services=[], extensions=[])
    mock_app_context.stack_manager.get_stack_status.return_value = mock_stack_status
    
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    mock_app_context.stack_manager.get_stack_status.assert_called_once_with(extensions_only=False)
    mock_app_context.display.status.assert_called_once_with(mock_stack_status)

@patch('ollama_stack_cli.commands.status.watch_status')
@patch('ollama_stack_cli.main.AppContext')
def test_status_command_watch_mode(MockAppContext, mock_watch_status, mock_app_context):
    """Tests that the 'status --watch' command starts watch mode."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.config.services = {'webui': MagicMock(type='docker')}
    
    result = runner.invoke(app, ["status", "--watch"])
    assert result.exit_code == 0
    mock_watch_status.assert_called_once_with(
        mock_app_context,
        extensions_only=False,
        json_output=False
    )

@patch('ollama_stack_cli.commands.status.watch_status')
@patch('ollama_stack_cli.main.AppContext')
def test_status_command_watch_mode_with_options(MockAppContext, mock_watch_status, mock_app_context):
    """Tests that watch mode passes through other options correctly."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.config.services = {'webui': MagicMock(type='docker')}
    
    result = runner.invoke(app, ["status", "--watch", "--extensions", "--json"])
    assert result.exit_code == 0
    mock_watch_status.assert_called_once_with(
        mock_app_context,
        extensions_only=True,
        json_output=True
    )

@patch('ollama_stack_cli.main.AppContext')
def test_status_command_stack_manager_failure(MockAppContext, mock_app_context):
    """Tests status command when StackManager.get_stack_status fails."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.config.services = {'webui': MagicMock(type='docker')}
    mock_app_context.stack_manager.get_stack_status.side_effect = Exception("Docker daemon not running")
    
    result = runner.invoke(app, ["status"])
    # Command should handle the error gracefully and exit with error code
    assert result.exit_code == 1
    mock_app_context.display.error.assert_called_once()

@patch('ollama_stack_cli.main.AppContext')
def test_status_command_mixed_service_status_logging(MockAppContext, mock_app_context):
    """Tests that status command logs mixed service states correctly."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.config.services = {
        'webui': MagicMock(type='docker'),
        'ollama': MagicMock(type='native-api')
    }
    
    # Mix of running and stopped services
    mock_stack_status = StackStatus(
        core_services=[
            ServiceStatus(name='webui', is_running=True),
            ServiceStatus(name='ollama', is_running=False)
        ],
        extensions=[]
    )
    mock_app_context.stack_manager.get_stack_status.return_value = mock_stack_status
    
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    mock_app_context.stack_manager.get_stack_status.assert_called_once_with(extensions_only=False)
    mock_app_context.display.status.assert_called_once_with(mock_stack_status)

@patch('ollama_stack_cli.main.AppContext')
def test_status_command_all_services_stopped_logging(MockAppContext, mock_app_context):
    """Tests that status command logs when all services are stopped."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.config.services = {
        'webui': MagicMock(type='docker'),
        'ollama': MagicMock(type='native-api')
    }
    
    # All services stopped
    mock_stack_status = StackStatus(
        core_services=[
            ServiceStatus(name='webui', is_running=False),
            ServiceStatus(name='ollama', is_running=False)
        ],
        extensions=[]
    )
    mock_app_context.stack_manager.get_stack_status.return_value = mock_stack_status
    
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    mock_app_context.stack_manager.get_stack_status.assert_called_once_with(extensions_only=False)
    mock_app_context.display.status.assert_called_once_with(mock_stack_status)

# Add all other status command tests here...
# (You'll copy them from the original test_commands.py file) 