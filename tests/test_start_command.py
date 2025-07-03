from typer.testing import CliRunner
from unittest.mock import MagicMock, patch
import pytest

from ollama_stack_cli.main import app
from ollama_stack_cli.schemas import ExtensionsConfig

runner = CliRunner()


# --- Start Command Tests ---

@patch('ollama_stack_cli.main.AppContext')
def test_start_command(MockAppContext, mock_app_context):
    """Tests that the 'start' command calls the correct stack manager methods."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.is_stack_running.return_value = False
    mock_app_context.stack_manager.get_running_services_summary.return_value = ([], [])
    mock_app_context.stack_manager.config.services = {'webui': MagicMock(type='docker'), 'ollama': MagicMock(type='native-api')}
    mock_app_context.config.fell_back_to_defaults = False
    
    result = runner.invoke(app, ["start"])
    assert result.exit_code == 0
    mock_app_context.stack_manager.get_running_services_summary.assert_called_once()
    mock_app_context.stack_manager.start_docker_services.assert_called_once_with(['webui'])
    mock_app_context.stack_manager.start_native_services.assert_called_once_with(['ollama'])

@patch('ollama_stack_cli.main.AppContext')
def test_start_command_with_update(MockAppContext, mock_app_context):
    """Tests that the 'start --update' command uses the unified update logic."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.is_stack_running.return_value = False
    mock_app_context.stack_manager.get_running_services_summary.return_value = ([], [])
    mock_app_context.stack_manager.config.services = {'webui': MagicMock(type='docker'), 'ollama': MagicMock(type='native-api')}
    mock_app_context.config.fell_back_to_defaults = False
    mock_app_context.config.app_config.extensions = ExtensionsConfig(enabled=[])
    
    result = runner.invoke(app, ["start", "--update"])
    assert result.exit_code == 0
    mock_app_context.stack_manager.get_running_services_summary.assert_called_once()
    mock_app_context.stack_manager.update_stack.assert_called_once_with(
        services_only=True, 
        force_restart=True, 
        called_from_start_restart=True
    )
    mock_app_context.stack_manager.start_docker_services.assert_called_once_with(['webui'])
    mock_app_context.stack_manager.start_native_services.assert_called_once_with(['ollama'])

@patch('ollama_stack_cli.main.AppContext')
def test_start_command_with_config_fallback(MockAppContext, mock_app_context):
    """Tests that the start command shows a message when config fell back to defaults."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.is_stack_running.return_value = False
    mock_app_context.stack_manager.get_running_services_summary.return_value = ([], [])
    mock_app_context.stack_manager.config.services = {'webui': MagicMock(type='docker'), 'ollama': MagicMock(type='native-api')}
    mock_app_context.config.fell_back_to_defaults = True
    
    result = runner.invoke(app, ["start"])
    assert result.exit_code == 0
    # Should call all the normal start operations
    mock_app_context.stack_manager.start_docker_services.assert_called_once_with(['webui'])
    mock_app_context.stack_manager.start_native_services.assert_called_once_with(['ollama'])

@patch('ollama_stack_cli.main.AppContext')
def test_start_command_with_update_failure(MockAppContext, mock_app_context):
    """Tests that 'start --update' handles update failure gracefully."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.is_stack_running.return_value = False
    mock_app_context.stack_manager.get_running_services_summary.return_value = ([], [])
    mock_app_context.stack_manager.config.services = {'webui': MagicMock(type='docker'), 'ollama': MagicMock(type='native-api')}
    mock_app_context.config.fell_back_to_defaults = False
    mock_app_context.config.app_config.extensions = ExtensionsConfig(enabled=[])
    
    # Mock update_stack to fail
    mock_app_context.stack_manager.update_stack.return_value = False
    
    result = runner.invoke(app, ["start", "--update"])
    assert result.exit_code == 0  # Command should not crash
    mock_app_context.stack_manager.get_running_services_summary.assert_called_once()
    mock_app_context.stack_manager.update_stack.assert_called_once_with(
        services_only=True, 
        force_restart=True, 
        called_from_start_restart=True
    )
    # Should not call start methods when update fails
    mock_app_context.stack_manager.start_docker_services.assert_not_called()
    mock_app_context.stack_manager.start_native_services.assert_not_called()

