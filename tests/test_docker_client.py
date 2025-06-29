from unittest.mock import MagicMock, patch, call, mock_open
import pytest
import docker
import subprocess
import socket
import urllib.error
import sys
import pathlib

from ollama_stack_cli.docker_client import DockerClient
from ollama_stack_cli.schemas import AppConfig, PlatformConfig, ServiceStatus, ResourceUsage, CheckReport, EnvironmentCheck

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

# =============================================================================
# Initialization Tests  
# =============================================================================

@patch('docker.from_env')
def test_docker_client_init_success(mock_docker_from_env, mock_config, mock_display):
    """Tests successful DockerClient initialization."""
    mock_docker_client = MagicMock()
    mock_docker_client.ping.return_value = True
    mock_docker_from_env.return_value = mock_docker_client

    client = DockerClient(config=mock_config, display=mock_display)
    
    assert client.client == mock_docker_client
    mock_docker_client.ping.assert_called_once()

@patch('docker.from_env')
def test_docker_client_init_docker_exception_exits(mock_docker_from_env, mock_config, mock_display):
    """Tests that DockerClient handles Docker daemon failure gracefully."""
    mock_docker_from_env.side_effect = docker.errors.DockerException("Docker not found")

    # Should not raise SystemExit anymore, just create client with client=None
    client = DockerClient(config=mock_config, display=mock_display)
    
    assert client.client is None

@patch('docker.from_env')
def test_docker_client_init_connection_refused_message(mock_docker_from_env, mock_config, mock_display):
    """Tests handling of connection refused errors."""
    mock_docker_from_env.side_effect = docker.errors.DockerException("Connection refused")

    # Should not raise SystemExit anymore, just create client with client=None
    client = DockerClient(config=mock_config, display=mock_display)
    
    assert client.client is None

@patch('docker.from_env')
def test_docker_client_init_ping_failure_exits(mock_docker_from_env, mock_config, mock_display):
    """Tests that DockerClient handles ping failures gracefully."""
    mock_docker_client = MagicMock()
    mock_docker_client.ping.side_effect = docker.errors.APIError("Ping failed")
    mock_docker_from_env.return_value = mock_docker_client

    # Should not raise SystemExit anymore, just create client with client=None
    client = DockerClient(config=mock_config, display=mock_display)
    
    assert client.client is None


# =============================================================================
# Docker Compose Operations Tests
# =============================================================================

@patch('subprocess.Popen')
@patch('docker.from_env')
def test_run_compose_command_success(mock_docker_from_env, mock_popen, mock_config, mock_display):
    """Tests successful _run_compose_command execution."""
    mock_process = MagicMock()
    mock_process.returncode = 0
    mock_process.stdout.readline.side_effect = ["success output\n", ""]
    mock_popen.return_value = mock_process

    client = DockerClient(config=mock_config, display=mock_display)
    compose_files = ['docker-compose.yml']
    
    result = client._run_compose_command(["up", "-d"], compose_files)
    
    assert result is True
    mock_popen.assert_called_once()
    expected_cmd = ["docker-compose", "-f", "docker-compose.yml", "up", "-d"]
    mock_popen.assert_called_with(
        expected_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        encoding='utf-8'
    )

@patch('subprocess.Popen')
@patch('docker.from_env')
def test_run_compose_command_multiple_files(mock_docker_from_env, mock_popen, mock_config, mock_display):
    """Tests _run_compose_command with multiple compose files."""
    mock_process = MagicMock()
    mock_process.returncode = 0
    mock_process.stdout.readline.side_effect = [""]
    mock_popen.return_value = mock_process

    client = DockerClient(config=mock_config, display=mock_display)
    compose_files = ['docker-compose.yml', 'docker-compose.override.yml']
    
    client._run_compose_command(["up", "-d"], compose_files)
    
    expected_cmd = [
        "docker-compose", 
        "-f", "docker-compose.yml", 
        "-f", "docker-compose.override.yml", 
        "up", "-d"
    ]
    mock_popen.assert_called_with(
        expected_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        encoding='utf-8'
    )

