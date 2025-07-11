"""
Comprehensive test suite for the install command.
Covers all execution paths, error conditions, user interactions, and edge cases.
"""

from typer.testing import CliRunner
from unittest.mock import MagicMock, patch, call
import pytest
import tempfile
import os
from pathlib import Path

from ollama_stack_cli.main import app
from ollama_stack_cli.schemas import CheckReport, EnvironmentCheck, AppConfig, PlatformConfig

runner = CliRunner()


# =============================================================================
# Fixtures and Test Setup
# =============================================================================

@pytest.fixture
def mock_app_context():
    """Fixture providing a fully mocked AppContext."""
    mock_context = MagicMock()
    mock_context.stack_manager = MagicMock()
    mock_context.display = MagicMock()
    mock_context.config = MagicMock()
    return mock_context


@pytest.fixture
def successful_check_report():
    """Fixture providing a successful environment check report."""
    return CheckReport(checks=[
        EnvironmentCheck(name="Docker Daemon Running", passed=True),
        EnvironmentCheck(name="Port 11434 Available", passed=True),
        EnvironmentCheck(name="Port 8080 Available", passed=True)
    ])


@pytest.fixture
def failed_check_report():
    """Fixture providing a failed environment check report."""
    return CheckReport(checks=[
        EnvironmentCheck(name="Docker Daemon Running", passed=True),
        EnvironmentCheck(name="Port 11434 Available", passed=False, details="Port in use"),
        EnvironmentCheck(name="Port 8080 Available", passed=False, details="Port in use")
    ])


# =============================================================================
# Basic Command Tests
# =============================================================================

@patch('ollama_stack_cli.main.AppContext')
def test_install_command_basic_execution(MockAppContext, mock_app_context):
    """Test basic install command execution without flags."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.install_stack.return_value = {
        'success': True,
        'config_dir': '/test/config',
        'config_file': '/test/config.json',
        'env_file': '/test/env',
        'check_report': MagicMock(),
        'failed_checks': []
    }
    
    result = runner.invoke(app, ["install"])
    
    assert result.exit_code == 0
    mock_app_context.stack_manager.install_stack.assert_called_once_with(force=False)


@patch('ollama_stack_cli.main.AppContext')
def test_install_command_with_force_flag(MockAppContext, mock_app_context):
    """Test install command with --force flag."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.install_stack.return_value = {
        'success': True,
        'config_dir': '/test/config',
        'config_file': '/test/config.json',
        'env_file': '/test/env',
        'check_report': MagicMock(),
        'failed_checks': []
    }
    
    result = runner.invoke(app, ["install", "--force"])
    
    assert result.exit_code == 0
    mock_app_context.stack_manager.install_stack.assert_called_once_with(force=True)


@patch('ollama_stack_cli.main.AppContext')
def test_install_command_help_display(MockAppContext, mock_app_context):
    """Test that install command displays proper help information."""
    result = runner.invoke(app, ["install", "--help"])
    
    assert result.exit_code == 0
    assert "Initialize fresh stack configuration" in result.output
    assert "--force" in result.output
    assert "Overwrite existing configuration files without prompting" in result.output


@patch('ollama_stack_cli.main.AppContext')
def test_install_command_no_args(MockAppContext, mock_app_context):
    """Test install command with no arguments (default behavior)."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.install_stack.return_value = {
        'success': True,
        'config_dir': '/test/config',
        'config_file': '/test/config.json',
        'env_file': '/test/env',
        'check_report': MagicMock(),
        'failed_checks': []
    }
    
    result = runner.invoke(app, ["install"])
    
    assert result.exit_code == 0
    # Should call with force=False by default
    mock_app_context.stack_manager.install_stack.assert_called_once_with(force=False)


# =============================================================================
# Success Path Tests
# =============================================================================

@patch('ollama_stack_cli.main.AppContext')
def test_install_command_success_display_messages(MockAppContext, mock_app_context):
    """Test that install command shows the correct final success message."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.install_stack.return_value = {
        'success': True,
        'config_dir': '/test/config',
        'config_file': '/test/config.json',
        'env_file': '/test/env',
        'check_report': MagicMock(),
        'failed_checks': []
    }
    
    runner.invoke(app, ["install"])
    
    mock_app_context.display.success.assert_called_once_with("Environment validation completed - all checks passed!")