@patch('ollama_stack_cli.main.AppContext')
def test_start_command_already_running(MockAppContext, mock_app_context):
    """Tests that the 'start' command exits early when stack is already running."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.is_stack_running.return_value = True
    mock_app_context.stack_manager.get_running_services_summary.return_value = (['webui'], ['ollama'])
    mock_app_context.stack_manager.config.services = {'webui': MagicMock(type='docker'), 'ollama': MagicMock(type='native-api')}
    mock_app_context.config.fell_back_to_defaults = False
    
    result = runner.invoke(app, ["start"])
    assert result.exit_code == 0
    mock_app_context.stack_manager.get_running_services_summary.assert_called_once()
    # Should not call start methods when already running
    mock_app_context.stack_manager.start_docker_services.assert_not_called()
    mock_app_context.stack_manager.start_native_services.assert_not_called()
    mock_app_context.stack_manager.pull_images.assert_not_called()

@patch('ollama_stack_cli.main.AppContext')
def test_start_command_with_update_already_running(MockAppContext, mock_app_context):
    """Tests that the 'start --update' command exits early when stack is already running (no image pull)."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.is_stack_running.return_value = True
    mock_app_context.stack_manager.get_running_services_summary.return_value = (['webui'], ['ollama'])
    mock_app_context.stack_manager.config.services = {'webui': MagicMock(type='docker'), 'ollama': MagicMock(type='native-api')}
    mock_app_context.config.fell_back_to_defaults = False
    
    result = runner.invoke(app, ["start", "--update"])
    assert result.exit_code == 0
    mock_app_context.stack_manager.get_running_services_summary.assert_called_once()
    # Should not pull images or start services when already running
    mock_app_context.stack_manager.pull_images.assert_not_called()
    mock_app_context.stack_manager.start_docker_services.assert_not_called()
    mock_app_context.stack_manager.start_native_services.assert_not_called()

@patch('ollama_stack_cli.main.AppContext')
def test_start_command_only_docker_services(MockAppContext, mock_app_context):
    """Tests start command when only Docker services exist."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.is_stack_running.return_value = False
    mock_app_context.stack_manager.get_running_services_summary.return_value = ([], [])
    mock_app_context.stack_manager.config.services = {'webui': MagicMock(type='docker'), 'mcp_proxy': MagicMock(type='docker')}
    mock_app_context.config.fell_back_to_defaults = False
    
    result = runner.invoke(app, ["start"])
    assert result.exit_code == 0
    mock_app_context.stack_manager.start_docker_services.assert_called_once_with(['webui', 'mcp_proxy'])
    mock_app_context.stack_manager.start_native_services.assert_not_called()

@patch('ollama_stack_cli.main.AppContext')
def test_start_command_only_native_services(MockAppContext, mock_app_context):
    """Tests start command when only native services exist."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.is_stack_running.return_value = False
    mock_app_context.stack_manager.get_running_services_summary.return_value = ([], [])
    mock_app_context.stack_manager.config.services = {'ollama': MagicMock(type='native-api'), 'custom_api': MagicMock(type='native-api')}
    mock_app_context.config.fell_back_to_defaults = False
    
    result = runner.invoke(app, ["start"])
    assert result.exit_code == 0
    mock_app_context.stack_manager.start_docker_services.assert_not_called()
    mock_app_context.stack_manager.start_native_services.assert_called_once_with(['ollama', 'custom_api'])

@patch('ollama_stack_cli.main.AppContext')
def test_start_command_no_services(MockAppContext, mock_app_context):
    """Tests start command when no services are configured."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.is_stack_running.return_value = False
    mock_app_context.stack_manager.get_running_services_summary.return_value = ([], [])
    mock_app_context.stack_manager.config.services = {}
    mock_app_context.config.fell_back_to_defaults = False
    
    result = runner.invoke(app, ["start"])
    assert result.exit_code == 0
    mock_app_context.stack_manager.start_docker_services.assert_not_called()
    mock_app_context.stack_manager.start_native_services.assert_not_called()

@patch('ollama_stack_cli.main.AppContext')
def test_start_command_service_filtering_with_unknown_types(MockAppContext, mock_app_context):
    """Tests that start command properly filters services, ignoring unknown types."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.is_stack_running.return_value = False
    mock_app_context.stack_manager.get_running_services_summary.return_value = ([], [])
    mock_app_context.stack_manager.config.services = {
        'webui': MagicMock(type='docker'),
        'ollama': MagicMock(type='native-api'),
        'unknown_service': MagicMock(type='unknown-type'),
        'external_api': MagicMock(type='external')
    }
    
    result = runner.invoke(app, ["start"])
    assert result.exit_code == 0
    # Should only start known service types
    mock_app_context.stack_manager.start_docker_services.assert_called_once_with(['webui'])
    mock_app_context.stack_manager.start_native_services.assert_called_once_with(['ollama'])

