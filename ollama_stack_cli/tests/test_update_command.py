from typer.testing import CliRunner
from unittest.mock import MagicMock, patch
import pytest

from ollama_stack_cli.main import app

runner = CliRunner()


# --- Update Command Tests ---

@patch('ollama_stack_cli.main.AppContext')
def test_update_command_stack_not_running(MockAppContext, mock_app_context):
    """Tests that 'update' command works when stack is not running."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.is_stack_running.return_value = False
    mock_app_context.stack_manager.update_stack.return_value = True
    mock_app_context.config.app_config.version = "0.4.0"  # Mock version to avoid version transition
    
    result = runner.invoke(app, ["update"])
    assert result.exit_code == 0
    mock_app_context.stack_manager.is_stack_running.assert_called_once()
    mock_app_context.stack_manager.update_stack.assert_called_once_with(
        services_only=False, 
        extensions_only=False, 
        force_restart=False,
        called_from_start_restart=False
    )

@patch('typer.confirm')
@patch('ollama_stack_cli.main.AppContext')
def test_update_command_stack_running_confirm_yes(MockAppContext, mock_confirm):
    """Tests that 'update' command stops and restarts when stack is running and user confirms."""
    mock_app_context = MagicMock()
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.is_stack_running.return_value = True
    mock_app_context.stack_manager.update_stack.return_value = True
    mock_app_context.config.app_config.version = "0.4.0"  # Mock version to avoid version transition
    mock_confirm.return_value = True
    
    result = runner.invoke(app, ["update"])
    assert result.exit_code == 0
    mock_app_context.stack_manager.is_stack_running.assert_called_once()
    mock_confirm.assert_called_once()
    mock_app_context.stack_manager.update_stack.assert_called_once_with(
        services_only=False, 
        extensions_only=False, 
        force_restart=True,
        called_from_start_restart=False
    )

@patch('typer.confirm')
@patch('ollama_stack_cli.main.AppContext')
def test_update_command_stack_running_confirm_no(MockAppContext, mock_confirm):
    """Tests that 'update' command cancels when user declines to stop running stack."""
    mock_app_context = MagicMock()
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.is_stack_running.return_value = True
    mock_app_context.config.app_config.version = "0.4.0"  # Mock version to avoid version transition
    mock_confirm.return_value = False
    
    result = runner.invoke(app, ["update"])
    assert result.exit_code == 0  # User cancellation is normal, not an error
    mock_app_context.stack_manager.is_stack_running.assert_called_once()
    mock_confirm.assert_called_once()
    # Should not proceed with any other operations
    mock_app_context.stack_manager.update_stack.assert_not_called()

@patch('ollama_stack_cli.main.AppContext')
def test_update_command_services_only(MockAppContext, mock_app_context):
    """Tests that 'update --services' only updates core services."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.is_stack_running.return_value = False
    mock_app_context.stack_manager.update_stack.return_value = True
    mock_app_context.config.app_config.version = "0.4.0"  # Mock version to avoid version transition
    
    result = runner.invoke(app, ["update", "--services"])
    assert result.exit_code == 0
    mock_app_context.stack_manager.update_stack.assert_called_once_with(
        services_only=True, 
        extensions_only=False, 
        force_restart=False,
        called_from_start_restart=False
    )

@patch('ollama_stack_cli.main.AppContext')  
def test_update_command_extensions_only(MockAppContext, mock_app_context):
    """Tests that 'update --extensions' only updates enabled extensions."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.is_stack_running.return_value = False
    mock_app_context.stack_manager.update_stack.return_value = True
    mock_app_context.config.app_config.version = "0.4.0"  # Mock version to avoid version transition
    
    result = runner.invoke(app, ["update", "--extensions"])
    assert result.exit_code == 0
    mock_app_context.stack_manager.update_stack.assert_called_once_with(
        services_only=False, 
        extensions_only=True, 
        force_restart=False,
        called_from_start_restart=False
    )

@patch('ollama_stack_cli.main.AppContext')
def test_update_command_conflicting_flags(MockAppContext, mock_app_context):
    """Tests that 'update --services --extensions' fails with error."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.is_stack_running.return_value = False
    mock_app_context.config.app_config.version = "0.4.0"  # Mock version to avoid version transition
    
    result = runner.invoke(app, ["update", "--services", "--extensions"])
    assert result.exit_code == 2  # Conflicting flags validation error
    # Should not proceed with any other operations due to early validation
    mock_app_context.stack_manager.update_stack.assert_not_called()

