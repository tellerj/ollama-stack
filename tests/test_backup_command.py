"""
Unit tests for the backup command.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile
import datetime
import typer

from ollama_stack_cli.commands.backup import backup_stack_logic, backup
from ollama_stack_cli.context import AppContext
from ollama_stack_cli.config import Config
from ollama_stack_cli.display import Display
from ollama_stack_cli.stack_manager import StackManager


class TestBackupCommand:
    """Test cases for the backup command."""
    
    @pytest.fixture
    def mock_app_context(self):
        """Create a mock AppContext for testing."""
        context = Mock(spec=AppContext)
        context.config = Mock(spec=Config)
        context.display = Mock(spec=Display)
        context.stack_manager = Mock(spec=StackManager)
        return context
    
    @pytest.fixture
    def temp_backup_dir(self):
        """Create a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    def test_backup_stack_logic_default_settings(self, mock_app_context):
        """Test backup with default settings."""
        # Mock successful backup
        mock_app_context.stack_manager.create_backup.return_value = True
        
        # Mock datetime to get predictable backup directory name
        with patch('ollama_stack_cli.commands.backup.datetime') as mock_datetime:
            mock_datetime.datetime.now.return_value.strftime.return_value = "20240101-120000"
            
            result = backup_stack_logic(mock_app_context)
            
            assert result is True
            mock_app_context.stack_manager.create_backup.assert_called_once()
            
            # Check the backup directory path
            call_args = mock_app_context.stack_manager.create_backup.call_args
            backup_dir = call_args[1]['backup_dir']
            assert "backup-20240101-120000" in str(backup_dir)
    
    def test_backup_stack_logic_custom_output_path(self, mock_app_context, temp_backup_dir):
        """Test backup with custom output path."""
        mock_app_context.stack_manager.create_backup.return_value = True
        
        custom_path = str(temp_backup_dir / "custom-backup")
        result = backup_stack_logic(
            mock_app_context,
            output_path=custom_path
        )
        
        assert result is True
        mock_app_context.stack_manager.create_backup.assert_called_once()
        
        # Check the backup directory path (resolve both paths to handle macOS symlinks)
        call_args = mock_app_context.stack_manager.create_backup.call_args
        backup_dir = call_args[1]['backup_dir']
        assert Path(backup_dir).resolve() == Path(custom_path).resolve()
    
    def test_backup_stack_logic_selective_backup(self, mock_app_context):
        """Test backup with selective options."""
        mock_app_context.stack_manager.create_backup.return_value = True
        
        result = backup_stack_logic(
            mock_app_context,
            include_volumes=False,
            include_config=True,
            include_extensions=False,
            compress=False
        )
        
        assert result is True
        mock_app_context.stack_manager.create_backup.assert_called_once()
        
        # Check backup configuration
        call_args = mock_app_context.stack_manager.create_backup.call_args
        backup_config = call_args[1]['backup_config']
        assert backup_config['include_volumes'] is False
        assert backup_config['include_config'] is True
        assert backup_config['include_extensions'] is False
        assert backup_config['compression'] is False
    
    def test_backup_stack_logic_no_items_selected(self, mock_app_context):
        """Test backup when no items are selected."""
        result = backup_stack_logic(
            mock_app_context,
            include_volumes=False,
            include_config=False,
            include_extensions=False
        )
        
        assert result is False
        mock_app_context.stack_manager.create_backup.assert_not_called()
    
    def test_backup_stack_logic_with_description(self, mock_app_context):
        """Test backup with description."""
        mock_app_context.stack_manager.create_backup.return_value = True
        
        result = backup_stack_logic(
            mock_app_context,
            description="Test backup description"
        )
        
        assert result is True
        mock_app_context.stack_manager.create_backup.assert_called_once()
    
    def test_backup_stack_logic_existing_directory_confirm_yes(self, mock_app_context, temp_backup_dir):
        """Test backup when directory exists and user confirms overwrite."""
        mock_app_context.stack_manager.create_backup.return_value = True
        
        # Create existing directory
        existing_dir = temp_backup_dir / "existing-backup"
        existing_dir.mkdir()
        
        with patch('typer.confirm', return_value=True):
            result = backup_stack_logic(
                mock_app_context,
                output_path=str(existing_dir)
            )
        
        assert result is True
        mock_app_context.stack_manager.create_backup.assert_called_once()
    
    def test_backup_stack_logic_existing_directory_confirm_no(self, mock_app_context, temp_backup_dir):
        """Test backup when directory exists and user cancels."""
        # Create existing directory
        existing_dir = temp_backup_dir / "existing-backup"
        existing_dir.mkdir()
        
        with patch('typer.confirm', return_value=False):
            result = backup_stack_logic(
                mock_app_context,
                output_path=str(existing_dir)
            )
        
        assert result is False
        mock_app_context.stack_manager.create_backup.assert_not_called()
    
    def test_backup_stack_logic_stack_manager_failure(self, mock_app_context):
        """Test backup when stack manager fails."""
        mock_app_context.stack_manager.create_backup.return_value = False
        
        result = backup_stack_logic(mock_app_context)
        
        assert result is False
        mock_app_context.stack_manager.create_backup.assert_called_once()
    
    def test_backup_stack_logic_exception_handling(self, mock_app_context):
        """Test backup with exception handling."""
        mock_app_context.stack_manager.create_backup.side_effect = Exception("Test error")
        
        result = backup_stack_logic(mock_app_context)
        
        assert result is False
        mock_app_context.stack_manager.create_backup.assert_called_once()
    
    def test_backup_stack_logic_success_display(self, mock_app_context):
        """Test backup success display panel."""
        mock_app_context.stack_manager.create_backup.return_value = True
        
        result = backup_stack_logic(
            mock_app_context,
            description="Test backup"
        )
        
        assert result is True
        mock_app_context.display.panel.assert_called_once()
        
        # Check panel content
        panel_call = mock_app_context.display.panel.call_args
        panel_content = panel_call[0][0]
        assert "Backup Created Successfully" in panel_content
        assert "Test backup" in panel_content
        assert "ollama-stack restore" in panel_content
    
    @patch('ollama_stack_cli.commands.backup.backup_stack_logic')
    def test_backup_command_success(self, mock_logic):
        """Test backup command with successful logic."""
        mock_logic.return_value = True
        mock_ctx = Mock()
        mock_ctx.obj = Mock(spec=AppContext)
        
        # Should not raise an exception
        backup(mock_ctx)
        
        mock_logic.assert_called_once_with(
            app_context=mock_ctx.obj,
            include_volumes=True,
            include_config=True,
            include_extensions=True,
            output_path=None,
            compress=True,
            description=None
        )
    
    @patch('ollama_stack_cli.commands.backup.backup_stack_logic')
    def test_backup_command_failure(self, mock_logic):
        """Test backup command with failed logic."""
        mock_logic.return_value = False
        mock_ctx = Mock()
        mock_ctx.obj = Mock(spec=AppContext)
        
        with pytest.raises(typer.Exit) as exc_info:
            backup(mock_ctx)
        
        assert exc_info.value.exit_code == 1
        mock_logic.assert_called_once()
    
    @patch('ollama_stack_cli.commands.backup.backup_stack_logic')
    def test_backup_command_custom_options(self, mock_logic):
        """Test backup command with custom options."""
        mock_logic.return_value = True
        mock_ctx = Mock()
        mock_ctx.obj = Mock(spec=AppContext)
        
        backup(
            mock_ctx,
            include_volumes=False,
            include_config=True,
            include_extensions=False,
            output="/custom/path",
            compress=False,
            description="Custom backup"
        )
        
        mock_logic.assert_called_once_with(
            app_context=mock_ctx.obj,
            include_volumes=False,
            include_config=True,
            include_extensions=False,
            output_path="/custom/path",
            compress=False,
            description="Custom backup"
        ) 