@patch('subprocess.Popen')
@patch('docker.from_env')
def test_run_compose_command_down_not_found_success(mock_docker_from_env, mock_popen, mock_config, mock_display):
    """Tests that 'down' command with 'not found' error returns success."""
    mock_process = MagicMock()
    mock_process.returncode = 1
    mock_process.stdout.readline.side_effect = ["Stack not found\n", ""]
    mock_popen.return_value = mock_process

    client = DockerClient(config=mock_config, display=mock_display)
    
    result = client._run_compose_command(["down"])
    
    assert result is True  # Should return True for "not found" on down

@patch('subprocess.Popen')
@patch('docker.from_env')
def test_run_compose_command_failure_logging(mock_docker_from_env, mock_popen, mock_config, mock_display):
    """Tests that _run_compose_command logs failures appropriately."""
    mock_process = MagicMock()
    mock_process.returncode = 1
    mock_process.stdout.readline.side_effect = ["real error output\n", ""]
    mock_popen.return_value = mock_process

    client = DockerClient(config=mock_config, display=mock_display)
    
    result = client._run_compose_command(["up", "-d"])
    
    assert result is False

@patch('docker.from_env')  
def test_pull_images_calls_compose_pull(mock_docker_from_env, mock_config, mock_display):
    """Tests that pull_images delegates to _run_compose_command."""
    client = DockerClient(config=mock_config, display=mock_display)
    client._run_compose_command = MagicMock(return_value=True)
    
    compose_files = ['docker-compose.yml', 'docker-compose.cpu.yml']
    result = client.pull_images(compose_files)

    client._run_compose_command.assert_called_once_with(["pull"], compose_files)
    assert result is True

@patch('docker.from_env')
def test_pull_images_default_compose_files(mock_docker_from_env, mock_config, mock_display):
    """Tests that pull_images uses default compose file when none provided."""
    client = DockerClient(config=mock_config, display=mock_display)
    client._run_compose_command = MagicMock(return_value=True)
    
    client.pull_images()

    client._run_compose_command.assert_called_once_with(["pull"], None)

@patch('docker.from_env')
def test_start_services_with_specific_services(mock_docker_from_env, mock_config, mock_display):
    """Tests start_services with specific service list."""
    client = DockerClient(config=mock_config, display=mock_display)
    client._run_compose_command = MagicMock()
    
    services = ['webui', 'ollama']
    compose_files = ['docker-compose.yml']
    client.start_services(services, compose_files)

    client._run_compose_command.assert_called_once_with(["up", "-d", "webui", "ollama"], compose_files)

@patch('docker.from_env')
def test_start_services_all_services(mock_docker_from_env, mock_config, mock_display):
    """Tests start_services without specific services (starts all)."""
    client = DockerClient(config=mock_config, display=mock_display)
    client._run_compose_command = MagicMock()
    
    compose_files = ['docker-compose.yml']
    client.start_services(None, compose_files)

    client._run_compose_command.assert_called_once_with(["up", "-d"], compose_files)

@patch('docker.from_env')
def test_stop_services(mock_docker_from_env, mock_config, mock_display):
    """Tests stop_services delegates to _run_compose_command."""
    client = DockerClient(config=mock_config, display=mock_display)
    client._run_compose_command = MagicMock()
    
    compose_files = ['docker-compose.yml']
    client.stop_services(compose_files)

    client._run_compose_command.assert_called_once_with(["down"], compose_files)


# =============================================================================
# Container Status and Monitoring Tests
# =============================================================================

@patch('docker.from_env')
def test_is_stack_running_true(mock_docker_from_env, mock_config, mock_display):
    """Tests is_stack_running returns True when containers are running."""
    mock_docker_client = MagicMock()
    mock_container = MagicMock()
    mock_docker_client.containers.list.return_value = [mock_container]
    mock_docker_from_env.return_value = mock_docker_client

    client = DockerClient(config=mock_config, display=mock_display)
    
    result = client.is_stack_running()
    
    assert result is True
    mock_docker_client.containers.list.assert_called_once_with(
        filters={"label": "ollama-stack.component", "status": "running"}
    )

