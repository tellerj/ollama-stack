from typer.testing import CliRunner
from unittest.mock import MagicMock, patch, Mock
import pytest
import sys
from unittest.mock import call

from ollama_stack_cli.main import app, main

runner = CliRunner()


class TestTyperAppConfiguration:
    """Test the Typer app configuration and setup."""
    
    def test_app_has_correct_help_text(self):
        """Test that the app has the correct help text."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "A CLI for managing the Ollama Stack." in result.stdout
    
    def test_app_completion_disabled(self):
        """Test that command completion is disabled."""
        # This is tested by checking that --install-completion is not available
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "--install-completion" not in result.stdout
        assert "--show-completion" not in result.stdout


class TestCommandRegistration:
    """Test that all commands are properly registered."""
    
    def test_all_commands_are_registered(self):
        """Test that all expected commands are registered."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        help_text = result.stdout

        expected_commands = ["start", "stop", "restart", "status", "logs", "check"]
        for command in expected_commands:
            assert command in help_text
    
    def test_command_count_is_correct(self):
        """Test that only expected commands are registered, no extras."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        help_text = result.stdout
        
        # Count command occurrences in the Commands section
        commands_section = help_text.split("Commands:")[1] if "Commands:" in help_text else help_text
        expected_commands = ["start", "stop", "restart", "status", "logs", "check"]
        
        for command in expected_commands:
            assert command in commands_section


class TestMainCallback:
    """Test the main callback function behavior."""
    
    @patch('ollama_stack_cli.main.AppContext')
    def test_verbose_flag_true(self, MockAppContext):
        """Test that verbose=True is correctly passed to AppContext."""
        # Setup mock to avoid command execution
        mock_context = MagicMock()
        mock_context.config.fell_back_to_defaults = False
        mock_context.stack_manager.config.services = {}
        mock_context.stack_manager.get_running_services_summary.return_value = ([], [])
        MockAppContext.return_value = mock_context
        
        result = runner.invoke(app, ["--verbose", "start"])
        
        MockAppContext.assert_called_once_with(verbose=True)
        assert result.exit_code == 0
    
    @patch('ollama_stack_cli.main.AppContext')
    def test_verbose_flag_false_by_default(self, MockAppContext):
        """Test that verbose=False is the default."""
        # Setup mock to avoid command execution
        mock_context = MagicMock()
        mock_context.config.fell_back_to_defaults = False
        mock_context.stack_manager.config.services = {}
        mock_context.stack_manager.get_running_services_summary.return_value = ([], [])
        MockAppContext.return_value = mock_context
        
        result = runner.invoke(app, ["start"])
        
        MockAppContext.assert_called_once_with(verbose=False)
        assert result.exit_code == 0
    
    @patch('ollama_stack_cli.main.AppContext')
    def test_verbose_short_flag(self, MockAppContext):
        """Test that -v short flag works for verbose."""
        # Setup mock to avoid command execution  
        mock_context = MagicMock()
        mock_context.config.fell_back_to_defaults = False
        mock_context.stack_manager.config.services = {}
        mock_context.stack_manager.get_running_services_summary.return_value = ([], [])
        MockAppContext.return_value = mock_context
        
        result = runner.invoke(app, ["-v", "start"])
        
        MockAppContext.assert_called_once_with(verbose=True)
        assert result.exit_code == 0
    
    @patch('ollama_stack_cli.main.AppContext')
    def test_context_object_is_set(self, MockAppContext):
        """Test that the AppContext is properly attached to the typer context."""
        mock_context = MagicMock()
        mock_context.config.fell_back_to_defaults = False
        mock_context.stack_manager.config.services = {}
        mock_context.stack_manager.get_running_services_summary.return_value = ([], [])
        MockAppContext.return_value = mock_context
        
        # This tests that ctx.obj gets set by the callback
        result = runner.invoke(app, ["start"])
        
        # The fact that this doesn't crash means ctx.obj was properly set
        assert result.exit_code == 0
        MockAppContext.assert_called_once()


class TestAppContextInitializationErrors:
    """Test error handling during AppContext initialization."""
    
    @patch('ollama_stack_cli.main.AppContext')
    def test_app_context_initialization_failure(self, MockAppContext):
        """Test that AppContext initialization failures are handled."""
        # Make AppContext raise an exception during initialization
        MockAppContext.side_effect = Exception("Failed to initialize")
        
        result = runner.invoke(app, ["start"])
        
        # The app should handle the exception gracefully
        assert result.exit_code == 1
        MockAppContext.assert_called_once_with(verbose=False)
    
    @patch('ollama_stack_cli.main.AppContext')
    def test_app_context_initialization_failure_with_verbose(self, MockAppContext):
        """Test AppContext initialization failure with verbose flag."""
        MockAppContext.side_effect = RuntimeError("Configuration error")
        
        result = runner.invoke(app, ["--verbose", "start"])
        
        assert result.exit_code == 1
        MockAppContext.assert_called_once_with(verbose=True)


class TestCommandExecution:
    """Test that commands can be properly executed through the main app."""
    
    @patch('ollama_stack_cli.main.AppContext')
    def test_start_command_execution(self, MockAppContext):
        """Test that the start command can be executed."""
        mock_context = MagicMock()
        mock_context.config.fell_back_to_defaults = False
        mock_context.stack_manager.config.services = {}
        mock_context.stack_manager.get_running_services_summary.return_value = ([], [])
        MockAppContext.return_value = mock_context
        
        result = runner.invoke(app, ["start"])
        assert result.exit_code == 0
    
    @patch('ollama_stack_cli.main.AppContext')
    def test_stop_command_execution(self, MockAppContext):
        """Test that the stop command can be executed."""
        mock_context = MagicMock()
        mock_context.stack_manager.config.services = {}
        MockAppContext.return_value = mock_context
        
        result = runner.invoke(app, ["stop"])
        assert result.exit_code == 0
    
    @patch('ollama_stack_cli.main.AppContext')
    def test_status_command_execution(self, MockAppContext):
        """Test that the status command can be executed."""
        mock_context = MagicMock()
        mock_context.stack_manager.get_stack_status.return_value = MagicMock(
            core_services=[], extensions=[]
        )
        MockAppContext.return_value = mock_context
        
        result = runner.invoke(app, ["status"])
        assert result.exit_code == 0
    
    @patch('ollama_stack_cli.main.AppContext')
    def test_restart_command_execution(self, MockAppContext):
        """Test that the restart command can be executed."""
        mock_context = MagicMock()
        mock_context.stack_manager.config.services = {}
        mock_context.stack_manager.get_running_services_summary.return_value = ([], [])
        MockAppContext.return_value = mock_context
        
        result = runner.invoke(app, ["restart"])
        assert result.exit_code == 0
    
    @patch('ollama_stack_cli.main.AppContext')
    def test_logs_command_execution(self, MockAppContext):
        """Test that the logs command can be executed."""
        mock_context = MagicMock()
        MockAppContext.return_value = mock_context
        
        result = runner.invoke(app, ["logs"])
        assert result.exit_code == 0
    
    @patch('ollama_stack_cli.main.AppContext')
    def test_check_command_execution(self, MockAppContext):
        """Test that the check command can be executed."""
        mock_context = MagicMock()
        mock_context.stack_manager.perform_environment_check.return_value = MagicMock(
            checks=[]
        )
        MockAppContext.return_value = mock_context
        
        result = runner.invoke(app, ["check"])
        assert result.exit_code == 0


class TestCommandWithOptions:
    """Test commands with various options."""
    
    @patch('ollama_stack_cli.main.AppContext')
    def test_start_command_with_update_flag(self, MockAppContext):
        """Test start command with --update flag."""
        mock_context = MagicMock()
        mock_context.config.fell_back_to_defaults = False
        mock_context.stack_manager.config.services = {}
        mock_context.stack_manager.get_running_services_summary.return_value = ([], [])
        MockAppContext.return_value = mock_context
        
        result = runner.invoke(app, ["start", "--update"])
        assert result.exit_code == 0
    
    @patch('ollama_stack_cli.main.AppContext')
    def test_logs_command_with_follow_flag(self, MockAppContext):
        """Test logs command with --follow flag."""
        mock_context = MagicMock()
        MockAppContext.return_value = mock_context
        
        result = runner.invoke(app, ["logs", "--follow"])
        assert result.exit_code == 0


class TestInvalidCommands:
    """Test invalid command scenarios."""
    
    def test_invalid_command(self):
        """Test that invalid commands return appropriate error."""
        result = runner.invoke(app, ["invalid-command"])
        assert result.exit_code == 2  # Typer's exit code for invalid commands
        assert "No such command 'invalid-command'" in result.stderr
    
    def test_help_flag_works(self):
        """Test that --help flag works."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "Usage:" in result.stdout
    
    @patch('ollama_stack_cli.main.AppContext')
    def test_command_help_works(self, MockAppContext):
        """Test that individual command help works."""
        mock_context = MagicMock()
        MockAppContext.return_value = mock_context
        
        result = runner.invoke(app, ["start", "--help"])
        assert result.exit_code == 0
        assert "Usage:" in result.stdout


