from unittest.mock import MagicMock, patch, call, mock_open
import pytest
import docker
import subprocess
import socket
import urllib.error
import sys
import pathlib
import os
import json
from pathlib import Path

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


# =============================================================================
# Enhanced Resource Management Tests - Phase 5.1
# =============================================================================

@patch('subprocess.Popen')
@patch('docker.from_env')
def test_pull_images_with_progress_success(mock_docker_from_env, mock_popen, mock_config, mock_display):
    """Tests pull_images_with_progress successful execution with progress display."""
    mock_process = MagicMock()
    mock_process.returncode = 0
    mock_process.stdout.readline.side_effect = [
        "Pulling ollama (ollama/ollama:latest)...\n",
        "Downloading 12345678 [====>    ] 45%\n",
        "Downloaded layer\n",
        "Pull complete for ollama\n",
        ""
    ]
    mock_popen.return_value = mock_process

    client = DockerClient(config=mock_config, display=mock_display)
    compose_files = ['docker-compose.yml']
    
    result = client.pull_images_with_progress(compose_files)
    
    assert result is True
    mock_popen.assert_called_once()
    expected_cmd = ["docker-compose", "-f", "docker-compose.yml", "pull"]
    mock_popen.assert_called_with(
        expected_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        encoding='utf-8'
    )
    
    # Display methods should not be called (using logging instead)
    assert not hasattr(mock_display, 'info') or not mock_display.info.called
    assert not hasattr(mock_display, 'success') or not mock_display.success.called

@patch('subprocess.Popen')
@patch('docker.from_env')
def test_pull_images_with_progress_default_compose_files(mock_docker_from_env, mock_popen, mock_config, mock_display):
    """Tests pull_images_with_progress uses default compose file when none provided."""
    mock_process = MagicMock()
    mock_process.returncode = 0
    mock_process.stdout.readline.side_effect = [""]
    mock_popen.return_value = mock_process

    client = DockerClient(config=mock_config, display=mock_display)
    
    result = client.pull_images_with_progress()
    
    assert result is True
    expected_cmd = ["docker-compose", "-f", "base.yml", "pull"]
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
def test_pull_images_with_progress_process_failure(mock_docker_from_env, mock_popen, mock_config, mock_display):
    """Tests pull_images_with_progress handles process failure."""
    mock_process = MagicMock()
    mock_process.returncode = 1
    mock_process.stdout.readline.side_effect = [
        "ERROR: Failed to pull image\n",
        "Network connection failed\n",
        ""
    ]
    mock_popen.return_value = mock_process

    client = DockerClient(config=mock_config, display=mock_display)
    
    result = client.pull_images_with_progress()
    
    assert result is False
    # Error logging should happen, but not through display methods
    assert not hasattr(mock_display, 'error') or not mock_display.error.called

@patch('subprocess.Popen')
@patch('docker.from_env')
def test_pull_images_with_progress_file_not_found(mock_docker_from_env, mock_popen, mock_config, mock_display):
    """Tests pull_images_with_progress handles docker-compose not found."""
    mock_popen.side_effect = FileNotFoundError("docker-compose not found")

    client = DockerClient(config=mock_config, display=mock_display)
    
    result = client.pull_images_with_progress()
    
    assert result is False
    # Error logging should happen, but not through display methods  
    assert not hasattr(mock_display, 'error') or not mock_display.error.called

@patch('subprocess.Popen')
@patch('docker.from_env')
def test_pull_images_with_progress_unexpected_exception(mock_docker_from_env, mock_popen, mock_config, mock_display):
    """Tests pull_images_with_progress handles unexpected exceptions."""
    mock_popen.side_effect = RuntimeError("Unexpected error")

    client = DockerClient(config=mock_config, display=mock_display)
    
    result = client.pull_images_with_progress()
    
    assert result is False
    # Error logging should happen, but not through display methods
    assert not hasattr(mock_display, 'error') or not mock_display.error.called

@patch('subprocess.Popen')
@patch('docker.from_env')
def test_pull_images_with_progress_error_in_output(mock_docker_from_env, mock_popen, mock_config, mock_display):
    """Tests pull_images_with_progress processes error lines in output."""
    mock_process = MagicMock()
    mock_process.returncode = 0
    mock_process.stdout.readline.side_effect = [
        "Pulling ollama...\n",
        "ERROR: Network timeout\n",
        "FAILED to download layer\n",
        "Pull complete\n",
        ""
    ]
    mock_popen.return_value = mock_process

    client = DockerClient(config=mock_config, display=mock_display)
    
    result = client.pull_images_with_progress()
    
    # Should still return True if process exit code is 0
    assert result is True

@patch('docker.from_env')
def test_remove_resources_no_docker_client(mock_docker_from_env, mock_config, mock_display):
    """Tests remove_resources when Docker client is not available."""
    client = DockerClient(config=mock_config, display=mock_display)
    client.client = None  # Simulate no Docker client
    
    result = client.remove_resources(remove_images=True)
    
    assert result is False