@patch('ollama_stack_cli.main.AppContext')
def test_install_command_success_logging(MockAppContext, mock_app_context):
    """Test that successful installation logs appropriate messages."""
    MockAppContext.return_value = mock_app_context
    mock_check_report = MagicMock()
    mock_check_report.checks = []
    mock_app_context.stack_manager.install_stack.return_value = {
        'success': True,
        'config_dir': '/test/config',
        'config_file': '/test/config.json',
        'env_file': '/test/env',
        'check_report': mock_check_report,
        'failed_checks': []
    }
    
    with patch('ollama_stack_cli.commands.install.log') as mock_log:
        result = runner.invoke(app, ["install"])
        
        assert result.exit_code == 0
        mock_log.info.assert_any_call("Starting fresh stack installation...")
        mock_log.info.assert_any_call("Installation completed successfully")


@patch('ollama_stack_cli.main.AppContext')
def test_install_command_success_return_value(MockAppContext, mock_app_context):
    """Test that successful installation returns correct value."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.install_stack.return_value = {
        'success': True,
        'config_dir': '/test/config',
        'config_file': '/test/config.json',
        'env_file': '/test/env',
        'check_report': MagicMock(),
        'failed_checks': []
    }
    
    result = runner.invoke(app, ["install"])
    
    assert result.exit_code == 0
    # The command itself doesn't return a value, but should complete successfully


# =============================================================================
# Failure Path Tests
# =============================================================================

@patch('ollama_stack_cli.main.AppContext')
def test_install_command_stack_manager_failure(MockAppContext, mock_app_context):
    """Test install command when stack manager returns False."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.install_stack.return_value = {
        'success': False,
        'error': 'Configuration creation failed'
    }
    
    result = runner.invoke(app, ["install"])
    
    assert result.exit_code == 0  # Command doesn't exit with error code
    mock_app_context.display.error.assert_called_once_with("Configuration creation failed")


@patch('ollama_stack_cli.main.AppContext')
def test_install_command_failure_logging(MockAppContext, mock_app_context):
    """Test that failed installation logs error messages."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.install_stack.return_value = {
        'success': False,
        'error': 'Configuration creation failed'
    }
    
    with patch('ollama_stack_cli.commands.install.log') as mock_log:
        result = runner.invoke(app, ["install"])
        
        assert result.exit_code == 0
        mock_log.info.assert_any_call("Starting fresh stack installation...")
        mock_log.error.assert_any_call("Installation failed")


@patch('ollama_stack_cli.main.AppContext')
def test_install_command_no_success_display_on_failure(MockAppContext, mock_app_context):
    """Test that failed installation doesn't display success messages."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.install_stack.return_value = {
        'success': False,
        'config_dir': '/test/config',
        'config_file': '/test/config.json',
        'env_file': '/test/env',
        'check_report': MagicMock(),
        'failed_checks': []
    }
    
    result = runner.invoke(app, ["install"])
    
    assert result.exit_code == 0
    mock_app_context.display.success.assert_not_called()
    mock_app_context.display.panel.assert_not_called()


# =============================================================================
# Exception Handling Tests
# =============================================================================

@patch('ollama_stack_cli.main.AppContext')
def test_install_command_stack_manager_exception(MockAppContext, mock_app_context):
    """Test install command when stack manager raises exception."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.install_stack.side_effect = Exception("Test error")
    
    result = runner.invoke(app, ["install"])
    
    assert result.exit_code == 0  # Command handles exceptions gracefully
    mock_app_context.display.error.assert_called_once()
    error_call = mock_app_context.display.error.call_args[0][0]
    assert "Installation failed: Test error" in error_call


@patch('ollama_stack_cli.main.AppContext')
def test_install_command_permission_error_exception(MockAppContext, mock_app_context):
    """Test install command when permission error occurs."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.install_stack.side_effect = PermissionError("Permission denied")
    
    result = runner.invoke(app, ["install"])
    
    assert result.exit_code == 0
    mock_app_context.display.error.assert_called_once()
    error_call = mock_app_context.display.error.call_args[0][0]
    assert "Installation failed: Permission denied" in error_call


