from typer.testing import CliRunner
from unittest.mock import MagicMock, patch
import pytest
from datetime import datetime

from ollama_stack_cli.main import app

runner = CliRunner()


# --- Logs Command Tests ---

@patch('ollama_stack_cli.main.AppContext')
def test_logs_command(MockAppContext, mock_app_context):
    """Tests the 'logs' command with no services configured."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.config.services = {}
    
    result = runner.invoke(app, ["logs"])
    assert result.exit_code == 0
    # When no services are configured, no log streaming should occur
    mock_app_context.stack_manager.stream_docker_logs.assert_not_called()
    mock_app_context.display.log_message.assert_not_called()

@patch('ollama_stack_cli.main.AppContext')
def test_logs_command_with_options(MockAppContext, mock_app_context):
    """Tests the 'logs' command with all options for a Docker service."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.stream_docker_logs.return_value = iter([])
    mock_app_context.stack_manager.config.services = {'ollama': MagicMock(type='docker')}
    
    result = runner.invoke(app, ["logs", "ollama", "--follow", "--tail", "100", "--level", "info"])
    assert result.exit_code == 0
    mock_app_context.stack_manager.stream_docker_logs.assert_called_once_with(
        "ollama", True, 100, "info", None, None
    )

@patch('ollama_stack_cli.main.AppContext')
def test_logs_command_empty_iterator(MockAppContext, mock_app_context):
    """Tests the 'logs' command with Docker services configured but no logs."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.stream_docker_logs.return_value = iter([])
    mock_app_context.stack_manager.config.services = {'webui': MagicMock(type='docker')}
    
    result = runner.invoke(app, ["logs"])
    assert result.exit_code == 0
    mock_app_context.stack_manager.stream_docker_logs.assert_called_once_with(
        None, False, None, None, None, None
    )
    mock_app_context.display.log_message.assert_not_called()

@patch('ollama_stack_cli.main.AppContext')
def test_logs_command_native_service(MockAppContext, mock_app_context):
    """Tests the 'logs' command with a native service (Apple Silicon Ollama)."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.stream_native_logs.return_value = iter(["native log line 1", "native log line 2"])
    mock_app_context.stack_manager.config.services = {'ollama': MagicMock(type='native-api')}
    
    result = runner.invoke(app, ["logs", "ollama"])
    assert result.exit_code == 0
    mock_app_context.stack_manager.stream_native_logs.assert_called_once_with(
        "ollama", False, None, None, None, None
    )
    assert mock_app_context.display.log_message.call_count == 2
    mock_app_context.display.log_message.assert_any_call("native log line 1")
    mock_app_context.display.log_message.assert_any_call("native log line 2")

@patch('ollama_stack_cli.main.AppContext')
def test_logs_command_mixed_services_all(MockAppContext, mock_app_context):
    """Tests the 'logs' command with mixed Docker and native services (streams Docker only)."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.stream_docker_logs.return_value = iter(["docker log 1"])
    mock_app_context.stack_manager.config.services = {
        'webui': MagicMock(type='docker'),
        'ollama': MagicMock(type='native-api')
    }
    
    result = runner.invoke(app, ["logs"])
    assert result.exit_code == 0
    # Should stream Docker services when no specific service is requested
    mock_app_context.stack_manager.stream_docker_logs.assert_called_once_with(
        None, False, None, None, None, None
    )
    mock_app_context.stack_manager.stream_native_logs.assert_not_called()

@patch('ollama_stack_cli.main.AppContext')
def test_logs_command_only_native_services(MockAppContext, mock_app_context):
    """Tests the 'logs' command with only native services configured."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.config.services = {'ollama': MagicMock(type='native-api')}
    
    result = runner.invoke(app, ["logs"])
    assert result.exit_code == 0
    # Should not stream anything and provide guidance
    mock_app_context.stack_manager.stream_docker_logs.assert_not_called()
    mock_app_context.stack_manager.stream_native_logs.assert_not_called()

