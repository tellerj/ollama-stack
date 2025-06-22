from unittest.mock import patch
import pytest

from ollama_stack_cli.context import AppContext

@patch('ollama_stack_cli.context.StackManager')
@patch('ollama_stack_cli.context.load_config')
@patch('ollama_stack_cli.context.Display')
def test_app_context_initialization(MockDisplay, mock_load_config, MockStackManager):
    """
    Tests that AppContext correctly initializes its components.
    """
    # Create an instance of AppContext
    ctx = AppContext(verbose=True)

    # Assert that our mocks were called correctly
    MockDisplay.assert_called_once_with(verbose=True)
    mock_load_config.assert_called_once()
    MockStackManager.assert_called_once_with(
        config=mock_load_config.return_value,
        display=MockDisplay.return_value
    )
    
    # Assert that the context has the correct instances
    assert ctx.display == MockDisplay.return_value
    assert ctx.config == mock_load_config.return_value
    assert ctx.stack_manager == MockStackManager.return_value
    
    # Configure the mock's verbose property and test it
    MockDisplay.return_value.verbose = True
    assert ctx.verbose is True

@patch('ollama_stack_cli.context.StackManager', side_effect=Exception("StackManager Error"))
@patch('ollama_stack_cli.context.load_config')
@patch('ollama_stack_cli.context.Display')
def test_app_context_init_stack_manager_failure(MockDisplay, mock_load_config, MockStackManager):
    """
    Tests that AppContext handles exceptions from StackManager init and exits.
    """
    with pytest.raises(SystemExit) as e:
        AppContext()
    
    assert e.type == SystemExit
    assert e.value.code == 1 