@patch('docker.from_env')
def test_remove_resources_success_with_images(mock_docker_from_env, mock_config, mock_display):
    """Tests remove_resources successfully removes images from stack containers."""
    mock_docker_client = MagicMock()
    
    # Mock containers that use our images
    mock_container1 = MagicMock()
    mock_container1.image.id = "image1"
    mock_container2 = MagicMock()
    mock_container2.image.id = "image2"
    mock_docker_client.containers.list.return_value = [mock_container1, mock_container2]
    mock_docker_from_env.return_value = mock_docker_client

    client = DockerClient(config=mock_config, display=mock_display)
    
    result = client.remove_resources(remove_images=True, force=False)
    
    assert result is True
    
    # Verify containers were queried and images were removed
    mock_docker_client.containers.list.assert_called_once_with(
        all=True, 
        filters={"label": "ollama-stack.component"}
    )
    mock_docker_client.images.remove.assert_any_call("image1", force=False)
    mock_docker_client.images.remove.assert_any_call("image2", force=False)
    assert mock_docker_client.images.remove.call_count == 2

@patch('docker.from_env')
def test_remove_resources_success_without_images(mock_docker_from_env, mock_config, mock_display):
    """Tests remove_resources when remove_images=False."""
    mock_docker_client = MagicMock()
    mock_docker_from_env.return_value = mock_docker_client

    client = DockerClient(config=mock_config, display=mock_display)
    
    result = client.remove_resources(remove_images=False)
    
    assert result is True
    
    # Should not attempt to remove images
    mock_docker_client.images.list.assert_not_called()
    mock_docker_client.images.remove.assert_not_called()

@patch('docker.from_env')
def test_remove_resources_image_removal_failure(mock_docker_from_env, mock_config, mock_display):
    """Tests remove_resources handles image removal failures gracefully."""
    mock_docker_client = MagicMock()
    
    # Mock containers that use our images
    mock_container1 = MagicMock()
    mock_container1.image.id = "image1"
    mock_container2 = MagicMock()
    mock_container2.image.id = "image2"
    mock_docker_client.containers.list.return_value = [mock_container1, mock_container2]
    
    # Make first image removal fail
    mock_docker_client.images.remove.side_effect = [
        Exception("Image in use"),
        None  # Second removal succeeds
    ]
    mock_docker_from_env.return_value = mock_docker_client

    client = DockerClient(config=mock_config, display=mock_display)
    
    result = client.remove_resources(remove_images=True)
    
    # Should return False due to partial failure
    assert result is False
    
    # But should continue and try to remove other images
    assert mock_docker_client.images.remove.call_count == 2

@patch('docker.from_env')
def test_remove_resources_compose_command_failure(mock_docker_from_env, mock_config, mock_display):
    """Tests remove_resources when no containers are found."""
    mock_docker_client = MagicMock()
    mock_docker_client.containers.list.return_value = []
    mock_docker_from_env.return_value = mock_docker_client

    client = DockerClient(config=mock_config, display=mock_display)
    
    result = client.remove_resources(remove_images=True)
    
    # Should return True when no containers are found
    assert result is True
    
    # Verify containers were queried but none were removed
    mock_docker_client.containers.list.assert_called_once_with(
        all=True, 
        filters={"label": "ollama-stack.component"}
    )
    mock_docker_client.images.remove.assert_not_called()



@patch('subprocess.run')
@patch('docker.from_env')
def test_export_compose_config_to_file_success(mock_docker_from_env, mock_subprocess_run, mock_config, mock_display):
    """Tests export_compose_config successfully exports to file."""
    mock_docker_client = MagicMock()
    mock_docker_from_env.return_value = mock_docker_client

    mock_subprocess_run.return_value = MagicMock(
        returncode=0,
        stdout="version: '3.8'\nservices:\n  ollama:\n    image: ollama/ollama\n"
    )

    client = DockerClient(config=mock_config, display=mock_display)
    
    with patch('builtins.open', mock_open()) as mock_file:
        result = client.export_compose_config(output_file="config.yml")
    
    assert result is True
    
    # Verify file was written
    mock_file.assert_called_once_with("config.yml", 'w')
    handle = mock_file()
    handle.write.assert_called_once_with("version: '3.8'\nservices:\n  ollama:\n    image: ollama/ollama\n")
    
    # Verify subprocess call
    expected_cmd = ["docker-compose", "-f", "base.yml", "config"]
    mock_subprocess_run.assert_called_with(expected_cmd, capture_output=True, text=True, encoding='utf-8')
    
    # Display methods should not be called (using logging instead)
    assert not hasattr(mock_display, 'success') or not mock_display.success.called

@patch('subprocess.run')
@patch('docker.from_env')
def test_export_compose_config_to_stdout_success(mock_docker_from_env, mock_subprocess_run, mock_config, mock_display):
    """Tests export_compose_config exports to stdout when no file specified."""
    mock_docker_client = MagicMock()
    mock_docker_from_env.return_value = mock_docker_client

    config_yaml = "version: '3.8'\nservices:\n  ollama:\n    image: ollama/ollama\n"
    mock_subprocess_run.return_value = MagicMock(
        returncode=0,
        stdout=config_yaml
    )

    client = DockerClient(config=mock_config, display=mock_display)
    
    with patch('builtins.print') as mock_print:
        result = client.export_compose_config()
    
    assert result is True
    
    # Verify output to stdout
    mock_print.assert_called_once_with(config_yaml)

