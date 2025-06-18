from unittest.mock import MagicMock, patch, call
import pytest
import docker
import subprocess
import urllib.error
from ollama_stack_cli.docker_client import DockerClient
from ollama_stack_cli.schemas import AppConfig, PlatformConfig

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
    # Test for Apple Silicon
    ("Darwin", "arm64", {}, "apple"),
    # Test for NVIDIA GPU
    ("Linux", "x86_64", {"Runtimes": {"nvidia": True}}, "nvidia"),
    # Test for standard CPU on Linux
    ("Linux", "x86_64", {}, "cpu"),
    # Test for standard CPU on Windows
    ("Windows", "AMD64", {}, "cpu"),
    # Test for Docker info failure
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
    """
    Tests that the platform detection logic correctly identifies the host system.
    """
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
    """
    Tests that DockerClient raises an exception if the Docker daemon is not available.
    """
    mock_docker_from_env.side_effect = docker.errors.DockerException("Docker not found")

    with pytest.raises(docker.errors.DockerException):
        DockerClient(config=mock_config, display=mock_display)
    
    mock_display.error.assert_called_once()

@patch('docker.from_env')
def test_get_compose_file_apple(mock_docker_from_env, mock_config, mock_display):
    """Tests compose file selection for Apple Silicon."""
    with patch('platform.system', return_value="Darwin"), \
         patch('platform.machine', return_value="arm64"):
        client = DockerClient(config=mock_config, display=mock_display)
        assert set(client.get_compose_file()) == {"base.yml", "apple.yml"}

@patch('docker.from_env')
def test_get_compose_file_cpu(mock_docker_from_env, mock_config, mock_display):
    """Tests compose file selection for a standard CPU."""
    # Mock docker info to ensure nvidia check fails
    mock_docker_client = MagicMock()
    mock_docker_client.info.return_value = {}
    mock_docker_from_env.return_value = mock_docker_client
    
    with patch('platform.system', return_value="Linux"), \
         patch('platform.machine', return_value="x86_64"):
        client = DockerClient(config=mock_config, display=mock_display)
        assert set(client.get_compose_file()) == {"base.yml"} 

@patch('docker.from_env')
def test_is_stack_running_returns_true_when_running(mock_docker_from_env, mock_config, mock_display):
    """Tests that is_stack_running returns True when containers are running."""
    mock_docker_client = MagicMock()

    # Simulate one running core service container found via its label
    mock_container = MagicMock()
    mock_container.labels = {"ollama-stack.component": "ollama"}
    mock_docker_client.containers.list.return_value = [mock_container]

    mock_docker_from_env.return_value = mock_docker_client

    client = DockerClient(config=mock_config, display=mock_display)
    client.platform = 'cpu' # Manually set platform to avoid side-effects from detect_platform
    assert client.is_stack_running() is True
    mock_display.info.assert_any_call("The following core services are already running: ollama")

@patch('docker.from_env')
def test_is_stack_running_returns_false_when_stopped(mock_docker_from_env, mock_config, mock_display):
    """Tests that is_stack_running returns False when no containers are running."""
    mock_docker_client = MagicMock()
    mock_docker_client.containers.list.return_value = []
    mock_docker_from_env.return_value = mock_docker_client

    client = DockerClient(config=mock_config, display=mock_display)
    client.platform = 'cpu' # Manually set platform to avoid side-effects from detect_platform
    
    # Reset mock because __init__ calls it during platform detection
    mock_display.info.reset_mock()

    assert client.is_stack_running() is False
    mock_display.info.assert_not_called()

@patch('subprocess.Popen')
@patch('docker.from_env')
def test_pull_images_calls_compose_pull(mock_docker_from_env, mock_popen, mock_config, mock_display):
    """Tests that the pull_images method correctly calls 'docker-compose pull'."""
    client = DockerClient(config=mock_config, display=mock_display)
    # Mock the compose command helper to simplify this unit test
    client._run_compose_command = MagicMock()
    
    # Reset mock because __init__ calls it during platform detection
    mock_display.info.reset_mock()

    client.pull_images()

    client._run_compose_command.assert_called_once_with(["pull"])
    mock_display.info.assert_called_once_with("Pulling latest images for core services...")