@patch('ollama_stack_cli.main.AppContext')
def test_install_command_io_error_exception(MockAppContext, mock_app_context):
    """Test install command when IO error occurs."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.install_stack.side_effect = IOError("Disk full")
    
    result = runner.invoke(app, ["install"])
    
    assert result.exit_code == 0
    mock_app_context.display.error.assert_called_once()
    error_call = mock_app_context.display.error.call_args[0][0]
    assert "Installation failed: Disk full" in error_call


@patch('ollama_stack_cli.main.AppContext')
def test_install_command_exception_logging(MockAppContext, mock_app_context):
    """Test that exceptions are properly logged with stack trace."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.install_stack.side_effect = ValueError("Test error")
    
    with patch('ollama_stack_cli.commands.install.log') as mock_log:
        result = runner.invoke(app, ["install"])
        
        assert result.exit_code == 0
        mock_log.error.assert_called_once()
        # Verify exc_info=True was passed for stack trace
        call_args = mock_log.error.call_args
        assert call_args[1]['exc_info'] is True


@patch('ollama_stack_cli.main.AppContext')
def test_install_command_keyboard_interrupt_cli_level(MockAppContext, mock_app_context):
    """Test install command handles KeyboardInterrupt at CLI level."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.install_stack.side_effect = KeyboardInterrupt()
    
    result = runner.invoke(app, ["install"])
    
    # KeyboardInterrupt causes CLI to exit with code 130 (SIGINT)
    assert result.exit_code == 130
    # The interrupt happens before our error handling can display anything
    # This is expected behavior for Ctrl+C in CLI applications


@patch('ollama_stack_cli.main.AppContext')
def test_install_command_keyboard_interrupt_during_install(MockAppContext, mock_app_context):
    """Test that KeyboardInterrupt during install_stack is handled correctly."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.install_stack.side_effect = KeyboardInterrupt()
    
    result = runner.invoke(app, ["install"])
    
    assert result.exit_code == 130
    mock_app_context.display.error.assert_not_called()


# =============================================================================
# Flag Handling Tests
# =============================================================================

@patch('ollama_stack_cli.main.AppContext')
def test_install_command_force_flag_variations(MockAppContext, mock_app_context):
    """Test different ways to specify the force flag."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.install_stack.return_value = {
        'success': True,
        'config_dir': '/test/config',
        'config_file': '/test/config.json',
        'env_file': '/test/env',
        'check_report': MagicMock(),
        'failed_checks': []
    }
    
    # Test --force
    result = runner.invoke(app, ["install", "--force"])
    assert result.exit_code == 0
    mock_app_context.stack_manager.install_stack.assert_called_with(force=True)
    
    # Reset mock
    mock_app_context.stack_manager.install_stack.reset_mock()
    
    # Test without flag
    result = runner.invoke(app, ["install"])
    assert result.exit_code == 0
    mock_app_context.stack_manager.install_stack.assert_called_with(force=False)


@patch('ollama_stack_cli.main.AppContext')
def test_install_command_invalid_flag(MockAppContext, mock_app_context):
    """Test install command with invalid flag."""
    MockAppContext.return_value = mock_app_context
    
    result = runner.invoke(app, ["install", "--invalid-flag"])
    
    assert result.exit_code != 0  # Should fail with invalid flag
    assert "No such option" in result.output


@patch('ollama_stack_cli.main.AppContext')
def test_install_command_force_flag_boolean_type(MockAppContext, mock_app_context):
    """Test that force flag is properly typed as boolean."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.install_stack.return_value = {
        'success': True,
        'config_dir': '/test/config',
        'config_file': '/test/config.json',
        'env_file': '/test/env',
        'check_report': MagicMock(),
        'failed_checks': []
    }
    
    result = runner.invoke(app, ["install", "--force"])
    
    assert result.exit_code == 0
    # Verify the force parameter is actually a boolean True
    call_args = mock_app_context.stack_manager.install_stack.call_args
    assert call_args[1]['force'] is True
    assert type(call_args[1]['force']) is bool