@patch('ollama_stack_cli.main.AppContext')
def test_start_command_calls_update_stack_correctly(MockAppContext, mock_app_context):
    """Tests that start --update command calls StackManager.update_stack with correct parameters."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.is_stack_running.return_value = False
    mock_app_context.stack_manager.get_running_services_summary.return_value = ([], [])
    mock_app_context.stack_manager.config.services = {'webui': MagicMock(type='docker')}
    mock_app_context.config.fell_back_to_defaults = False
    mock_app_context.stack_manager.update_stack.return_value = True
    
    result = runner.invoke(app, ["start", "--update"])
    assert result.exit_code == 0
    mock_app_context.stack_manager.update_stack.assert_called_once_with(
        services_only=True, 
        force_restart=True, 
        called_from_start_restart=True  # Should be True when called from start
    )

@patch('ollama_stack_cli.main.AppContext')
def test_start_command_docker_services_exception(MockAppContext, mock_app_context):
    """Tests start command handles exceptions from start_docker_services gracefully."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.is_stack_running.return_value = False
    mock_app_context.stack_manager.get_running_services_summary.return_value = ([], [])
    mock_app_context.stack_manager.config.services = {'webui': MagicMock(type='docker')}
    mock_app_context.config.fell_back_to_defaults = False
    mock_app_context.stack_manager.start_docker_services.side_effect = Exception("Docker daemon not running")
    
    # Should not crash - command architecture lets exceptions bubble up to CLI layer
    result = runner.invoke(app, ["start"])
    # The exception will be caught by typer and result in exit code 1
    assert result.exit_code == 1

@patch('ollama_stack_cli.main.AppContext')
def test_start_command_native_services_exception(MockAppContext, mock_app_context):
    """Tests start command handles exceptions from start_native_services gracefully."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.is_stack_running.return_value = False
    mock_app_context.stack_manager.get_running_services_summary.return_value = ([], [])
    mock_app_context.stack_manager.config.services = {'ollama': MagicMock(type='native-api')}
    mock_app_context.config.fell_back_to_defaults = False
    mock_app_context.stack_manager.start_native_services.side_effect = Exception("Ollama not installed")
    
    result = runner.invoke(app, ["start"])
    assert result.exit_code == 1

@patch('ollama_stack_cli.main.AppContext')  
def test_start_command_returns_false_on_early_exit(MockAppContext, mock_app_context):
    """Tests that start_services_logic returns False when conditions aren't met."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.config.fell_back_to_defaults = False
    mock_app_context.stack_manager.config.services = {'webui': MagicMock(type='docker')}
    # All services already running - should return True and exit early
    mock_app_context.stack_manager.get_running_services_summary.return_value = (['webui'], [])
    
    from ollama_stack_cli.commands.start import start_services_logic
    result = start_services_logic(mock_app_context, update=False)
    assert result == True  # Should return True when all services already running
    # Should not call start methods when already running
    mock_app_context.stack_manager.start_docker_services.assert_not_called()
    mock_app_context.stack_manager.start_native_services.assert_not_called()

@patch('ollama_stack_cli.main.AppContext')
def test_start_command_partial_service_failures_edge_case(MockAppContext, mock_app_context):
    """Tests start command behavior when some services start and others don't."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.is_stack_running.return_value = False
    mock_app_context.stack_manager.get_running_services_summary.return_value = (['webui'], [])  # Only webui running
    mock_app_context.stack_manager.config.services = {
        'webui': MagicMock(type='docker'), 
        'mcp_proxy': MagicMock(type='docker'),
        'ollama': MagicMock(type='native-api')
    }
    mock_app_context.config.fell_back_to_defaults = False
    
    result = runner.invoke(app, ["start"])
    assert result.exit_code == 0
    # Should only start services that aren't running
    mock_app_context.stack_manager.start_docker_services.assert_called_once_with(['mcp_proxy'])
    mock_app_context.stack_manager.start_native_services.assert_called_once_with(['ollama']) 