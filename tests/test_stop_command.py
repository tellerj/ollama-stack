from typer.testing import CliRunner
from unittest.mock import MagicMock, patch
import pytest

from ollama_stack_cli.main import app

runner = CliRunner()


# --- Stop Command Tests ---

@patch('ollama_stack_cli.main.AppContext')
def test_stop_command(MockAppContext, mock_app_context):
    """Tests that the 'stop' command calls stack_manager methods for both Docker and native services."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.config.services = {'webui': MagicMock(type='docker'), 'ollama': MagicMock(type='native-api')}
    
    result = runner.invoke(app, ["stop"])
    assert result.exit_code == 0
    mock_app_context.stack_manager.stop_docker_services.assert_called_once()
    mock_app_context.stack_manager.stop_native_services.assert_called_once_with(['ollama'])

@patch('ollama_stack_cli.main.AppContext')
def test_stop_command_only_docker_services(MockAppContext, mock_app_context):
    """Tests stop command when only Docker services exist."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.config.services = {'webui': MagicMock(type='docker'), 'mcp_proxy': MagicMock(type='docker')}
    
    result = runner.invoke(app, ["stop"])
    assert result.exit_code == 0
    mock_app_context.stack_manager.stop_docker_services.assert_called_once()
    mock_app_context.stack_manager.stop_native_services.assert_not_called()

@patch('ollama_stack_cli.main.AppContext')
def test_stop_command_only_native_services(MockAppContext, mock_app_context):
    """Tests stop command when only native services exist."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.config.services = {'ollama': MagicMock(type='native-api')}
    
    result = runner.invoke(app, ["stop"])
    assert result.exit_code == 0
    mock_app_context.stack_manager.stop_docker_services.assert_not_called()
    mock_app_context.stack_manager.stop_native_services.assert_called_once_with(['ollama'])

@patch('ollama_stack_cli.main.AppContext')
def test_stop_command_no_services(MockAppContext, mock_app_context):
    """Tests stop command when no services are configured."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.config.services = {}
    
    result = runner.invoke(app, ["stop"])
    assert result.exit_code == 0
    mock_app_context.stack_manager.stop_docker_services.assert_not_called()
    mock_app_context.stack_manager.stop_native_services.assert_not_called()

@patch('ollama_stack_cli.main.AppContext')
def test_stop_command_service_filtering_with_unknown_types(MockAppContext, mock_app_context):
    """Tests that stop command properly filters services, ignoring unknown types."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.config.services = {
        'webui': MagicMock(type='docker'),
        'ollama': MagicMock(type='native-api'),
        'unknown_service': MagicMock(type='unknown-type')
    }
    
    result = runner.invoke(app, ["stop"])
    assert result.exit_code == 0
    # Should only stop known service types
    mock_app_context.stack_manager.stop_docker_services.assert_called_once()
    mock_app_context.stack_manager.stop_native_services.assert_called_once_with(['ollama']) 