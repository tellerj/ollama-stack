from unittest.mock import patch, MagicMock, call
import pytest
import logging

from ollama_stack_cli.context import AppContext


# =============================================================================
# Successful Initialization Tests
# =============================================================================

@patch('ollama_stack_cli.context.StackManager')
@patch('ollama_stack_cli.context.Display')
@patch('ollama_stack_cli.context.Config')
def test_app_context_initialization_with_verbose_true(MockConfig, MockDisplay, MockStackManager):
    """Tests that AppContext correctly initializes its components with verbose=True."""
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

    # Assert that our mocks were called correctly with proper parameters
    MockDisplay.assert_called_once_with(verbose=True)
    MockConfig.assert_called_once_with(mock_display_instance)
    MockStackManager.assert_called_once_with(mock_app_config, mock_display_instance)
    
    # Assert that the context has the correct instances
    assert ctx.config is mock_config_instance
    assert ctx.display is mock_display_instance
    assert ctx.stack_manager is mock_stack_manager_instance
    
    # Test the verbose property
    assert ctx.verbose is True

@patch('ollama_stack_cli.context.StackManager')
@patch('ollama_stack_cli.context.Display')
@patch('ollama_stack_cli.context.Config')
def test_app_context_initialization_with_verbose_false_default(MockConfig, MockDisplay, MockStackManager):
    """Tests that AppContext correctly initializes its components with verbose=False (default)."""
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

    # Assert that our mocks were called correctly with proper parameters
    MockDisplay.assert_called_once_with(verbose=False)
    MockConfig.assert_called_once_with(mock_display_instance)
    MockStackManager.assert_called_once_with(mock_app_config, mock_display_instance)
    
    # Test the verbose property
    assert ctx.verbose is False

@patch('ollama_stack_cli.context.StackManager')
@patch('ollama_stack_cli.context.Display')
@patch('ollama_stack_cli.context.Config')
def test_app_context_initialization_explicit_verbose_false(MockConfig, MockDisplay, MockStackManager):
    """Tests AppContext initialization with explicitly set verbose=False."""
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
    
    # Create an instance of AppContext with explicit verbose=False
    ctx = AppContext(verbose=False)

    # Assert that our mocks were called correctly
    MockDisplay.assert_called_once_with(verbose=False)
    MockConfig.assert_called_once_with(mock_display_instance)
    MockStackManager.assert_called_once_with(mock_app_config, mock_display_instance)
    
    # Test the verbose property
    assert ctx.verbose is False

@patch('ollama_stack_cli.context.StackManager')
@patch('ollama_stack_cli.context.Display')
@patch('ollama_stack_cli.context.Config')
def test_app_context_component_initialization_order(MockConfig, MockDisplay, MockStackManager):
    """Tests that AppContext initializes components in the correct order."""
    # Setup mocks
    mock_config_instance = MagicMock()
    mock_app_config = MagicMock()
    mock_config_instance.app_config = mock_app_config
    MockConfig.return_value = mock_config_instance
    
    mock_display_instance = MagicMock()
    MockDisplay.return_value = mock_display_instance
    
    mock_stack_manager_instance = MagicMock()
    MockStackManager.return_value = mock_stack_manager_instance
    
    # Create AppContext
    AppContext(verbose=True)
    
    # Verify the initialization order through call order
    # Display should be created first, then Config with Display, then StackManager with both
    MockDisplay.assert_called_once_with(verbose=True)
    MockConfig.assert_called_once_with(mock_display_instance)
    MockStackManager.assert_called_once_with(mock_app_config, mock_display_instance)

@patch('ollama_stack_cli.context.StackManager')
@patch('ollama_stack_cli.context.Display')
@patch('ollama_stack_cli.context.Config')
def test_app_context_property_assignments(MockConfig, MockDisplay, MockStackManager):
    """Tests that AppContext correctly assigns all properties during initialization."""
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