@patch('docker.from_env')
def test_is_stack_running_false(mock_docker_from_env, mock_config, mock_display):
    """Tests is_stack_running returns False when no containers are running."""
    mock_docker_client = MagicMock()
    mock_docker_client.containers.list.return_value = []
    mock_docker_from_env.return_value = mock_docker_client

    client = DockerClient(config=mock_config, display=mock_display)
    
    result = client.is_stack_running()
    
    assert result is False

@patch('docker.from_env')
def test_is_stack_running_api_error(mock_docker_from_env, mock_config, mock_display):
    """Tests is_stack_running raises APIError on Docker failure."""
    mock_docker_client = MagicMock()
    mock_docker_client.containers.list.side_effect = docker.errors.APIError("API error")
    mock_docker_from_env.return_value = mock_docker_client

    client = DockerClient(config=mock_config, display=mock_display)
    
    with pytest.raises(docker.errors.APIError):
        client.is_stack_running()

@patch('docker.from_env')
def test_get_container_status_success(mock_docker_from_env, mock_config, mock_display):
    """Tests get_container_status for running containers."""
    mock_docker_client = MagicMock()
    
    # Mock container with ollama-stack.component label
    mock_container = MagicMock()
    mock_container.labels = {"ollama-stack.component": "webui"}
    mock_container.status = "running"
    mock_container.ports = {"80/tcp": [{"HostPort": "8080"}]}
    mock_container.stats.return_value = {
        "cpu_stats": {"cpu_usage": {"total_usage": 100}, "system_cpu_usage": 1000, "online_cpus": 2},
        "precpu_stats": {"cpu_usage": {"total_usage": 50}, "system_cpu_usage": 500},
        "memory_stats": {"usage": 104857600}  # 100MB
    }
    
    mock_docker_client.containers.list.return_value = [mock_container]
    mock_docker_from_env.return_value = mock_docker_client

    client = DockerClient(config=mock_config, display=mock_display)
    
    # Health checking is now handled by StackManager, so DockerClient returns 'unknown'
    statuses = client.get_container_status(['webui'])

    assert len(statuses) == 1
    status = statuses[0]
    assert status.name == 'webui'
    assert status.is_running is True
    assert status.status == 'running'
    assert status.health == 'unknown'  # DockerClient no longer does health checking
    assert '80/tcp' in status.ports
    assert status.ports['80/tcp'] == 8080

@patch('docker.from_env')
def test_get_container_status_not_found(mock_docker_from_env, mock_config, mock_display):
    """Tests get_container_status for services with no containers."""
    mock_docker_client = MagicMock()
    mock_docker_client.containers.list.return_value = []
    mock_docker_from_env.return_value = mock_docker_client

    client = DockerClient(config=mock_config, display=mock_display)
    
    statuses = client.get_container_status(['webui'])

    assert len(statuses) == 1
    status = statuses[0]
    assert status.name == 'webui'
    assert status.is_running is False
    assert status.status == 'not found'
    assert status.health == 'unknown'

@patch('docker.from_env')
def test_get_container_status_api_error(mock_docker_from_env, mock_config, mock_display):
    """Tests that get_container_status raises APIError on docker failure."""
    mock_docker_client = MagicMock()
    mock_docker_client.containers.list.side_effect = docker.errors.APIError("API error")
    mock_docker_from_env.return_value = mock_docker_client

    client = DockerClient(config=mock_config, display=mock_display)
    
    with pytest.raises(docker.errors.APIError):
        client.get_container_status(service_names=['webui'])

@patch('docker.from_env')
def test_parse_ports_with_host_ports(mock_docker_from_env, mock_config, mock_display):
    """Tests _parse_ports with host port mapping."""
    client = DockerClient(config=mock_config, display=mock_display)
    
    port_data = {
        "80/tcp": [{"HostPort": "8080"}],
        "443/tcp": [{"HostPort": "8443"}]
    }
    
    result = client._parse_ports(port_data)
    
    assert result == {"80/tcp": 8080, "443/tcp": 8443}

