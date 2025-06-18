from typer.testing import CliRunner
from unittest.mock import MagicMock, patch
import pytest

from ollama_stack_cli.main import app

runner = CliRunner()

@pytest.fixture
def mock_app_context():
    """Fixture to mock the AppContext and its components."""
    mock_context = MagicMock()
    mock_context.docker_client = MagicMock()
    mock_context.display = MagicMock()
    return mock_context

@patch('ollama_stack_cli.main.AppContext')
def test_verbose_flag(MockAppContext):
    """Tests that the verbose flag is correctly passed to the AppContext."""
    MockAppContext.return_value = MagicMock()
    
    runner.invoke(app, ["--verbose", "start"], catch_exceptions=False)
    MockAppContext.assert_called_once_with(verbose=True)
    
    MockAppContext.reset_mock()
    
    runner.invoke(app, ["start"], catch_exceptions=False)
    MockAppContext.assert_called_once_with(verbose=False)

@patch('ollama_stack_cli.main.AppContext')
def test_start_command(MockAppContext, mock_app_context):
    """Tests that the 'start' command calls docker_client.start_services."""
    MockAppContext.return_value = mock_app_context

    result = runner.invoke(app, ["start"])

    assert result.exit_code == 0
    mock_app_context.docker_client.start_services.assert_called_once_with(update=False)

@patch('ollama_stack_cli.main.AppContext')
def test_start_command_with_update(MockAppContext, mock_app_context):
    """Tests that the 'start --update' command calls start_services with update=True."""
    MockAppContext.return_value = mock_app_context

    result = runner.invoke(app, ["start", "--update"])

    assert result.exit_code == 0
    mock_app_context.docker_client.start_services.assert_called_once_with(update=True)

@patch('ollama_stack_cli.main.AppContext')
def test_stop_command(MockAppContext, mock_app_context):
    """Tests that the 'stop' command calls docker_client.stop_services."""
    MockAppContext.return_value = mock_app_context

    result = runner.invoke(app, ["stop"])

    assert result.exit_code == 0
    mock_app_context.docker_client.stop_services.assert_called_once()

@patch('ollama_stack_cli.main.AppContext')
def test_restart_command(MockAppContext, mock_app_context):
    """Tests that 'restart' calls stop_services then start_services."""
    MockAppContext.return_value = mock_app_context
    
    manager = MagicMock()
    manager.attach_mock(mock_app_context.docker_client.stop_services, 'stop')
    manager.attach_mock(mock_app_context.docker_client.start_services, 'start')
    
    result = runner.invoke(app, ["restart"])

    assert result.exit_code == 0
    
    # Check that calls happened in the correct order
    expected_calls = ['stop', 'start']
    assert [call[0] for call in manager.method_calls] == expected_calls 