@patch('ollama_stack_cli.main.AppContext')
def test_update_command_with_enabled_extensions(MockAppContext, mock_app_context):
    """Tests that update command handles enabled extensions correctly."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.is_stack_running.return_value = False
    mock_app_context.stack_manager.update_stack.return_value = True
    mock_app_context.config.app_config.version = "0.4.0"  # Mock version to avoid version transition
    
    result = runner.invoke(app, ["update"])
    assert result.exit_code == 0
    mock_app_context.stack_manager.update_stack.assert_called_once_with(
        services_only=False, 
        extensions_only=False, 
        force_restart=False,
        called_from_start_restart=False
    )

@patch('ollama_stack_cli.main.AppContext')
def test_update_command_update_stack_failure(MockAppContext, mock_app_context):
    """Tests that update command handles update_stack failure gracefully."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.is_stack_running.return_value = False
    mock_app_context.stack_manager.update_stack.return_value = False
    mock_app_context.config.app_config.version = "0.4.0"  # Mock version to avoid version transition
    
    result = runner.invoke(app, ["update"])
    assert result.exit_code == 1
    mock_app_context.stack_manager.update_stack.assert_called_once_with(
        services_only=False, 
        extensions_only=False, 
        force_restart=False,
        called_from_start_restart=False
    )

@patch('typer.confirm')
@patch('ollama_stack_cli.main.AppContext')
def test_update_command_confirmation_exception(MockAppContext, mock_confirm, mock_app_context):
    """Tests update command handles exceptions from typer.confirm gracefully."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.is_stack_running.return_value = True
    mock_app_context.config.app_config.version = "0.4.0"  # Mock version to avoid version transition
    mock_confirm.side_effect = KeyboardInterrupt("User interrupted")
    
    result = runner.invoke(app, ["update"])
    assert result.exit_code == 130  # KeyboardInterrupt results in exit code 130 (SIGINT)
    mock_confirm.assert_called_once()
    mock_app_context.stack_manager.update_stack.assert_not_called()

@patch('ollama_stack_cli.main.AppContext')
def test_update_command_stack_manager_exception(MockAppContext, mock_app_context):
    """Tests update command handles StackManager exceptions gracefully."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.is_stack_running.side_effect = Exception("Docker daemon not running")
    mock_app_context.config.app_config.version = "0.4.0"  # Mock version to avoid version transition
    
    result = runner.invoke(app, ["update"])
    assert result.exit_code == 1
    mock_app_context.stack_manager.is_stack_running.assert_called_once()
    mock_app_context.stack_manager.update_stack.assert_not_called()

@patch('ollama_stack_cli.main.AppContext')
def test_update_command_integration_with_stack_manager_flags(MockAppContext, mock_app_context):
    """Tests that update command properly delegates all flag combinations to StackManager."""
    MockAppContext.return_value = mock_app_context
    mock_app_context.stack_manager.is_stack_running.return_value = False
    mock_app_context.stack_manager.update_stack.return_value = True
    mock_app_context.config.app_config.version = "0.4.0"  # Mock version to avoid version transition
    
    # Test all flag combinations
    test_cases = [
        ([], {"services_only": False, "extensions_only": False, "force_restart": False, "called_from_start_restart": False}),
        (["--services"], {"services_only": True, "extensions_only": False, "force_restart": False, "called_from_start_restart": False}),
        (["--extensions"], {"services_only": False, "extensions_only": True, "force_restart": False, "called_from_start_restart": False}),
    ]
    
    for flags, expected_kwargs in test_cases:
        mock_app_context.stack_manager.update_stack.reset_mock()
        result = runner.invoke(app, ["update"] + flags)
        assert result.exit_code == 0
        mock_app_context.stack_manager.update_stack.assert_called_once_with(**expected_kwargs) 