# =============================================================================
# Error Handling Tests - Display Initialization Failures
# =============================================================================

@patch('ollama_stack_cli.context.StackManager')
@patch('ollama_stack_cli.context.Config')
@patch('ollama_stack_cli.context.log')
def test_app_context_display_initialization_failure(mock_log, MockConfig, MockStackManager):
    """Tests that AppContext handles exceptions from Display init and exits gracefully."""
    # Create a mock fallback display for error reporting
    mock_fallback_display = MagicMock()
    
    with patch('ollama_stack_cli.context.Display') as MockDisplay:
        # First call (self.display creation) raises exception
        # Second call (fallback display for error reporting) succeeds
        MockDisplay.side_effect = [Exception("Display Error"), mock_fallback_display]
        
        with pytest.raises(SystemExit) as exc_info:
            AppContext()
        
        # Verify exit code
        assert exc_info.value.code == 1
        
        # Verify Display was called twice: once for main, once for fallback
        assert MockDisplay.call_count == 2
        MockDisplay.assert_has_calls([
            call(verbose=False),  # First call for main display
            call(verbose=True)    # Second call for fallback display
        ])
        
        # Verify logging was called with correct parameters
        mock_log.error.assert_called_once()
        args, kwargs = mock_log.error.call_args
        assert "Failed to initialize application" in args[0]
        assert "Display Error" in args[0]
        assert kwargs.get('exc_info') is True
        
        # Verify other components were not initialized
        MockConfig.assert_not_called()
        MockStackManager.assert_not_called()


# =============================================================================
# Error Handling Tests - Config Initialization Failures
# =============================================================================

@patch('ollama_stack_cli.context.StackManager')
@patch('ollama_stack_cli.context.log')
def test_app_context_config_initialization_failure(mock_log, MockStackManager):
    """Tests that AppContext handles exceptions from Config init and exits gracefully."""
    mock_fallback_display = MagicMock()
    
    with patch('ollama_stack_cli.context.Display') as MockDisplay, \
         patch('ollama_stack_cli.context.Config') as MockConfig:
        
        # Main display succeeds, fallback display succeeds
        mock_display_instance = MagicMock()
        MockDisplay.side_effect = [mock_display_instance, mock_fallback_display]
        
        # Config initialization fails
        MockConfig.side_effect = Exception("Config Error")
        
        with pytest.raises(SystemExit) as exc_info:
            AppContext()
        
        # Verify exit code
        assert exc_info.value.code == 1
        
        # Verify Display was called twice: once for main, once for fallback
        assert MockDisplay.call_count == 2
        MockDisplay.assert_has_calls([
            call(verbose=False),  # First call for main display
            call(verbose=True)    # Second call for fallback display
        ])
        
        # Verify Config was called with the display instance
        MockConfig.assert_called_once_with(mock_display_instance)
        
        # Verify logging was called with correct parameters
        mock_log.error.assert_called_once()
        args, kwargs = mock_log.error.call_args
        assert "Failed to initialize application" in args[0]
        assert "Config Error" in args[0]
        assert kwargs.get('exc_info') is True
        
        # Verify StackManager was not initialized
        MockStackManager.assert_not_called()

@patch('ollama_stack_cli.context.log')
def test_app_context_config_initialization_failure_with_verbose(mock_log):
    """Tests Config init failure with verbose=True propagates to fallback Display."""
    mock_fallback_display = MagicMock()
    
    with patch('ollama_stack_cli.context.Display') as MockDisplay, \
         patch('ollama_stack_cli.context.Config') as MockConfig, \
         patch('ollama_stack_cli.context.StackManager') as MockStackManager:
        
        # Main display succeeds, fallback display succeeds
        mock_display_instance = MagicMock()
        MockDisplay.side_effect = [mock_display_instance, mock_fallback_display]
        
        # Config initialization fails
        MockConfig.side_effect = Exception("Config Error")
        
        with pytest.raises(SystemExit):
            AppContext(verbose=True)
        
        # Verify Display calls: first with verbose=True, second fallback with verbose=True
        MockDisplay.assert_has_calls([
            call(verbose=True),   # First call for main display
            call(verbose=True)    # Second call for fallback display
        ])


