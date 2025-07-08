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

def test_backup_stack_logic_success_all_defaults(mock_app_context):
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
    
    # Verify display panel was called
    mock_app_context.display.panel.assert_called_once()
    panel_call = mock_app_context.display.panel.call_args[0][0]
    assert "✅ Backup Created Successfully" in panel_call
    assert "ollama-stack restore" in panel_call

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

def test_backup_stack_logic_with_description(mock_app_context):
    """Test backup with description."""
    mock_app_context.stack_manager.create_backup.return_value = True
    
    description = "Before major update"
    result = backup_stack_logic(mock_app_context, description=description)
    
    assert result == True
    
    # Verify description is shown in display panel
    panel_call = mock_app_context.display.panel.call_args[0][0]
    assert f"📝 Description: {description}" in panel_call

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

def test_backup_stack_logic_no_items_selected(mock_app_context):
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

@patch('ollama_stack_cli.commands.backup.typer.confirm')
def test_backup_stack_logic_existing_directory_user_cancels(mock_confirm, mock_app_context):
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

def test_backup_stack_logic_stack_manager_failure(mock_app_context):
    """Test backup failure when StackManager.create_backup() returns False."""
    mock_app_context.stack_manager.create_backup.return_value = False
    
    result = backup_stack_logic(mock_app_context)
    
    # Should fail
    assert result == False
    
    # Display panel should not be called on failure
    mock_app_context.display.panel.assert_not_called()

def test_backup_stack_logic_stack_manager_exception(mock_app_context):
    """Test backup failure when StackManager.create_backup() raises exception."""
    mock_app_context.stack_manager.create_backup.side_effect = Exception("Disk full")
    
    result = backup_stack_logic(mock_app_context)
    
    # Should fail gracefully
    assert result == False
    
    # Display panel should not be called on failure
    mock_app_context.display.panel.assert_not_called()


# =============================================================================
# backup_stack_logic() Tests - Edge Cases
# =============================================================================

def test_backup_stack_logic_relative_path_resolution(mock_app_context):
    """Test that relative paths are properly resolved to absolute paths."""
    mock_app_context.stack_manager.create_backup.return_value = True
    
    result = backup_stack_logic(mock_app_context, output_path="./relative/backup")
    
    assert result == True
    
    # Verify path was resolved to absolute
    call_args = mock_app_context.stack_manager.create_backup.call_args
    backup_dir = call_args[1]['backup_dir']
    assert backup_dir.is_absolute()

def test_backup_stack_logic_empty_description(mock_app_context):
    """Test backup with empty description."""
    mock_app_context.stack_manager.create_backup.return_value = True
    
    result = backup_stack_logic(mock_app_context, description="")
    
    assert result == True
    
    # Empty description should not appear in panel
    panel_call = mock_app_context.display.panel.call_args[0][0]
    assert "📝 Description:" not in panel_call

def test_backup_stack_logic_whitespace_description(mock_app_context):
    """Test backup with whitespace-only description."""
    mock_app_context.stack_manager.create_backup.return_value = True
    
    result = backup_stack_logic(mock_app_context, description="   ")
    
    assert result == True
    
    # Whitespace description should appear in panel
    panel_call = mock_app_context.display.panel.call_args[0][0]
    assert "📝 Description:    " in panel_call

def test_backup_stack_logic_long_description(mock_app_context):
    """Test backup with very long description."""
    mock_app_context.stack_manager.create_backup.return_value = True
    
    long_description = "A" * 500  # 500 character description
    result = backup_stack_logic(mock_app_context, description=long_description)
    
    assert result == True
    
    # Long description should be handled without issues
    panel_call = mock_app_context.display.panel.call_args[0][0]
    assert long_description in panel_call

def test_backup_stack_logic_special_characters_in_path(mock_app_context):
    """Test backup with special characters in output path."""
    mock_app_context.stack_manager.create_backup.return_value = True
    
    special_path = "/tmp/backup with spaces & symbols!@#"
    result = backup_stack_logic(mock_app_context, output_path=special_path)
    
    assert result == True
    
    # Path with special characters should be handled
    call_args = mock_app_context.stack_manager.create_backup.call_args
    backup_dir = call_args[1]['backup_dir']
    assert special_path in str(backup_dir)