@patch('subprocess.run')
@patch('docker.from_env')
def test_export_compose_config_custom_compose_files(mock_docker_from_env, mock_subprocess_run, mock_config, mock_display):
    """Tests export_compose_config with custom compose files."""
    mock_docker_client = MagicMock()
    mock_docker_from_env.return_value = mock_docker_client

    mock_subprocess_run.return_value = MagicMock(returncode=0, stdout="config")

    client = DockerClient(config=mock_config, display=mock_display)
    compose_files = ['docker-compose.yml', 'docker-compose.override.yml']
    
    with patch('builtins.print'):
        result = client.export_compose_config(compose_files=compose_files)
    
    assert result is True
    
    # Verify command with multiple files
    expected_cmd = [
        "docker-compose", 
        "-f", "docker-compose.yml", 
        "-f", "docker-compose.override.yml", 
        "config"
    ]
    mock_subprocess_run.assert_called_with(expected_cmd, capture_output=True, text=True, encoding='utf-8')

@patch('subprocess.run')
@patch('docker.from_env')
def test_export_compose_config_process_failure(mock_docker_from_env, mock_subprocess_run, mock_config, mock_display):
    """Tests export_compose_config handles subprocess failure."""
    mock_docker_client = MagicMock()
    mock_docker_from_env.return_value = mock_docker_client

    mock_subprocess_run.return_value = MagicMock(
        returncode=1,
        stderr="Invalid compose file"
    )

    client = DockerClient(config=mock_config, display=mock_display)
    
    result = client.export_compose_config()
    
    assert result is False
    # Error logging should happen, but not through display methods
    assert not hasattr(mock_display, 'error') or not mock_display.error.called

@patch('subprocess.run')
@patch('docker.from_env')
def test_export_compose_config_exception_handling(mock_docker_from_env, mock_subprocess_run, mock_config, mock_display):
    """Tests export_compose_config handles exceptions."""
    mock_docker_client = MagicMock()
    mock_docker_from_env.return_value = mock_docker_client

    mock_subprocess_run.side_effect = Exception("Unexpected error")

    client = DockerClient(config=mock_config, display=mock_display)
    
    result = client.export_compose_config()
    
    assert result is False
    # Error logging should happen, but not through display methods
    assert not hasattr(mock_display, 'error') or not mock_display.error.called

@patch('subprocess.run')
@patch('docker.from_env')
def test_export_compose_config_file_write_permission_error(mock_docker_from_env, mock_subprocess_run, mock_config, mock_display):
    """Tests export_compose_config handles file permission errors."""
    mock_docker_client = MagicMock()
    mock_docker_from_env.return_value = mock_docker_client

    mock_subprocess_run.return_value = MagicMock(returncode=0, stdout="config")

    client = DockerClient(config=mock_config, display=mock_display)
    
    with patch('builtins.open', side_effect=PermissionError("Permission denied")):
        result = client.export_compose_config(output_file="config.yml")
    
    assert result is False
    # Error logging should happen, but not through display methods
    assert not hasattr(mock_display, 'error') or not mock_display.error.called

# =============================================================================
# Edge Cases and Error Scenarios for Phase 5.1 Methods
# =============================================================================

@patch('subprocess.Popen')
@patch('docker.from_env')
def test_pull_images_with_progress_empty_output(mock_docker_from_env, mock_popen, mock_config, mock_display):
    """Tests pull_images_with_progress with empty stdout."""
    mock_process = MagicMock()
    mock_process.returncode = 0
    mock_process.stdout.readline.side_effect = [""]
    mock_popen.return_value = mock_process

    client = DockerClient(config=mock_config, display=mock_display)
    
    result = client.pull_images_with_progress()
    
    assert result is True

@patch('subprocess.Popen')
@patch('docker.from_env')
def test_pull_images_with_progress_mixed_output_levels(mock_docker_from_env, mock_popen, mock_config, mock_display):
    """Tests pull_images_with_progress processes different output types correctly."""
    mock_process = MagicMock()
    mock_process.returncode = 0
    mock_process.stdout.readline.side_effect = [
        "Pulling service1\n",
        "Downloading layer abc123\n",
        "Downloaded layer def456\n",
        "Pull complete for service1\n",
        "WARNING: Deprecated feature\n",
        "INFO: Using cached layer\n",
        ""
    ]
    mock_popen.return_value = mock_process

    client = DockerClient(config=mock_config, display=mock_display)
    
    result = client.pull_images_with_progress()
    
    assert result is True

@patch('docker.from_env')
def test_remove_resources_force_removal(mock_docker_from_env, mock_config, mock_display):
    """Tests remove_resources with force=True."""
    mock_docker_client = MagicMock()
    
    # Mock container that uses our image
    mock_container1 = MagicMock()
    mock_container1.image.id = "image1"
    mock_docker_client.containers.list.return_value = [mock_container1]
    mock_docker_from_env.return_value = mock_docker_client

    client = DockerClient(config=mock_config, display=mock_display)
    
    result = client.remove_resources(remove_images=True, force=True)
    
    assert result is True
    mock_docker_client.images.remove.assert_called_with("image1", force=True)

