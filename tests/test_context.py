from unittest.mock import patch
import pytest

from ollama_stack_cli.context import AppContext

@patch('ollama_stack_cli.context.DockerClient')
@patch('ollama_stack_cli.context.load_config')
@patch('ollama_stack_cli.context.Display')
def test_app_context_initialization(MockDisplay, mock_load_config, MockDockerClient):
    """
    Tests that AppContext correctly initializes its components.
    """
    # Create an instance of AppContext
    ctx = AppContext(verbose=True)

    # Assert that our mocks were called correctly
    MockDisplay.assert_called_once_with(verbose=True)
    mock_load_config.assert_called_once()
    MockDockerClient.assert_called_once_with(
        config=mock_load_config.return_value,
        display=MockDisplay.return_value
    )
    
    # Assert that the context has the correct instances
    assert ctx.display == MockDisplay.return_value
    assert ctx.config == mock_load_config.return_value
    assert ctx.docker_client == MockDockerClient.return_value
    
    # Configure the mock's verbose property and test it
    MockDisplay.return_value.verbose = True
    assert ctx.verbose is True

@patch('ollama_stack_cli.context.DockerClient', side_effect=Exception("Docker Error"))
@patch('ollama_stack_cli.context.load_config')
@patch('ollama_stack_cli.context.Display')
def test_app_context_init_docker_failure(MockDisplay, mock_load_config, MockDockerClient):
    """
    Tests that AppContext handles exceptions from DockerClient init and exits.
    """
    with pytest.raises(SystemExit) as e:
        AppContext()
    
    assert e.type == SystemExit
    assert e.value.code == 1 