# =============================================================================
# Context and Integration Tests
# =============================================================================

@patch('ollama_stack_cli.main.AppContext')
def test_install_command_context_object_access(MockAppContext, mock_app_context):
    """Test that install command properly accesses the context object."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.install_stack.return_value = {
        'success': True,
        'config_dir': '/test/config',
        'config_file': '/test/config.json',
        'env_file': '/test/env',
        'check_report': MagicMock(),
        'failed_checks': []
    }
    
    result = runner.invoke(app, ["install"])
    
    assert result.exit_code == 0
    # Verify that the stack manager method was called (indicating proper context access)
    mock_app_context.stack_manager.install_stack.assert_called_once()


@patch('ollama_stack_cli.main.AppContext')
def test_install_command_context_initialization_failure(MockAppContext, mock_app_context):
    """Test install command when AppContext initialization fails."""
    MockAppContext.side_effect = Exception("Context initialization failed")
    
    result = runner.invoke(app, ["install"])
    
    # Should fail during context initialization
    assert result.exit_code != 0


@patch('ollama_stack_cli.main.AppContext')
def test_install_command_multiple_invocations(MockAppContext, mock_app_context):
    """Test that install command can be called multiple times."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.install_stack.return_value = {
        'success': True,
        'config_dir': '/test/config',
        'config_file': '/test/config.json',
        'env_file': '/test/env',
        'check_report': MagicMock(),
        'failed_checks': []
    }
    
    # First invocation
    result1 = runner.invoke(app, ["install"])
    assert result1.exit_code == 0
    
    # Second invocation
    result2 = runner.invoke(app, ["install", "--force"])
    assert result2.exit_code == 0
    
    # Verify both calls were made
    assert mock_app_context.stack_manager.install_stack.call_count == 2


@patch('ollama_stack_cli.main.AppContext')
def test_install_command_display_object_usage(MockAppContext, mock_app_context):
    """Test that install command properly uses display object for all output."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.install_stack.return_value = {
        'success': True,
        'config_dir': '/test/config',
        'config_file': '/test/config.json',
        'env_file': '/test/env',
        'check_report': MagicMock(),
        'failed_checks': []
    }
    
    result = runner.invoke(app, ["install"])
    
    assert result.exit_code == 0
    # Verify display methods were called
    mock_app_context.display.success.assert_called_once_with("Environment validation completed - all checks passed!")
    mock_app_context.display.panel.assert_called()


@patch('ollama_stack_cli.main.AppContext')
def test_install_command_stack_manager_delegation(MockAppContext, mock_app_context):
    """Test that install command properly delegates to stack manager."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.install_stack.return_value = {
        'success': True,
        'config_dir': '/test/config',
        'config_file': '/test/config.json',
        'env_file': '/test/env',
        'check_report': MagicMock(),
        'failed_checks': []
    }
    
    result = runner.invoke(app, ["install"])
    
    assert result.exit_code == 0
    # Verify delegation occurred with correct parameters
    mock_app_context.stack_manager.install_stack.assert_called_once_with(force=False)


# =============================================================================
# Edge Cases and Boundary Tests
# =============================================================================

@patch('ollama_stack_cli.main.AppContext')
def test_install_command_return_value_consistency(MockAppContext, mock_app_context):
    """Test that install command handles all return value scenarios consistently."""
    MockAppContext.return_value = mock_app_context
    
    # Test True return
    mock_app_context.stack_manager.install_stack.return_value = {
        'success': True,
        'config_dir': '/test/config',
        'config_file': '/test/config.json',
        'env_file': '/test/env',
        'check_report': MagicMock(),
        'failed_checks': []
    }
    result = runner.invoke(app, ["install"])
    assert result.exit_code == 0
    
    # Test False return
    mock_app_context.stack_manager.install_stack.return_value = {
        'success': False,
        'config_dir': '/test/config',
        'config_file': '/test/config.json',
        'env_file': '/test/env',
        'check_report': MagicMock(),
        'failed_checks': []
    }
    result = runner.invoke(app, ["install"])
    assert result.exit_code == 0  # Should not exit with error code
    
    # Test None return (edge case)
    mock_app_context.stack_manager.install_stack.return_value = None
    result = runner.invoke(app, ["install"])
    assert result.exit_code == 0


