from unittest.mock import patch, MagicMock
import pytest

from ollama_stack_cli.context import AppContext

@patch('ollama_stack_cli.context.StackManager')
@patch('ollama_stack_cli.context.Display')
@patch('ollama_stack_cli.context.Config')
def test_app_context_initialization_with_verbose_true(MockConfig, MockDisplay, MockStackManager):
    """
    Tests that AppContext correctly initializes its components with verbose=True.
    """
    # Setup mocks
    mock_config_instance = MagicMock()
    mock_app_config = MagicMock()
    mock_config_instance.app_config = mock_app_config
    MockConfig.return_value = mock_config_instance
    
    mock_display_instance = MagicMock()
    mock_display_instance.verbose = True
    MockDisplay.return_value = mock_display_instance
    
    mock_stack_manager_instance = MagicMock()
    MockStackManager.return_value = mock_stack_manager_instance
    
    # Create an instance of AppContext
    ctx = AppContext(verbose=True)

    # Assert that our mocks were called correctly
    MockConfig.assert_called_once()
    MockDisplay.assert_called_once_with(verbose=True)
    MockStackManager.assert_called_once_with(
        mock_app_config,
        mock_display_instance
    )
    
    # Assert that the context has the correct instances
    assert ctx.config == mock_config_instance
    assert ctx.display == mock_display_instance
    assert ctx.stack_manager == mock_stack_manager_instance
    
    # Test the verbose property
    assert ctx.verbose is True

@patch('ollama_stack_cli.context.StackManager')
@patch('ollama_stack_cli.context.Display')
@patch('ollama_stack_cli.context.Config')
def test_app_context_initialization_with_verbose_false(MockConfig, MockDisplay, MockStackManager):
    """
    Tests that AppContext correctly initializes its components with verbose=False (default).
    """
    # Setup mocks
    mock_config_instance = MagicMock()
    mock_app_config = MagicMock()
    mock_config_instance.app_config = mock_app_config
    MockConfig.return_value = mock_config_instance
    
    mock_display_instance = MagicMock()
    mock_display_instance.verbose = False
    MockDisplay.return_value = mock_display_instance
    
    mock_stack_manager_instance = MagicMock()
    MockStackManager.return_value = mock_stack_manager_instance
    
    # Create an instance of AppContext with default verbose
    ctx = AppContext()

    # Assert that our mocks were called correctly
    MockConfig.assert_called_once()
    MockDisplay.assert_called_once_with(verbose=False)
    MockStackManager.assert_called_once_with(
        mock_app_config,
        mock_display_instance
    )
    
    # Test the verbose property
    assert ctx.verbose is False

@patch('ollama_stack_cli.context.StackManager')
@patch('ollama_stack_cli.context.Display')
@patch('ollama_stack_cli.context.Config')
def test_app_context_config_initialization_failure(MockConfig, MockDisplay, MockStackManager):
    """
    Tests that AppContext handles exceptions from Config init and exits.
    """
    mock_display_instance = MagicMock()
    MockDisplay.return_value = mock_display_instance
    MockConfig.side_effect = Exception("Config Error")
    
    with pytest.raises(SystemExit) as exc_info:
        AppContext()
    
    assert exc_info.value.code == 1
    # AppContext creates a second Display instance for error reporting
    assert MockDisplay.call_count == 2
    MockConfig.assert_called_once_with(mock_display_instance)
    # Note: AppContext uses Python logging for error reporting, not display.error()
    MockStackManager.assert_not_called()

@patch('ollama_stack_cli.context.StackManager')
@patch('ollama_stack_cli.context.Display')
@patch('ollama_stack_cli.context.Config')
def test_app_context_display_initialization_failure(MockConfig, MockDisplay, MockStackManager):
    """
    Tests that AppContext handles exceptions from Display init and exits.
    """
    mock_config_instance = MagicMock()
    MockConfig.return_value = mock_config_instance
    
    # First Display call fails, second succeeds for error reporting
    mock_display_for_error = MagicMock()
    with patch('ollama_stack_cli.context.Display', side_effect=[Exception("Display Error"), mock_display_for_error]):
        with pytest.raises(SystemExit) as exc_info:
            AppContext()
    
    assert exc_info.value.code == 1
    # Note: AppContext uses Python logging for error reporting
    MockStackManager.assert_not_called()

@patch('ollama_stack_cli.context.StackManager', side_effect=Exception("StackManager Error"))
@patch('ollama_stack_cli.context.Display')
@patch('ollama_stack_cli.context.Config')
def test_app_context_stack_manager_initialization_failure(MockConfig, MockDisplay, MockStackManager):
    """
    Tests that AppContext handles exceptions from StackManager init and exits.
    """
    mock_config_instance = MagicMock()
    mock_app_config = MagicMock()
    mock_config_instance.app_config = mock_app_config
    MockConfig.return_value = mock_config_instance
    
    mock_display_instance = MagicMock()
    MockDisplay.return_value = mock_display_instance
    
    with pytest.raises(SystemExit) as exc_info:
        AppContext()
    
    assert exc_info.value.code == 1
    MockConfig.assert_called_once()
    # AppContext creates a second Display instance for error reporting
    assert MockDisplay.call_count == 2
    MockStackManager.assert_called_once_with(
        mock_app_config,
        mock_display_instance
    )
    # Note: AppContext uses Python logging for error reporting

@patch('ollama_stack_cli.context.StackManager')
@patch('ollama_stack_cli.context.Display')
@patch('ollama_stack_cli.context.Config')
def test_app_context_verbose_property_delegation(MockConfig, MockDisplay, MockStackManager):
    """
    Tests that the verbose property correctly delegates to the display object.
    """
    # Setup mocks
    mock_config_instance = MagicMock()
    MockConfig.return_value = mock_config_instance
    
    mock_display_instance = MagicMock()
    mock_display_instance.verbose = True
    MockDisplay.return_value = mock_display_instance
    
    mock_stack_manager_instance = MagicMock()
    MockStackManager.return_value = mock_stack_manager_instance
    
    ctx = AppContext(verbose=True)
    
    # Test that verbose property delegates to display
    assert ctx.verbose == mock_display_instance.verbose
    
    # Change the display verbose property and verify it's reflected
    mock_display_instance.verbose = False
    assert ctx.verbose is False

@patch('ollama_stack_cli.context.StackManager')
@patch('ollama_stack_cli.context.Display')
@patch('ollama_stack_cli.context.Config')
def test_app_context_property_assignments(MockConfig, MockDisplay, MockStackManager):
    """
    Tests that AppContext correctly assigns all properties during initialization.
    """
    # Setup mocks with specific instances
    mock_config_instance = MagicMock()
    mock_app_config = MagicMock()
    mock_config_instance.app_config = mock_app_config
    MockConfig.return_value = mock_config_instance
    
    mock_display_instance = MagicMock()
    MockDisplay.return_value = mock_display_instance
    
    mock_stack_manager_instance = MagicMock()
    MockStackManager.return_value = mock_stack_manager_instance
    
    ctx = AppContext()
    
    # Verify all properties are correctly assigned
    assert ctx.config is mock_config_instance
    assert ctx.display is mock_display_instance
    assert ctx.stack_manager is mock_stack_manager_instance 