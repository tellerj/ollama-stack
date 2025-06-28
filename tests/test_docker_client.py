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

# Platform detection tests removed - this functionality moved to StackManager 

@patch('docker.from_env')
def test_docker_client_init_raises_on_docker_error(mock_docker_from_env, mock_config, mock_display):
    """Tests that DockerClient raises an exception if the Docker daemon is not available."""
    mock_docker_from_env.side_effect = docker.errors.DockerException("Docker not found")

    with pytest.raises(docker.errors.DockerException):
        DockerClient(config=mock_config, display=mock_display)

# Compose file tests removed - this functionality moved to StackManager

@patch('subprocess.Popen')
@patch('docker.from_env')
def test_pull_images_calls_compose_pull(mock_docker_from_env, mock_popen, mock_config, mock_display):
    """Tests that the pull_images method correctly calls 'docker-compose pull'."""
    client = DockerClient(config=mock_config, display=mock_display)
    client._run_compose_command = MagicMock()
    
    compose_files = ['docker-compose.yml', 'docker-compose.cpu.yml']
    client.pull_images(compose_files)

    client._run_compose_command.assert_called_once_with(["pull"], compose_files)

@patch('subprocess.Popen')
@patch('docker.from_env')
def test_run_compose_command_failure(mock_docker_from_env, mock_popen, mock_config, mock_display):
    """Tests that _run_compose_command handles a non-zero exit code from subprocess."""
    mock_process = MagicMock()
    mock_process.returncode = 1
    mock_process.stdout.readline.side_effect = ["error output\n", ""]
    mock_popen.return_value = mock_process

    client = DockerClient(config=mock_config, display=mock_display)
    compose_files = ['docker-compose.yml']
    
    assert client._run_compose_command(["up", "-d"], compose_files) is False

@patch('docker.from_env')
def test_get_container_status_api_error(mock_docker_from_env, mock_config, mock_display):
    """Tests that get_container_status raises APIError on docker failure."""
    mock_docker_client = MagicMock()
    mock_docker_client.containers.list.side_effect = docker.errors.APIError("API error")
    mock_docker_from_env.return_value = mock_docker_client

    client = DockerClient(config=mock_config, display=mock_display)
    
    with pytest.raises(docker.errors.APIError):
        client.get_container_status(service_names=['webui'])

@patch('subprocess.Popen')
@patch('docker.from_env')
def test_stream_logs_constructs_correct_command(mock_docker_from_env, mock_popen, mock_config, mock_display):
    """Tests that stream_logs constructs the correct docker-compose command."""
    mock_process = MagicMock()
    mock_process.stdout.readline.side_effect = ["", ""]
    mock_popen.return_value = mock_process

    client = DockerClient(config=mock_config, display=mock_display)
    compose_files = ['docker-compose.yml', 'docker-compose.cpu.yml']
    
    list(client.stream_logs(service_or_extension="ollama", follow=True, tail=50, compose_files=compose_files))
    
    mock_popen.assert_called_once()
    args, _ = mock_popen.call_args
    # This check is a bit fragile, but confirms the core components are there
    assert "logs" in args[0]
    assert "ollama" in args[0]