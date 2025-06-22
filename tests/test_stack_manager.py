import pytest
from unittest.mock import MagicMock, patch, call

from ollama_stack_cli.stack_manager import StackManager
from ollama_stack_cli.schemas import AppConfig, PlatformConfig, ServiceStatus, StackStatus, CheckReport, ResourceUsage

# Fixtures

@pytest.fixture
def mock_display():
    """Fixture for a mocked Display object."""
    return MagicMock()

@pytest.fixture
def mock_config():
    """Fixture for a mocked AppConfig object."""
    config = MagicMock(spec=AppConfig)
    config.docker_compose_file = "base.yml"
    config.platform = {
        "apple": PlatformConfig(compose_file="apple.yml"),
        "nvidia": PlatformConfig(compose_file="nvidia.yml"),
    }
    # Provide a dictionary of service names as the StackManager will iterate over them
    config.services = {
        "ollama": {"name": "ollama"},
        "webui": {"name": "webui"},
        "mcp_proxy": {"name": "mcp_proxy"},
    }
    return config

@pytest.fixture
def mock_docker_client():
    """Fixture for a mocked DockerClient."""
    return MagicMock()

@pytest.fixture
def mock_ollama_api_client():
    """Fixture for a mocked OllamaApiClient."""
    return MagicMock()

@pytest.fixture
def stack_manager(mock_config, mock_display, mock_docker_client, mock_ollama_api_client):
    """Fixture to create a StackManager with mocked clients."""
    with patch('ollama_stack_cli.stack_manager.DockerClient', return_value=mock_docker_client), \
         patch('ollama_stack_cli.stack_manager.OllamaApiClient', return_value=mock_ollama_api_client):
        manager = StackManager(config=mock_config, display=mock_display)
        # We need to inject the mocked clients into the manager instance for assertion purposes
        manager.docker_client = mock_docker_client
        manager.ollama_api_client = mock_ollama_api_client
        return manager

# Platform-Specific Tests

def test_get_stack_status_on_apple(stack_manager, mock_docker_client, mock_ollama_api_client):
    """Tests get_stack_status orchestration on Apple Silicon."""
    stack_manager.platform = 'apple'
    
    mock_docker_client.get_container_status.return_value = [
        ServiceStatus(name='webui', is_running=True, status='running'),
        ServiceStatus(name='mcp_proxy', is_running=False)
    ]
    mock_ollama_api_client.get_status.return_value = ServiceStatus(
        name='ollama', is_running=True, status='idle (native)'
    )
    
    status = stack_manager.get_stack_status()
    
    mock_docker_client.get_container_status.assert_called_once_with(['webui', 'mcp_proxy'])
    mock_ollama_api_client.get_status.assert_called_once()
    
    assert len(status.core_services) == 3
    webui = next(s for s in status.core_services if s.name == 'webui')
    ollama = next(s for s in status.core_services if s.name == 'ollama')
    assert webui.is_running is True
    assert ollama.status == 'idle (native)'

def test_get_stack_status_on_linux(stack_manager, mock_docker_client, mock_ollama_api_client):
    """Tests get_stack_status orchestration on Linux/CPU."""
    stack_manager.platform = 'cpu'
    
    mock_docker_client.get_container_status.return_value = [
        ServiceStatus(name='webui', is_running=True),
        ServiceStatus(name='ollama', is_running=True),
        ServiceStatus(name='mcp_proxy', is_running=True),
    ]
    
    status = stack_manager.get_stack_status()
    
    mock_docker_client.get_container_status.assert_called_once_with(['ollama', 'webui', 'mcp_proxy'])
    mock_ollama_api_client.get_status.assert_not_called()
    assert len(status.core_services) == 3

def test_stream_logs_for_native_ollama_on_apple(stack_manager, mock_docker_client, mock_display):
    """Tests that stream_logs provides a message for native Ollama on Apple Silicon."""
    stack_manager.platform = 'apple'
    
    # We must consume the generator for the code to execute
    list(stack_manager.stream_logs(service_or_extension='ollama'))
    
    mock_docker_client.stream_logs.assert_not_called()
    mock_display.warning.assert_called_once()
    mock_display.info.assert_called_once()

# Orchestration Logic Tests
def test_start_services_when_already_running(stack_manager, mock_docker_client, mock_display):
    """Tests that start_services exits early if the stack is already running."""
    mock_docker_client.is_stack_running.return_value = True

    stack_manager.start_services()

    mock_docker_client.is_stack_running.assert_called_once()
    mock_display.info.assert_called_once_with("Ollama Stack is already running.")
    # Ensure that pull and start are not called if the stack is running
    mock_docker_client.pull_images.assert_not_called()
    mock_docker_client.start_services.assert_not_called()

def test_start_services_with_update(stack_manager, mock_docker_client):
    """Tests that start_services calls pull_images when update=True."""
    mock_docker_client.is_stack_running.return_value = False
    
    stack_manager.start_services(update=True)
    
    mock_docker_client.is_stack_running.assert_called_once()
    mock_docker_client.pull_images.assert_called_once()
    mock_docker_client.start_services.assert_called_once()

def test_stop_services(stack_manager, mock_docker_client):
    """Tests that stop_services calls docker_client.stop_services."""
    stack_manager.stop_services()
    mock_docker_client.stop_services.assert_called_once()

def test_restart_services_call_order(stack_manager):
    """Tests that restart calls stop_services then start_services."""
    # Use a new mock with attached methods to check call order
    manager_mock = MagicMock()
    stack_manager.stop_services = MagicMock()
    stack_manager.start_services = MagicMock()
    manager_mock.attach_mock(stack_manager.stop_services, 'stop')
    manager_mock.attach_mock(stack_manager.start_services, 'start')

    stack_manager.restart_services(update=True)
    
    expected_calls = [call.stop(), call.start(update=True)]
    manager_mock.assert_has_calls(expected_calls)
    
def test_run_environment_checks(stack_manager, mock_docker_client):
    """Tests that environment checks are delegated to the docker client."""
    mock_report = CheckReport(checks=[])
    mock_docker_client.run_environment_checks.return_value = mock_report
    
    report = stack_manager.run_environment_checks()
    
    mock_docker_client.run_environment_checks.assert_called_once()
    assert report == mock_report 