@patch('docker.from_env')
def test_remove_resources_no_images_found(mock_docker_from_env, mock_config, mock_display):
    """Tests remove_resources when no containers with stack labels exist."""
    mock_docker_client = MagicMock()
    mock_docker_client.containers.list.return_value = []  # No containers
    mock_docker_from_env.return_value = mock_docker_client

    client = DockerClient(config=mock_config, display=mock_display)
    
    result = client.remove_resources(remove_images=True)
    
    assert result is True
    # Should not attempt to remove any images
    mock_docker_client.images.remove.assert_not_called()

@patch('subprocess.run')
@patch('docker.from_env')
def test_export_compose_config_empty_config(mock_docker_from_env, mock_subprocess_run, mock_config, mock_display):
    """Tests export_compose_config with empty configuration output."""
    mock_docker_client = MagicMock()
    mock_docker_from_env.return_value = mock_docker_client

    mock_subprocess_run.return_value = MagicMock(returncode=0, stdout="")

    client = DockerClient(config=mock_config, display=mock_display)
    
    with patch('builtins.print') as mock_print:
        result = client.export_compose_config()
    
    assert result is True
    mock_print.assert_called_once_with("")

def test_backup_volumes_no_client(mock_config, mock_display):
    """Test backup_volumes when client is None"""
    client = DockerClient(config=mock_config, display=mock_display)
    client.client = None  # Simulate no docker client
    
    result = client.backup_volumes(["vol1"], Path("/backup/path"))
    
    assert result is False

def test_backup_volumes_volume_not_found(mock_config, mock_display):
    """Test backup_volumes when volume doesn't exist"""
    mock_client = MagicMock()
    mock_client.volumes.get.side_effect = docker.errors.NotFound("Volume not found")
    
    client = DockerClient(config=mock_config, display=mock_display)
    client.client = mock_client
    
    with patch("pathlib.Path.mkdir"):
        result = client.backup_volumes(["nonexistent_vol"], Path("/backup/path"))
    
    assert result is True  # Should succeed because volume not found is handled gracefully
    mock_client.volumes.get.assert_called_once_with("nonexistent_vol")

def test_backup_volumes_container_run_fails(mock_config, mock_display):
    """Test backup_volumes when container run fails"""
    with patch("pathlib.Path.mkdir"), patch("pathlib.Path.exists", return_value=True):
        mock_client = MagicMock()
        mock_volume = MagicMock()
        mock_volume.name = "test_vol"
        mock_client.volumes.get.return_value = mock_volume
        mock_client.containers.run.side_effect = docker.errors.APIError("Container run failed")
        
        client = DockerClient(config=mock_config, display=mock_display)
        client.client = mock_client
        
        result = client.backup_volumes(["test_vol"], Path("/backup/path"))
        
        assert result is False
        mock_client.volumes.get.assert_called_once_with("test_vol")
        mock_client.containers.run.assert_called_once()

def test_backup_volumes_container_wait_fails(mock_config, mock_display):
    """Test backup_volumes when container wait returns non-zero exit code"""
    with patch("pathlib.Path.mkdir"), patch("pathlib.Path.exists", return_value=False):
        mock_client = MagicMock()
        mock_volume = MagicMock()
        mock_volume.name = "test_vol"
        mock_client.volumes.get.return_value = mock_volume
        
        mock_container = MagicMock()
        mock_container.wait.return_value = {"StatusCode": 1}
        mock_container.logs.return_value = b"Backup failed"
        mock_client.containers.run.return_value = mock_container
        
        client = DockerClient(config=mock_config, display=mock_display)
        client.client = mock_client
        
        result = client.backup_volumes(["test_vol"], Path("/backup/path"))
        
        assert result is False
        mock_client.containers.run.assert_called_once()

def test_backup_volumes_empty_list(mock_config, mock_display):
    """Test backup_volumes with empty volume list"""
    mock_client = MagicMock()
    client = DockerClient(config=mock_config, display=mock_display)
    client.client = mock_client
    
    with patch("pathlib.Path.mkdir"):
        result = client.backup_volumes([], Path("/backup/path"))
    
    assert result is True
    mock_client.volumes.get.assert_not_called()
    mock_client.containers.run.assert_not_called()

def test_backup_volumes_backup_dir_creation(mock_config, mock_display):
    """Test backup_volumes creates backup directory structure"""
    with patch("pathlib.Path.mkdir") as mock_mkdir, patch("pathlib.Path.exists") as mock_exists:
        mock_exists.return_value = True
        
        mock_client = MagicMock()
        mock_volume = MagicMock()
        mock_volume.name = "test_vol"
        mock_client.volumes.get.return_value = mock_volume
        
        mock_container = MagicMock()
        mock_container.wait.return_value = {"StatusCode": 0}
        mock_client.containers.run.return_value = mock_container
        
        client = DockerClient(config=mock_config, display=mock_display)
        client.client = mock_client
        
        result = client.backup_volumes(["test_vol"], Path("/backup/path"))
        
        assert result is True
        mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)