@patch('docker.from_env')
def test_parse_ports_without_host_ports(mock_docker_from_env, mock_config, mock_display):
    """Tests _parse_ports with no host port mapping."""
    client = DockerClient(config=mock_config, display=mock_display)
    
    port_data = {
        "80/tcp": None,
        "443/tcp": []
    }
    
    result = client._parse_ports(port_data)
    
    assert result == {"80/tcp": None, "443/tcp": None}

@patch('docker.from_env')
def test_parse_ports_empty(mock_docker_from_env, mock_config, mock_display):
    """Tests _parse_ports with empty port data."""
    client = DockerClient(config=mock_config, display=mock_display)
    
    result = client._parse_ports({})
    
    assert result == {}

@patch('docker.from_env')
def test_get_resource_usage_running_container(mock_docker_from_env, mock_config, mock_display):
    """Tests _get_resource_usage for running container."""
    client = DockerClient(config=mock_config, display=mock_display)
    
    mock_container = MagicMock()
    mock_container.status = "running"
    mock_container.stats.return_value = {
        "cpu_stats": {"cpu_usage": {"total_usage": 200}, "system_cpu_usage": 2000, "online_cpus": 4},
        "precpu_stats": {"cpu_usage": {"total_usage": 100}, "system_cpu_usage": 1000},
        "memory_stats": {"usage": 209715200}  # 200MB
    }
    
    result = client._get_resource_usage(mock_container)
    
    assert result.cpu_percent == 40.0  # (200-100)/(2000-1000) * 4 * 100 = 40%
    assert result.memory_mb == 200.0

@patch('docker.from_env')
def test_get_resource_usage_stopped_container(mock_docker_from_env, mock_config, mock_display):
    """Tests _get_resource_usage for stopped container."""
    client = DockerClient(config=mock_config, display=mock_display)
    
    mock_container = MagicMock()
    mock_container.status = "stopped"
    
    result = client._get_resource_usage(mock_container)
    
    assert result.cpu_percent is None
    assert result.memory_mb is None

@patch('docker.from_env')
def test_get_resource_usage_stats_error(mock_docker_from_env, mock_config, mock_display):
    """Tests _get_resource_usage handles stats errors gracefully."""
    client = DockerClient(config=mock_config, display=mock_display)
    
    mock_container = MagicMock()
    mock_container.status = "running"
    mock_container.stats.side_effect = docker.errors.APIError("Stats unavailable")
    
    result = client._get_resource_usage(mock_container)
    
    assert result.cpu_percent is None
    assert result.memory_mb is None

# =============================================================================
# Log Streaming Tests
# =============================================================================

@patch('subprocess.Popen')
@patch('docker.from_env')
def test_stream_logs_all_options(mock_docker_from_env, mock_popen, mock_config, mock_display):
    """Tests stream_logs with all options specified."""
    mock_process = MagicMock()
    mock_process.returncode = 0
    mock_process.stdout.readline.side_effect = ["log line 1\n", "log line 2\n", ""]
    mock_popen.return_value = mock_process

    client = DockerClient(config=mock_config, display=mock_display)
    compose_files = ['docker-compose.yml']
    
    logs = list(client.stream_logs(
        service_or_extension="ollama",
        follow=True,
        tail=100,
        since="2023-01-01T00:00:00",
        until="2023-01-01T23:59:59",
        compose_files=compose_files
    ))
    
    assert logs == ["log line 1", "log line 2"]
    mock_popen.assert_called_once()
    
    # Verify the command construction
    expected_cmd = [
        "docker-compose", "-f", "docker-compose.yml", "logs",
        "--follow", "--tail", "100", "--since", "2023-01-01T00:00:00",
        "--until", "2023-01-01T23:59:59", "ollama"
    ]
    mock_popen.assert_called_with(
        expected_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        encoding='utf-8'
    )