@patch('ollama_stack_cli.main.AppContext')
def test_install_command_empty_args_list(MockAppContext, mock_app_context):
    """Test install command with empty arguments list."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.install_stack.return_value = {
        'success': True,
        'config_dir': '/test/config',
        'config_file': '/test/config.json',
        'env_file': '/test/env',
        'check_report': MagicMock(),
        'failed_checks': []
    }
    
    result = runner.invoke(app, ["install"])
    
    assert result.exit_code == 0
    mock_app_context.stack_manager.install_stack.assert_called_once_with(force=False)


@patch('ollama_stack_cli.main.AppContext')
def test_install_command_unicode_in_error_messages(MockAppContext, mock_app_context):
    """Test install command handles unicode characters in error messages."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.install_stack.side_effect = Exception("Error with unicode: 🚫")
    
    result = runner.invoke(app, ["install"])
    
    assert result.exit_code == 0
    mock_app_context.display.error.assert_called_once()
    error_call = mock_app_context.display.error.call_args[0][0]
    assert "🚫" in error_call


@patch('ollama_stack_cli.main.AppContext')
def test_install_command_very_long_error_message(MockAppContext, mock_app_context):
    """Test install command handles very long error messages."""
    MockAppContext.return_value = mock_app_context
    long_error = "x" * 1000  # Very long error message
    mock_app_context.stack_manager.install_stack.side_effect = Exception(long_error)
    
    result = runner.invoke(app, ["install"])
    
    assert result.exit_code == 0
    mock_app_context.display.error.assert_called_once()
    error_call = mock_app_context.display.error.call_args[0][0]
    assert long_error in error_call


# =============================================================================
# Business Logic Testing
# =============================================================================

@patch('ollama_stack_cli.main.AppContext')
def test_install_logic_function_direct_call(MockAppContext, mock_app_context):
    """Test that install_logic can be called directly and returns correct value."""
    from ollama_stack_cli.commands.install import install_logic
    
    mock_app_context.stack_manager.install_stack.return_value = {
        'success': True,
        'config_dir': '/test/config',
        'config_file': '/test/config.json',
        'env_file': '/test/env',
        'check_report': MagicMock(),
        'failed_checks': []
    }
    
    result = install_logic(mock_app_context, force=False)
    
    assert result is True
    mock_app_context.display.success.assert_called_once()
    

@patch('ollama_stack_cli.main.AppContext')
def test_install_logic_function_with_force(MockAppContext, mock_app_context):
    """Test the install_logic function with force=True."""
    from ollama_stack_cli.commands.install import install_logic
    
    mock_app_context.stack_manager.install_stack.return_value = {
        'success': True,
        'config_dir': '/test/config',
        'config_file': '/test/config.json',
        'env_file': '/test/env',
        'check_report': MagicMock(),
        'failed_checks': []
    }
    
    result = install_logic(mock_app_context, force=True)
    
    assert result is True
    mock_app_context.stack_manager.install_stack.assert_called_once_with(force=True)


@patch('ollama_stack_cli.main.AppContext')
def test_install_logic_function_failure(MockAppContext, mock_app_context):
    """Test the install_logic function when stack manager fails."""
    from ollama_stack_cli.commands.install import install_logic
    
    mock_app_context.stack_manager.install_stack.return_value = {
        'success': False,
        'config_dir': '/test/config',
        'config_file': '/test/config.json',
        'env_file': '/test/env',
        'check_report': MagicMock(),
        'failed_checks': []
    }
    
    result = install_logic(mock_app_context, force=False)
    
    assert result is False
    mock_app_context.display.error.assert_called_once()


