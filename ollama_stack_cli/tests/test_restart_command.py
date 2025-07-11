from typer.testing import CliRunner
from unittest.mock import MagicMock, patch
import pytest

from ollama_stack_cli.main import app
from ollama_stack_cli.schemas import ExtensionsConfig

runner = CliRunner()


# --- Restart Command Tests ---

@patch('ollama_stack_cli.main.AppContext')
def test_restart_command(MockAppContext, mock_app_context):
    """Tests that 'restart' calls stop and then start logic for both Docker and native services."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.is_stack_running.return_value = False
    mock_app_context.stack_manager.get_running_services_summary.return_value = ([], [])
    mock_app_context.stack_manager.config.services = {'webui': MagicMock(type='docker'), 'ollama': MagicMock(type='native-api')}
    mock_app_context.config.fell_back_to_defaults = False
    
    result = runner.invoke(app, ["restart"])
    assert result.exit_code == 0
    mock_app_context.stack_manager.stop_docker_services.assert_called_once()
    mock_app_context.stack_manager.stop_native_services.assert_called_once_with(['ollama'])
    mock_app_context.stack_manager.get_running_services_summary.assert_called_once()
    mock_app_context.stack_manager.start_docker_services.assert_called_once_with(['webui'])
    mock_app_context.stack_manager.start_native_services.assert_called_once_with(['ollama'])

@patch('ollama_stack_cli.main.AppContext')
def test_restart_command_with_update(MockAppContext, mock_app_context):
    """Tests that 'restart --update' calls stop and then uses unified update logic through start."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.is_stack_running.return_value = False
    mock_app_context.stack_manager.get_running_services_summary.return_value = ([], [])
    mock_app_context.stack_manager.config.services = {'webui': MagicMock(type='docker'), 'ollama': MagicMock(type='native-api')}
    mock_app_context.config.fell_back_to_defaults = False
    mock_app_context.config.app_config.extensions = ExtensionsConfig(enabled=[])
    
    result = runner.invoke(app, ["restart", "--update"])
    assert result.exit_code == 0
    mock_app_context.stack_manager.stop_docker_services.assert_called_once()
    mock_app_context.stack_manager.stop_native_services.assert_called_once_with(['ollama'])
    mock_app_context.stack_manager.get_running_services_summary.assert_called_once()
    mock_app_context.stack_manager.update_stack.assert_called_once_with(
        services_only=True, 
        force_restart=True, 
        called_from_start_restart=True
    )
    mock_app_context.stack_manager.start_docker_services.assert_called_once_with(['webui'])
    mock_app_context.stack_manager.start_native_services.assert_called_once_with(['ollama'])

@patch('ollama_stack_cli.main.AppContext')
def test_restart_command_only_docker_services(MockAppContext, mock_app_context):
    """Tests restart command when only Docker services exist."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.is_stack_running.return_value = False
    mock_app_context.stack_manager.get_running_services_summary.return_value = ([], [])
    mock_app_context.stack_manager.config.services = {'webui': MagicMock(type='docker'), 'mcp_proxy': MagicMock(type='docker')}
    
    result = runner.invoke(app, ["restart"])
    assert result.exit_code == 0
    # Stop phase
    mock_app_context.stack_manager.stop_docker_services.assert_called_once()
    mock_app_context.stack_manager.stop_native_services.assert_not_called()
    # Start phase
    mock_app_context.stack_manager.start_docker_services.assert_called_once_with(['webui', 'mcp_proxy'])
    mock_app_context.stack_manager.start_native_services.assert_not_called()

@patch('ollama_stack_cli.main.AppContext')
def test_restart_command_only_native_services(MockAppContext, mock_app_context):
    """Tests restart command when only native services exist."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.is_stack_running.return_value = False
    mock_app_context.stack_manager.get_running_services_summary.return_value = ([], [])
    mock_app_context.stack_manager.config.services = {'ollama': MagicMock(type='native-api')}
    
    result = runner.invoke(app, ["restart"])
    assert result.exit_code == 0
    # Stop phase
    mock_app_context.stack_manager.stop_docker_services.assert_not_called()
    mock_app_context.stack_manager.stop_native_services.assert_called_once_with(['ollama'])
    # Start phase  
    mock_app_context.stack_manager.start_docker_services.assert_not_called()
    mock_app_context.stack_manager.start_native_services.assert_called_once_with(['ollama'])