@patch('ollama_stack_cli.commands.backup.datetime')
def test_backup_stack_logic_timestamp_format(mock_datetime, mock_app_context):
    """Test that default backup directory uses correct timestamp format."""
    mock_app_context.stack_manager.create_backup.return_value = True
    mock_datetime.datetime.now.return_value.strftime.return_value = "20240315-143022"
    
    result = backup_stack_logic(mock_app_context)
    
    assert result == True
    
    # Verify timestamp format is used correctly
    mock_datetime.datetime.now.assert_called_once()
    mock_datetime.datetime.now.return_value.strftime.assert_called_once_with("%Y%m%d-%H%M%S")


# =============================================================================
# backup() Command Tests - Integration
# =============================================================================

def test_backup_command_success(mock_typer_context):
    """Test successful backup command execution."""
    mock_typer_context.obj.stack_manager.create_backup.return_value = True
    
    with patch('ollama_stack_cli.commands.backup.datetime') as mock_datetime:
        mock_datetime.datetime.now.return_value.strftime.return_value = "20240101-120000"
        
        # Should not raise exception
        backup(mock_typer_context)
    
    # Verify StackManager was called
    mock_typer_context.obj.stack_manager.create_backup.assert_called_once()

def test_backup_command_failure_raises_exit(mock_typer_context):
    """Test that backup command raises Typer.Exit on failure."""
    mock_typer_context.obj.stack_manager.create_backup.return_value = False
    
    with pytest.raises(typer.Exit) as exc_info:
        backup(mock_typer_context)
    
    # Should exit with code 1
    assert exc_info.value.exit_code == 1

def test_backup_command_all_parameters(mock_typer_context):
    """Test backup command with all parameters specified."""
    mock_typer_context.obj.stack_manager.create_backup.return_value = True
    
    # Call with all parameters
    backup(
        ctx=mock_typer_context,
        include_volumes=False,
        include_config=True,
        include_extensions=False,
        output="/custom/backup",
        compress=False,
        description="Test backup"
    )
    
    # Verify delegation to business logic
    mock_typer_context.obj.stack_manager.create_backup.assert_called_once()
    
    # Verify parameters were passed through correctly
    call_args = mock_typer_context.obj.stack_manager.create_backup.call_args
    backup_config = call_args[1]['backup_config']
    assert backup_config['include_volumes'] == False
    assert backup_config['include_config'] == True
    assert backup_config['include_extensions'] == False
    assert backup_config['compression'] == False

def test_backup_command_default_parameters(mock_typer_context):
    """Test backup command with default parameters."""
    mock_typer_context.obj.stack_manager.create_backup.return_value = True
    
    # Call with defaults
    backup(mock_typer_context)
    
    # Verify defaults were applied
    call_args = mock_typer_context.obj.stack_manager.create_backup.call_args
    backup_config = call_args[1]['backup_config']
    assert backup_config['include_volumes'] == True
    assert backup_config['include_config'] == True
    assert backup_config['include_extensions'] == True
    assert backup_config['compression'] == True


# =============================================================================
# Logging and Display Tests
# =============================================================================

@patch('ollama_stack_cli.commands.backup.log')
def test_backup_logging_messages(mock_log, mock_app_context):
    """Test that appropriate logging messages are generated."""
    mock_app_context.stack_manager.create_backup.return_value = True
    
    description = "Test backup"
    backup_stack_logic(
        mock_app_context,
        include_volumes=True,
        include_config=False,
        include_extensions=True,
        output_path="/test/backup",
        description=description
    )
    
    # Verify key logging calls
    assert any("Creating backup in:" in str(call) for call in mock_log.info.call_args_list)
    assert any("Backup description:" in str(call) for call in mock_log.info.call_args_list)
    assert any("Backup will include:" in str(call) for call in mock_log.info.call_args_list)
    assert any("Starting backup process..." in str(call) for call in mock_log.info.call_args_list)
    assert any("Backup completed successfully!" in str(call) for call in mock_log.info.call_args_list)

@patch('ollama_stack_cli.commands.backup.log')
def test_backup_error_logging(mock_log, mock_app_context):
    """Test error logging scenarios."""
    
    # Test no items selected
    backup_stack_logic(
        mock_app_context,
        include_volumes=False,
        include_config=False,
        include_extensions=False
    )
    
    mock_log.error.assert_called_with("No backup items selected - nothing to backup")
    
    # Test StackManager failure
    mock_log.reset_mock()
    mock_app_context.stack_manager.create_backup.return_value = False
    
    backup_stack_logic(mock_app_context)
    
    mock_log.error.assert_called_with("Backup failed - check logs for details")
    
    # Test exception handling
    mock_log.reset_mock()
    mock_app_context.stack_manager.create_backup.side_effect = RuntimeError("Test error")
    
    backup_stack_logic(mock_app_context)
    
    mock_log.error.assert_called_with("Backup failed with error: Test error")