def test_backup_volumes_partial_failure(mock_config, mock_display):
    """Test backup_volumes with some volumes failing"""
    with patch("pathlib.Path.mkdir"), patch("pathlib.Path.exists") as mock_patches:
        mock_mkdir = mock_patches[0]
        mock_exists = mock_patches[1]
        mock_exists.return_value = True
        
        mock_client = MagicMock()
        
        # First volume succeeds
        mock_vol1 = MagicMock()
        mock_vol1.name = "vol1"
        
        # Second volume fails
        def volume_get_side_effect(name):
            if name == "vol1":
                return mock_vol1
            elif name == "vol2":
                raise docker.errors.NotFound("Volume not found")
        
        mock_client.volumes.get.side_effect = volume_get_side_effect
        
        mock_container = MagicMock()
        mock_container.wait.return_value = {"StatusCode": 0}
        mock_client.containers.run.return_value = mock_container
        
        client = DockerClient(config=mock_config, display=mock_display)
        client.client = mock_client
        
        result = client.backup_volumes(["vol1", "vol2"], Path("/backup/path"))
        
        assert result is True  # Should succeed even if some volumes are not found (they are skipped)
        assert mock_client.volumes.get.call_count == 2
    
def test_restore_volumes_success(mock_config, mock_display):
    """Test restore_volumes successful execution"""
    with patch("pathlib.Path.exists", return_value=True):
        mock_client = MagicMock()
        mock_volume = MagicMock()
        mock_volume.name = "test_vol"
        mock_client.volumes.get.side_effect = docker.errors.NotFound("Volume not found")
        mock_client.volumes.create.return_value = mock_volume
        
        mock_container = MagicMock()
        mock_container.wait.return_value = {"StatusCode": 0}
        mock_client.containers.run.return_value = mock_container
        
        client = DockerClient(config=mock_config, display=mock_display)
        client.client = mock_client
        
        result = client.restore_volumes(["test_vol"], Path("/backup/path"))
        
        assert result is True
        mock_client.volumes.create.assert_called_once_with(name="test_vol")
        mock_client.containers.run.assert_called_once()

def test_restore_volumes_multiple_volumes(mock_config, mock_display):
    """Test restore_volumes with multiple volumes"""
    with patch("pathlib.Path.exists", return_value=True):
        mock_client = MagicMock()
        
        mock_vol1 = MagicMock()
        mock_vol1.name = "vol1"
        mock_vol2 = MagicMock()
        mock_vol2.name = "vol2"
        
        mock_client.volumes.get.side_effect = docker.errors.NotFound("Volume not found")
        mock_client.volumes.create.side_effect = [mock_vol1, mock_vol2]
        
        mock_container = MagicMock()
        mock_container.wait.return_value = {"StatusCode": 0}
        mock_client.containers.run.return_value = mock_container
        
        client = DockerClient(config=mock_config, display=mock_display)
        client.client = mock_client
        
        result = client.restore_volumes(["vol1", "vol2"], Path("/backup/path"))
        
        assert result is True
        assert mock_client.volumes.create.call_count == 2
        assert mock_client.containers.run.call_count == 2
        mock_client.volumes.create.assert_any_call(name="vol1")
        mock_client.volumes.create.assert_any_call(name="vol2")

def test_restore_volumes_no_client(mock_config, mock_display):
    """Test restore_volumes when client is None"""
    client = DockerClient(config=mock_config, display=mock_display)
    client.client = None
    
    result = client.restore_volumes(["vol1"], Path("/backup/path"))
    
    assert result is False

def test_restore_volumes_backup_file_missing(mock_config, mock_display):
    """Test restore_volumes when backup file doesn't exist"""
    with patch("pathlib.Path.exists", return_value=False):
        mock_client = MagicMock()
        client = DockerClient(config=mock_config, display=mock_display)
        client.client = mock_client
        
        result = client.restore_volumes(["test_vol"], Path("/backup/path"))
        
        assert result is False
        mock_client.volumes.create.assert_not_called()
        mock_client.containers.run.assert_not_called()

def test_restore_volumes_volume_create_fails(mock_config, mock_display):
    """Test restore_volumes when volume creation fails"""
    with patch("pathlib.Path.exists", return_value=True):
        mock_client = MagicMock()
        mock_client.volumes.get.side_effect = docker.errors.NotFound("Volume not found")
        mock_client.volumes.create.side_effect = docker.errors.APIError("Volume creation failed")
        
        client = DockerClient(config=mock_config, display=mock_display)
        client.client = mock_client
        
        result = client.restore_volumes(["test_vol"], Path("/backup/path"))
        
        assert result is False
        mock_client.volumes.create.assert_called_once_with(name="test_vol")