# =============================================================================
# Error Handling Tests - StackManager Initialization Failures
# =============================================================================

@patch('ollama_stack_cli.context.log')
def test_app_context_stack_manager_initialization_failure(mock_log):
    """Tests that AppContext handles exceptions from StackManager init and exits gracefully."""
    mock_fallback_display = MagicMock()
    
    with patch('ollama_stack_cli.context.Display') as MockDisplay, \
         patch('ollama_stack_cli.context.Config') as MockConfig, \
         patch('ollama_stack_cli.context.StackManager') as MockStackManager:
        
        # Setup successful Display and Config
        mock_display_instance = MagicMock()
        mock_config_instance = MagicMock()
        mock_app_config = MagicMock()
        mock_config_instance.app_config = mock_app_config
        
        MockDisplay.side_effect = [mock_display_instance, mock_fallback_display]
        MockConfig.return_value = mock_config_instance
        
        # StackManager initialization fails
        MockStackManager.side_effect = Exception("StackManager Error")
        
        with pytest.raises(SystemExit) as exc_info:
            AppContext()
        
        # Verify exit code
        assert exc_info.value.code == 1
        
        # Verify all components were called in order
        MockDisplay.assert_has_calls([
            call(verbose=False),  # First call for main display
            call(verbose=True)    # Second call for fallback display
        ])
        MockConfig.assert_called_once_with(mock_display_instance)
        MockStackManager.assert_called_once_with(mock_app_config, mock_display_instance)
        
        # Verify logging was called with correct parameters
        mock_log.error.assert_called_once()
        args, kwargs = mock_log.error.call_args
        assert "Failed to initialize application" in args[0]
        assert "StackManager Error" in args[0]
        assert kwargs.get('exc_info') is True


# =============================================================================
# Error Handling Tests - Multiple Component Failures
# =============================================================================

@patch('ollama_stack_cli.context.log')
def test_app_context_fallback_display_creation_failure(mock_log):
    """Tests behavior when both main and fallback Display creation fail."""
    with patch('ollama_stack_cli.context.Display') as MockDisplay:
        # Both Display calls fail
        MockDisplay.side_effect = [Exception("Display Error"), Exception("Fallback Display Error")]
        
        # When fallback Display creation fails, the exception propagates (this is current behavior)
        # The fallback Display creation is not wrapped in try/catch, so the second exception propagates
        with pytest.raises(Exception) as exc_info:
            AppContext()
        
        # The second exception (Fallback Display Error) should propagate
        assert str(exc_info.value) == "Fallback Display Error"
        assert MockDisplay.call_count == 2

@patch('ollama_stack_cli.context.log')
def test_app_context_error_logging_message_format(mock_log):
    """Tests that error logging contains proper message format and exception details."""
    mock_fallback_display = MagicMock()
    
    with patch('ollama_stack_cli.context.Display') as MockDisplay, \
         patch('ollama_stack_cli.context.Config') as MockConfig:
        
        mock_display_instance = MagicMock()
        MockDisplay.side_effect = [mock_display_instance, mock_fallback_display]
        
        # Create a specific exception to test logging
        test_exception = ValueError("Specific test error message")
        MockConfig.side_effect = test_exception
        
        with pytest.raises(SystemExit):
            AppContext()
        
        # Verify logging call details
        mock_log.error.assert_called_once()
        args, kwargs = mock_log.error.call_args
        
        # Check message format
        assert args[0] == "Failed to initialize application: Specific test error message"
        assert kwargs.get('exc_info') is True


# =============================================================================
# Property and Delegation Tests
# =============================================================================