@patch('subprocess.Popen')
@patch('docker.from_env')
def test_stream_logs_minimal_options(mock_docker_from_env, mock_popen, mock_config, mock_display):
    """Tests stream_logs with minimal options."""
    mock_process = MagicMock()
    mock_process.returncode = 0
    mock_process.stdout.readline.side_effect = [""]
    mock_popen.return_value = mock_process

    client = DockerClient(config=mock_config, display=mock_display)
    
    list(client.stream_logs())
    
    expected_cmd = ["docker-compose", "-f", "base.yml", "logs"]
    mock_popen.assert_called_with(
        expected_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        encoding='utf-8'
    )

@patch('subprocess.Popen')
@patch('docker.from_env')
def test_stream_logs_process_failure(mock_docker_from_env, mock_popen, mock_config, mock_display):
    """Tests stream_logs handles subprocess failure."""
    mock_process = MagicMock()
    mock_process.returncode = 1
    mock_process.stdout.readline.side_effect = [""]
    mock_popen.return_value = mock_process

    client = DockerClient(config=mock_config, display=mock_display)
    
    logs = list(client.stream_logs())
    
    assert logs == []

@patch('subprocess.Popen')
@patch('docker.from_env')
def test_stream_logs_file_not_found(mock_docker_from_env, mock_popen, mock_config, mock_display):
    """Tests stream_logs handles FileNotFoundError."""
    mock_popen.side_effect = FileNotFoundError("docker-compose not found")

    client = DockerClient(config=mock_config, display=mock_display)
    
    logs = list(client.stream_logs())
    
    assert logs == []

@patch('subprocess.Popen')
@patch('docker.from_env')
def test_stream_logs_unexpected_error(mock_docker_from_env, mock_popen, mock_config, mock_display):
    """Tests stream_logs handles unexpected errors."""
    mock_popen.side_effect = RuntimeError("Unexpected error")

    client = DockerClient(config=mock_config, display=mock_display)
    
    logs = list(client.stream_logs())
    
    assert logs == []


# =============================================================================
# Environment Validation Tests
# =============================================================================

@patch('docker.from_env')
def test_run_environment_checks_docker_unavailable(mock_docker_from_env, mock_config, mock_display):
    """Tests run_environment_checks when Docker daemon is unavailable."""
    # First, allow the client to be created successfully
    mock_docker_client = MagicMock()
    mock_docker_client.ping.return_value = True  # Allow initial creation
    mock_docker_from_env.return_value = mock_docker_client

    client = DockerClient(config=mock_config, display=mock_display)
    
    # Now make ping fail when run_environment_checks calls it
    mock_docker_client.ping.side_effect = docker.errors.DockerException("Docker not available")
    
    report = client.run_environment_checks()
    
    assert len(report.checks) == 1
    docker_check = report.checks[0]
    assert docker_check.name == "Docker Daemon Running"
    assert docker_check.passed is False
    assert "Docker not available" in docker_check.details

@patch('docker.from_env')
def test_run_environment_checks_success_cpu_platform(mock_docker_from_env, mock_config, mock_display):
    """Tests run_environment_checks for CPU platform."""
    mock_docker_client = MagicMock()
    mock_docker_client.ping.return_value = True
    mock_docker_from_env.return_value = mock_docker_client

    client = DockerClient(config=mock_config, display=mock_display)
    
    # Mock the port availability checks
    with patch.object(client, '_is_port_available', return_value=True), \
         patch.object(client, '_check_compose_files', return_value=[]):
        
        report = client.run_environment_checks(fix=False, platform='cpu')
    
    # Should have Docker daemon check + 3 port checks + compose file checks
    assert len(report.checks) >= 4
    
    # Verify Docker daemon check passed
    docker_check = next(c for c in report.checks if c.name == "Docker Daemon Running")
    assert docker_check.passed is True

