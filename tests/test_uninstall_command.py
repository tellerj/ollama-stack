from typer.testing import CliRunner
from unittest.mock import MagicMock, patch
import pytest

from ollama_stack_cli.main import app

runner = CliRunner()


# --- Happy Path Tests ---

@patch('ollama_stack_cli.main.AppContext')
def test_uninstall_command_basic_default(MockAppContext, mock_app_context):
    """Tests basic uninstall with no flags - preserves volumes and config."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.uninstall_stack.return_value = True
    
    result = runner.invoke(app, ["uninstall"])
    assert result.exit_code == 0
    mock_app_context.stack_manager.uninstall_stack.assert_called_once_with(
        remove_volumes=False,
        remove_config=False, 
        force=False
    )

@patch('ollama_stack_cli.main.AppContext')
def test_uninstall_command_remove_volumes_only(MockAppContext, mock_app_context):
    """Tests uninstall with --remove-volumes flag only."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.uninstall_stack.return_value = True
    
    result = runner.invoke(app, ["uninstall", "--remove-volumes"])
    assert result.exit_code == 0
    mock_app_context.stack_manager.uninstall_stack.assert_called_once_with(
        remove_volumes=True,
        remove_config=False, 
        force=False
    )

@patch('ollama_stack_cli.main.AppContext')
def test_uninstall_command_remove_config_only(MockAppContext, mock_app_context):
    """Tests uninstall with --remove-config flag only."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.uninstall_stack.return_value = True
    
    result = runner.invoke(app, ["uninstall", "--remove-config"])
    assert result.exit_code == 0
    mock_app_context.stack_manager.uninstall_stack.assert_called_once_with(
        remove_volumes=False,
        remove_config=True, 
        force=False
    )

@patch('ollama_stack_cli.main.AppContext')
def test_uninstall_command_force_only(MockAppContext, mock_app_context):
    """Tests uninstall with --force flag only."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.uninstall_stack.return_value = True
    
    result = runner.invoke(app, ["uninstall", "--force"])
    assert result.exit_code == 0
    mock_app_context.stack_manager.uninstall_stack.assert_called_once_with(
        remove_volumes=False,
        remove_config=False, 
        force=True
    )

@patch('ollama_stack_cli.main.AppContext')
def test_uninstall_command_all_flag(MockAppContext, mock_app_context):
    """Tests uninstall with --all flag - should enable both remove_volumes and remove_config."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.uninstall_stack.return_value = True
    
    result = runner.invoke(app, ["uninstall", "--all"])
    assert result.exit_code == 0
    mock_app_context.stack_manager.uninstall_stack.assert_called_once_with(
        remove_volumes=True,  # Should be True due to --all flag
        remove_config=True,   # Should be True due to --all flag
        force=False
    )

@patch('ollama_stack_cli.main.AppContext')
def test_uninstall_command_all_flag_short_form(MockAppContext, mock_app_context):
    """Tests uninstall with -a flag (short form of --all)."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.uninstall_stack.return_value = True
    
    result = runner.invoke(app, ["uninstall", "-a"])
    assert result.exit_code == 0
    mock_app_context.stack_manager.uninstall_stack.assert_called_once_with(
        remove_volumes=True,  # Should be True due to -a flag
        remove_config=True,   # Should be True due to -a flag
        force=False
    )

@patch('ollama_stack_cli.main.AppContext')
def test_uninstall_command_all_combinations(MockAppContext, mock_app_context):
    """Tests all valid flag combinations to ensure correct parameter passing."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.uninstall_stack.return_value = True
    
    # Test matrix of all flag combinations
    test_cases = [
        # (command_args, expected_remove_volumes, expected_remove_config, expected_force)
        ([], False, False, False),
        (["--remove-volumes"], True, False, False),
        (["--remove-config"], False, True, False),
        (["--force"], False, False, True),
        (["--remove-volumes", "--remove-config"], True, True, False),
        (["--remove-volumes", "--force"], True, False, True),
        (["--remove-config", "--force"], False, True, True),
        (["--remove-volumes", "--remove-config", "--force"], True, True, True),
        (["--all"], True, True, False),  # --all should set both volumes and config
        (["--all", "--force"], True, True, True),
        (["-a"], True, True, False),  # -a should work same as --all
        (["-a", "--force"], True, True, True),
    ]
    
    for command_args, expected_volumes, expected_config, expected_force in test_cases:
        mock_app_context.stack_manager.uninstall_stack.reset_mock()
        
        result = runner.invoke(app, ["uninstall"] + command_args)
        assert result.exit_code == 0, f"Failed for args: {command_args}"
        mock_app_context.stack_manager.uninstall_stack.assert_called_once_with(
            remove_volumes=expected_volumes,
            remove_config=expected_config, 
            force=expected_force
        )

@patch('ollama_stack_cli.main.AppContext')
def test_uninstall_command_all_flag_overrides_individual_flags(MockAppContext, mock_app_context):
    """Tests that --all flag logic overrides individual flags when combined."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.uninstall_stack.return_value = True
    
    # Even if individual flags are False, --all should force both to True
    result = runner.invoke(app, ["uninstall", "--all"])
    assert result.exit_code == 0
    mock_app_context.stack_manager.uninstall_stack.assert_called_once_with(
        remove_volumes=True,  # Forced by --all
        remove_config=True,   # Forced by --all
        force=False
    )