@patch('ollama_stack_cli.commands.backup.log')
@patch('ollama_stack_cli.commands.backup.typer.confirm')
def test_backup_warning_logging(mock_confirm, mock_log, mock_app_context):
    """Test warning logging for existing directories."""
    mock_confirm.return_value = True
    mock_app_context.stack_manager.create_backup.return_value = True
    
    with patch('pathlib.Path.exists', return_value=True):
        backup_stack_logic(mock_app_context, output_path="/existing")
    
    # Verify warning was logged
    assert any("Backup directory already exists:" in str(call) for call in mock_log.warning.call_args_list)

def test_backup_display_panel_content(mock_app_context):
    """Test display panel content formatting."""
    mock_app_context.stack_manager.create_backup.return_value = True
    
    backup_items = ["Docker volumes (models, conversations)", "Configuration files"]
    description = "Test backup description"
    
    backup_stack_logic(
        mock_app_context,
        include_volumes=True,
        include_config=True,
        include_extensions=False,
        compress=True,
        description=description
    )
    
    # Verify display panel was called with correct content
    mock_app_context.display.panel.assert_called_once()
    panel_content = mock_app_context.display.panel.call_args[0][0]
    
    # Check all expected content is present
    assert "✅ Backup Created Successfully" in panel_content
    assert "📁 Location:" in panel_content
    assert "📋 Includes:" in panel_content
    assert "🔒 Compressed: Yes" in panel_content
    assert f"📝 Description: {description}" in panel_content
    assert "💡 To restore this backup, run:" in panel_content
    assert "ollama-stack restore" in panel_content
    
    # Check border style
    assert mock_app_context.display.panel.call_args[1]['border_style'] == "green"

def test_backup_display_panel_no_compression(mock_app_context):
    """Test display panel with compression disabled."""
    mock_app_context.stack_manager.create_backup.return_value = True
    
    backup_stack_logic(mock_app_context, compress=False)
    
    panel_content = mock_app_context.display.panel.call_args[0][0]
    assert "🔒 Compressed: No" in panel_content


# =============================================================================
# Parameter Validation Tests
# =============================================================================

def test_backup_various_flag_combinations(mock_app_context):
    """Test various combinations of include flags."""
    mock_app_context.stack_manager.create_backup.return_value = True
    
    test_cases = [
        # (include_volumes, include_config, include_extensions, should_succeed)
        (True, True, True, True),    # All enabled
        (True, True, False, True),   # Volumes and config
        (True, False, True, True),   # Volumes and extensions
        (False, True, True, True),   # Config and extensions
        (True, False, False, True),  # Only volumes
        (False, True, False, True),  # Only config
        (False, False, True, True),  # Only extensions
        (False, False, False, False) # None (should fail)
    ]
    
    for include_volumes, include_config, include_extensions, should_succeed in test_cases:
        mock_app_context.stack_manager.create_backup.reset_mock()
        
        result = backup_stack_logic(
            mock_app_context,
            include_volumes=include_volumes,
            include_config=include_config,
            include_extensions=include_extensions
        )
        
        assert result == should_succeed
        
        if should_succeed:
            mock_app_context.stack_manager.create_backup.assert_called_once()
        else:
            mock_app_context.stack_manager.create_backup.assert_not_called()

def test_backup_path_types(mock_app_context):
    """Test different types of output paths."""
    mock_app_context.stack_manager.create_backup.return_value = True
    
    test_paths = [
        "/absolute/path",
        "relative/path", 
        "./current/relative",
        "../parent/relative",
        "~/home/relative",
        "/path/with spaces/backup",
        "/path-with-dashes_and_underscores/backup"
    ]
    
    for test_path in test_paths:
        mock_app_context.stack_manager.create_backup.reset_mock()
        
        result = backup_stack_logic(mock_app_context, output_path=test_path)
        
        assert result == True
        mock_app_context.stack_manager.create_backup.assert_called_once()
        
        # Verify path was processed
        call_args = mock_app_context.stack_manager.create_backup.call_args
        backup_dir = call_args[1]['backup_dir']
        assert isinstance(backup_dir, Path)

def test_backup_description_types(mock_app_context):
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
        mock_app_context.display.reset_mock()
        
        result = backup_stack_logic(mock_app_context, description=description)
        
        assert result == True
        mock_app_context.stack_manager.create_backup.assert_called_once()
        
        # Verify description handling in display
        if description and description.strip():
            panel_content = mock_app_context.display.panel.call_args[0][0]
            assert f"📝 Description: {description}" in panel_content