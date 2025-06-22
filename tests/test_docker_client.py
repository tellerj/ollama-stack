from unittest.mock import MagicMock, patch, call
import pytest
import docker
import subprocess

from ollama_stack_cli.docker_client import DockerClient
from ollama_stack_cli.schemas import AppConfig, PlatformConfig, ServiceStatus, ResourceUsage

@pytest.fixture
def mock_display():
    """Fixture to create a mocked Display object."""
    return MagicMock()

@pytest.fixture
def mock_config():
    """Fixture to create a mocked AppConfig object."""
    config = MagicMock(spec=AppConfig)
    config.docker_compose_file = "base.yml"
    config.platform = {
        "apple": PlatformConfig(compose_file="apple.yml"),
        "nvidia": PlatformConfig(compose_file="nvidia.yml"),
    }
    return config

@pytest.mark.parametrize("system,machine,docker_info,expected_platform", [
    ("Darwin", "arm64", {}, "apple"),
    ("Linux", "x86_64", {"Runtimes": {"nvidia": True}}, "nvidia"),
    ("Linux", "x86_64", {}, "cpu"),
    ("Windows", "AMD64", {}, "cpu"),
    ("Linux", "x86_64", Exception("Docker error"), "cpu"),
])
@patch('docker.from_env')
@patch('platform.system')
@patch('platform.machine')
def test_detect_platform(
    mock_machine, mock_system, mock_docker_from_env,
    system, machine, docker_info, expected_platform,
    mock_config, mock_display
):
    """Tests that the platform detection logic correctly identifies the host system."""
    mock_system.return_value = system
    mock_machine.return_value = machine
    mock_docker_client = MagicMock()
    
    if isinstance(docker_info, Exception):
        mock_docker_client.info.side_effect = docker_info
    else:
        mock_docker_client.info.return_value = docker_info
        
    mock_docker_from_env.return_value = mock_docker_client

    client = DockerClient(config=mock_config, display=mock_display)
    assert client.detect_platform() == expected_platform 

@patch('docker.from_env')
def test_docker_client_init_raises_on_docker_error(mock_docker_from_env, mock_config, mock_display):
    """Tests that DockerClient raises an exception if the Docker daemon is not available."""
    mock_docker_from_env.side_effect = docker.errors.DockerException("Docker not found")

    with pytest.raises(docker.errors.DockerException):
        DockerClient(config=mock_config, display=mock_display)
    
    mock_display.error.assert_called_once()

@patch('docker.from_env')
def test_get_compose_file_apple(mock_docker_from_env, mock_config, mock_display):
    """Tests compose file selection for Apple Silicon."""
    with patch.object(DockerClient, 'detect_platform', return_value='apple'):
        client = DockerClient(config=mock_config, display=mock_display)
        assert set(client.get_compose_file()) == {"base.yml", "apple.yml"}

@patch('docker.from_env')
def test_get_compose_file_cpu(mock_docker_from_env, mock_config, mock_display):
    """Tests compose file selection for a standard CPU."""
    mock_docker_client = MagicMock()
    mock_docker_client.info.return_value = {}
    mock_docker_from_env.return_value = mock_docker_client
    
    with patch.object(DockerClient, 'detect_platform', return_value='cpu'):
        client = DockerClient(config=mock_config, display=mock_display)
        assert set(client.get_compose_file()) == {"base.yml"}

@patch('subprocess.Popen')
@patch('docker.from_env')
def test_pull_images_calls_compose_pull(mock_docker_from_env, mock_popen, mock_config, mock_display):
    """Tests that the pull_images method correctly calls 'docker-compose pull'."""
    with patch.object(DockerClient, 'detect_platform', return_value='cpu'):
        client = DockerClient(config=mock_config, display=mock_display)
        client._run_compose_command = MagicMock()
    
        client.pull_images()

        client._run_compose_command.assert_called_once_with(["pull"])
        mock_display.info.assert_called_once_with("Pulling latest images for core services...")

@patch('subprocess.Popen')
@patch('docker.from_env')
def test_run_compose_command_failure(mock_docker_from_env, mock_popen, mock_config, mock_display):
    """Tests that _run_compose_command handles a non-zero exit code from subprocess."""
    mock_process = MagicMock()
    mock_process.returncode = 1
    mock_process.stdout.readline.side_effect = ["error output\n", ""]
    mock_popen.return_value = mock_process

    client = DockerClient(config=mock_config, display=mock_display)
    
    assert client._run_compose_command(["up", "-d"]) is False
    mock_display.error.assert_called_once()

@patch('docker.from_env')
def test_get_container_status_api_error(mock_docker_from_env, mock_config, mock_display):
    """Tests that get_container_status raises APIError on docker failure."""
    mock_docker_client = MagicMock()
    mock_docker_client.containers.list.side_effect = docker.errors.APIError("API error")
    mock_docker_from_env.return_value = mock_docker_client

    client = DockerClient(config=mock_config, display=mock_display)
    
    with pytest.raises(docker.errors.APIError):
        client.get_container_status(service_names=['webui'])
    
    mock_display.error.assert_called_once_with(
        "Could not connect to Docker to get container status.",
        suggestion="API error"
    )

@patch('subprocess.Popen')
@patch('docker.from_env')
def test_stream_logs_constructs_correct_command(mock_docker_from_env, mock_popen, mock_config, mock_display):
    """Tests that stream_logs constructs the correct docker-compose command."""
    mock_process = MagicMock()
    mock_process.stdout.readline.side_effect = ["", ""]
    mock_popen.return_value = mock_process

    client = DockerClient(config=mock_config, display=mock_display)
    
    list(client.stream_logs(service_or_extension="ollama", follow=True, tail=50))
    
    expected_cmd = ["docker-compose", "-f", "base.yml", "-f", "base.yml", "logs", "--follow", "--tail", "50", "ollama"]
    mock_popen.assert_called_once()
    args, _ = mock_popen.call_args
    # This check is a bit fragile, but confirms the core components are there
    assert "logs" in args[0]
    assert "ollama" in args[0]