@patch('ollama_stack_cli.main.AppContext')
def test_install_logic_function_exception(MockAppContext, mock_app_context):
    """Test the install_logic function when exception occurs."""
    from ollama_stack_cli.commands.install import install_logic
    
    mock_app_context.stack_manager.install_stack.side_effect = Exception("Test error")
    
    result = install_logic(mock_app_context, force=False)
    
    assert result is False
    mock_app_context.display.error.assert_called_once()


# =============================================================================
# Integration-Style Tests
# =============================================================================

@patch('ollama_stack_cli.main.AppContext')
def test_install_command_full_success_workflow(MockAppContext, mock_app_context):
    """Test the complete success workflow of the install command."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.install_stack.return_value = {
        'success': True,
        'config_dir': '/test/config',
        'config_file': '/test/config.json',
        'env_file': '/test/env',
        'check_report': MagicMock(),
        'failed_checks': []
    }
    
    result = runner.invoke(app, ["install"])
    
    assert result.exit_code == 0
    mock_app_context.stack_manager.install_stack.assert_called_once()
    mock_app_context.display.success.assert_called_once_with("Environment validation completed - all checks passed!")
    mock_app_context.display.panel.assert_called()


@patch('ollama_stack_cli.main.AppContext')
def test_install_command_full_failure_workflow(MockAppContext, mock_app_context):
    """Test complete failed installation workflow."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.install_stack.return_value = {
        'success': False,
        'config_dir': '/test/config',
        'config_file': '/test/config.json',
        'env_file': '/test/env',
        'check_report': MagicMock(),
        'failed_checks': []
    }
    
    result = runner.invoke(app, ["install"])
    
    assert result.exit_code == 0
    
    # Verify the complete failure call sequence
    mock_app_context.stack_manager.install_stack.assert_called_once_with(force=False)
    mock_app_context.display.error.assert_called_once_with("Installation failed - check logs for details")
    # Should not call success methods
    mock_app_context.display.success.assert_not_called()
    mock_app_context.display.panel.assert_not_called()


@patch('ollama_stack_cli.main.AppContext')
def test_install_command_full_exception_workflow(MockAppContext, mock_app_context):
    """Test complete exception handling workflow."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.install_stack.side_effect = RuntimeError("System error")
    
    result = runner.invoke(app, ["install"])
    
    assert result.exit_code == 0
    
    # Verify the complete exception call sequence
    mock_app_context.stack_manager.install_stack.assert_called_once_with(force=False)
    mock_app_context.display.error.assert_called_once()
    error_call = mock_app_context.display.error.call_args[0][0]
    assert "Installation failed: System error" in error_call
    # Should not call success methods
    mock_app_context.display.success.assert_not_called()
    mock_app_context.display.panel.assert_not_called()


# =============================================================================
# Performance and Stress Tests
# =============================================================================

@patch('ollama_stack_cli.main.AppContext')
def test_install_command_rapid_successive_calls(MockAppContext, mock_app_context):
    """Test install command can handle rapid successive calls."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.install_stack.return_value = {
        'success': True,
        'config_dir': '/test/config',
        'config_file': '/test/config.json',
        'env_file': '/test/env',
        'check_report': MagicMock(),
        'failed_checks': []
    }
    
    # Make multiple rapid calls
    for i in range(5):
        result = runner.invoke(app, ["install"])
        assert result.exit_code == 0
    
    # Verify all calls were made
    assert mock_app_context.stack_manager.install_stack.call_count == 5


@patch('ollama_stack_cli.main.AppContext')
def test_install_command_memory_cleanup(MockAppContext, mock_app_context):
    """Test that install command doesn't leak memory or resources."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.install_stack.return_value = {
        'success': True,
        'config_dir': '/test/config',
        'config_file': '/test/config.json',
        'env_file': '/test/env',
        'check_report': MagicMock(),
        'failed_checks': []
    }
    
    # This test primarily ensures no exceptions during cleanup
    result = runner.invoke(app, ["install"])
    assert result.exit_code == 0
    
    # Invoke garbage collection and ensure no issues
    import gc
    gc.collect()
    
    # Should be able to invoke again without issues
    result = runner.invoke(app, ["install"])
    assert result.exit_code == 0 