@patch('ollama_stack_cli.context.StackManager')
@patch('ollama_stack_cli.context.Display')
@patch('ollama_stack_cli.context.Config')
def test_app_context_verbose_property_delegation(MockConfig, MockDisplay, MockStackManager):
    """Tests that the verbose property correctly delegates to the display object."""
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
    assert ctx.verbose is True
    
    # Change the display verbose property and verify it's reflected
    mock_display_instance.verbose = False
    assert ctx.verbose is False

@patch('ollama_stack_cli.context.StackManager')
@patch('ollama_stack_cli.context.Display')
@patch('ollama_stack_cli.context.Config')
def test_app_context_verbose_property_consistency(MockConfig, MockDisplay, MockStackManager):
    """Tests that verbose property remains consistent with display throughout lifecycle."""
    # Setup mocks
    mock_config_instance = MagicMock()
    MockConfig.return_value = mock_config_instance
    
    mock_display_instance = MagicMock()
    mock_display_instance.verbose = False
    MockDisplay.return_value = mock_display_instance
    
    MockStackManager.return_value = MagicMock()
    
    ctx = AppContext()
    
    # Test initial state
    assert ctx.verbose is False
    
    # Test that multiple accesses return the same value
    assert ctx.verbose == ctx.verbose
    
    # Test that the property always reflects the display's current state
    mock_display_instance.verbose = True
    assert ctx.verbose is True


# =============================================================================
# Parameter Passing and Integration Tests
# =============================================================================

@patch('ollama_stack_cli.context.StackManager')
@patch('ollama_stack_cli.context.Display')
@patch('ollama_stack_cli.context.Config')
def test_app_context_config_receives_display_instance(MockConfig, MockDisplay, MockStackManager):
    """Tests that Config receives the exact Display instance created by AppContext."""
    # Setup mocks
    mock_display_instance = MagicMock()
    MockDisplay.return_value = mock_display_instance
    
    mock_config_instance = MagicMock()
    MockConfig.return_value = mock_config_instance
    
    MockStackManager.return_value = MagicMock()
    
    AppContext(verbose=True)
    
    # Verify Config was called with the exact display instance
    MockConfig.assert_called_once_with(mock_display_instance)

@patch('ollama_stack_cli.context.StackManager')
@patch('ollama_stack_cli.context.Display')
@patch('ollama_stack_cli.context.Config')
def test_app_context_stack_manager_receives_correct_parameters(MockConfig, MockDisplay, MockStackManager):
    """Tests that StackManager receives the correct app_config and display instances."""
    # Setup mocks
    mock_display_instance = MagicMock()
    MockDisplay.return_value = mock_display_instance
    
    mock_config_instance = MagicMock()
    mock_app_config = MagicMock()
    mock_config_instance.app_config = mock_app_config
    MockConfig.return_value = mock_config_instance
    
    mock_stack_manager_instance = MagicMock()
    MockStackManager.return_value = mock_stack_manager_instance
    
    AppContext()
    
    # Verify StackManager was called with the exact instances
    MockStackManager.assert_called_once_with(mock_app_config, mock_display_instance)

@patch('ollama_stack_cli.context.StackManager')
@patch('ollama_stack_cli.context.Display')
@patch('ollama_stack_cli.context.Config')
def test_app_context_handles_none_app_config(MockConfig, MockDisplay, MockStackManager):
    """Tests that AppContext handles the case where config.app_config is None."""
    # Setup mocks
    mock_display_instance = MagicMock()
    MockDisplay.return_value = mock_display_instance
    
    mock_config_instance = MagicMock()
    mock_config_instance.app_config = None  # Test None app_config
    MockConfig.return_value = mock_config_instance
    
    mock_stack_manager_instance = MagicMock()
    MockStackManager.return_value = mock_stack_manager_instance
    
    AppContext()
    
    # Verify StackManager was still called with None (should be handled by StackManager)
    MockStackManager.assert_called_once_with(None, mock_display_instance) 