@patch('ollama_stack_cli.main.AppContext')
def test_logs_command_unknown_service(MockAppContext, mock_app_context):
    """Tests the 'logs' command with an unknown service name."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.stream_docker_logs.return_value = iter([])
    mock_app_context.stack_manager.config.services = {'webui': MagicMock(type='docker')}
    
    result = runner.invoke(app, ["logs", "unknown_service"])
    assert result.exit_code == 0
    # Should attempt Docker streaming for unknown services
    mock_app_context.stack_manager.stream_docker_logs.assert_called_once_with(
        "unknown_service", False, None, None, None, None
    )

@patch('ollama_stack_cli.main.AppContext')
def test_logs_command_remote_service(MockAppContext, mock_app_context):
    """Tests the 'logs' command with a remote service (should not yield logs)."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.config.services = {'external_api': MagicMock(type='remote-api')}
    
    result = runner.invoke(app, ["logs", "external_api"])
    assert result.exit_code == 0
    # Should not call any streaming methods
    mock_app_context.stack_manager.stream_docker_logs.assert_not_called()
    mock_app_context.stack_manager.stream_native_logs.assert_not_called()
    # Should not display any log messages since remote services don't yield content
    mock_app_context.display.log_message.assert_not_called()

@patch('ollama_stack_cli.main.AppContext')
def test_logs_command_unknown_service_type(MockAppContext, mock_app_context):
    """Tests the 'logs' command with a service having an unknown service type."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.config.services = {'weird_service': MagicMock(type='unknown-type')}
    
    result = runner.invoke(app, ["logs", "weird_service"])
    assert result.exit_code == 0
    # Should not call any streaming methods for unknown service types
    mock_app_context.stack_manager.stream_docker_logs.assert_not_called()
    mock_app_context.stack_manager.stream_native_logs.assert_not_called()
    mock_app_context.display.log_message.assert_not_called()

@patch('ollama_stack_cli.main.AppContext')
def test_logs_command_native_service_with_options(MockAppContext, mock_app_context):
    """Tests the 'logs' command with native service and all options."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.stream_native_logs.return_value = iter(["ollama log 1", "ollama log 2"])
    mock_app_context.stack_manager.config.services = {'ollama': MagicMock(type='native-api')}
    
    result = runner.invoke(app, ["logs", "ollama", "--follow", "--tail", "100", "--level", "debug"])
    assert result.exit_code == 0
    mock_app_context.stack_manager.stream_native_logs.assert_called_once_with(
        "ollama", True, 100, "debug", None, None
    )
    assert mock_app_context.display.log_message.call_count == 2

@patch('ollama_stack_cli.main.AppContext')
def test_logs_command_with_datetime_options(MockAppContext, mock_app_context):
    """Tests the 'logs' command with datetime since/until options."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.stream_docker_logs.return_value = iter(["timestamped log"])
    mock_app_context.stack_manager.config.services = {'webui': MagicMock(type='docker')}
    
    since_time = datetime(2023, 6, 18, 10, 30, 0)
    until_time = datetime(2023, 6, 18, 11, 30, 0)
    
    result = runner.invoke(app, ["logs", "webui", "--since", since_time.isoformat(), "--until", until_time.isoformat()])
    assert result.exit_code == 0
    # Should convert datetime objects to ISO strings
    mock_app_context.stack_manager.stream_docker_logs.assert_called_once_with(
        "webui", False, None, None, since_time.isoformat(), until_time.isoformat()
    )

@patch('ollama_stack_cli.main.AppContext')
def test_logs_command_line_counting(MockAppContext, mock_app_context):
    """Tests that the logs command properly counts and reports streamed lines."""
    MockAppContext.return_value = mock_app_context
    mock_logs = ["line 1", "line 2", "line 3"]
    mock_app_context.stack_manager.stream_docker_logs.return_value = iter(mock_logs)
    mock_app_context.stack_manager.config.services = {'webui': MagicMock(type='docker')}
    
    result = runner.invoke(app, ["logs", "webui"])
    assert result.exit_code == 0
    
    # Should display all log lines
    assert mock_app_context.display.log_message.call_count == 3
    for i, log_line in enumerate(mock_logs):
        mock_app_context.display.log_message.assert_any_call(log_line)

@patch('ollama_stack_cli.main.AppContext')
def test_logs_command_no_log_output(MockAppContext, mock_app_context):
    """Tests logs command when no log output is received."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.stream_docker_logs.return_value = iter([])
    mock_app_context.stack_manager.config.services = {'webui': MagicMock(type='docker')}
    
    result = runner.invoke(app, ["logs", "webui"])
    assert result.exit_code == 0
    
    # Should not display any log messages
    mock_app_context.display.log_message.assert_not_called()

