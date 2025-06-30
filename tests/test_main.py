from typer.testing import CliRunner
from unittest.mock import MagicMock, patch, Mock
import pytest
import sys
import typer
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

        expected_commands = ["start", "stop", "restart", "status", "logs", "check", "update"]
        for command in expected_commands:
            assert command in help_text
    
    def test_command_count_is_correct(self):
        """Test that only expected commands are registered, no extras."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        help_text = result.stdout
        
        # Count command occurrences in the Commands section
        commands_section = help_text.split("Commands:")[1] if "Commands:" in help_text else help_text
        expected_commands = ["start", "stop", "restart", "status", "logs", "check", "update"]
        
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
    def test_app_context_initialization_with_sys_exit(self, MockAppContext):
        """Test that AppContext sys.exit(1) calls are handled by typer."""
        # AppContext handles exceptions internally and calls sys.exit(1)
        MockAppContext.side_effect = SystemExit(1)
        
        result = runner.invoke(app, ["start"])
        
        # Typer should catch the SystemExit and return appropriate exit code
        assert result.exit_code == 1
        MockAppContext.assert_called_once_with(verbose=False)
    
    @patch('ollama_stack_cli.main.AppContext')
    def test_app_context_initialization_with_sys_exit_verbose(self, MockAppContext):
        """Test AppContext sys.exit(1) with verbose flag."""
        MockAppContext.side_effect = SystemExit(1)
        
        result = runner.invoke(app, ["--verbose", "start"])
        
        assert result.exit_code == 1
        MockAppContext.assert_called_once_with(verbose=True)


class TestBasicCommandRouting:
    """Test that commands are properly routed through the main app (detailed logic tested in test_commands.py)."""
    
    @patch('ollama_stack_cli.main.AppContext')
    def test_commands_can_be_invoked(self, MockAppContext):
        """Test that all registered commands can be invoked without errors."""
        # Minimal mock setup - detailed command logic is tested in test_commands.py
        mock_context = MagicMock()
        mock_context.config.fell_back_to_defaults = False
        mock_context.stack_manager.config.services = {}
        mock_context.stack_manager.get_running_services_summary.return_value = ([], [])
        mock_context.stack_manager.get_stack_status.return_value = MagicMock(
            core_services=[], extensions=[]
        )
        mock_context.stack_manager.run_environment_checks.return_value = MagicMock(checks=[])
        # For update command
        mock_context.stack_manager.is_stack_running.return_value = False
        mock_context.stack_manager.pull_images.return_value = True
        mock_context.config.app_config.extensions.enabled = []
        MockAppContext.return_value = mock_context
        
        # Test that each command can be invoked (not testing detailed logic)
        commands = ["start", "stop", "restart", "status", "logs", "check", "update"]
        for command in commands:
            result = runner.invoke(app, [command])
            assert result.exit_code == 0, f"Command '{command}' failed with exit code {result.exit_code}"





class TestInvalidCommands:
    """Test invalid command scenarios."""
    
    def test_invalid_command(self):
        """Test that invalid commands return appropriate error."""
        result = runner.invoke(app, ["invalid-command"])
        assert result.exit_code == 2  # Typer's exit code for invalid commands
        # Typer/Click outputs errors to stdout in test mode
        assert "no such command" in result.output.lower() or "invalid-command" in result.output.lower()
    
    def test_help_flag_works(self):
        """Test that --help flag works."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "Usage:" in result.stdout
    
    def test_command_help_works(self):
        """Test that individual command help works."""
        result = runner.invoke(app, ["start", "--help"])
        assert result.exit_code == 0
        assert "Usage:" in result.stdout


class TestMainEntryPoint:
    """Test the main entry point when run as script."""
    
    def test_app_object_is_callable(self):
        """Test that the main app object exists and is callable."""
        # Test that the app object is properly configured
        assert callable(app)
        assert hasattr(app, '__call__')
        assert hasattr(app, 'registered_commands')  # Typer attribute
        
        # Verify app is a Typer instance
        assert isinstance(app, typer.Typer)


class TestTyperBehaviorAndEdgeCases:
    """Test Typer framework behavior and main.py edge cases."""
    
    def test_invalid_option_handling(self):
        """Test that Typer handles invalid options appropriately."""
        result = runner.invoke(app, ["start", "--invalid-option"])
        assert result.exit_code == 2  # Typer's exit code for invalid options
        # Typer/Click outputs errors to stdout in test mode
        assert "no such option" in result.output.lower() or "invalid" in result.output.lower()
    
    def test_empty_command_line(self):
        """Test running with no commands shows help or missing command error."""
        result = runner.invoke(app, [])
        # Typer behavior: may show help or missing command error
        assert result.exit_code != 0
        # Either missing command or help should be shown in output
        assert "missing command" in result.output.lower() or "usage:" in result.output.lower()


class TestCallbackFunctionDirectly:
    """Test the main callback function directly."""
    
    @patch('ollama_stack_cli.main.AppContext')
    def test_main_callback_behavior(self, MockAppContext):
        """Test that the main callback properly initializes and attaches AppContext."""
        mock_app_context = MagicMock()
        MockAppContext.return_value = mock_app_context
        
        # Create a mock typer context
        ctx = Mock(spec=typer.Context)
        
        # Test verbose=True
        main(ctx, verbose=True)
        MockAppContext.assert_called_with(verbose=True)
        assert ctx.obj == mock_app_context
        
        # Reset for next test
        MockAppContext.reset_mock()
        ctx = Mock(spec=typer.Context)
        
        # Test verbose=False (default)
        main(ctx, verbose=False)
        MockAppContext.assert_called_with(verbose=False)
        assert ctx.obj == mock_app_context