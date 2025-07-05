"""
Unit tests for the migrate command.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from ollama_stack_cli.commands.migrate import migrate_stack_logic, migrate
from ollama_stack_cli.context import AppContext
from ollama_stack_cli.config import Config
from ollama_stack_cli.display import Display
from ollama_stack_cli.stack_manager import StackManager


class TestMigrateCommand:
    """Test cases for the migrate command."""
    
    @pytest.fixture
    def mock_app_context(self):
        """Create a mock AppContext for testing."""
        context = Mock(spec=AppContext)
        context.config = Mock(spec=Config)
        context.display = Mock(spec=Display)
        context.stack_manager = Mock(spec=StackManager)
        return context
    
    def test_migrate_stack_logic_no_migration_needed(self, mock_app_context):
        """Test migrate when current version equals target version."""
        result = migrate_stack_logic(
            mock_app_context,
            target_version="0.2.0"  # Same as current version
        )
        
        assert result is True
        mock_app_context.stack_manager.migrate_stack.assert_not_called()
        mock_app_context.display.panel.assert_called_once()
        
        # Check no migration panel content
        panel_call = mock_app_context.display.panel.call_args
        panel_content = panel_call[0][0]
        assert "No Migration Required" in panel_content
    
    def test_migrate_stack_logic_default_target_version(self, mock_app_context):
        """Test migrate with default target version (latest)."""
        mock_app_context.stack_manager.migrate_stack.return_value = True
        mock_app_context.stack_manager.is_stack_running.return_value = False
        
        with patch('typer.confirm', return_value=True):
            result = migrate_stack_logic(mock_app_context)
        
        assert result is True
        mock_app_context.stack_manager.migrate_stack.assert_called_once()
    
    def test_migrate_stack_logic_dry_run_mode(self, mock_app_context):
        """Test migrate in dry-run mode."""
        result = migrate_stack_logic(
            mock_app_context,
            target_version="0.3.0",
            dry_run=True
        )
        
        assert result is True
        mock_app_context.stack_manager.migrate_stack.assert_not_called()
        mock_app_context.display.panel.assert_called_once()
        
        # Check dry run panel content
        panel_call = mock_app_context.display.panel.call_args
        panel_content = panel_call[0][0]
        assert "Migration Plan (Dry Run)" in panel_content
        assert "0.2.0 → 0.3.0" in panel_content
    
    def test_migrate_stack_logic_version_specific_migration_030(self, mock_app_context):
        """Test migrate with version-specific migration for 0.3.0."""
        mock_app_context.stack_manager.migrate_stack.return_value = True
        mock_app_context.stack_manager.is_stack_running.return_value = False
        
        with patch('typer.confirm', return_value=True):
            result = migrate_stack_logic(
                mock_app_context,
                target_version="0.3.0"
            )
        
        assert result is True
        mock_app_context.stack_manager.migrate_stack.assert_called_once_with(
            target_version="0.3.0",
            migration_path=None
        )
    
    def test_migrate_stack_logic_version_specific_migration_040(self, mock_app_context):
        """Test migrate with version-specific migration for 0.4.0."""
        mock_app_context.stack_manager.migrate_stack.return_value = True
        mock_app_context.stack_manager.is_stack_running.return_value = False
        
        with patch('typer.confirm', return_value=True):
            result = migrate_stack_logic(
                mock_app_context,
                target_version="0.4.0"
            )
        
        assert result is True
        mock_app_context.stack_manager.migrate_stack.assert_called_once_with(
            target_version="0.4.0",
            migration_path=None
        )
    
    def test_migrate_stack_logic_generic_migration(self, mock_app_context):
        """Test migrate with generic migration for unknown version."""
        mock_app_context.stack_manager.migrate_stack.return_value = True
        mock_app_context.stack_manager.is_stack_running.return_value = False
        
        with patch('typer.confirm', return_value=True):
            result = migrate_stack_logic(
                mock_app_context,
                target_version="1.0.0"
            )
        
        assert result is True
        mock_app_context.stack_manager.migrate_stack.assert_called_once_with(
            target_version="1.0.0",
            migration_path=None
        )
    
    def test_migrate_stack_logic_user_cancellation(self, mock_app_context):
        """Test migrate when user cancels the operation."""
        mock_app_context.stack_manager.is_stack_running.return_value = False
        
        with patch('typer.confirm', return_value=False):
            result = migrate_stack_logic(
                mock_app_context,
                target_version="0.3.0"
            )
        
        assert result is False
        mock_app_context.stack_manager.migrate_stack.assert_not_called()
    
    def test_migrate_stack_logic_stack_running_user_cancels(self, mock_app_context):
        """Test migrate when stack is running and user cancels."""
        mock_app_context.stack_manager.is_stack_running.return_value = True
        
        with patch('typer.confirm', side_effect=[True, False]):  # First confirm migration, then cancel stack stop
            result = migrate_stack_logic(
                mock_app_context,
                target_version="0.3.0"
            )
        
        assert result is False
        mock_app_context.stack_manager.migrate_stack.assert_not_called()
    
    def test_migrate_stack_logic_stack_running_user_confirms(self, mock_app_context):
        """Test migrate when stack is running and user confirms."""
        mock_app_context.stack_manager.migrate_stack.return_value = True
        mock_app_context.stack_manager.is_stack_running.return_value = True
        
        with patch('typer.confirm', return_value=True):  # Confirm both migration and stack stop
            result = migrate_stack_logic(
                mock_app_context,
                target_version="0.3.0"
            )
        
        assert result is True
        mock_app_context.stack_manager.migrate_stack.assert_called_once()
    
    def test_migrate_stack_logic_no_backup(self, mock_app_context):
        """Test migrate without backup."""
        mock_app_context.stack_manager.migrate_stack.return_value = True
        mock_app_context.stack_manager.is_stack_running.return_value = False
        
        with patch('typer.confirm', return_value=True):
            result = migrate_stack_logic(
                mock_app_context,
                target_version="0.3.0",
                backup=False
            )
        
        assert result is True
        mock_app_context.stack_manager.migrate_stack.assert_called_once()
    
    def test_migrate_stack_logic_successful_migration(self, mock_app_context):
        """Test successful migration with success display."""
        mock_app_context.stack_manager.migrate_stack.return_value = True
        mock_app_context.stack_manager.is_stack_running.return_value = False
        
        with patch('typer.confirm', return_value=True):
            result = migrate_stack_logic(
                mock_app_context,
                target_version="0.3.0",
                backup=True
            )
        
        assert result is True
        mock_app_context.stack_manager.migrate_stack.assert_called_once()
        mock_app_context.display.panel.assert_called()
        
        # Check success panel content
        panel_calls = mock_app_context.display.panel.call_args_list
        success_panel = panel_calls[-1]  # Last call should be success panel
        panel_content = success_panel[0][0]
        assert "Migration Completed Successfully" in panel_content
        assert "0.2.0 → 0.3.0" in panel_content
        assert "ollama-stack start" in panel_content
    
    def test_migrate_stack_logic_migration_failure(self, mock_app_context):
        """Test migration when stack manager fails."""
        mock_app_context.stack_manager.migrate_stack.return_value = False
        mock_app_context.stack_manager.is_stack_running.return_value = False
        
        with patch('typer.confirm', return_value=True):
            result = migrate_stack_logic(
                mock_app_context,
                target_version="0.3.0"
            )
        
        assert result is False
        mock_app_context.stack_manager.migrate_stack.assert_called_once()
    
    def test_migrate_stack_logic_exception_handling(self, mock_app_context):
        """Test migrate with exception handling."""
        mock_app_context.stack_manager.migrate_stack.side_effect = Exception("Test error")
        mock_app_context.stack_manager.is_stack_running.return_value = False
        
        with patch('typer.confirm', return_value=True):
            result = migrate_stack_logic(
                mock_app_context,
                target_version="0.3.0"
            )
        
        assert result is False
        mock_app_context.stack_manager.migrate_stack.assert_called_once()
    
    def test_migrate_stack_logic_breaking_changes_display(self, mock_app_context):
        """Test migrate with breaking changes display."""
        mock_app_context.stack_manager.migrate_stack.return_value = True
        mock_app_context.stack_manager.is_stack_running.return_value = False
        
        with patch('typer.confirm', return_value=True):
            result = migrate_stack_logic(
                mock_app_context,
                target_version="0.3.0"  # Has breaking changes
            )
        
        assert result is True
        # Should display breaking changes warning
        panel_calls = mock_app_context.display.panel.call_args_list
        warning_panel = panel_calls[0]  # First call should be warning panel
        panel_content = warning_panel[0][0]
        assert "Breaking Changes Detected" in panel_content
    
    @patch('ollama_stack_cli.commands.migrate.migrate_stack_logic')
    def test_migrate_command_success(self, mock_logic):
        """Test migrate command with successful logic."""
        mock_logic.return_value = True
        mock_ctx = Mock()
        mock_ctx.obj = Mock(spec=AppContext)
        
        # Should not raise an exception
        migrate(mock_ctx)
        
        mock_logic.assert_called_once_with(
            app_context=mock_ctx.obj,
            target_version=None,
            backup=True,
            dry_run=False
        )
    
    @patch('ollama_stack_cli.commands.migrate.migrate_stack_logic')
    def test_migrate_command_failure(self, mock_logic):
        """Test migrate command with failed logic."""
        mock_logic.return_value = False
        mock_ctx = Mock()
        mock_ctx.obj = Mock(spec=AppContext)
        
        with pytest.raises(SystemExit) as exc_info:
            migrate(mock_ctx)
        
        assert exc_info.value.code == 1
        mock_logic.assert_called_once()
    
    @patch('ollama_stack_cli.commands.migrate.migrate_stack_logic')
    def test_migrate_command_custom_options(self, mock_logic):
        """Test migrate command with custom options."""
        mock_logic.return_value = True
        mock_ctx = Mock()
        mock_ctx.obj = Mock(spec=AppContext)
        
        migrate(
            mock_ctx,
            target_version="0.3.0",
            backup=False,
            dry_run=True
        )
        
        mock_logic.assert_called_once_with(
            app_context=mock_ctx.obj,
            target_version="0.3.0",
            backup=False,
            dry_run=True
        ) 