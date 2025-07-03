from typer.testing import CliRunner
from unittest.mock import MagicMock, patch
import pytest

from ollama_stack_cli.main import app
from ollama_stack_cli.schemas import CheckReport, EnvironmentCheck

runner = CliRunner()


# --- Check Command Tests ---

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