@patch('docker.from_env')
def test_run_environment_checks_nvidia_platform(mock_docker_from_env, mock_config, mock_display):
    """Tests run_environment_checks for NVIDIA platform."""
    mock_docker_client = MagicMock()
    mock_docker_client.ping.return_value = True
    mock_docker_client.info.return_value = {'Runtimes': {'nvidia': {'path': '/usr/bin/nvidia-container-runtime'}}}
    mock_docker_from_env.return_value = mock_docker_client

    client = DockerClient(config=mock_config, display=mock_display)
    
    # Mock the port availability checks
    with patch.object(client, '_is_port_available', return_value=True), \
         patch.object(client, '_check_compose_files', return_value=[]):
        
        report = client.run_environment_checks(fix=False, platform='nvidia')
    
    # Should include NVIDIA runtime check
    nvidia_check = next(c for c in report.checks if c.name == "NVIDIA Docker Toolkit")
    assert nvidia_check.passed is True

@patch('docker.from_env')
def test_run_environment_checks_with_fix(mock_docker_from_env, mock_config, mock_display):
    """Tests run_environment_checks with fix=True."""
    mock_docker_client = MagicMock()
    mock_docker_client.ping.return_value = True
    mock_docker_from_env.return_value = mock_docker_client

    client = DockerClient(config=mock_config, display=mock_display)
    
    # Mock pull_images to succeed
    with patch.object(client, 'pull_images', return_value=True), \
         patch.object(client, '_is_port_available', return_value=True), \
         patch.object(client, '_check_compose_files', return_value=[]):
        
        report = client.run_environment_checks(fix=True)
    
    # Should include image pull check when fix=True
    image_check = next(c for c in report.checks if c.name == "Docker Images")
    assert image_check.passed is True

@patch('socket.socket')
@patch('docker.from_env')
def test_is_port_available_true(mock_docker_from_env, mock_socket, mock_config, mock_display):
    """Tests _is_port_available returns True for available port."""
    mock_sock = MagicMock()
    mock_sock.connect_ex.return_value = 1  # Connection failed (port available)
    mock_socket.return_value.__enter__.return_value = mock_sock

    client = DockerClient(config=mock_config, display=mock_display)
    
    result = client._is_port_available(8080)
    
    assert result is True
    mock_sock.settimeout.assert_called_once_with(1)
    mock_sock.connect_ex.assert_called_once_with(('localhost', 8080))

@patch('socket.socket')
@patch('docker.from_env')
def test_is_port_available_false(mock_docker_from_env, mock_socket, mock_config, mock_display):
    """Tests _is_port_available returns False for unavailable port."""
    mock_sock = MagicMock()
    mock_sock.connect_ex.return_value = 0  # Connection succeeded (port in use)
    mock_socket.return_value.__enter__.return_value = mock_sock

    client = DockerClient(config=mock_config, display=mock_display)
    
    result = client._is_port_available(8080)
    
    assert result is False

@patch('socket.socket')
@patch('docker.from_env')
def test_is_port_available_exception(mock_docker_from_env, mock_socket, mock_config, mock_display):
    """Tests _is_port_available handles exceptions gracefully."""
    mock_socket.side_effect = Exception("Socket error")

    client = DockerClient(config=mock_config, display=mock_display)
    
    result = client._is_port_available(8080)
    
    assert result is False

@patch('docker.from_env')
def test_check_required_ports_all_available(mock_docker_from_env, mock_config, mock_display):
    """Tests _check_required_ports when all ports are available."""
    client = DockerClient(config=mock_config, display=mock_display)
    
    with patch.object(client, '_is_port_available', return_value=True):
        checks = client._check_required_ports()
    
    assert len(checks) == 3  # Ollama, WebUI, MCP Proxy
    for check in checks:
        assert check.passed is True
        assert "Available" in check.name

@patch('docker.from_env')
def test_check_required_ports_some_unavailable(mock_docker_from_env, mock_config, mock_display):
    """Tests _check_required_ports when some ports are unavailable."""
    client = DockerClient(config=mock_config, display=mock_display)
    
    # Mock port 11434 (Ollama) as unavailable, others available
    def port_available_side_effect(port):
        return port != 11434
    
    with patch.object(client, '_is_port_available', side_effect=port_available_side_effect):
        checks = client._check_required_ports()
    
    ollama_check = next(c for c in checks if "11434" in c.name)
    assert ollama_check.passed is False
    assert "already in use" in ollama_check.details

