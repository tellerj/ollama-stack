from unittest.mock import MagicMock, patch
import pytest
from ollama_stack_cli.display import Display

@patch('ollama_stack_cli.display.Console')
def test_display_methods_call_console(MockConsole):
    """
    Tests that the Display methods call the underlying rich Console with expected strings.
    """
    mock_console_instance = MockConsole.return_value
    display = Display()

    # Test success
    display.success("It worked")
    mock_console_instance.print.assert_called_with("[bold green]Success:[/] It worked")

    # Test error
    display.error("It failed", suggestion="Try again")
    assert mock_console_instance.print.called
    panel_arg = mock_console_instance.print.call_args[0][0]
    assert "Error:" in panel_arg.renderable
    assert "It failed" in panel_arg.renderable
    assert "Suggestion:" in panel_arg.renderable
    assert "Try again" in panel_arg.renderable
    assert panel_arg.border_style == "red"

    # Test info
    display.info("Just so you know")
    mock_console_instance.print.assert_called_with("[bold blue]Info:[/] Just so you know")

    # Test warning
    display.warning("Look out")
    mock_console_instance.print.assert_called_with("[bold yellow]Warning:[/] Look out")

    # Test panel
    display.panel("Content", title="Title")
    panel_arg = mock_console_instance.print.call_args[0][0]
    assert panel_arg.title == "[bold]Title[/bold]"
    assert panel_arg.border_style == "blue"
    
    # Test verbose property
    assert not display.verbose
    verbose_display = Display(verbose=True)
    assert verbose_display.verbose 