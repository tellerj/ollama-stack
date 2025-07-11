"""
Unit tests for the backup command implementation.

Tests cover backup_stack_logic() business logic and the backup() command interface,
including happy paths, error scenarios, user interactions, and edge cases.
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, call
from datetime import datetime
import typer

from ollama_stack_cli.commands.backup import backup_stack_logic, backup
from ollama_stack_cli.context import AppContext


@pytest.fixture
def mock_app_context():
    """Create a mock AppContext for testing."""
    mock_context = MagicMock(spec=AppContext)
    mock_context.stack_manager = MagicMock()
    mock_context.display = MagicMock()
    return mock_context


@pytest.fixture
def mock_typer_context(mock_app_context):
    """Create a mock Typer context with AppContext."""
    mock_ctx = MagicMock()
    mock_ctx.obj = mock_app_context
    return mock_ctx


# =============================================================================
# backup_stack_logic() Tests - Happy Path
# =============================================================================

@patch('ollama_stack_cli.commands.backup.log')
def test_backup_stack_logic_success_all_defaults(mock_log, mock_app_context):
    """Test successful backup with all default options."""
    # Mock successful backup creation
    mock_app_context.stack_manager.create_backup.return_value = True
    
    with patch('ollama_stack_cli.commands.backup.datetime') as mock_datetime:
        mock_datetime.datetime.now.return_value.strftime.return_value = "20240101-120000"
        
        result = backup_stack_logic(mock_app_context)
    
    # Should succeed
    assert result == True
    
    # Verify StackManager was called with correct parameters
    mock_app_context.stack_manager.create_backup.assert_called_once()
    call_args = mock_app_context.stack_manager.create_backup.call_args
    
    # Check backup directory path
    backup_dir = call_args[1]['backup_dir']
    assert "backup-20240101-120000" in str(backup_dir)
    assert ".ollama-stack/backups" in str(backup_dir)
    
    # Check backup config
    backup_config = call_args[1]['backup_config']
    assert backup_config['include_volumes'] == True
    assert backup_config['include_config'] == True
    assert backup_config['include_extensions'] == True
    assert backup_config['compression'] == True
    
    # Verify logging was called for success and backup information
    mock_log.info.assert_any_call("Backup completed successfully!")
    # Check that backup details are logged
    logged_calls = [call.args[0] for call in mock_log.info.call_args_list]
    assert any("Location:" in call for call in logged_calls)
    assert any("ollama-stack restore" in call for call in logged_calls)

def test_backup_stack_logic_custom_output_path(mock_app_context):
    """Test backup with custom output path."""
    mock_app_context.stack_manager.create_backup.return_value = True
    
    custom_path = "/tmp/my-custom-backup"
    result = backup_stack_logic(mock_app_context, output_path=custom_path)
    
    assert result == True
    
    # Verify custom path was used (resolve paths to handle macOS /tmp -> /private/tmp)
    call_args = mock_app_context.stack_manager.create_backup.call_args
    backup_dir = call_args[1]['backup_dir']
    assert str(backup_dir.resolve()) == str(Path(custom_path).resolve())

@patch('ollama_stack_cli.commands.backup.log')
def test_backup_stack_logic_with_description(mock_log, mock_app_context):
    """Test backup with description."""
    mock_app_context.stack_manager.create_backup.return_value = True
    
    description = "Before major update"
    result = backup_stack_logic(mock_app_context, description=description)
    
    assert result == True
    
    # Verify description is logged
    mock_log.info.assert_any_call(f"Backup description: {description}")
    mock_log.info.assert_any_call(f"Description: {description}")

def test_backup_stack_logic_selective_backup_options(mock_app_context):
    """Test backup with selective options."""
    mock_app_context.stack_manager.create_backup.return_value = True
    
    # Test volumes only
    result = backup_stack_logic(
        mock_app_context,
        include_volumes=True,
        include_config=False,
        include_extensions=False,
        compress=False
    )
    
    assert result == True
    
    # Verify backup config
    call_args = mock_app_context.stack_manager.create_backup.call_args
    backup_config = call_args[1]['backup_config']
    assert backup_config['include_volumes'] == True
    assert backup_config['include_config'] == False
    assert backup_config['include_extensions'] == False
    assert backup_config['compression'] == False

def test_backup_stack_logic_expanduser_path(mock_app_context):
    """Test that output path properly expands user home directory."""
    mock_app_context.stack_manager.create_backup.return_value = True
    
    result = backup_stack_logic(mock_app_context, output_path="~/my-backup")
    
    assert result == True
    
    # Verify path expansion
    call_args = mock_app_context.stack_manager.create_backup.call_args
    backup_dir = call_args[1]['backup_dir']
    assert "~" not in str(backup_dir)  # Should be expanded


# =============================================================================
# backup_stack_logic() Tests - Error Cases
# =============================================================================

@patch('ollama_stack_cli.commands.backup.log')
def test_backup_stack_logic_no_items_selected(mock_log, mock_app_context):
    """Test backup failure when no items are selected."""
    result = backup_stack_logic(
        mock_app_context,
        include_volumes=False,
        include_config=False,
        include_extensions=False
    )
    
    # Should fail
    assert result == False
    
    # StackManager should not be called
    mock_app_context.stack_manager.create_backup.assert_not_called()
    
    # Should log error
    mock_log.error.assert_called_with("No backup items selected - nothing to backup")

@patch('ollama_stack_cli.commands.backup.typer.confirm')
@patch('ollama_stack_cli.commands.backup.log')
def test_backup_stack_logic_existing_directory_user_cancels(mock_log, mock_confirm, mock_app_context):
    """Test backup cancellation when directory exists and user declines overwrite."""
    mock_confirm.return_value = False
    
    with patch('pathlib.Path.exists', return_value=True):
        result = backup_stack_logic(mock_app_context, output_path="/existing/path")
    
    # Should fail due to user cancellation
    assert result == False
    
    # Verify user was prompted
    mock_confirm.assert_called_once_with("Do you want to overwrite the existing backup?")
    
    # StackManager should not be called
    mock_app_context.stack_manager.create_backup.assert_not_called()
    
    # Should log cancellation
    mock_log.info.assert_called_with("Backup cancelled by user")

@patch('ollama_stack_cli.commands.backup.typer.confirm')
def test_backup_stack_logic_existing_directory_user_confirms(mock_confirm, mock_app_context):
    """Test backup continuation when directory exists and user confirms overwrite."""
    mock_confirm.return_value = True
    mock_app_context.stack_manager.create_backup.return_value = True
    
    with patch('pathlib.Path.exists', return_value=True):
        result = backup_stack_logic(mock_app_context, output_path="/existing/path")
    
    # Should succeed
    assert result == True
    
    # Verify user was prompted and StackManager was called
    mock_confirm.assert_called_once()
    mock_app_context.stack_manager.create_backup.assert_called_once()

@patch('ollama_stack_cli.commands.backup.log')
def test_backup_stack_logic_stack_manager_failure(mock_log, mock_app_context):
    """Test backup failure when StackManager.create_backup() returns False."""
    mock_app_context.stack_manager.create_backup.return_value = False
    
    result = backup_stack_logic(mock_app_context)
    
    # Should fail
    assert result == False
    
    # Should log error
    mock_log.error.assert_called_with("Backup failed - check logs for details")

@patch('ollama_stack_cli.commands.backup.log')
def test_backup_stack_logic_stack_manager_exception(mock_log, mock_app_context):
    """Test backup failure when StackManager.create_backup() raises exception."""
    mock_app_context.stack_manager.create_backup.side_effect = Exception("Test error")
    
    result = backup_stack_logic(mock_app_context)
    
    # Should fail
    assert result == False
    
    # Should log exception
    mock_log.error.assert_called_with("Backup failed with error: Test error")

def test_backup_stack_logic_relative_path_resolution(mock_app_context):
    """Test that relative paths are properly resolved."""
    mock_app_context.stack_manager.create_backup.return_value = True
    
    result = backup_stack_logic(mock_app_context, output_path="./relative/path")
    
    assert result == True
    
    # Verify path resolution
    call_args = mock_app_context.stack_manager.create_backup.call_args
    backup_dir = call_args[1]['backup_dir']
    assert backup_dir.is_absolute()

@patch('ollama_stack_cli.commands.backup.log')
def test_backup_stack_logic_empty_description(mock_log, mock_app_context):
    """Test backup with empty description."""
    mock_app_context.stack_manager.create_backup.return_value = True
    
    result = backup_stack_logic(mock_app_context, description="")
    
    assert result == True
    
    # Empty description should not be logged
    description_calls = [call for call in mock_log.info.call_args_list if "Description:" in str(call)]
    assert len(description_calls) == 0

@patch('ollama_stack_cli.commands.backup.log')
def test_backup_stack_logic_whitespace_description(mock_log, mock_app_context):
    """Test backup with whitespace-only description."""
    mock_app_context.stack_manager.create_backup.return_value = True
    
    result = backup_stack_logic(mock_app_context, description="   ")
    
    assert result == True
    
    # Whitespace description should be logged as-is
    mock_log.info.assert_any_call("Description:    ")

@patch('ollama_stack_cli.commands.backup.log')
def test_backup_stack_logic_long_description(mock_log, mock_app_context):
    """Test backup with very long description."""
    mock_app_context.stack_manager.create_backup.return_value = True
    
    long_description = "A" * 500  # 500 character description
    result = backup_stack_logic(mock_app_context, description=long_description)
    
    assert result == True
    
    # Long description should be logged without issues
    mock_log.info.assert_any_call(f"Description: {long_description}")

def test_backup_stack_logic_special_characters_in_path(mock_app_context):
    """Test backup with special characters in path."""
    mock_app_context.stack_manager.create_backup.return_value = True
    
    special_path = "/path/with spaces/and-dashes/backup_2024"
    result = backup_stack_logic(mock_app_context, output_path=special_path)
    
    assert result == True
    
    # Verify special characters are handled correctly
    call_args = mock_app_context.stack_manager.create_backup.call_args
    backup_dir = call_args[1]['backup_dir']
    assert str(backup_dir) == str(Path(special_path).expanduser().resolve())

@patch('ollama_stack_cli.commands.backup.datetime')
def test_backup_stack_logic_timestamp_format(mock_datetime, mock_app_context):
    """Test that timestamp format is correct."""
    mock_app_context.stack_manager.create_backup.return_value = True
    mock_datetime.datetime.now.return_value.strftime.return_value = "20241025-143022"
    
    result = backup_stack_logic(mock_app_context)
    
    assert result == True
    
    # Verify timestamp format call
    mock_datetime.datetime.now.return_value.strftime.assert_called_with("%Y%m%d-%H%M%S")
    
    # Verify timestamp in path
    call_args = mock_app_context.stack_manager.create_backup.call_args
    backup_dir = call_args[1]['backup_dir']
    assert "backup-20241025-143022" in str(backup_dir)


# =============================================================================
# backup() Command Interface Tests
# =============================================================================

def test_backup_command_success(mock_typer_context):
    """Test backup command success."""
    with patch('ollama_stack_cli.commands.backup.backup_stack_logic', return_value=True) as mock_logic:
        backup(mock_typer_context, include_volumes=True)
        
        mock_logic.assert_called_once_with(
            app_context=mock_typer_context.obj,
            include_volumes=True,
            include_config=True,
            include_extensions=True,
            output_path=None,
            compress=True,
            description=None
        )

def test_backup_command_failure_raises_exit(mock_typer_context):
    """Test backup command failure raises typer.Exit."""
    with patch('ollama_stack_cli.commands.backup.backup_stack_logic', return_value=False):
        with pytest.raises(typer.Exit) as exc_info:
            backup(mock_typer_context)
        
        assert exc_info.value.exit_code == 1

def test_backup_command_all_parameters(mock_typer_context):
    """Test backup command with all parameters specified."""
    with patch('ollama_stack_cli.commands.backup.backup_stack_logic', return_value=True) as mock_logic:
        backup(
            ctx=mock_typer_context,
            include_volumes=False,
            include_config=False,
            include_extensions=False,
            output="/custom/path",
            compress=False,
            description="Test backup"
        )
        
        mock_logic.assert_called_once_with(
            app_context=mock_typer_context.obj,
            include_volumes=False,
            include_config=False,
            include_extensions=False,
            output_path="/custom/path",
            compress=False,
            description="Test backup"
        )

def test_backup_command_default_parameters(mock_typer_context):
    """Test backup command with default parameters."""
    with patch('ollama_stack_cli.commands.backup.backup_stack_logic', return_value=True) as mock_logic:
        backup(ctx=mock_typer_context)
        
        mock_logic.assert_called_once_with(
            app_context=mock_typer_context.obj,
            include_volumes=True,
            include_config=True,
            include_extensions=True,
            output_path=None,
            compress=True,
            description=None
        )


# =============================================================================
# Logging Tests
# =============================================================================

@patch('ollama_stack_cli.commands.backup.log')
def test_backup_logging_messages(mock_log, mock_app_context):
    """Test that appropriate logging messages are called."""
    mock_app_context.stack_manager.create_backup.return_value = True
    
    result = backup_stack_logic(
        mock_app_context,
        include_volumes=True,
        include_config=True,
        include_extensions=False,
        description="Test backup"
    )
    
    assert result == True
    
    # Verify key logging calls
    mock_log.info.assert_any_call("Backup description: Test backup")
    mock_log.info.assert_any_call("Backup will include: Docker volumes (models, conversations), Configuration files")
    mock_log.info.assert_any_call("Starting backup process...")
    mock_log.info.assert_any_call("Backup completed successfully!")

@patch('ollama_stack_cli.commands.backup.log')
def test_backup_error_logging(mock_log, mock_app_context):
    """Test error logging scenarios."""
    # Test no items selected
    result = backup_stack_logic(
        mock_app_context,
        include_volumes=False,
        include_config=False,
        include_extensions=False
    )
    
    assert result == False
    mock_log.error.assert_called_with("No backup items selected - nothing to backup")
    
    # Reset mock
    mock_log.reset_mock()
    
    # Test StackManager failure
    mock_app_context.stack_manager.create_backup.return_value = False
    result = backup_stack_logic(mock_app_context)
    
    assert result == False
    mock_log.error.assert_called_with("Backup failed - check logs for details")

@patch('ollama_stack_cli.commands.backup.log')
@patch('ollama_stack_cli.commands.backup.typer.confirm')
def test_backup_warning_logging(mock_confirm, mock_log, mock_app_context):
    """Test warning logging for existing directory."""
    mock_confirm.return_value = False
    
    with patch('pathlib.Path.exists', return_value=True):
        result = backup_stack_logic(mock_app_context, output_path="/existing/path")
    
    assert result == False
    mock_log.warning.assert_called()  # Should warn about existing directory


# =============================================================================
# Content and Format Tests
# =============================================================================

@patch('ollama_stack_cli.commands.backup.log')
def test_backup_logging_content(mock_log, mock_app_context):
    """Test logging content formatting."""
    mock_app_context.stack_manager.create_backup.return_value = True
    
    backup_items = ["Docker volumes (models, conversations)", "Configuration files"]
    description = "Test backup description"
    
    with patch('ollama_stack_cli.commands.backup.datetime') as mock_datetime:
        mock_datetime.datetime.now.return_value.strftime.return_value = "20240101-120000"
        
        backup_stack_logic(
            mock_app_context,
            include_volumes=True,
            include_config=True,
            include_extensions=False,
            compress=True,
            description=description
        )
    
    # Verify logging content
    logged_calls = [call.args[0] for call in mock_log.info.call_args_list]
    
    # Check for key information
    assert any("Backup description: Test backup description" in call for call in logged_calls)
    assert any("Backup will include: Docker volumes (models, conversations), Configuration files" in call for call in logged_calls)
    assert any("Compressed: Yes" in call for call in logged_calls)
    assert any("ollama-stack restore" in call for call in logged_calls)

@patch('ollama_stack_cli.commands.backup.log')
def test_backup_logging_no_compression(mock_log, mock_app_context):
    """Test logging with compression disabled."""
    mock_app_context.stack_manager.create_backup.return_value = True
    
    backup_stack_logic(mock_app_context, compress=False)
    
    logged_calls = [call.args[0] for call in mock_log.info.call_args_list]
    assert any("Compressed: No" in call for call in logged_calls)

def test_backup_various_flag_combinations(mock_app_context):
    """Test various combinations of backup flags."""
    mock_app_context.stack_manager.create_backup.return_value = True
    
    test_cases = [
        # (volumes, config, extensions, expected_count)
        (True, True, True, 3),      # All items
        (True, False, False, 1),    # Volumes only
        (False, True, False, 1),    # Config only
        (False, False, True, 1),    # Extensions only
        (True, True, False, 2),     # Volumes + config
        (True, False, True, 2),     # Volumes + extensions
        (False, True, True, 2),     # Config + extensions
    ]
    
    for volumes, config, extensions, expected_count in test_cases:
        mock_app_context.stack_manager.create_backup.reset_mock()
        
        result = backup_stack_logic(
            mock_app_context,
            include_volumes=volumes,
            include_config=config,
            include_extensions=extensions
        )
        
        assert result == True
        
        # Verify backup config
        call_args = mock_app_context.stack_manager.create_backup.call_args
        backup_config = call_args[1]['backup_config']
        assert backup_config['include_volumes'] == volumes
        assert backup_config['include_config'] == config
        assert backup_config['include_extensions'] == extensions

def test_backup_path_types(mock_app_context):
    """Test different types of backup paths."""
    mock_app_context.stack_manager.create_backup.return_value = True
    
    test_paths = [
        "/absolute/path",
        "./relative/path",
        "~/home/path",
        "../parent/path",
        "simple_name",
    ]
    
    for test_path in test_paths:
        mock_app_context.stack_manager.create_backup.reset_mock()
        
        result = backup_stack_logic(mock_app_context, output_path=test_path)
        
        assert result == True
        
        # Verify path is resolved and absolute
        call_args = mock_app_context.stack_manager.create_backup.call_args
        backup_dir = call_args[1]['backup_dir']
        assert backup_dir.is_absolute()

@patch('ollama_stack_cli.commands.backup.log')
def test_backup_description_types(mock_log, mock_app_context):
    """Test different types of descriptions."""
    mock_app_context.stack_manager.create_backup.return_value = True
    
    test_descriptions = [
        "Simple description",
        "Description with special chars: !@#$%^&*()",
        "Multi-line\ndescription\nwith newlines",
        "Very " + "long " * 100 + "description",
        "Unicode: 你好世界 🌍",
        "",  # Empty string
        "   ",  # Whitespace only
    ]
    
    for description in test_descriptions:
        mock_app_context.stack_manager.create_backup.reset_mock()
        mock_log.reset_mock()
        
        result = backup_stack_logic(mock_app_context, description=description)
        
        assert result == True
        mock_app_context.stack_manager.create_backup.assert_called_once()
        
        # Verify description handling in logging
        if description and description.strip():
            logged_calls = [call.args[0] for call in mock_log.info.call_args_list]
            assert any(f"Description: {description}" in call for call in logged_calls)