# --- Error and Failure Cases ---

@patch('ollama_stack_cli.main.AppContext')
def test_uninstall_command_stack_manager_failure(MockAppContext, mock_app_context):
    """Tests uninstall command when StackManager.uninstall_stack returns False."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.uninstall_stack.return_value = False
    
    result = runner.invoke(app, ["uninstall"])
    assert result.exit_code == 1  # Should exit with error code
    mock_app_context.stack_manager.uninstall_stack.assert_called_once_with(
        remove_volumes=False,
        remove_config=False, 
        force=False
    )

@patch('ollama_stack_cli.main.AppContext')
def test_uninstall_command_stack_manager_exception(MockAppContext, mock_app_context):
    """Tests uninstall command when StackManager.uninstall_stack raises an exception."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.uninstall_stack.side_effect = Exception("Docker daemon not running")
    
    result = runner.invoke(app, ["uninstall"])
    assert result.exit_code == 1  # Should exit with error code
    mock_app_context.stack_manager.uninstall_stack.assert_called_once()

@patch('ollama_stack_cli.main.AppContext')
def test_uninstall_command_missing_app_context(MockAppContext):
    """Tests uninstall command when AppContext is None (edge case)."""
    MockAppContext.return_value = None
    
    result = runner.invoke(app, ["uninstall"])
    assert result.exit_code == 1  # Should fail gracefully

@patch('ollama_stack_cli.main.AppContext')
def test_uninstall_command_stack_manager_failure_with_flags(MockAppContext, mock_app_context):
    """Tests that failure handling works correctly with various flag combinations."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.uninstall_stack.return_value = False
    
    # Test failure with different flag combinations
    test_cases = [
        ["--remove-volumes"],
        ["--remove-config"],
        ["--all"],
        ["--force"],
        ["--remove-volumes", "--remove-config", "--force"]
    ]
    
    for command_args in test_cases:
        mock_app_context.stack_manager.uninstall_stack.reset_mock()
        
        result = runner.invoke(app, ["uninstall"] + command_args)
        assert result.exit_code == 1, f"Should fail with args: {command_args}"
        mock_app_context.stack_manager.uninstall_stack.assert_called_once()


# --- Edge Cases and Complex Scenarios ---

@patch('ollama_stack_cli.main.AppContext')
def test_uninstall_logic_all_flag_processing(MockAppContext, mock_app_context):
    """Tests the specific logic in uninstall_logic for --all flag processing."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.uninstall_stack.return_value = True
    
    # Test that --all flag correctly modifies the remove_volumes and remove_config flags
    # even when they start as False
    result = runner.invoke(app, ["uninstall", "--all"])
    assert result.exit_code == 0
    
    # Verify that the call to uninstall_stack has both flags set to True
    call_args = mock_app_context.stack_manager.uninstall_stack.call_args
    assert call_args.kwargs['remove_volumes'] == True
    assert call_args.kwargs['remove_config'] == True
    assert call_args.kwargs['force'] == False