@patch('docker.from_env')
def test_check_nvidia_runtime_available(mock_docker_from_env, mock_config, mock_display):
    """Tests _check_nvidia_runtime when NVIDIA runtime is available."""
    mock_docker_client = MagicMock()
    mock_docker_client.info.return_value = {'Runtimes': {'nvidia': {'path': '/usr/bin/nvidia-container-runtime'}}}
    mock_docker_from_env.return_value = mock_docker_client

    client = DockerClient(config=mock_config, display=mock_display)
    
    check = client._check_nvidia_runtime()
    
    assert check.name == "NVIDIA Docker Toolkit"
    assert check.passed is True
    assert "NVIDIA runtime is available" in check.details

@patch('docker.from_env')
def test_check_nvidia_runtime_unavailable(mock_docker_from_env, mock_config, mock_display):
    """Tests _check_nvidia_runtime when NVIDIA runtime is not available."""
    mock_docker_client = MagicMock()
    mock_docker_client.info.return_value = {'Runtimes': {}}
    mock_docker_from_env.return_value = mock_docker_client

    client = DockerClient(config=mock_config, display=mock_display)
    
    check = client._check_nvidia_runtime()
    
    assert check.passed is False
    assert "NVIDIA runtime not found" in check.details
    assert "nvidia-docker2" in check.suggestion

@patch('docker.from_env')
def test_check_nvidia_runtime_exception(mock_docker_from_env, mock_config, mock_display):
    """Tests _check_nvidia_runtime handles exceptions gracefully."""
    mock_docker_client = MagicMock()
    mock_docker_client.info.side_effect = Exception("Info unavailable")
    mock_docker_from_env.return_value = mock_docker_client

    client = DockerClient(config=mock_config, display=mock_display)
    
    check = client._check_nvidia_runtime()
    
    assert check.passed is False
    assert "Could not verify NVIDIA runtime" in check.details

@patch('pathlib.Path.exists')
@patch('docker.from_env')
def test_check_compose_files_exist(mock_docker_from_env, mock_exists, mock_config, mock_display):
    """Tests _check_compose_files when compose file exists."""
    mock_exists.return_value = True

    client = DockerClient(config=mock_config, display=mock_display)
    
    checks = client._check_compose_files(fix=False)
    
    assert len(checks) == 1
    check = checks[0]
    assert check.passed is True
    assert mock_config.docker_compose_file in check.name

@patch('pathlib.Path.exists')
@patch('docker.from_env')
def test_check_compose_files_missing(mock_docker_from_env, mock_exists, mock_config, mock_display):
    """Tests _check_compose_files when compose file is missing."""
    mock_exists.return_value = False

    client = DockerClient(config=mock_config, display=mock_display)
    
    checks = client._check_compose_files(fix=False)
    
    assert len(checks) == 1
    check = checks[0]
    assert check.passed is False
    assert "not found" in check.details

@patch('docker.from_env')
def test_check_and_pull_images_success(mock_docker_from_env, mock_config, mock_display):
    """Tests _check_and_pull_images when pull succeeds."""
    client = DockerClient(config=mock_config, display=mock_display)
    
    with patch.object(client, 'pull_images', return_value=True):
        check = client._check_and_pull_images()
    
    assert check.name == "Docker Images"
    assert check.passed is True
    assert "Successfully pulled" in check.details

@patch('docker.from_env')
def test_check_and_pull_images_failure(mock_docker_from_env, mock_config, mock_display):
    """Tests _check_and_pull_images when pull fails."""
    client = DockerClient(config=mock_config, display=mock_display)
    
    with patch.object(client, 'pull_images', side_effect=Exception("Network error")):
        check = client._check_and_pull_images()
    
    assert check.passed is False
    assert "Failed to pull" in check.details
    assert "Network error" in check.details