def test_restore_volumes_container_run_fails(mock_config, mock_display):
    """Test restore_volumes when container run fails"""
    with patch("pathlib.Path.exists", return_value=True):
        mock_client = MagicMock()
        mock_volume = MagicMock()
        mock_volume.name = "test_vol"
        mock_client.volumes.get.side_effect = docker.errors.NotFound("Volume not found")
        mock_client.volumes.create.return_value = mock_volume
        mock_client.containers.run.side_effect = docker.errors.APIError("Container run failed")
        
        client = DockerClient(config=mock_config, display=mock_display)
        client.client = mock_client
        
        result = client.restore_volumes(["test_vol"], Path("/backup/path"))
        
        assert result is False
        mock_client.volumes.create.assert_called_once_with(name="test_vol")
        mock_client.containers.run.assert_called_once()

def test_restore_volumes_container_wait_fails(mock_config, mock_display):
    """Test restore_volumes when container wait returns non-zero exit code"""
    with patch("pathlib.Path.exists", return_value=True):
        mock_client = MagicMock()
        mock_volume = MagicMock()
        mock_volume.name = "test_vol"
        mock_client.volumes.get.side_effect = docker.errors.NotFound("Volume not found")
        mock_client.volumes.create.return_value = mock_volume
        
        # When detach=False, container failures raise exceptions rather than returning exit codes
        mock_client.containers.run.side_effect = docker.errors.ContainerError(
            container=MagicMock(),
            exit_status=1,
            command="tar -xzf /backup/test_vol.tar.gz -C /data",
            image="alpine:latest",
            stderr=b"Restore failed"
        )
        
        client = DockerClient(config=mock_config, display=mock_display)
        client.client = mock_client
        
        result = client.restore_volumes(["test_vol"], Path("/backup/path"))
        
        assert result is False
        mock_client.containers.run.assert_called_once()

def test_restore_volumes_empty_list(mock_config, mock_display):
    """Test restore_volumes with empty volume list"""
    mock_client = MagicMock()
    client = DockerClient(config=mock_config, display=mock_display)
    client.client = mock_client
    
    result = client.restore_volumes([], Path("/backup/path"))
    
    assert result is True
    mock_client.volumes.create.assert_not_called()
    mock_client.containers.run.assert_not_called()

def test_restore_volumes_existing_volume_handling(mock_config, mock_display):
    """Test restore_volumes handles existing volumes correctly"""
    with patch("pathlib.Path.exists", return_value=True):
        mock_client = MagicMock()
        
        # First call creates volume, second call volume already exists
        mock_volume = MagicMock()
        mock_volume.name = "test_vol"
        mock_client.volumes.get.side_effect = docker.errors.NotFound("Volume not found")
        mock_client.volumes.create.side_effect = [
            mock_volume,  # First volume created successfully
            docker.errors.APIError("Volume already exists")  # Second volume already exists
        ]
        
        mock_container = MagicMock()
        mock_container.wait.return_value = {"StatusCode": 0}
        mock_client.containers.run.return_value = mock_container
        
        client = DockerClient(config=mock_config, display=mock_display)
        client.client = mock_client
        
        result = client.restore_volumes(["vol1", "vol2"], Path("/backup/path"))
        
        assert result is False  # Should fail if volume creation fails
        assert mock_client.volumes.create.call_count == 2

def test_restore_volumes_partial_failure(mock_config, mock_display):
    """Test restore_volumes with some volumes failing"""
    with patch("pathlib.Path.exists", return_value=True):
        mock_client = MagicMock()
        
        mock_vol1 = MagicMock()
        mock_vol1.name = "vol1"
        mock_client.volumes.get.side_effect = docker.errors.NotFound("Volume not found")
        mock_client.volumes.create.side_effect = [
            mock_vol1,  # First volume succeeds
            docker.errors.APIError("Volume creation failed")  # Second volume fails
        ]
        
        mock_container = MagicMock()
        mock_container.wait.return_value = {"StatusCode": 0}
        mock_client.containers.run.return_value = mock_container
        
        client = DockerClient(config=mock_config, display=mock_display)
        client.client = mock_client
        
        result = client.restore_volumes(["vol1", "vol2"], Path("/backup/path"))
        
        assert result is False  # Should fail if any volume fails
        assert mock_client.volumes.create.call_count == 2