@patch('ollama_stack_cli.commands.uninstall.log')
@patch('ollama_stack_cli.main.AppContext')
def test_uninstall_logic_all_flag_logging(MockAppContext, mock_log, mock_app_context):
    """Tests that --all flag logs the debug message correctly."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.uninstall_stack.return_value = True
    
    result = runner.invoke(app, ["uninstall", "--all"])
    assert result.exit_code == 0
    
    # Verify debug log message was called
    mock_log.debug.assert_called_with("--all flag enabled: setting remove_volumes=True, remove_config=True")

@patch('ollama_stack_cli.main.AppContext')
def test_uninstall_command_parameter_isolation(MockAppContext, mock_app_context):
    """Tests that parameters are properly isolated between multiple command invocations."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.uninstall_stack.return_value = True
    
    # First call with --all
    result1 = runner.invoke(app, ["uninstall", "--all"])
    assert result1.exit_code == 0
    
    # Second call with no flags - should not be affected by previous call
    result2 = runner.invoke(app, ["uninstall"])
    assert result2.exit_code == 0
    
    # Verify the second call has the correct default parameters
    last_call_args = mock_app_context.stack_manager.uninstall_stack.call_args
    assert last_call_args.kwargs['remove_volumes'] == False
    assert last_call_args.kwargs['remove_config'] == False
    assert last_call_args.kwargs['force'] == False

@patch('ollama_stack_cli.main.AppContext')
def test_uninstall_command_context_object_access(MockAppContext, mock_app_context):
    """Tests that the command correctly accesses the AppContext from ctx.obj."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.uninstall_stack.return_value = True
    
    result = runner.invoke(app, ["uninstall"])
    assert result.exit_code == 0
    
    # Verify that AppContext was accessed and uninstall_stack was called on it
    mock_app_context.stack_manager.uninstall_stack.assert_called_once()

@patch('ollama_stack_cli.main.AppContext')
def test_uninstall_command_boolean_flag_handling(MockAppContext, mock_app_context):
    """Tests that boolean flags are handled correctly (not as string values)."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.uninstall_stack.return_value = True
    
    result = runner.invoke(app, ["uninstall", "--remove-volumes", "--force"])
    assert result.exit_code == 0
    
    # Verify that boolean values are passed, not strings
    call_args = mock_app_context.stack_manager.uninstall_stack.call_args
    assert call_args.kwargs['remove_volumes'] is True  # Boolean True, not string
    assert call_args.kwargs['remove_config'] is False  # Boolean False, not string
    assert call_args.kwargs['force'] is True  # Boolean True, not string

@patch('ollama_stack_cli.main.AppContext')
def test_uninstall_command_help_text_accessibility(MockAppContext, mock_app_context):
    """Tests that help text is accessible and command is properly registered."""
    # Test that help can be accessed without errors
    result = runner.invoke(app, ["uninstall", "--help"])
    assert result.exit_code == 0
    assert "Clean up all stack resources" in result.output
    assert "--remove-volumes" in result.output
    assert "--remove-config" in result.output
    assert "--all" in result.output
    assert "--force" in result.output

@patch('ollama_stack_cli.main.AppContext')
def test_uninstall_command_comprehensive_error_scenarios(MockAppContext, mock_app_context):
    """Tests various error scenarios with different flag combinations."""
    MockAppContext.return_value = mock_app_context
    
    error_scenarios = [
        # (exception_type, error_message, command_args)
        (RuntimeError, "Docker daemon not running", []),
        (ConnectionError, "Network error", ["--remove-volumes"]),
        (PermissionError, "Permission denied", ["--remove-config"]),
        (ValueError, "Invalid configuration", ["--all"]),
        (OSError, "Filesystem error", ["--force"]),
    ]
    
    for exception_type, error_message, command_args in error_scenarios:
        mock_app_context.stack_manager.uninstall_stack.reset_mock()
        mock_app_context.stack_manager.uninstall_stack.side_effect = exception_type(error_message)
        
        result = runner.invoke(app, ["uninstall"] + command_args)
        assert result.exit_code == 1, f"Should fail for {exception_type.__name__} with args {command_args}"
        mock_app_context.stack_manager.uninstall_stack.assert_called_once()

@patch('ollama_stack_cli.main.AppContext')
def test_uninstall_command_return_value_consistency(MockAppContext, mock_app_context):
    """Tests that command return behavior is consistent across success and failure cases."""
    MockAppContext.return_value = mock_app_context
    
    # Test success case
    mock_app_context.stack_manager.uninstall_stack.return_value = True
    result = runner.invoke(app, ["uninstall"])
    assert result.exit_code == 0
    
    # Test failure case  
    mock_app_context.stack_manager.uninstall_stack.return_value = False
    result = runner.invoke(app, ["uninstall"])
    assert result.exit_code == 1
    
    # Test exception case
    mock_app_context.stack_manager.uninstall_stack.side_effect = Exception("Test error")
    result = runner.invoke(app, ["uninstall"])
    assert result.exit_code == 1 