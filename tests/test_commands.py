from typer.testing import CliRunner
from unittest.mock import MagicMock, patch
import pytest

from ollama_stack_cli.main import app
from ollama_stack_cli.schemas import StackStatus, CheckReport, ServiceStatus

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
    """Tests that the 'start' command calls the correct stack manager methods."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.is_stack_running.return_value = False
    mock_app_context.config.services = {'webui': MagicMock(type='docker'), 'ollama': MagicMock(type='native-api')}
    
    result = runner.invoke(app, ["start"])
    assert result.exit_code == 0
    mock_app_context.stack_manager.is_stack_running.assert_called_once()
    mock_app_context.stack_manager.start_docker_services.assert_called_once_with(['webui'])
    mock_app_context.stack_manager.start_native_services.assert_called_once_with(['ollama'])

@patch('ollama_stack_cli.main.AppContext')
def test_start_command_with_update(MockAppContext, mock_app_context):
    """Tests that the 'start --update' command calls the correct stack manager methods including pull_images."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.is_stack_running.return_value = False
    mock_app_context.config.services = {'webui': MagicMock(type='docker'), 'ollama': MagicMock(type='native-api')}
    
    result = runner.invoke(app, ["start", "--update"])
    assert result.exit_code == 0
    mock_app_context.stack_manager.is_stack_running.assert_called_once()
    mock_app_context.stack_manager.pull_images.assert_called_once()
    mock_app_context.stack_manager.start_docker_services.assert_called_once_with(['webui'])
    mock_app_context.stack_manager.start_native_services.assert_called_once_with(['ollama'])

@patch('ollama_stack_cli.main.AppContext')
def test_stop_command(MockAppContext, mock_app_context):
    """Tests that the 'stop' command calls stack_manager methods for both Docker and native services."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.config.services = {'webui': MagicMock(type='docker'), 'ollama': MagicMock(type='native-api')}
    
    result = runner.invoke(app, ["stop"])
    assert result.exit_code == 0
    mock_app_context.stack_manager.stop_docker_services.assert_called_once()
    mock_app_context.stack_manager.stop_native_services.assert_called_once_with(['ollama'])

@patch('ollama_stack_cli.main.AppContext')
def test_restart_command(MockAppContext, mock_app_context):
    """Tests that 'restart' calls stop and then start logic for both Docker and native services."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.is_stack_running.return_value = False
    mock_app_context.config.services = {'webui': MagicMock(type='docker'), 'ollama': MagicMock(type='native-api')}
    
    result = runner.invoke(app, ["restart"])
    assert result.exit_code == 0
    mock_app_context.stack_manager.stop_docker_services.assert_called_once()
    mock_app_context.stack_manager.stop_native_services.assert_called_once_with(['ollama'])
    mock_app_context.stack_manager.is_stack_running.assert_called_once()
    mock_app_context.stack_manager.start_docker_services.assert_called_once_with(['webui'])
    mock_app_context.stack_manager.start_native_services.assert_called_once_with(['ollama'])

@patch('ollama_stack_cli.main.AppContext')
def test_restart_command_with_update(MockAppContext, mock_app_context):
    """Tests that 'restart --update' calls stop, pull_images, and then start logic for both Docker and native services."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.is_stack_running.return_value = False
    mock_app_context.config.services = {'webui': MagicMock(type='docker'), 'ollama': MagicMock(type='native-api')}
    
    result = runner.invoke(app, ["restart", "--update"])
    assert result.exit_code == 0
    mock_app_context.stack_manager.stop_docker_services.assert_called_once()
    mock_app_context.stack_manager.stop_native_services.assert_called_once_with(['ollama'])
    mock_app_context.stack_manager.is_stack_running.assert_called_once()
    mock_app_context.stack_manager.pull_images.assert_called_once()
    mock_app_context.stack_manager.start_docker_services.assert_called_once_with(['webui'])
    mock_app_context.stack_manager.start_native_services.assert_called_once_with(['ollama'])

@patch('ollama_stack_cli.main.AppContext')
def test_status_command(MockAppContext, mock_app_context):
    """Tests that the 'status' command calls the correct services."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.config.services = {'webui': MagicMock(type='docker'), 'ollama': MagicMock(type='native-api')}
    
    # Mock return values
    mock_docker_status = [ServiceStatus(name='webui', is_running=True)]
    mock_ollama_status = ServiceStatus(name='ollama', is_running=True)
    mock_app_context.stack_manager.get_docker_services_status.return_value = mock_docker_status
    mock_app_context.stack_manager.get_ollama_status.return_value = mock_ollama_status
    
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    mock_app_context.stack_manager.get_docker_services_status.assert_called_once_with(['webui'])
    mock_app_context.stack_manager.get_ollama_status.assert_called_once()
    mock_app_context.display.status.assert_called_once()