@patch('ollama_stack_cli.main.AppContext')
def test_logs_command_stack_manager_exception(MockAppContext, mock_app_context):
    """Tests logs command when StackManager throws an exception."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.stream_docker_logs.side_effect = Exception("Docker daemon not running")
    mock_app_context.stack_manager.config.services = {'webui': MagicMock(type='docker')}
    
    result = runner.invoke(app, ["logs", "webui"])
    assert result.exit_code == 1
    
    # Should display error message
    mock_app_context.display.error.assert_called_once()
    error_call = mock_app_context.display.error.call_args
    assert "Unable to stream logs" in error_call[0][0]
    assert "Docker daemon not running" in error_call[0][0]

@patch('ollama_stack_cli.main.AppContext')
def test_logs_command_keyboard_interrupt(MockAppContext, mock_app_context):
    """Tests logs command handles KeyboardInterrupt (Ctrl+C) with standard signal exit code."""
    MockAppContext.return_value = mock_app_context
    
    def interrupt_generator():
        yield "log line 1"
        yield "log line 2"
        raise KeyboardInterrupt()
    
    mock_app_context.stack_manager.stream_docker_logs.return_value = interrupt_generator()
    mock_app_context.stack_manager.config.services = {'webui': MagicMock(type='docker')}
    
    result = runner.invoke(app, ["logs", "webui"])
    assert result.exit_code == 130  # Standard UNIX signal exit code for SIGINT
    
    # Should display the log lines that were received before interruption
    assert mock_app_context.display.log_message.call_count == 2

@patch('ollama_stack_cli.main.AppContext')
def test_logs_command_mixed_services_with_guidance(MockAppContext, mock_app_context):
    """Tests logs command with mixed services provides appropriate guidance."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.stream_docker_logs.return_value = iter(["docker log"])
    mock_app_context.stack_manager.config.services = {
        'webui': MagicMock(type='docker'),
        'mcp_proxy': MagicMock(type='docker'),
        'ollama': MagicMock(type='native-api')
    }
    
    result = runner.invoke(app, ["logs"])
    assert result.exit_code == 0
    
    # Should stream Docker logs and provide guidance about native services
    mock_app_context.stack_manager.stream_docker_logs.assert_called_once_with(
        None, False, None, None, None, None
    )
    mock_app_context.stack_manager.stream_native_logs.assert_not_called()

@patch('ollama_stack_cli.main.AppContext')
def test_logs_command_native_service_empty_logs(MockAppContext, mock_app_context):
    """Tests logs command with native service that returns no logs."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.stream_native_logs.return_value = iter([])
    mock_app_context.stack_manager.config.services = {'ollama': MagicMock(type='native-api')}
    
    result = runner.invoke(app, ["logs", "ollama"])
    assert result.exit_code == 0
    
    # Should call native log streaming but get no output
    mock_app_context.stack_manager.stream_native_logs.assert_called_once()
    mock_app_context.display.log_message.assert_not_called()

@patch('ollama_stack_cli.main.AppContext')
def test_logs_command_exception_during_streaming(MockAppContext, mock_app_context):
    """Tests logs command when exception occurs during log streaming."""
    MockAppContext.return_value = mock_app_context
    
    def failing_generator():
        yield "log line 1"
        raise RuntimeError("Network connection lost")
    
    mock_app_context.stack_manager.stream_docker_logs.return_value = failing_generator()
    mock_app_context.stack_manager.config.services = {'webui': MagicMock(type='docker')}
    
    result = runner.invoke(app, ["logs", "webui"])
    assert result.exit_code == 1
    
    # Should display one log line before the error
    mock_app_context.display.log_message.assert_called_once_with("log line 1")
    # Should display error message
    mock_app_context.display.error.assert_called_once()
    error_call = mock_app_context.display.error.call_args
    assert "Unable to stream logs" in error_call[0][0]
    assert "Network connection lost" in error_call[0][0] 