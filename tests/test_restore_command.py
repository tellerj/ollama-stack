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
    
    @patch('ollama_stack_cli.commands.restore.log')
    def test_restore_stack_logic_validate_only_success(self, mock_log, mock_app_context, temp_backup_dir):
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
        
        # Should log validation success
        mock_log.info.assert_any_call("Validation-only mode - restore not performed")
        mock_log.info.assert_any_call("Status: Valid and ready for restore")
    
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
        
        with patch('ollama_stack_cli.config.get_default_config_file') as mock_config_file, \
             patch('ollama_stack_cli.config.get_default_env_file') as mock_env_file:
            mock_config_file.return_value.exists.return_value = False
            mock_env_file.return_value.exists.return_value = False
            
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
        
        with patch('ollama_stack_cli.config.get_default_config_file') as mock_config_file, \
             patch('ollama_stack_cli.config.get_default_env_file') as mock_env_file, \
             patch('typer.confirm', return_value=False):
            mock_config_file.return_value.exists.return_value = True
            mock_env_file.return_value.exists.return_value = True
            
            result = restore_stack_logic(
                mock_app_context,
                backup_path=str(temp_backup_dir),
                force=False
            )
        
        assert result is False
        # Should only be called once for validation
        assert mock_app_context.stack_manager.restore_from_backup.call_count == 1
    
    @patch('ollama_stack_cli.commands.restore.log')
    def test_restore_stack_logic_successful_restore(self, mock_log, mock_app_context, temp_backup_dir):
        """Test successful restore operation."""
        mock_app_context.stack_manager.restore_from_backup.side_effect = [True, True]  # validation, then restore
        mock_app_context.stack_manager.is_stack_running.return_value = False
        
        with patch('ollama_stack_cli.config.get_default_config_file') as mock_config_file, \
             patch('ollama_stack_cli.config.get_default_env_file') as mock_env_file:
            mock_config_file.return_value.exists.return_value = False
            mock_env_file.return_value.exists.return_value = False
            
            result = restore_stack_logic(
                mock_app_context,
                backup_path=str(temp_backup_dir),
                include_volumes=True
            )
        
        assert result is True
        # Should be called twice: validation and restore
        assert mock_app_context.stack_manager.restore_from_backup.call_count == 2
        
        # Check success logging
        mock_log.info.assert_any_call("Restore completed successfully!")
        logged_calls = [call.args[0] for call in mock_log.info.call_args_list]
        assert any("Next steps:" in call for call in logged_calls)
        assert any("ollama-stack start" in call for call in logged_calls)
    
    def test_restore_stack_logic_restore_failure(self, mock_app_context, temp_backup_dir):
        """Test restore when stack manager restore fails."""
        mock_app_context.stack_manager.restore_from_backup.side_effect = [True, False]  # validation success, restore failure
        mock_app_context.stack_manager.is_stack_running.return_value = False
        
        with patch('ollama_stack_cli.config.get_default_config_file') as mock_config_file, \
             patch('ollama_stack_cli.config.get_default_env_file') as mock_env_file:
            mock_config_file.return_value.exists.return_value = False
            mock_env_file.return_value.exists.return_value = False
            
            result = restore_stack_logic(
                mock_app_context,
                backup_path=str(temp_backup_dir)
            )
        
        assert result is False
        # Should be called twice: validation and restore
        assert mock_app_context.stack_manager.restore_from_backup.call_count == 2
    
    def test_restore_stack_logic_exception_handling(self, mock_app_context, temp_backup_dir):
        """Test restore exception handling."""
        mock_app_context.stack_manager.restore_from_backup.side_effect = Exception("Test error")
        
        result = restore_stack_logic(
            mock_app_context,
            backup_path=str(temp_backup_dir)
        )
        
        assert result is False
    
    @patch('ollama_stack_cli.commands.restore.log')
    def test_restore_stack_logic_without_volumes(self, mock_log, mock_app_context, temp_backup_dir):
        """Test restore without including volumes."""
        mock_app_context.stack_manager.restore_from_backup.side_effect = [True, True]  # validation, then restore
        mock_app_context.stack_manager.is_stack_running.return_value = False
        
        with patch('ollama_stack_cli.config.get_default_config_file') as mock_config_file, \
             patch('ollama_stack_cli.config.get_default_env_file') as mock_env_file:
            mock_config_file.return_value.exists.return_value = False
            mock_env_file.return_value.exists.return_value = False
            
            result = restore_stack_logic(
                mock_app_context,
                backup_path=str(temp_backup_dir),
                include_volumes=False
            )
        
        assert result is True
        # Should be called twice: validation and restore
        assert mock_app_context.stack_manager.restore_from_backup.call_count == 2
        
        # Verify restore items logged correctly
        logged_calls = [call.args[0] for call in mock_log.info.call_args_list]
        restore_items_call = next((call for call in logged_calls if "Restore will include:" in call), None)
        assert restore_items_call is not None
        assert "Configuration files" in restore_items_call
        assert "Docker volumes" not in restore_items_call
    
    @patch('ollama_stack_cli.commands.restore.restore_stack_logic')
    def test_restore_command_success(self, mock_logic):
        """Test restore command success."""
        mock_logic.return_value = True
        
        # Create mock context
        mock_ctx = Mock()
        mock_ctx.obj = Mock()
        
        # Should not raise exception
        restore(
            ctx=mock_ctx,
            backup_path="/test/backup",
            include_volumes=True,
            validate_only=False,
            force=False
        )
        
        mock_logic.assert_called_once_with(
            app_context=mock_ctx.obj,
            backup_path="/test/backup",
            include_volumes=True,
            validate_only=False,
            force=False
        )
    
    @patch('ollama_stack_cli.commands.restore.restore_stack_logic')
    def test_restore_command_failure(self, mock_logic):
        """Test restore command failure raises typer.Exit."""
        mock_logic.return_value = False
        
        mock_ctx = Mock()
        mock_ctx.obj = Mock()
        
        with pytest.raises(typer.Exit) as exc_info:
            restore(
                ctx=mock_ctx,
                backup_path="/test/backup"
            )
        
        assert exc_info.value.exit_code == 1
    
    @patch('ollama_stack_cli.commands.restore.restore_stack_logic')
    def test_restore_command_custom_options(self, mock_logic):
        """Test restore command with custom options."""
        mock_logic.return_value = True
        
        mock_ctx = Mock()
        mock_ctx.obj = Mock()
        
        restore(
            ctx=mock_ctx,
            backup_path="/test/backup",
            include_volumes=False,
            validate_only=True,
            force=True
        )
        
        mock_logic.assert_called_once_with(
            app_context=mock_ctx.obj,
            backup_path="/test/backup",
            include_volumes=False,
            validate_only=True,
            force=True
        ) 