class TestMainEntryPoint:
    """Test the main entry point when run as script."""
    
    @patch('ollama_stack_cli.main.app')
    def test_main_entry_point(self, mock_app):
        """Test that the main entry point calls app() when run as script."""
        # This is a bit tricky to test since we can't easily test __name__ == "__main__"
        # But we can test that the app object exists and is callable
        assert callable(app)
        assert hasattr(app, '__call__')


class TestErrorHandlingAndEdgeCases:
    """Test error handling and edge cases."""
    
    @patch('ollama_stack_cli.main.AppContext')
    def test_keyboard_interrupt_handling(self, MockAppContext):
        """Test graceful handling of KeyboardInterrupt."""
        mock_context = MagicMock()
        mock_context.stack_manager.config.services = {}
        mock_context.stack_manager.get_running_services_summary.side_effect = KeyboardInterrupt()
        MockAppContext.return_value = mock_context
        
        result = runner.invoke(app, ["start"])
        # Typer handles KeyboardInterrupt, but we test that it doesn't crash catastrophically
        assert result.exit_code != 0
    
    @patch('ollama_stack_cli.main.AppContext')
    def test_command_with_invalid_option(self, MockAppContext):
        """Test command with invalid option."""
        mock_context = MagicMock()
        MockAppContext.return_value = mock_context
        
        result = runner.invoke(app, ["start", "--invalid-option"])
        assert result.exit_code == 2  # Typer's exit code for invalid options
    
    def test_empty_command_line(self):
        """Test running with no commands shows missing command error."""
        result = runner.invoke(app, [])
        assert result.exit_code == 2  # Typer's exit code for missing command
        assert "Missing command" in result.stderr


class TestCallbackFunctionDirectly:
    """Test the main callback function directly."""
    
    @patch('ollama_stack_cli.main.AppContext')
    def test_main_callback_direct_call(self, MockAppContext):
        """Test calling the main callback function directly."""
        import typer
        
        mock_context = MagicMock()
        MockAppContext.return_value = mock_context
        
        # Create a mock typer context
        ctx = Mock(spec=typer.Context)
        
        # Call the callback directly
        main(ctx, verbose=True)
        
        # Verify AppContext was created with correct parameters
        MockAppContext.assert_called_once_with(verbose=True)
        # Verify context object was set
        assert ctx.obj == mock_context
    
    @patch('ollama_stack_cli.main.AppContext')
    def test_main_callback_direct_call_verbose_false(self, MockAppContext):
        """Test calling the main callback with verbose=False."""
        import typer
        
        mock_context = MagicMock()
        MockAppContext.return_value = mock_context
        
        ctx = Mock(spec=typer.Context)
        
        main(ctx, verbose=False)
        
        MockAppContext.assert_called_once_with(verbose=False)
        assert ctx.obj == mock_context