@patch('ollama_stack_cli.main.AppContext')
def test_check_command(MockAppContext, mock_app_context):
    """Tests that the 'check' command calls the correct services."""
    MockAppContext.return_value = mock_app_context
    mock_check_report = CheckReport(checks=[])
    mock_app_context.stack_manager.run_docker_environment_checks.return_value = mock_check_report
    result = runner.invoke(app, ["check"])
    assert result.exit_code == 0
    mock_app_context.stack_manager.run_docker_environment_checks.assert_called_once_with(fix=False, verbose=False)
    mock_app_context.display.check_report.assert_called_once_with(mock_check_report)

@patch('ollama_stack_cli.main.AppContext')
def test_logs_command(MockAppContext, mock_app_context):
    """Tests the 'logs' command with default options."""
    MockAppContext.return_value = mock_app_context
    mock_logs = ["log line 1", "log line 2"]
    mock_app_context.stack_manager.stream_docker_logs.return_value = iter(mock_logs)
    mock_app_context.config.services = {}
    
    result = runner.invoke(app, ["logs"])
    assert result.exit_code == 0
    mock_app_context.stack_manager.stream_docker_logs.assert_called_once_with(
        None, False, None, None, None, None
    )
    assert mock_app_context.display.log_message.call_count == 2
    mock_app_context.display.log_message.assert_any_call("log line 1")
    mock_app_context.display.log_message.assert_any_call("log line 2")

@patch('ollama_stack_cli.main.AppContext')
def test_logs_command_with_options(MockAppContext, mock_app_context):
    """Tests the 'logs' command with all options."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.stream_docker_logs.return_value = iter([])
    mock_app_context.config.services = {'ollama': MagicMock(type='docker')}
    
    result = runner.invoke(app, ["logs", "ollama", "--follow", "--tail", "100", "--level", "info"])
    assert result.exit_code == 0
    mock_app_context.stack_manager.stream_docker_logs.assert_called_once_with(
        "ollama", True, 100, "info", None, None
    )

@patch('ollama_stack_cli.main.AppContext')
def test_logs_command_empty_iterator(MockAppContext, mock_app_context):
    """Tests the 'logs' command handles an empty stream gracefully."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.stream_docker_logs.return_value = iter([])
    mock_app_context.config.services = {}
    
    result = runner.invoke(app, ["logs"])
    assert result.exit_code == 0
    mock_app_context.stack_manager.stream_docker_logs.assert_called_once_with(
        None, False, None, None, None, None
    )
    mock_app_context.display.log_message.assert_not_called()

# --- Additional Command Tests for Edge Cases ---

@patch('ollama_stack_cli.main.AppContext')
def test_start_command_already_running(MockAppContext, mock_app_context):
    """Tests that the 'start' command exits early when stack is already running."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.is_stack_running.return_value = True
    mock_app_context.config.services = {'webui': MagicMock(type='docker'), 'ollama': MagicMock(type='native-api')}
    
    result = runner.invoke(app, ["start"])
    assert result.exit_code == 0
    mock_app_context.stack_manager.is_stack_running.assert_called_once()
    # Should not call start methods when already running
    mock_app_context.stack_manager.start_docker_services.assert_not_called()
    mock_app_context.stack_manager.start_native_services.assert_not_called()
    mock_app_context.stack_manager.pull_images.assert_not_called()

@patch('ollama_stack_cli.main.AppContext')
def test_start_command_with_update_already_running(MockAppContext, mock_app_context):
    """Tests that the 'start --update' command exits early when stack is already running (no image pull)."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.is_stack_running.return_value = True
    mock_app_context.config.services = {'webui': MagicMock(type='docker'), 'ollama': MagicMock(type='native-api')}
    
    result = runner.invoke(app, ["start", "--update"])
    assert result.exit_code == 0
    mock_app_context.stack_manager.is_stack_running.assert_called_once()
    # Should not pull images or start services when already running
    mock_app_context.stack_manager.pull_images.assert_not_called()
    mock_app_context.stack_manager.start_docker_services.assert_not_called()
    mock_app_context.stack_manager.start_native_services.assert_not_called()