def test_export_stack_state_success(mock_config, mock_display):
    """Test export_stack_state successful execution with all resource types"""
    with patch("pathlib.Path.mkdir"), patch("builtins.open", mock_open()) as mock_file:
        mock_client = MagicMock()
        mock_client.version.return_value = {"Version": "20.10.0"}
        
        # Mock containers
        mock_container = MagicMock()
        mock_container.name = "test_container"
        mock_container.image.tags = ["test:latest"]
        mock_container.status = "running"
        mock_container.labels = {}
        mock_container.ports = {}
        mock_container.attrs = {
            "Created": "2023-01-01T00:00:00Z",
            "Config": {
                "Env": ["VAR=value"],
                "Cmd": ["nginx"],
                "Volumes": {}
            }
        }
        mock_client.containers.list.return_value = [mock_container]
        
        # Mock volumes
        mock_volume = MagicMock()
        mock_volume.name = "test_volume"
        mock_volume.attrs = {
            "Driver": "local",
            "Mountpoint": "/var/lib/docker/volumes/test_volume",
            "Labels": {},
            "CreatedAt": "2023-01-01T00:00:00Z",
            "Options": {}
        }
        mock_client.volumes.list.return_value = [mock_volume]
        
        # Mock networks
        mock_network = MagicMock()
        mock_network.name = "test_network"
        mock_network.attrs = {
            "Driver": "bridge",
            "Labels": {},
            "Created": "2023-01-01T00:00:00Z",
            "Options": {},
            "IPAM": {"Driver": "default"}
        }
        mock_client.networks.list.return_value = [mock_network]
        
        # Mock images
        mock_image = MagicMock()
        mock_image.id = "image123"
        mock_image.tags = ["test:latest"]
        mock_image.labels = {}
        mock_image.attrs = {
            "Created": "2023-01-01T00:00:00Z",
            "Size": 1000
        }
        mock_client.images.list.return_value = [mock_image]
        
        client = DockerClient(config=mock_config, display=mock_display)
        client.client = mock_client
        
        with patch("json.dump") as mock_json_dump:
            result = client.export_stack_state(Path("/export/path/state.json"))
            
            assert result is True
            mock_json_dump.assert_called_once()
            
            # Verify the structure of exported data
            exported_data = mock_json_dump.call_args[0][0]
            assert "containers" in exported_data
            assert "volumes" in exported_data
            assert "networks" in exported_data
            assert "images" in exported_data
            assert len(exported_data["containers"]) == 1
            assert len(exported_data["volumes"]) == 1
            assert len(exported_data["networks"]) == 1
            assert len(exported_data["images"]) == 1

def test_export_stack_state_no_client(mock_config, mock_display):
    """Test export_stack_state when client is None"""
    client = DockerClient(config=mock_config, display=mock_display)
    client.client = None
    
    result = client.export_stack_state(Path("/export/path/state.json"))
    
    assert result is False

def test_export_stack_state_file_write_error(mock_config, mock_display):
    """Test export_stack_state when file write fails"""
    mock_client = MagicMock()
    mock_client.containers.list.return_value = []
    mock_client.volumes.list.return_value = []
    mock_client.networks.list.return_value = []
    mock_client.images.list.return_value = []
    
    client = DockerClient(config=mock_config, display=mock_display)
    client.client = mock_client
    
    with patch("builtins.open", side_effect=IOError("File write failed")):
        result = client.export_stack_state(Path("/export/path/state.json"))
        
        assert result is False

def test_export_stack_state_containers_api_error(mock_config, mock_display):
    """Test export_stack_state when containers API fails"""
    with patch("pathlib.Path.mkdir"), patch("builtins.open", mock_open()) as mock_file_open:
        mock_client = MagicMock()
        mock_client.containers.list.side_effect = docker.errors.APIError("Containers API failed")
        
        client = DockerClient(config=mock_config, display=mock_display)
        client.client = mock_client
        
        result = client.export_stack_state(Path("/export/path/state.json"))
        
        assert result is True  # Should still succeed even if containers API fails
    
def test_export_stack_state_volumes_api_error(mock_config, mock_display):
    """Test export_stack_state when volumes API fails"""
    with patch("pathlib.Path.mkdir"), patch("builtins.open", mock_open()) as mock_file_open:
        mock_client = MagicMock()
        mock_client.containers.list.return_value = []
        mock_client.volumes.list.side_effect = docker.errors.APIError("Volumes API failed")
        
        client = DockerClient(config=mock_config, display=mock_display)
        client.client = mock_client
        
        result = client.export_stack_state(Path("/export/path/state.json"))
        
        assert result is True  # Should still succeed even if volumes API fails
    
def test_export_stack_state_networks_api_error(mock_config, mock_display):
    """Test export_stack_state when networks API fails"""
    with patch("pathlib.Path.mkdir"), patch("builtins.open", mock_open()) as mock_file_open:
        mock_client = MagicMock()
        mock_client.containers.list.return_value = []
        mock_client.volumes.list.return_value = []
        mock_client.networks.list.side_effect = docker.errors.APIError("Networks API failed")
        
        client = DockerClient(config=mock_config, display=mock_display)
        client.client = mock_client
        
        result = client.export_stack_state(Path("/export/path/state.json"))
        
        assert result is True  # Should still succeed even if networks API fails
    
def test_export_stack_state_images_api_error(mock_config, mock_display):
    """Test export_stack_state when images API fails"""
    with patch("pathlib.Path.mkdir"), patch("builtins.open", mock_open()) as mock_file_open:
        mock_client = MagicMock()
        mock_client.containers.list.return_value = []
        mock_client.volumes.list.return_value = []
        mock_client.networks.list.return_value = []
        mock_client.images.list.side_effect = docker.errors.APIError("Images API failed")
        
        client = DockerClient(config=mock_config, display=mock_display)
        client.client = mock_client
        
        result = client.export_stack_state(Path("/export/path/state.json"))
        
        assert result is True  # Should still succeed even if images API fails
    