@patch('subprocess.Popen')
@patch('docker.from_env')
def test_run_compose_command_failure(mock_docker_from_env, mock_popen, mock_config, mock_display):
    """Tests that _run_compose_command handles a non-zero exit code from subprocess."""
    # Configure the mock Popen process to simulate a failure
    mock_process = MagicMock()
    mock_process.returncode = 1
    mock_process.stdout.readline.return_value = "error output"
    # Make the iterator stop after one line
    mock_process.stdout.readline.side_effect = ["error output\n", ""]
    mock_popen.return_value = mock_process

    client = DockerClient(config=mock_config, display=mock_display)
    
    # The command should return False on failure
    assert client._run_compose_command(["up", "-d"]) is False

    # Check that an error was displayed
    mock_display.error.assert_called_once()
    args, kwargs = mock_display.error.call_args
    assert "Docker Compose command failed" in args[0]
    assert "suggestion" in kwargs
    assert "error output" in kwargs["suggestion"]

@patch('time.sleep')
@patch('urllib.request.urlopen')
@patch('docker.from_env')
def test_perform_health_checks_success(mock_docker_from_env, mock_urlopen, mock_sleep, mock_config, mock_display):
    """Tests that health checks succeed when services respond correctly."""
    # Mock the urlopen context manager to return a successful response
    mock_response = MagicMock()
    mock_response.status = 200
    mock_urlopen.return_value.__enter__.return_value = mock_response

    client = DockerClient(config=mock_config, display=mock_display)
    assert client._perform_health_checks() is True
    
    # Check that all health check URLs were called
    expected_calls = [
        call('http://localhost:11434', timeout=3),
        call('http://localhost:8080', timeout=3),
        call('http://localhost:8200', timeout=3),
    ]
    # We don't care about the order, so we check if the set of calls is the same
    assert len(mock_urlopen.call_args_list) == len(expected_calls)
    assert all(c in mock_urlopen.call_args_list for c in expected_calls)

    mock_display.success.assert_called_with("All services are healthy.")

@patch('time.sleep')
@patch('urllib.request.urlopen')
@patch('docker.from_env')
def test_perform_health_checks_timeout(mock_docker_from_env, mock_urlopen, mock_sleep, mock_config, mock_display):
    """Tests that health checks fail after a timeout."""
    # Simulate a URLError to make the checks fail
    mock_urlopen.side_effect = urllib.error.URLError("test error")

    client = DockerClient(config=mock_config, display=mock_display)
    # Temporarily shorten the timeout for the test
    client.HEALTH_CHECK_TIMEOUT = 0.1
    
    assert client._perform_health_checks() is False
    mock_display.error.assert_called_with(
        "One or more services failed the health check.",
        suggestion="Check the service logs with `ollama-stack logs` for more details."
    )

@patch('docker.from_env')
def test_start_services_when_already_running(mock_docker_from_env, mock_config, mock_display):
    """Tests that start_services exits early if the stack is already running."""
    client = DockerClient(config=mock_config, display=mock_display)
    client.is_stack_running = MagicMock(return_value=True)
    client._run_compose_command = MagicMock()

    client.start_services()

    client.is_stack_running.assert_called_once()
    # Should not attempt to start services
    client._run_compose_command.assert_not_called()
    # Should show the panel with access points
    mock_display.panel.assert_called_once()

@patch('docker.from_env')
def test_start_services_with_update(mock_docker_from_env, mock_config, mock_display):
    """Tests that start_services calls pull_images when update=True."""
    client = DockerClient(config=mock_config, display=mock_display)
    client.is_stack_running = MagicMock(return_value=False)
    client.pull_images = MagicMock()
    client._run_compose_command = MagicMock(return_value=True) # Simulate compose up success
    client._perform_health_checks = MagicMock(return_value=True) # Simulate health check success
    
    client.start_services(update=True)
    
    client.is_stack_running.assert_called_once()
    client.pull_images.assert_called_once()
    client._run_compose_command.assert_called_once_with(["up", "-d"])
    client._perform_health_checks.assert_called_once() 