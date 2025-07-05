"""
Unit tests for the restore command.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile
import typer

from ollama_stack_cli.commands.restore import restore_stack_logic, restore
from ollama_stack_cli.context import AppContext
from ollama_stack_cli.config import Config
from ollama_stack_cli.display import Display
from ollama_stack_cli.stack_manager import StackManager


class TestRestoreCommand:
    """Test cases for the restore command."""
    
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
        """Create a temporary backup directory for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            backup_dir = Path(temp_dir)
            # Create backup manifest file
            manifest_file = backup_dir / "backup_manifest.json"
            manifest_file.write_text('{"backup_id": "test", "created_at": "2024-01-01"}')
            yield backup_dir
    
    def test_restore_stack_logic_backup_not_found(self, mock_app_context):
        """Test restore when backup directory doesn't exist."""
        result = restore_stack_logic(
            mock_app_context,
            backup_path="/nonexistent/path"
        )
        
        assert result is False
        mock_app_context.stack_manager.restore_from_backup.assert_not_called()
    
    def test_restore_stack_logic_backup_not_directory(self, mock_app_context):
        """Test restore when backup path is not a directory."""
        with tempfile.NamedTemporaryFile() as temp_file:
            result = restore_stack_logic(
                mock_app_context,
                backup_path=temp_file.name
            )
            
            assert result is False
            mock_app_context.stack_manager.restore_from_backup.assert_not_called()
    
    def test_restore_stack_logic_no_manifest(self, mock_app_context):
        """Test restore when backup manifest is missing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            result = restore_stack_logic(
                mock_app_context,
                backup_path=temp_dir
            )
            
            assert result is False
            mock_app_context.stack_manager.restore_from_backup.assert_not_called()
    
    def test_restore_stack_logic_validation_failure(self, mock_app_context, temp_backup_dir):
        """Test restore when backup validation fails."""
        mock_app_context.stack_manager.restore_from_backup.return_value = False
        
        result = restore_stack_logic(
            mock_app_context,
            backup_path=str(temp_backup_dir)
        )
        
        assert result is False
        # Should be called once for validation (resolve paths for comparison)
        call_args = mock_app_context.stack_manager.restore_from_backup.call_args
        assert Path(call_args[1]['backup_dir']).resolve() == temp_backup_dir.resolve()
        assert call_args[1]['validate_only'] is True
    
    def test_restore_stack_logic_validate_only_success(self, mock_app_context, temp_backup_dir):
        """Test restore in validate-only mode."""
        mock_app_context.stack_manager.restore_from_backup.return_value = True
        
        result = restore_stack_logic(
            mock_app_context,
            backup_path=str(temp_backup_dir),
            validate_only=True
        )
        
        assert result is True
        # Should be called once for validation (resolve paths for comparison)
        call_args = mock_app_context.stack_manager.restore_from_backup.call_args
        assert Path(call_args[1]['backup_dir']).resolve() == temp_backup_dir.resolve()
        assert call_args[1]['validate_only'] is True
        mock_app_context.display.panel.assert_called_once()
    
    def test_restore_stack_logic_stack_running_no_force(self, mock_app_context, temp_backup_dir):
        """Test restore when stack is running and no force flag."""
        mock_app_context.stack_manager.restore_from_backup.side_effect = [True, True]  # validation, then restore
        mock_app_context.stack_manager.is_stack_running.return_value = True
        
        with patch('typer.confirm', return_value=False):
            result = restore_stack_logic(
                mock_app_context,
                backup_path=str(temp_backup_dir),
                force=False
            )
        
        assert result is False
        # Should only be called once for validation
        assert mock_app_context.stack_manager.restore_from_backup.call_count == 1
    
    def test_restore_stack_logic_stack_running_with_force(self, mock_app_context, temp_backup_dir):
        """Test restore when stack is running with force flag."""
        mock_app_context.stack_manager.restore_from_backup.side_effect = [True, True]  # validation, then restore
        mock_app_context.stack_manager.is_stack_running.return_value = True
        
        with patch('ollama_stack_cli.config.DEFAULT_CONFIG_FILE') as mock_config_file, \
             patch('ollama_stack_cli.config.DEFAULT_ENV_FILE') as mock_env_file:
            mock_config_file.exists.return_value = False
            mock_env_file.exists.return_value = False
            
            result = restore_stack_logic(
                mock_app_context,
                backup_path=str(temp_backup_dir),
                force=True
            )
        
        assert result is True
        # Should be called twice: validation and restore
        assert mock_app_context.stack_manager.restore_from_backup.call_count == 2
    
    def test_restore_stack_logic_config_conflict_no_force(self, mock_app_context, temp_backup_dir):
        """Test restore when config files exist and no force flag."""
        mock_app_context.stack_manager.restore_from_backup.side_effect = [True, True]  # validation, then restore
        mock_app_context.stack_manager.is_stack_running.return_value = False
        
        with patch('ollama_stack_cli.config.DEFAULT_CONFIG_FILE') as mock_config_file, \
             patch('ollama_stack_cli.config.DEFAULT_ENV_FILE') as mock_env_file, \
             patch('typer.confirm', return_value=False):
            mock_config_file.exists.return_value = True
            mock_env_file.exists.return_value = True
            
            result = restore_stack_logic(
                mock_app_context,
                backup_path=str(temp_backup_dir),
                force=False
            )
        
        assert result is False
        # Should only be called once for validation
        assert mock_app_context.stack_manager.restore_from_backup.call_count == 1
    
    def test_restore_stack_logic_successful_restore(self, mock_app_context, temp_backup_dir):
        """Test successful restore operation."""
        mock_app_context.stack_manager.restore_from_backup.side_effect = [True, True]  # validation, then restore
        mock_app_context.stack_manager.is_stack_running.return_value = False
        
        with patch('ollama_stack_cli.config.DEFAULT_CONFIG_FILE') as mock_config_file, \
             patch('ollama_stack_cli.config.DEFAULT_ENV_FILE') as mock_env_file:
            mock_config_file.exists.return_value = False
            mock_env_file.exists.return_value = False
            
            result = restore_stack_logic(
                mock_app_context,
                backup_path=str(temp_backup_dir),
                include_volumes=True
            )
        
        assert result is True
        # Should be called twice: validation and restore
        assert mock_app_context.stack_manager.restore_from_backup.call_count == 2
        mock_app_context.display.panel.assert_called_once()
        
        # Check success panel content
        panel_call = mock_app_context.display.panel.call_args
        panel_content = panel_call[0][0]
        assert "Restore Completed Successfully" in panel_content
        assert "ollama-stack start" in panel_content
    
    def test_restore_stack_logic_restore_failure(self, mock_app_context, temp_backup_dir):
        """Test restore when stack manager restore fails."""
        mock_app_context.stack_manager.restore_from_backup.side_effect = [True, False]  # validation success, restore failure
        mock_app_context.stack_manager.is_stack_running.return_value = False
        
        with patch('ollama_stack_cli.config.DEFAULT_CONFIG_FILE') as mock_config_file, \
             patch('ollama_stack_cli.config.DEFAULT_ENV_FILE') as mock_env_file:
            mock_config_file.exists.return_value = False
            mock_env_file.exists.return_value = False
            
            result = restore_stack_logic(
                mock_app_context,
                backup_path=str(temp_backup_dir)
            )
        
        assert result is False
        # Should be called twice: validation and restore
        assert mock_app_context.stack_manager.restore_from_backup.call_count == 2
    
    def test_restore_stack_logic_exception_handling(self, mock_app_context, temp_backup_dir):
        """Test restore with exception handling."""
        mock_app_context.stack_manager.restore_from_backup.side_effect = Exception("Test error")
        
        result = restore_stack_logic(
            mock_app_context,
            backup_path=str(temp_backup_dir)
        )
        
        assert result is False
        mock_app_context.stack_manager.restore_from_backup.assert_called_once()
    
    def test_restore_stack_logic_without_volumes(self, mock_app_context, temp_backup_dir):
        """Test restore without including volumes."""
        mock_app_context.stack_manager.restore_from_backup.side_effect = [True, True]  # validation, then restore
        mock_app_context.stack_manager.is_stack_running.return_value = False
        
        with patch('ollama_stack_cli.config.DEFAULT_CONFIG_FILE') as mock_config_file, \
             patch('ollama_stack_cli.config.DEFAULT_ENV_FILE') as mock_env_file:
            mock_config_file.exists.return_value = False
            mock_env_file.exists.return_value = False
            
            result = restore_stack_logic(
                mock_app_context,
                backup_path=str(temp_backup_dir),
                include_volumes=False
            )
        
        assert result is True
        # Check that volumes are not mentioned in the restore items
        panel_call = mock_app_context.display.panel.call_args
        panel_content = panel_call[0][0]
        assert "Docker volumes" not in panel_content
        assert "Configuration files" in panel_content
    
    @patch('ollama_stack_cli.commands.restore.restore_stack_logic')
    def test_restore_command_success(self, mock_logic):
        """Test restore command with successful logic."""
        mock_logic.return_value = True
        mock_ctx = Mock()
        mock_ctx.obj = Mock(spec=AppContext)
        
        # Should not raise an exception
        restore(mock_ctx, "/backup/path")
        
        mock_logic.assert_called_once_with(
            app_context=mock_ctx.obj,
            backup_path="/backup/path",
            include_volumes=True,
            validate_only=False,
            force=False
        )
    
    @patch('ollama_stack_cli.commands.restore.restore_stack_logic')
    def test_restore_command_failure(self, mock_logic):
        """Test restore command with failed logic."""
        mock_logic.return_value = False
        mock_ctx = Mock()
        mock_ctx.obj = Mock(spec=AppContext)
        
        with pytest.raises(typer.Exit) as exc_info:
            restore(mock_ctx, "/backup/path")
        
        assert exc_info.value.exit_code == 1
        mock_logic.assert_called_once()
    
    @patch('ollama_stack_cli.commands.restore.restore_stack_logic')
    def test_restore_command_custom_options(self, mock_logic):
        """Test restore command with custom options."""
        mock_logic.return_value = True
        mock_ctx = Mock()
        mock_ctx.obj = Mock(spec=AppContext)
        
        restore(
            mock_ctx,
            "/backup/path",
            include_volumes=False,
            validate_only=True,
            force=True
        )
        
        mock_logic.assert_called_once_with(
            app_context=mock_ctx.obj,
            backup_path="/backup/path",
            include_volumes=False,
            validate_only=True,
            force=True
        ) 