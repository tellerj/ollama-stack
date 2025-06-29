from typer.testing import CliRunner
from unittest.mock import MagicMock, patch
import pytest

from ollama_stack_cli.main import app
from ollama_stack_cli.schemas import StackStatus, CheckReport, ServiceStatus, EnvironmentCheck

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
    """Tests that the 'start --update' command calls the correct stack manager methods including pull_images."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.is_stack_running.return_value = False
    mock_app_context.stack_manager.get_running_services_summary.return_value = ([], [])
    mock_app_context.stack_manager.config.services = {'webui': MagicMock(type='docker'), 'ollama': MagicMock(type='native-api')}
    mock_app_context.config.fell_back_to_defaults = False
    
    result = runner.invoke(app, ["start", "--update"])
    assert result.exit_code == 0
    mock_app_context.stack_manager.get_running_services_summary.assert_called_once()
    mock_app_context.stack_manager.pull_images.assert_called_once()
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
def test_stop_command(MockAppContext, mock_app_context):
    """Tests that the 'stop' command calls stack_manager methods for both Docker and native services."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.config.services = {'webui': MagicMock(type='docker'), 'ollama': MagicMock(type='native-api')}
    
    result = runner.invoke(app, ["stop"])
    assert result.exit_code == 0
    mock_app_context.stack_manager.stop_docker_services.assert_called_once()
    mock_app_context.stack_manager.stop_native_services.assert_called_once_with(['ollama'])

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
    """Tests that 'restart --update' calls stop, pull_images, and then start logic for both Docker and native services."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.is_stack_running.return_value = False
    mock_app_context.stack_manager.get_running_services_summary.return_value = ([], [])
    mock_app_context.stack_manager.config.services = {'webui': MagicMock(type='docker'), 'ollama': MagicMock(type='native-api')}
    mock_app_context.config.fell_back_to_defaults = False
    
    result = runner.invoke(app, ["restart", "--update"])
    assert result.exit_code == 0
    mock_app_context.stack_manager.stop_docker_services.assert_called_once()
    mock_app_context.stack_manager.stop_native_services.assert_called_once_with(['ollama'])
    mock_app_context.stack_manager.get_running_services_summary.assert_called_once()
    mock_app_context.stack_manager.pull_images.assert_called_once()
    mock_app_context.stack_manager.start_docker_services.assert_called_once_with(['webui'])
    mock_app_context.stack_manager.start_native_services.assert_called_once_with(['ollama'])

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
def test_check_command(MockAppContext, mock_app_context):
    """Tests that the 'check' command calls the correct services."""
    MockAppContext.return_value = mock_app_context
    mock_check_report = CheckReport(checks=[
        EnvironmentCheck(name="Docker Daemon Running", passed=True),
        EnvironmentCheck(name="Port 11434 Available", passed=True)
    ])
    mock_app_context.stack_manager.run_environment_checks.return_value = mock_check_report
    mock_app_context.config.fell_back_to_defaults = False
    
    result = runner.invoke(app, ["check"])
    assert result.exit_code == 0
    mock_app_context.stack_manager.run_environment_checks.assert_called_once_with(fix=False)
    mock_app_context.display.check_report.assert_called_once_with(mock_check_report)

@patch('ollama_stack_cli.main.AppContext')
def test_check_command_with_fix(MockAppContext, mock_app_context):
    """Tests that the 'check --fix' command calls the correct services with fix=True."""
    MockAppContext.return_value = mock_app_context
    mock_check_report = CheckReport(checks=[
        EnvironmentCheck(name="Docker Daemon Running", passed=True),
        EnvironmentCheck(name="Docker Images", passed=True, details="Successfully pulled latest Docker images")
    ])
    mock_app_context.stack_manager.run_environment_checks.return_value = mock_check_report
    mock_app_context.config.fell_back_to_defaults = False
    
    result = runner.invoke(app, ["check", "--fix"])
    assert result.exit_code == 0
    mock_app_context.stack_manager.run_environment_checks.assert_called_once_with(fix=True)
    mock_app_context.display.check_report.assert_called_once_with(mock_check_report)

@patch('ollama_stack_cli.main.AppContext')
def test_check_command_with_config_fallback(MockAppContext, mock_app_context):
    """Tests that the check command handles config fallback scenarios."""
    MockAppContext.return_value = mock_app_context
    mock_check_report = CheckReport(checks=[
        EnvironmentCheck(name="Docker Daemon Running", passed=True)
    ])
    mock_app_context.stack_manager.run_environment_checks.return_value = mock_check_report
    mock_app_context.config.fell_back_to_defaults = True
    
    result = runner.invoke(app, ["check"])
    assert result.exit_code == 0
    mock_app_context.stack_manager.run_environment_checks.assert_called_once_with(fix=False)
    mock_app_context.display.check_report.assert_called_once_with(mock_check_report)
    # Should not call config.save() without --fix flag
    mock_app_context.config.save.assert_not_called()

@patch('ollama_stack_cli.main.AppContext')
def test_check_command_with_config_fallback_and_fix(MockAppContext, mock_app_context):
    """Tests that the check --fix command saves config when it fell back to defaults."""
    MockAppContext.return_value = mock_app_context
    mock_check_report = CheckReport(checks=[
        EnvironmentCheck(name="Docker Daemon Running", passed=True)
    ])
    mock_app_context.stack_manager.run_environment_checks.return_value = mock_check_report
    mock_app_context.config.fell_back_to_defaults = True
    
    result = runner.invoke(app, ["check", "--fix"])
    assert result.exit_code == 0
    mock_app_context.stack_manager.run_environment_checks.assert_called_once_with(fix=True)
    mock_app_context.config.save.assert_called_once()  # Should save config when --fix is used
    mock_app_context.display.check_report.assert_called_once_with(mock_check_report)

@patch('ollama_stack_cli.main.AppContext')
def test_check_command_with_config_fallback_and_fix_save_failure(MockAppContext, mock_app_context):
    """Tests that the check --fix command handles config save failures gracefully."""
    MockAppContext.return_value = mock_app_context
    mock_check_report = CheckReport(checks=[
        EnvironmentCheck(name="Docker Daemon Running", passed=True)
    ])
    mock_app_context.stack_manager.run_environment_checks.return_value = mock_check_report
    mock_app_context.config.fell_back_to_defaults = True
    mock_app_context.config.save.side_effect = Exception("Permission denied")
    
    result = runner.invoke(app, ["check", "--fix"])
    assert result.exit_code == 0  # Should not exit with error, just log it
    mock_app_context.stack_manager.run_environment_checks.assert_called_once_with(fix=True)
    mock_app_context.config.save.assert_called_once()
    mock_app_context.display.check_report.assert_called_once_with(mock_check_report)

@patch('ollama_stack_cli.main.AppContext')
def test_check_command_all_checks_passed(MockAppContext, mock_app_context):
    """Tests check command summary logging when all checks pass."""
    MockAppContext.return_value = mock_app_context
    mock_check_report = CheckReport(checks=[
        EnvironmentCheck(name="Docker Daemon Running", passed=True),
        EnvironmentCheck(name="Port 11434 Available", passed=True),
        EnvironmentCheck(name="Ollama Installation", passed=True)
    ])
    mock_app_context.stack_manager.run_environment_checks.return_value = mock_check_report
    mock_app_context.config.fell_back_to_defaults = False
    
    result = runner.invoke(app, ["check"])
    assert result.exit_code == 0
    mock_app_context.stack_manager.run_environment_checks.assert_called_once_with(fix=False)
    mock_app_context.display.check_report.assert_called_once_with(mock_check_report)

@patch('ollama_stack_cli.main.AppContext')
def test_check_command_some_checks_failed(MockAppContext, mock_app_context):
    """Tests check command summary logging when some checks fail."""
    MockAppContext.return_value = mock_app_context
    mock_check_report = CheckReport(checks=[
        EnvironmentCheck(name="Docker Daemon Running", passed=True),
        EnvironmentCheck(name="Port 11434 Available", passed=False, details="Port in use"),
        EnvironmentCheck(name="Ollama Installation", passed=True)
    ])
    mock_app_context.stack_manager.run_environment_checks.return_value = mock_check_report
    mock_app_context.config.fell_back_to_defaults = False
    
    result = runner.invoke(app, ["check"])
    assert result.exit_code == 0
    mock_app_context.stack_manager.run_environment_checks.assert_called_once_with(fix=False)
    mock_app_context.display.check_report.assert_called_once_with(mock_check_report)

@patch('ollama_stack_cli.main.AppContext')
def test_check_command_no_checks_returned(MockAppContext, mock_app_context):
    """Tests check command when no checks are returned (edge case)."""
    MockAppContext.return_value = mock_app_context
    mock_check_report = CheckReport(checks=[])
    mock_app_context.stack_manager.run_environment_checks.return_value = mock_check_report
    mock_app_context.config.fell_back_to_defaults = False
    
    result = runner.invoke(app, ["check"])
    assert result.exit_code == 0
    mock_app_context.stack_manager.run_environment_checks.assert_called_once_with(fix=False)
    mock_app_context.display.check_report.assert_called_once_with(mock_check_report)

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
    from datetime import datetime
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

# --- Additional Command Tests for Edge Cases ---

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