def test_export_stack_state_empty_resources(mock_config, mock_display):
    """Test export_stack_state with no resources"""
    with patch("pathlib.Path.mkdir"), patch("builtins.open", mock_open()) as mock_file:
        mock_client = MagicMock()
        mock_client.version.return_value = {"Version": "20.10.0"}
        mock_client.containers.list.return_value = []
        mock_client.volumes.list.return_value = []
        mock_client.networks.list.return_value = []
        mock_client.images.list.return_value = []
        
        client = DockerClient(config=mock_config, display=mock_display)
        client.client = mock_client
        
        with patch("json.dump") as mock_json_dump:
            result = client.export_stack_state(Path("/export/path/state.json"))
            
            assert result is True
            mock_json_dump.assert_called_once()
            
            # Verify empty data structure
            exported_data = mock_json_dump.call_args[0][0]
            assert exported_data["containers"] == []
            assert exported_data["volumes"] == []
            assert exported_data["networks"] == []
            assert exported_data["images"] == []

def test_export_stack_state_partial_api_failure(mock_config, mock_display):
    """Test export_stack_state with partial API failures"""
    with patch("pathlib.Path.mkdir"), patch("builtins.open", mock_open()) as mock_file_open:
        mock_client = MagicMock()
        
        # Containers succeed
        mock_container = MagicMock()
        mock_container.name = "test_container"
        mock_container.image.tags = ["test:latest"]
        mock_container.status = "running"
        mock_container.labels = {}
        mock_container.ports = {}
        mock_container.attrs = {
            "Created": "2023-01-01T00:00:00Z",
            "Config": {
                "Env": ["VAR=value"],
                "Cmd": ["cmd"],
                "Volumes": {}
            }
        }
        mock_client.containers.list.return_value = [mock_container]
        
        # Volumes fail
        mock_client.volumes.list.side_effect = docker.errors.APIError("Volumes API failed")
        
        client = DockerClient(config=mock_config, display=mock_display)
        client.client = mock_client
        
        result = client.export_stack_state(Path("/export/path/state.json"))
        
        assert result is True  # Should still succeed even if some API calls fail
    
def test_export_stack_state_json_serialization_error(mock_config, mock_display):
    """Test export_stack_state when JSON serialization fails"""
    mock_client = MagicMock()
    mock_client.containers.list.return_value = []
    mock_client.volumes.list.return_value = []
    mock_client.networks.list.return_value = []
    mock_client.images.list.return_value = []
    
    client = DockerClient(config=mock_config, display=mock_display)
    client.client = mock_client
    
    with patch("builtins.open", mock_open()):
        with patch("json.dump", side_effect=ValueError("JSON serialization failed")):
            result = client.export_stack_state(Path("/export/path/state.json"))
            
            assert result is False

def test_export_stack_state_directory_creation(mock_config, mock_display):
    """Test export_stack_state creates parent directories"""
    with patch("pathlib.Path.mkdir") as mock_mkdir, patch("builtins.open", mock_open()) as mock_file:
        mock_client = MagicMock()
        mock_client.version.return_value = {"Version": "20.10.0"}
        mock_client.containers.list.return_value = []
        mock_client.volumes.list.return_value = []
        mock_client.networks.list.return_value = []
        mock_client.images.list.return_value = []
        
        client = DockerClient(config=mock_config, display=mock_display)
        client.client = mock_client
        
        with patch("json.dump") as mock_json_dump:
            result = client.export_stack_state(Path("/export/path/state.json"))
            
            assert result is True
            mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)

def test_export_stack_state_complex_data_structure(mock_config, mock_display):
    """Test export_stack_state with complex nested data structures"""
    with patch("pathlib.Path.mkdir"), patch("builtins.open", mock_open()) as mock_file_open:
        mock_client = MagicMock()
        
        # Mock complex container data
        mock_container = MagicMock()
        mock_container.name = "test_container"
        mock_container.image.tags = ["test:latest"]
        mock_container.status = "running"
        mock_container.labels = {"com.docker.compose.project": "test"}
        mock_container.ports = {}
        mock_container.attrs = {
            "Created": "2023-01-01T00:00:00Z",
            "Config": {
                "Env": ["VAR1=value1", "VAR2=value2"],
                "Cmd": ["nginx"],
                "Volumes": {}
            }
        }
        mock_client.containers.list.return_value = [mock_container]
        
        # Mock complex volume data
        mock_volume = MagicMock()
        mock_volume.name = "test_volume"
        mock_volume.attrs = {
            "Driver": "local",
            "Mountpoint": "/var/lib/docker/volumes/test_volume",
            "Labels": {"com.docker.compose.project": "test"},
            "CreatedAt": "2023-01-01T00:00:00Z",
            "Options": {"device": "/dev/sda1", "type": "ext4"}
        }
        mock_client.volumes.list.return_value = [mock_volume]
        
        mock_client.networks.list.return_value = []
        mock_client.images.list.return_value = []
        
        client = DockerClient(config=mock_config, display=mock_display)
        client.client = mock_client
        
        result = client.export_stack_state(Path("/export/path/state.json"))
        
        assert result is True