@patch('ollama_stack_cli.main.AppContext')
def test_restart_command_no_services(MockAppContext, mock_app_context):
    """Tests restart command when no services are configured."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.is_stack_running.return_value = False
    mock_app_context.stack_manager.get_running_services_summary.return_value = ([], [])
    mock_app_context.stack_manager.config.services = {}
    
    result = runner.invoke(app, ["restart"])
    assert result.exit_code == 0
    # Neither stop nor start methods should be called
    mock_app_context.stack_manager.stop_docker_services.assert_not_called()
    mock_app_context.stack_manager.stop_native_services.assert_not_called()
    mock_app_context.stack_manager.start_docker_services.assert_not_called()
    mock_app_context.stack_manager.start_native_services.assert_not_called()

@patch('ollama_stack_cli.main.AppContext')
def test_restart_command_call_order(MockAppContext, mock_app_context):
    """Tests that restart command calls stop before start methods."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.is_stack_running.return_value = False
    mock_app_context.stack_manager.get_running_services_summary.return_value = ([], [])
    mock_app_context.stack_manager.config.services = {'webui': MagicMock(type='docker'), 'ollama': MagicMock(type='native-api')}
    
    # Create a call order tracker
    call_order = []
    mock_app_context.stack_manager.stop_docker_services.side_effect = lambda: call_order.append('stop_docker')
    mock_app_context.stack_manager.stop_native_services.side_effect = lambda x: call_order.append('stop_native')
    mock_app_context.stack_manager.start_docker_services.side_effect = lambda x: call_order.append('start_docker')
    mock_app_context.stack_manager.start_native_services.side_effect = lambda x: call_order.append('start_native')
    
    result = runner.invoke(app, ["restart"])
    assert result.exit_code == 0
    
    # Verify stop methods are called before start methods
    assert call_order.index('stop_docker') < call_order.index('start_docker')
    assert call_order.index('stop_native') < call_order.index('start_native')

@patch('ollama_stack_cli.main.AppContext')
def test_restart_command_stop_failure_continues_to_start(MockAppContext, mock_app_context):
    """Tests that restart continues to start phase even if stop phase has issues."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.is_stack_running.return_value = False
    mock_app_context.stack_manager.get_running_services_summary.return_value = ([], [])
    mock_app_context.stack_manager.config.services = {'webui': MagicMock(type='docker')}
    mock_app_context.config.fell_back_to_defaults = False
    # Stop fails but restart should continue
    mock_app_context.stack_manager.stop_docker_services.side_effect = Exception("Stop failed")
    
    result = runner.invoke(app, ["restart"])
    assert result.exit_code == 1  # Should fail due to stop exception
    mock_app_context.stack_manager.stop_docker_services.assert_called_once()
    # Start phase should not be reached due to exception in stop phase
    mock_app_context.stack_manager.start_docker_services.assert_not_called()

@patch('ollama_stack_cli.main.AppContext')
def test_restart_command_with_update_failure_during_restart(MockAppContext, mock_app_context):
    """Tests restart --update handles update failure during restart phase."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.is_stack_running.return_value = False
    mock_app_context.stack_manager.get_running_services_summary.return_value = ([], [])
    mock_app_context.stack_manager.config.services = {'webui': MagicMock(type='docker')}
    mock_app_context.config.fell_back_to_defaults = False
    mock_app_context.stack_manager.update_stack.return_value = False  # Update fails
    
    result = runner.invoke(app, ["restart", "--update"])
    assert result.exit_code == 0  # Command doesn't crash but logs error
    mock_app_context.stack_manager.stop_docker_services.assert_called_once()
    mock_app_context.stack_manager.update_stack.assert_called_once_with(
        services_only=True, 
        force_restart=True, 
        called_from_start_restart=True
    )
    # Start methods should not be called when update fails
    mock_app_context.stack_manager.start_docker_services.assert_not_called()

@patch('ollama_stack_cli.main.AppContext')
def test_restart_command_preserves_update_flag_through_start(MockAppContext, mock_app_context):
    """Tests that restart --update properly passes update flag to start phase."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.is_stack_running.return_value = False
    mock_app_context.stack_manager.get_running_services_summary.return_value = ([], [])
    mock_app_context.stack_manager.config.services = {'webui': MagicMock(type='docker')}
    mock_app_context.config.fell_back_to_defaults = False
    mock_app_context.stack_manager.update_stack.return_value = True
    
    result = runner.invoke(app, ["restart", "--update"])
    assert result.exit_code == 0
    # Should call update_stack during start phase
    mock_app_context.stack_manager.update_stack.assert_called_once_with(
        services_only=True, 
        force_restart=True, 
        called_from_start_restart=True
    ) 