@patch('ollama_stack_cli.main.AppContext')
def test_start_command_only_docker_services(MockAppContext, mock_app_context):
    """Tests start command when only Docker services exist."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.is_stack_running.return_value = False
    mock_app_context.config.services = {'webui': MagicMock(type='docker'), 'mcp_proxy': MagicMock(type='docker')}
    
    result = runner.invoke(app, ["start"])
    assert result.exit_code == 0
    mock_app_context.stack_manager.start_docker_services.assert_called_once_with(['webui', 'mcp_proxy'])
    mock_app_context.stack_manager.start_native_services.assert_not_called()

@patch('ollama_stack_cli.main.AppContext')
def test_start_command_only_native_services(MockAppContext, mock_app_context):
    """Tests start command when only native services exist."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.is_stack_running.return_value = False
    mock_app_context.config.services = {'ollama': MagicMock(type='native-api'), 'custom_api': MagicMock(type='native-api')}
    
    result = runner.invoke(app, ["start"])
    assert result.exit_code == 0
    mock_app_context.stack_manager.start_docker_services.assert_not_called()
    mock_app_context.stack_manager.start_native_services.assert_called_once_with(['ollama', 'custom_api'])

@patch('ollama_stack_cli.main.AppContext')
def test_start_command_no_services(MockAppContext, mock_app_context):
    """Tests start command when no services are configured."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.is_stack_running.return_value = False
    mock_app_context.config.services = {}
    
    result = runner.invoke(app, ["start"])
    assert result.exit_code == 0
    mock_app_context.stack_manager.start_docker_services.assert_not_called()
    mock_app_context.stack_manager.start_native_services.assert_not_called()

@patch('ollama_stack_cli.main.AppContext')
def test_stop_command_only_docker_services(MockAppContext, mock_app_context):
    """Tests stop command when only Docker services exist."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.config.services = {'webui': MagicMock(type='docker'), 'mcp_proxy': MagicMock(type='docker')}
    
    result = runner.invoke(app, ["stop"])
    assert result.exit_code == 0
    mock_app_context.stack_manager.stop_docker_services.assert_called_once()
    mock_app_context.stack_manager.stop_native_services.assert_not_called()

@patch('ollama_stack_cli.main.AppContext')
def test_stop_command_only_native_services(MockAppContext, mock_app_context):
    """Tests stop command when only native services exist."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.config.services = {'ollama': MagicMock(type='native-api')}
    
    result = runner.invoke(app, ["stop"])
    assert result.exit_code == 0
    mock_app_context.stack_manager.stop_docker_services.assert_not_called()
    mock_app_context.stack_manager.stop_native_services.assert_called_once_with(['ollama'])

@patch('ollama_stack_cli.main.AppContext')
def test_stop_command_no_services(MockAppContext, mock_app_context):
    """Tests stop command when no services are configured."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.config.services = {}
    
    result = runner.invoke(app, ["stop"])
    assert result.exit_code == 0
    mock_app_context.stack_manager.stop_docker_services.assert_not_called()
    mock_app_context.stack_manager.stop_native_services.assert_not_called()

@patch('ollama_stack_cli.main.AppContext')
def test_restart_command_only_docker_services(MockAppContext, mock_app_context):
    """Tests restart command when only Docker services exist."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.is_stack_running.return_value = False
    mock_app_context.config.services = {'webui': MagicMock(type='docker'), 'mcp_proxy': MagicMock(type='docker')}
    
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
    mock_app_context.config.services = {'ollama': MagicMock(type='native-api')}
    
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
    mock_app_context.config.services = {}
    
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
    mock_app_context.config.services = {'webui': MagicMock(type='docker'), 'ollama': MagicMock(type='native-api')}
    
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
def test_start_command_service_filtering_with_unknown_types(MockAppContext, mock_app_context):
    """Tests that start command properly filters services, ignoring unknown types."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.is_stack_running.return_value = False
    mock_app_context.config.services = {
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
def test_stop_command_service_filtering_with_unknown_types(MockAppContext, mock_app_context):
    """Tests that stop command properly filters services, ignoring unknown types."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.config.services = {
        'webui': MagicMock(type='docker'),
        'ollama': MagicMock(type='native-api'),
        'unknown_service': MagicMock(type='unknown-type')
    }
    
    result = runner.invoke(app, ["stop"])
    assert result.exit_code == 0
    # Should only stop known service types
    mock_app_context.stack_manager.stop_docker_services.assert_called_once()
    mock_app_context.stack_manager.stop_native_services.assert_called_once_with(['ollama']) 