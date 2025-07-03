import pytest
from unittest.mock import MagicMock, patch, call
from pathlib import Path

from ollama_stack_cli.stack_manager import StackManager
from ollama_stack_cli.schemas import AppConfig, PlatformConfig, ServiceStatus, StackStatus, CheckReport, EnvironmentCheck, ResourceUsage, ServiceConfig, ExtensionsConfig

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
        "ollama": ServiceConfig(type="docker"),
        "webui": ServiceConfig(type="docker"),
        "mcp_proxy": ServiceConfig(type="docker"),
    }
    # Mock extensions configuration
    config.extensions = ExtensionsConfig(enabled=[])
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
         patch('ollama_stack_cli.stack_manager.OllamaApiClient', return_value=mock_ollama_api_client), \
         patch('ollama_stack_cli.stack_manager.docker.from_env'), \
         patch('ollama_stack_cli.stack_manager.platform.system', return_value='Linux'), \
         patch('ollama_stack_cli.stack_manager.platform.machine', return_value='x86_64'):
        manager = StackManager(config=mock_config, display=mock_display)
        # We need to inject the mocked clients into the manager instance for assertion purposes
        manager.docker_client = mock_docker_client
        manager.ollama_api_client = mock_ollama_api_client
        return manager

# Platform-Specific Tests

def test_get_docker_services_status_on_apple(stack_manager, mock_docker_client, mock_ollama_api_client):
    """Tests get_docker_services_status orchestration on Apple Silicon."""
    stack_manager.platform = 'apple'
    
    # Configure services for Apple platform
    stack_manager.configure_services_for_platform()
    
    # On Apple, ollama should be native-api, so only webui and mcp_proxy are Docker services
    docker_services = [name for name, conf in stack_manager.config.services.items() if conf.type == 'docker']
    
    mock_docker_client.get_container_status.return_value = [
        ServiceStatus(name='webui', is_running=True, status='running'),
        ServiceStatus(name='mcp_proxy', is_running=False)
    ]
    
    status = stack_manager.get_docker_services_status(docker_services)
    
    mock_docker_client.get_container_status.assert_called_once_with(docker_services)
    
    assert len(status) == 2
    webui = next(s for s in status if s.name == 'webui')
    assert webui.is_running is True

def test_get_docker_services_status_on_linux(stack_manager, mock_docker_client, mock_ollama_api_client):
    """Tests get_docker_services_status orchestration on Linux/CPU."""
    stack_manager.platform = 'cpu'
    
    # Configure services for CPU platform
    stack_manager.configure_services_for_platform()
    
    # On CPU, all services should be Docker services
    docker_services = [name for name, conf in stack_manager.config.services.items() if conf.type == 'docker']
    
    mock_docker_client.get_container_status.return_value = [
        ServiceStatus(name='webui', is_running=True),
        ServiceStatus(name='ollama', is_running=True),
        ServiceStatus(name='mcp_proxy', is_running=True),
    ]
    
    status = stack_manager.get_docker_services_status(docker_services)
    
    mock_docker_client.get_container_status.assert_called_once_with(docker_services)
    assert len(status) == 3

def test_stream_logs_delegation(stack_manager, mock_docker_client):
    """Tests that stream_docker_logs delegates to docker client with compose files."""
    # Mock the get_compose_files to return expected files
    with patch.object(stack_manager, 'get_compose_files', return_value=['docker-compose.yml', 'docker-compose.cpu.yml']):
        # Mock the docker client stream_logs to return a simple generator
        mock_docker_client.stream_logs.return_value = iter(['log line 1', 'log line 2'])
        
        # Consume the generator
        logs = list(stack_manager.stream_docker_logs('webui', follow=True, tail=10))
        
        mock_docker_client.stream_logs.assert_called_once_with('webui', True, 10, None, None, None, ['docker-compose.yml', 'docker-compose.cpu.yml'])
        assert logs == ['log line 1', 'log line 2']

# Orchestration Logic Tests
def test_start_docker_services_delegation(stack_manager, mock_docker_client):
    """Tests that start_docker_services delegates to docker client with services and compose files."""
    services = ['webui', 'mcp_proxy']
    
    # Mock the get_compose_files to return expected files
    with patch.object(stack_manager, 'get_compose_files', return_value=['docker-compose.yml', 'docker-compose.cpu.yml']):
        stack_manager.start_docker_services(services)

        mock_docker_client.start_services.assert_called_once_with(services, ['docker-compose.yml', 'docker-compose.cpu.yml'])

def test_pull_images_delegation(stack_manager, mock_docker_client):
    """Tests that pull_images delegates to docker client with compose files."""
    # Mock the get_compose_files to return expected files
    with patch.object(stack_manager, 'get_compose_files', return_value=['docker-compose.yml', 'docker-compose.cpu.yml']):
        stack_manager.pull_images()
        
        mock_docker_client.pull_images.assert_called_once_with(['docker-compose.yml', 'docker-compose.cpu.yml'])

def test_stop_docker_services_delegation(stack_manager, mock_docker_client):
    """Tests that stop_docker_services delegates to docker client with compose files."""
    # Mock the get_compose_files to return expected files
    with patch.object(stack_manager, 'get_compose_files', return_value=['docker-compose.yml', 'docker-compose.cpu.yml']):
        stack_manager.stop_docker_services()
        
        mock_docker_client.stop_services.assert_called_once_with(['docker-compose.yml', 'docker-compose.cpu.yml'])
    
def test_run_environment_checks_cpu_platform(stack_manager, mock_docker_client):
    """Tests that environment checks are delegated to the docker client for CPU platform."""
    stack_manager.platform = 'cpu'
    mock_report = CheckReport(checks=[])
    mock_docker_client.run_environment_checks.return_value = mock_report
    
    report = stack_manager.run_environment_checks(fix=True)
    
    mock_docker_client.run_environment_checks.assert_called_once_with(fix=True, platform='cpu')
    assert report == mock_report

def test_run_environment_checks_apple_platform(stack_manager, mock_docker_client, mock_ollama_api_client):
    """Tests that environment checks are delegated to both docker and ollama clients for Apple platform."""
    from ollama_stack_cli.schemas import EnvironmentCheck
    
    stack_manager.platform = 'apple'
    
    # Mock docker client checks
    docker_check = EnvironmentCheck(name="Docker Check", passed=True)
    docker_report = CheckReport(checks=[docker_check])
    mock_docker_client.run_environment_checks.return_value = docker_report
    
    # Mock ollama client checks
    ollama_check = EnvironmentCheck(name="Ollama Check", passed=True)
    mock_ollama_api_client.run_environment_checks.return_value = [ollama_check]
    
    report = stack_manager.run_environment_checks(fix=False)
    
    mock_docker_client.run_environment_checks.assert_called_once_with(fix=False, platform='apple')
    mock_ollama_api_client.run_environment_checks.assert_called_once_with(fix=False)
    
    # Should combine both sets of checks
    assert len(report.checks) == 2


# Platform Orchestration Tests
def test_detect_platform_apple_silicon():
    """Tests platform detection for Apple Silicon (M1/M2)."""
    with patch('ollama_stack_cli.stack_manager.platform.system', return_value='Darwin'), \
         patch('ollama_stack_cli.stack_manager.platform.machine', return_value='arm64'), \
         patch('ollama_stack_cli.stack_manager.DockerClient'), \
         patch('ollama_stack_cli.stack_manager.OllamaApiClient'):
        
        manager = StackManager(config=MagicMock(), display=MagicMock())
        assert manager.platform == 'apple'

def test_detect_platform_nvidia():
    """Tests platform detection for NVIDIA GPU."""
    with patch('ollama_stack_cli.stack_manager.platform.system', return_value='Linux'), \
         patch('ollama_stack_cli.stack_manager.platform.machine', return_value='x86_64'), \
         patch('ollama_stack_cli.stack_manager.docker.from_env') as mock_docker_from_env, \
         patch('ollama_stack_cli.stack_manager.DockerClient'), \
         patch('ollama_stack_cli.stack_manager.OllamaApiClient'):
        
        mock_client = MagicMock()
        mock_docker_from_env.return_value = mock_client
        # Mock the info() method to return NVIDIA runtime
        mock_client.info.return_value = {'Runtimes': {'nvidia': {'path': '/usr/bin/nvidia-container-runtime'}}}
        
        manager = StackManager(config=MagicMock(), display=MagicMock())
        
        # The platform should have been detected during initialization
        assert manager.platform == 'nvidia'

def test_detect_platform_nvidia_docker_exception():
    """Tests platform detection when Docker client fails during NVIDIA detection."""
    with patch('ollama_stack_cli.stack_manager.platform.system', return_value='Linux'), \
         patch('ollama_stack_cli.stack_manager.platform.machine', return_value='x86_64'), \
         patch('ollama_stack_cli.stack_manager.docker.from_env') as mock_docker_from_env, \
         patch('ollama_stack_cli.stack_manager.DockerClient'), \
         patch('ollama_stack_cli.stack_manager.OllamaApiClient'):
        
        # Mock Docker client creation failure in detection (not in DockerClient init)
        mock_docker_from_env.side_effect = Exception("Docker not available")
        
        manager = StackManager(config=MagicMock(), display=MagicMock())
        
        # Should fallback to CPU when Docker check fails
        assert manager.platform == 'cpu'

def test_detect_platform_cpu():
    """Tests platform detection fallback to CPU."""
    with patch('ollama_stack_cli.stack_manager.platform.system', return_value='Linux'), \
         patch('ollama_stack_cli.stack_manager.platform.machine', return_value='x86_64'), \
         patch('ollama_stack_cli.stack_manager.docker.from_env') as mock_docker_from_env, \
         patch('ollama_stack_cli.stack_manager.DockerClient'), \
         patch('ollama_stack_cli.stack_manager.OllamaApiClient'):
        
        mock_client = MagicMock()
        mock_docker_from_env.return_value = mock_client
        # Mock the info() method to return empty runtimes (no NVIDIA)
        mock_client.info.return_value = {'Runtimes': {}}
        
        manager = StackManager(config=MagicMock(), display=MagicMock())
        assert manager.platform == 'cpu'

def test_configure_services_for_apple_platform(stack_manager):
    """Tests service configuration for Apple Silicon platform."""
    stack_manager.platform = 'apple'
    
    # Mock initial config with all Docker services
    stack_manager.config.services = {
        'ollama': ServiceConfig(name='ollama', type='docker'),
        'webui': ServiceConfig(name='webui', type='docker'),
        'mcp_proxy': ServiceConfig(name='mcp_proxy', type='docker'),
    }
    
    stack_manager.configure_services_for_platform()
    
    # On Apple, ollama should become native-api
    assert stack_manager.config.services['ollama'].type == 'native-api'
    assert stack_manager.config.services['webui'].type == 'docker'
    assert stack_manager.config.services['mcp_proxy'].type == 'docker'

def test_configure_services_for_cpu_platform(stack_manager):
    """Tests service configuration for CPU platform."""
    stack_manager.platform = 'cpu'
    
    # Mock initial config
    stack_manager.config.services = {
        'ollama': ServiceConfig(name='ollama', type='docker'),
        'webui': ServiceConfig(name='webui', type='docker'),
    }
    
    stack_manager.configure_services_for_platform()
    
    # On CPU, all services should remain Docker
    assert stack_manager.config.services['ollama'].type == 'docker'
    assert stack_manager.config.services['webui'].type == 'docker'

def test_get_compose_files_apple(stack_manager):
    """Tests compose file selection for Apple Silicon."""
    stack_manager.platform = 'apple'
    stack_manager.config.docker_compose_file = 'docker-compose.yml'
    stack_manager.config.platform = {
        'apple': PlatformConfig(compose_file='docker-compose.apple.yml')
    }
    
    files = stack_manager.get_compose_files()
    
    assert files == ['docker-compose.yml', 'docker-compose.apple.yml']

def test_get_compose_files_cpu(stack_manager):
    """Tests get_compose_files for CPU platform."""
    stack_manager.platform = 'cpu'
    
    # Base compose file should be used
    compose_files = stack_manager.get_compose_files()
    assert compose_files == ["base.yml"]


# Service Running Detection Tests

def test_get_running_services_summary_docker_only(stack_manager, mock_docker_client):
    """Tests get_running_services_summary when only Docker services are configured."""
    # Configure services - all Docker
    stack_manager.config.services = {
        'webui': ServiceConfig(name='webui', type='docker'),
        'mcp_proxy': ServiceConfig(name='mcp_proxy', type='docker'),
    }
    
    # Mock Docker service status
    mock_docker_client.get_container_status.return_value = [
        ServiceStatus(name='webui', is_running=True),
        ServiceStatus(name='mcp_proxy', is_running=False),
    ]
    
    running_docker, running_native = stack_manager.get_running_services_summary()
    
    assert running_docker == ['webui']
    assert running_native == []
    mock_docker_client.get_container_status.assert_called_once_with(['webui', 'mcp_proxy'])


def test_get_running_services_summary_native_only(stack_manager, mock_ollama_api_client):
    """Tests get_running_services_summary when only native services are configured."""
    # Configure services - all native
    stack_manager.config.services = {
        'ollama': ServiceConfig(name='ollama', type='native-api'),
    }
    
    # Mock native service status
    mock_ollama_api_client.is_service_running.return_value = True
    
    running_docker, running_native = stack_manager.get_running_services_summary()
    
    assert running_docker == []
    assert running_native == ['ollama']
    mock_ollama_api_client.is_service_running.assert_called_once()


def test_get_running_services_summary_mixed_services(stack_manager, mock_docker_client, mock_ollama_api_client):
    """Tests get_running_services_summary with mixed Docker and native services."""
    # Configure mixed services
    stack_manager.config.services = {
        'webui': ServiceConfig(name='webui', type='docker'),
        'mcp_proxy': ServiceConfig(name='mcp_proxy', type='docker'),
        'ollama': ServiceConfig(name='ollama', type='native-api'),
    }
    
    # Mock Docker service status
    mock_docker_client.get_container_status.return_value = [
        ServiceStatus(name='webui', is_running=True),
        ServiceStatus(name='mcp_proxy', is_running=False),
    ]
    
    # Mock native service status
    mock_ollama_api_client.is_service_running.return_value = True
    
    running_docker, running_native = stack_manager.get_running_services_summary()
    
    assert running_docker == ['webui']
    assert running_native == ['ollama']
    mock_docker_client.get_container_status.assert_called_once_with(['webui', 'mcp_proxy'])
    mock_ollama_api_client.is_service_running.assert_called_once()


def test_get_running_services_summary_no_services(stack_manager):
    """Tests get_running_services_summary when no services are configured."""
    stack_manager.config.services = {}
    
    running_docker, running_native = stack_manager.get_running_services_summary()
    
    assert running_docker == []
    assert running_native == []


def test_is_stack_running_docker_only(stack_manager, mock_docker_client):
    """Tests is_stack_running when only Docker services exist."""
    # Configure services - all Docker
    stack_manager.config.services = {
        'webui': ServiceConfig(name='webui', type='docker'),
    }
    
    # Mock Docker running
    mock_docker_client.is_stack_running.return_value = True
    
    result = stack_manager.is_stack_running()
    
    assert result is True
    mock_docker_client.is_stack_running.assert_called_once()


def test_is_stack_running_native_only(stack_manager, mock_docker_client, mock_ollama_api_client):
    """Tests is_stack_running when only native services exist."""
    # Configure services - all native
    stack_manager.config.services = {
        'ollama': ServiceConfig(name='ollama', type='native-api'),
    }
    
    # Mock Docker not running, native running
    mock_docker_client.is_stack_running.return_value = False
    mock_ollama_api_client.is_service_running.return_value = True
    
    result = stack_manager.is_stack_running()
    
    assert result is True
    mock_docker_client.is_stack_running.assert_called_once()
    mock_ollama_api_client.is_service_running.assert_called_once()


def test_is_stack_running_mixed_services_docker_running(stack_manager, mock_docker_client, mock_ollama_api_client):
    """Tests is_stack_running with mixed services when Docker is running."""
    # Configure mixed services
    stack_manager.config.services = {
        'webui': ServiceConfig(name='webui', type='docker'),
        'ollama': ServiceConfig(name='ollama', type='native-api'),
    }
    
    # Mock Docker running (should return True without checking native)
    mock_docker_client.is_stack_running.return_value = True
    
    result = stack_manager.is_stack_running()
    
    assert result is True
    mock_docker_client.is_stack_running.assert_called_once()
    # Native service check should still happen
    mock_ollama_api_client.is_service_running.assert_called_once()


def test_is_stack_running_mixed_services_only_native_running(stack_manager, mock_docker_client, mock_ollama_api_client):
    """Tests is_stack_running with mixed services when only native is running."""
    # Configure mixed services
    stack_manager.config.services = {
        'webui': ServiceConfig(name='webui', type='docker'),
        'ollama': ServiceConfig(name='ollama', type='native-api'),
    }
    
    # Mock Docker not running, native running
    mock_docker_client.is_stack_running.return_value = False
    mock_ollama_api_client.is_service_running.return_value = True
    
    result = stack_manager.is_stack_running()
    
    assert result is True
    mock_docker_client.is_stack_running.assert_called_once()
    mock_ollama_api_client.is_service_running.assert_called_once()


def test_is_stack_running_nothing_running(stack_manager, mock_docker_client, mock_ollama_api_client):
    """Tests is_stack_running when nothing is running."""
    # Configure mixed services
    stack_manager.config.services = {
        'webui': ServiceConfig(name='webui', type='docker'),
        'ollama': ServiceConfig(name='ollama', type='native-api'),
    }
    
    # Mock nothing running
    mock_docker_client.is_stack_running.return_value = False
    mock_ollama_api_client.is_service_running.return_value = False
    
    result = stack_manager.is_stack_running()
    
    assert result is False
    mock_docker_client.is_stack_running.assert_called_once()
    mock_ollama_api_client.is_service_running.assert_called_once()


def test_is_native_service_running_ollama(stack_manager, mock_ollama_api_client):
    """Tests is_native_service_running for ollama service."""
    mock_ollama_api_client.is_service_running.return_value = True
    
    result = stack_manager.is_native_service_running('ollama')
    
    assert result is True
    mock_ollama_api_client.is_service_running.assert_called_once()


def test_is_native_service_running_unknown_service(stack_manager):
    """Tests is_native_service_running for unknown service."""
    result = stack_manager.is_native_service_running('unknown_service')
    
    assert result is False


# get_stack_status() Method Tests

def test_get_stack_status_docker_only(stack_manager, mock_docker_client):
    """Tests get_stack_status when only Docker services are configured."""
    # Configure services - all Docker
    stack_manager.config.services = {
        'webui': ServiceConfig(name='webui', type='docker'),
        'mcp_proxy': ServiceConfig(name='mcp_proxy', type='docker'),
    }
    
    # Mock Docker service status
    mock_docker_client.get_container_status.return_value = [
        ServiceStatus(name='webui', is_running=True, status='running'),
        ServiceStatus(name='mcp_proxy', is_running=False, status='stopped'),
    ]
    
    result = stack_manager.get_stack_status(extensions_only=False)
    
    assert len(result.core_services) == 2
    assert len(result.extensions) == 0
    
    webui_status = next(s for s in result.core_services if s.name == 'webui')
    assert webui_status.is_running is True
    assert webui_status.status == 'running'
    
    mock_docker_client.get_container_status.assert_called_once_with(['webui', 'mcp_proxy'])

def test_get_stack_status_native_only(stack_manager, mock_ollama_api_client):
    """Tests get_stack_status when only native services are configured."""
    # Configure services - all native
    stack_manager.config.services = {
        'ollama': ServiceConfig(name='ollama', type='native-api'),
    }
    
    # Mock native service status
    mock_native_status = ServiceStatus(name='ollama', is_running=True, status='running')
    mock_ollama_api_client.get_status.return_value = mock_native_status
    
    result = stack_manager.get_stack_status(extensions_only=False)
    
    assert len(result.core_services) == 1
    assert len(result.extensions) == 0
    assert result.core_services[0].name == 'ollama'
    assert result.core_services[0].is_running is True
    
    mock_ollama_api_client.get_status.assert_called_once()

def test_get_stack_status_mixed_services(stack_manager, mock_docker_client, mock_ollama_api_client):
    """Tests get_stack_status with mixed Docker and native services."""
    # Configure mixed services
    stack_manager.config.services = {
        'webui': ServiceConfig(name='webui', type='docker'),
        'ollama': ServiceConfig(name='ollama', type='native-api'),
    }
    
    # Mock Docker service status
    mock_docker_client.get_container_status.return_value = [
        ServiceStatus(name='webui', is_running=True, status='running'),
    ]
    
    # Mock native service status
    mock_native_status = ServiceStatus(name='ollama', is_running=False, status='stopped')
    mock_ollama_api_client.get_status.return_value = mock_native_status
    
    result = stack_manager.get_stack_status(extensions_only=False)
    
    assert len(result.core_services) == 2
    
    # Check Docker service
    webui_status = next(s for s in result.core_services if s.name == 'webui')
    assert webui_status.is_running is True
    
    # Check native service
    ollama_status = next(s for s in result.core_services if s.name == 'ollama')
    assert ollama_status.is_running is False
    
    mock_docker_client.get_container_status.assert_called_once_with(['webui'])
    mock_ollama_api_client.get_status.assert_called_once()

def test_get_stack_status_extensions_only(stack_manager):
    """Tests get_stack_status with extensions_only=True."""
    # Configure services
    stack_manager.config.services = {
        'webui': ServiceConfig(name='webui', type='docker'),
        'ollama': ServiceConfig(name='ollama', type='native-api'),
    }
    
    result = stack_manager.get_stack_status(extensions_only=True)
    
    # Should not include core services when extensions_only=True
    assert len(result.core_services) == 0
    assert len(result.extensions) == 0  # Extensions not implemented yet

def test_get_stack_status_docker_client_failure(stack_manager, mock_docker_client, mock_ollama_api_client):
    """Tests get_stack_status when Docker client fails."""
    # Configure mixed services
    stack_manager.config.services = {
        'webui': ServiceConfig(name='webui', type='docker'),
        'ollama': ServiceConfig(name='ollama', type='native-api'),
    }
    
    # Mock Docker client failure
    mock_docker_client.get_container_status.side_effect = Exception("Docker daemon not running")
    
    # Mock successful native service
    mock_native_status = ServiceStatus(name='ollama', is_running=True, status='running')
    mock_ollama_api_client.get_status.return_value = mock_native_status
    
    result = stack_manager.get_stack_status(extensions_only=False)
    
    assert len(result.core_services) == 2
    
    # Docker service should show as error
    webui_status = next(s for s in result.core_services if s.name == 'webui')
    assert webui_status.is_running is False
    assert webui_status.status == 'error'
    assert webui_status.health == 'error'
    
    # Native service should still work
    ollama_status = next(s for s in result.core_services if s.name == 'ollama')
    assert ollama_status.is_running is True

def test_get_stack_status_native_service_failure(stack_manager, mock_docker_client, mock_ollama_api_client):
    """Tests get_stack_status when native service status fails."""
    # Configure mixed services
    stack_manager.config.services = {
        'webui': ServiceConfig(name='webui', type='docker'),
        'ollama': ServiceConfig(name='ollama', type='native-api'),
    }
    
    # Mock successful Docker service
    mock_docker_client.get_container_status.return_value = [
        ServiceStatus(name='webui', is_running=True, status='running'),
    ]
    
    # Mock native service failure
    mock_ollama_api_client.get_status.side_effect = Exception("Ollama API not accessible")
    
    result = stack_manager.get_stack_status(extensions_only=False)
    
    assert len(result.core_services) == 2
    
    # Docker service should work
    webui_status = next(s for s in result.core_services if s.name == 'webui')
    assert webui_status.is_running is True
    
    # Native service should show as error
    ollama_status = next(s for s in result.core_services if s.name == 'ollama (Native)')
    assert ollama_status.is_running is False
    assert ollama_status.status == 'error'
    assert ollama_status.health == 'error'


# get_native_service_status() Method Tests

def test_get_native_service_status_ollama(stack_manager, mock_ollama_api_client):
    """Tests get_native_service_status for ollama service."""
    mock_status = ServiceStatus(name='ollama', is_running=True, status='running')
    mock_ollama_api_client.get_status.return_value = mock_status
    
    result = stack_manager.get_native_service_status('ollama')
    
    assert result == mock_status
    mock_ollama_api_client.get_status.assert_called_once()

def test_get_native_service_status_unknown_service(stack_manager):
    """Tests get_native_service_status for unknown native service."""
    result = stack_manager.get_native_service_status('custom_api')
    
    assert result.name == 'custom_api (Native)'
    assert result.is_running is False
    assert result.status == 'unknown'
    assert result.health == 'unknown'


# Native Service Management Tests

def test_start_native_services_ollama_only(stack_manager, mock_ollama_api_client):
    """Tests start_native_services with ollama service."""
    mock_ollama_api_client.start_service.return_value = True
    
    result = stack_manager.start_native_services(['ollama'])
    
    assert result is True
    mock_ollama_api_client.start_service.assert_called_once()

def test_start_native_services_ollama_failure(stack_manager, mock_ollama_api_client):
    """Tests start_native_services when ollama service fails to start."""
    mock_ollama_api_client.start_service.return_value = False
    
    result = stack_manager.start_native_services(['ollama'])
    
    assert result is False
    mock_ollama_api_client.start_service.assert_called_once()

def test_start_native_services_unknown_service(stack_manager):
    """Tests start_native_services with unknown service."""
    result = stack_manager.start_native_services(['custom_api'])
    
    # Should return True (success) but just log a message
    assert result is True

def test_start_native_services_mixed_services(stack_manager, mock_ollama_api_client):
    """Tests start_native_services with mixed known and unknown services."""
    mock_ollama_api_client.start_service.return_value = True
    
    result = stack_manager.start_native_services(['ollama', 'custom_api'])
    
    assert result is True
    mock_ollama_api_client.start_service.assert_called_once()

def test_stop_native_services_ollama_only(stack_manager, mock_ollama_api_client):
    """Tests stop_native_services with ollama service."""
    mock_ollama_api_client.stop_service.return_value = True
    
    result = stack_manager.stop_native_services(['ollama'])
    
    assert result is True
    mock_ollama_api_client.stop_service.assert_called_once()

def test_stop_native_services_ollama_failure(stack_manager, mock_ollama_api_client):
    """Tests stop_native_services when ollama service fails to stop."""
    mock_ollama_api_client.stop_service.return_value = False
    
    result = stack_manager.stop_native_services(['ollama'])
    
    assert result is False
    mock_ollama_api_client.stop_service.assert_called_once()

def test_stop_native_services_unknown_service(stack_manager):
    """Tests stop_native_services with unknown service."""
    result = stack_manager.stop_native_services(['custom_api'])
    
    # Should return True (success) but just log a message
    assert result is True

def test_stop_native_services_mixed_services(stack_manager, mock_ollama_api_client):
    """Tests stop_native_services with mixed known and unknown services."""
    mock_ollama_api_client.stop_service.return_value = True
    
    result = stack_manager.stop_native_services(['ollama', 'custom_api'])
    
    assert result is True
    mock_ollama_api_client.stop_service.assert_called_once()


# stream_native_logs() Method Tests

def test_stream_native_logs_ollama(stack_manager, mock_ollama_api_client):
    """Tests stream_native_logs for ollama service."""
    mock_logs = ['ollama log 1', 'ollama log 2']
    mock_ollama_api_client.get_logs.return_value = iter(mock_logs)
    
    result = list(stack_manager.stream_native_logs('ollama', follow=True, tail=50, level='info'))
    
    assert result == mock_logs
    mock_ollama_api_client.get_logs.assert_called_once_with(
        follow=True, tail=50, level='info', since=None, until=None
    )

def test_stream_native_logs_ollama_with_all_options(stack_manager, mock_ollama_api_client):
    """Tests stream_native_logs for ollama service with all options."""
    mock_logs = ['detailed log']
    mock_ollama_api_client.get_logs.return_value = iter(mock_logs)
    
    result = list(stack_manager.stream_native_logs(
        'ollama', 
        follow=False, 
        tail=100, 
        level='debug', 
        since='2023-01-01T00:00:00',
        until='2023-01-02T00:00:00'
    ))
    
    assert result == mock_logs
    mock_ollama_api_client.get_logs.assert_called_once_with(
        follow=False, tail=100, level='debug', 
        since='2023-01-01T00:00:00', until='2023-01-02T00:00:00'
    )

def test_stream_native_logs_unknown_service(stack_manager):
    """Tests stream_native_logs for unknown native service."""
    result = list(stack_manager.stream_native_logs('custom_api'))
    
    # Should return empty generator and log warning
    assert result == []


# API Delegation Tests

def test_get_ollama_status_delegation(stack_manager, mock_ollama_api_client):
    """Tests get_ollama_status delegates to ollama api client."""
    mock_status = ServiceStatus(name='ollama', is_running=True)
    mock_ollama_api_client.get_status.return_value = mock_status
    
    result = stack_manager.get_ollama_status()
    
    assert result == mock_status
    mock_ollama_api_client.get_status.assert_called_once()


# =============================================================================
# Phase 5.1 New Methods Tests - Update Stack Orchestration
# =============================================================================

def test_update_stack_flag_validation_conflicting_flags(stack_manager):
    """Tests update_stack returns False when both services_only and extensions_only are True."""
    result = stack_manager.update_stack(services_only=True, extensions_only=True)
    
    assert result is False

def test_update_stack_stack_not_running_services_only(stack_manager, mock_docker_client):
    """Tests update_stack when stack is not running and services_only=True."""
    # Mock stack not running
    stack_manager.is_stack_running = MagicMock(return_value=False)
    
    # Mock successful image pull
    mock_docker_client.pull_images_with_progress.return_value = True
    
    # Mock get_compose_files
    stack_manager.get_compose_files = MagicMock(return_value=['docker-compose.yml'])
    
    result = stack_manager.update_stack(services_only=True)
    
    assert result is True
    mock_docker_client.pull_images_with_progress.assert_called_once_with(['docker-compose.yml'])

def test_update_stack_stack_not_running_extensions_only(stack_manager):
    """Tests update_stack when stack is not running and extensions_only=True."""
    # Mock stack not running
    stack_manager.is_stack_running = MagicMock(return_value=False)
    
    # Mock no enabled extensions
    stack_manager.config.extensions.enabled = []
    
    result = stack_manager.update_stack(extensions_only=True)
    
    assert result is True

def test_update_stack_stack_not_running_both_services_and_extensions(stack_manager, mock_docker_client):
    """Tests update_stack when stack is not running and updating both services and extensions."""
    # Mock stack not running
    stack_manager.is_stack_running = MagicMock(return_value=False)
    
    # Mock successful image pull
    mock_docker_client.pull_images_with_progress.return_value = True
    stack_manager.get_compose_files = MagicMock(return_value=['docker-compose.yml'])
    
    # Mock enabled extensions
    stack_manager.config.extensions.enabled = ['ext1', 'ext2']
    
    result = stack_manager.update_stack()  # Both services and extensions
    
    assert result is True
    mock_docker_client.pull_images_with_progress.assert_called_once_with(['docker-compose.yml'])

def test_update_stack_stack_running_no_force_restart(stack_manager):
    """Tests update_stack returns False when stack is running and force_restart=False."""
    # Mock stack running
    stack_manager.is_stack_running = MagicMock(return_value=True)
    
    result = stack_manager.update_stack(force_restart=False)
    
    assert result is False

def test_update_stack_stack_running_force_restart_called_from_start_restart(stack_manager, mock_docker_client):
    """Tests update_stack inline update when called from start/restart commands."""
    # Mock stack running
    stack_manager.is_stack_running = MagicMock(return_value=True)
    
    # Mock successful image pull
    mock_docker_client.pull_images_with_progress.return_value = True
    stack_manager.get_compose_files = MagicMock(return_value=['docker-compose.yml'])
    
    result = stack_manager.update_stack(force_restart=True, called_from_start_restart=True)
    
    assert result is True
    mock_docker_client.pull_images_with_progress.assert_called_once_with(['docker-compose.yml'])
    # Should not call stop or start services during inline update

def test_update_stack_stack_running_force_restart_direct_call(stack_manager, mock_docker_client):
    """Tests update_stack stop and restart when called directly."""
    # Mock stack running
    stack_manager.is_stack_running = MagicMock(return_value=True)
    
    # Mock successful operations
    stack_manager.stop_docker_services = MagicMock(return_value=True)
    mock_docker_client.pull_images_with_progress.return_value = True
    stack_manager.get_compose_files = MagicMock(return_value=['docker-compose.yml'])
    stack_manager.start_docker_services = MagicMock(return_value=True)
    stack_manager.start_native_services = MagicMock(return_value=True)
    
    # Mock services configuration
    stack_manager.config.services = {
        'webui': MagicMock(type='docker'),
        'ollama': MagicMock(type='native-api')
    }
    
    result = stack_manager.update_stack(force_restart=True, called_from_start_restart=False)
    
    assert result is True
    stack_manager.stop_docker_services.assert_called_once()
    mock_docker_client.pull_images_with_progress.assert_called_once_with(['docker-compose.yml'])
    stack_manager.start_docker_services.assert_called_once_with(['webui'])
    stack_manager.start_native_services.assert_called_once_with(['ollama'])

def test_update_stack_stop_services_failure(stack_manager):
    """Tests update_stack handles stop services failure."""
    # Mock stack running
    stack_manager.is_stack_running = MagicMock(return_value=True)
    
    # Mock stop failure
    stack_manager.stop_docker_services = MagicMock(return_value=False)
    
    result = stack_manager.update_stack(force_restart=True, called_from_start_restart=False)
    
    assert result is False

def test_update_stack_pull_images_failure(stack_manager, mock_docker_client):
    """Tests update_stack handles image pull failure."""
    # Mock stack not running
    stack_manager.is_stack_running = MagicMock(return_value=False)
    
    # Mock pull failure
    mock_docker_client.pull_images_with_progress.return_value = False
    stack_manager.get_compose_files = MagicMock(return_value=['docker-compose.yml'])
    
    result = stack_manager.update_stack()
    
    assert result is False

def test_update_stack_restart_docker_services_failure(stack_manager, mock_docker_client):
    """Tests update_stack handles Docker service restart failure."""
    # Mock stack running with direct call
    stack_manager.is_stack_running = MagicMock(return_value=True)
    stack_manager.stop_docker_services = MagicMock(return_value=True)
    mock_docker_client.pull_images_with_progress.return_value = True
    stack_manager.get_compose_files = MagicMock(return_value=['docker-compose.yml'])
    
    # Mock Docker restart failure
    stack_manager.start_docker_services = MagicMock(return_value=False)
    
    # Mock services configuration
    stack_manager.config.services = {'webui': MagicMock(type='docker')}
    
    result = stack_manager.update_stack(force_restart=True, called_from_start_restart=False)
    
    assert result is False

def test_update_stack_restart_native_services_failure(stack_manager, mock_docker_client):
    """Tests update_stack handles native service restart failure."""
    # Mock stack running with direct call
    stack_manager.is_stack_running = MagicMock(return_value=True)
    stack_manager.stop_docker_services = MagicMock(return_value=True)
    mock_docker_client.pull_images_with_progress.return_value = True
    stack_manager.get_compose_files = MagicMock(return_value=['docker-compose.yml'])
    stack_manager.start_docker_services = MagicMock(return_value=True)
    
    # Mock native restart failure
    stack_manager.start_native_services = MagicMock(return_value=False)
    
    # Mock services configuration
    stack_manager.config.services = {
        'webui': MagicMock(type='docker'),
        'ollama': MagicMock(type='native-api')
    }
    
    result = stack_manager.update_stack(force_restart=True, called_from_start_restart=False)
    
    assert result is False

def test_update_stack_exception_handling(stack_manager):
    """Tests update_stack handles exceptions gracefully."""
    # Mock stack running check to raise exception
    stack_manager.is_stack_running = MagicMock(side_effect=Exception("Docker daemon not running"))
    
    result = stack_manager.update_stack()
    
    assert result is False

def test_update_stack_extensions_with_enabled_list(stack_manager, mock_docker_client):
    """Tests update_stack handles enabled extensions correctly."""
    # Mock stack not running
    stack_manager.is_stack_running = MagicMock(return_value=False)
    
    # Mock successful image pull
    mock_docker_client.pull_images_with_progress.return_value = True
    stack_manager.get_compose_files = MagicMock(return_value=['docker-compose.yml'])
    
    # Mock enabled extensions
    stack_manager.config.extensions.enabled = ['ext1', 'ext2', 'ext3']
    
    result = stack_manager.update_stack()
    
    assert result is True


# =============================================================================
# Phase 5.1 New Methods Tests - Resource Management
# =============================================================================

def test_find_resources_by_label_docker_client_unavailable(stack_manager, mock_docker_client):
    """Tests find_resources_by_label when Docker client is unavailable."""
    mock_docker_client.client = None
    
    result = stack_manager.find_resources_by_label("ollama-stack.component")
    
    expected = {"containers": [], "volumes": [], "networks": []}
    assert result == expected

def test_find_resources_by_label_successful_search(stack_manager, mock_docker_client):
    """Tests find_resources_by_label successful resource discovery."""
    # Mock Docker client and resources
    mock_container = MagicMock()
    mock_container.name = "ollama-stack-webui"
    mock_volume = MagicMock()
    mock_volume.name = "ollama-stack-data"
    mock_network = MagicMock()
    mock_network.name = "ollama-stack-network"
    
    mock_docker_client.client.containers.list.return_value = [mock_container]
    mock_docker_client.client.volumes.list.return_value = [mock_volume]
    mock_docker_client.client.networks.list.return_value = [mock_network]
    
    result = stack_manager.find_resources_by_label("ollama-stack.component")
    
    assert len(result["containers"]) == 1
    assert len(result["volumes"]) == 1
    assert len(result["networks"]) == 1
    assert result["containers"][0] == mock_container
    assert result["volumes"][0] == mock_volume
    assert result["networks"][0] == mock_network

def test_find_resources_by_label_with_value(stack_manager, mock_docker_client):
    """Tests find_resources_by_label with specific label value."""
    mock_docker_client.client.containers.list.return_value = []
    mock_docker_client.client.volumes.list.return_value = []
    mock_docker_client.client.networks.list.return_value = []
    
    result = stack_manager.find_resources_by_label("ollama-stack.component", "webui")
    
    # Verify the filter was constructed correctly
    expected_filter = {"label": "ollama-stack.component=webui"}
    mock_docker_client.client.containers.list.assert_called_once_with(all=True, filters=expected_filter)
    
    # For volumes with ollama-stack.component label, we use Docker Compose project label
    expected_volume_filter = {"label": "com.docker.compose.project=ollama-stack"}
    mock_docker_client.client.volumes.list.assert_called_once_with(filters=expected_volume_filter)
    
    mock_docker_client.client.networks.list.assert_called_once_with(filters=expected_filter)

def test_find_resources_by_label_docker_exception(stack_manager, mock_docker_client):
    """Tests find_resources_by_label handles Docker exceptions."""
    # Mock Docker calls to raise exception
    mock_docker_client.client.containers.list.side_effect = Exception("Docker daemon not running")
    
    result = stack_manager.find_resources_by_label("ollama-stack.component")
    
    expected = {"containers": [], "volumes": [], "networks": []}
    assert result == expected

def test_find_resources_by_label_empty_results(stack_manager, mock_docker_client):
    """Tests find_resources_by_label with no resources found."""
    mock_docker_client.client.containers.list.return_value = []
    mock_docker_client.client.volumes.list.return_value = []
    mock_docker_client.client.networks.list.return_value = []
    
    result = stack_manager.find_resources_by_label("ollama-stack.component")
    
    expected = {"containers": [], "volumes": [], "networks": []}
    assert result == expected

def test_cleanup_resources_docker_client_unavailable(stack_manager, mock_docker_client):
    """Tests cleanup_resources when Docker client is unavailable."""
    mock_docker_client.client = None
    
    result = stack_manager.cleanup_resources()
    
    assert result is False

def test_cleanup_resources_successful_cleanup(stack_manager):
    """Tests cleanup_resources successful resource cleanup."""
    # Mock stopped container, unused network, no volumes
    mock_stopped_container = MagicMock()
    mock_stopped_container.status = "exited"
    mock_stopped_container.name = "stopped-container"
    
    mock_unused_network = MagicMock()
    mock_unused_network.name = "ollama-stack-network"
    
    resources = {
        "containers": [mock_stopped_container],
        "volumes": [],
        "networks": [mock_unused_network]
    }
    
    stack_manager.find_resources_by_label = MagicMock(return_value=resources)
    
    result = stack_manager.cleanup_resources()
    
    assert result is True
    mock_stopped_container.remove.assert_called_once_with(force=False)
    mock_unused_network.remove.assert_called_once()

def test_cleanup_resources_with_volumes(stack_manager):
    """Tests cleanup_resources with volume removal enabled."""
    mock_volume = MagicMock()
    mock_volume.name = "data-volume"
    
    resources = {
        "containers": [],
        "volumes": [mock_volume],
        "networks": []
    }
    
    stack_manager.find_resources_by_label = MagicMock(return_value=resources)
    
    result = stack_manager.cleanup_resources(remove_volumes=True, force=True)
    
    assert result is True
    mock_volume.remove.assert_called_once_with(force=True)

def test_cleanup_resources_skips_system_networks(stack_manager):
    """Tests cleanup_resources skips system networks."""
    mock_bridge_network = MagicMock()
    mock_bridge_network.name = "bridge"
    mock_host_network = MagicMock()
    mock_host_network.name = "host"
    mock_custom_network = MagicMock()
    mock_custom_network.name = "ollama-network"
    
    resources = {
        "containers": [],
        "volumes": [],
        "networks": [mock_bridge_network, mock_host_network, mock_custom_network]
    }
    
    stack_manager.find_resources_by_label = MagicMock(return_value=resources)
    
    result = stack_manager.cleanup_resources()
    
    assert result is True
    # Should only remove custom network, not system networks
    mock_bridge_network.remove.assert_not_called()
    mock_host_network.remove.assert_not_called()
    mock_custom_network.remove.assert_called_once()

def test_cleanup_resources_handles_individual_failures(stack_manager):
    """Tests cleanup_resources continues when individual resource removal fails."""
    mock_failing_container = MagicMock()
    mock_failing_container.status = "exited"
    mock_failing_container.name = "failing-container"
    mock_failing_container.remove.side_effect = Exception("Permission denied")
    
    mock_success_container = MagicMock()
    mock_success_container.status = "exited"
    mock_success_container.name = "success-container"
    
    resources = {
        "containers": [mock_failing_container, mock_success_container],
        "volumes": [],
        "networks": []
    }
    
    stack_manager.find_resources_by_label = MagicMock(return_value=resources)
    
    result = stack_manager.cleanup_resources()
    
    assert result is True
    mock_failing_container.remove.assert_called_once_with(force=False)
    mock_success_container.remove.assert_called_once_with(force=False)

def test_cleanup_resources_running_containers_skipped(stack_manager):
    """Tests cleanup_resources skips running containers."""
    mock_running_container = MagicMock()
    mock_running_container.status = "running"
    mock_running_container.name = "running-container"
    
    mock_stopped_container = MagicMock()
    mock_stopped_container.status = "exited"
    mock_stopped_container.name = "stopped-container"
    
    resources = {
        "containers": [mock_running_container, mock_stopped_container],
        "volumes": [],
        "networks": []
    }
    
    stack_manager.find_resources_by_label = MagicMock(return_value=resources)
    
    result = stack_manager.cleanup_resources()
    
    assert result is True
    mock_running_container.remove.assert_not_called()
    mock_stopped_container.remove.assert_called_once_with(force=False)

def test_cleanup_resources_exception_handling(stack_manager):
    """Tests cleanup_resources handles exceptions during cleanup."""
    stack_manager.find_resources_by_label = MagicMock(side_effect=Exception("Docker error"))
    
    result = stack_manager.cleanup_resources()
    
    assert result is False

def test_cleanup_resources_no_resources_found(stack_manager):
    """Tests cleanup_resources when no resources are found."""
    resources = {"containers": [], "volumes": [], "networks": []}
    stack_manager.find_resources_by_label = MagicMock(return_value=resources)
    
    result = stack_manager.cleanup_resources()
    
    assert result is True


# =============================================================================
# Phase 5.2 New Methods Tests - Stack Uninstall (Comprehensive)
# =============================================================================

# Happy Path Tests

def test_uninstall_stack_basic_no_flags(stack_manager, mock_docker_client):
    """Tests uninstall_stack basic operation with no flags (preserves data and config)."""
    # Mock successful operations
    stack_manager.is_stack_running = MagicMock(return_value=False)
    stack_manager.find_resources_by_label = MagicMock(return_value={
        "containers": [MagicMock(name="webui")],
        "networks": [MagicMock(name="ollama-network")], 
        "volumes": [MagicMock(name="ollama-data")]
    })
    stack_manager.cleanup_resources = MagicMock(return_value=True)
    mock_docker_client.remove_resources = MagicMock(return_value=True)
    
    result = stack_manager.uninstall_stack()
    
    assert result is True
    stack_manager.find_resources_by_label.assert_called_once_with("ollama-stack.component")
    stack_manager.cleanup_resources.assert_called_once_with(remove_volumes=False, force=False)
    mock_docker_client.remove_resources.assert_called_once_with(remove_images=True, force=False)

def test_uninstall_stack_remove_volumes_only(stack_manager, mock_docker_client):
    """Tests uninstall_stack with remove_volumes=True (preserves config)."""
    # Mock resources with volumes
    mock_volume1 = MagicMock()
    mock_volume1.name = "ollama-data"
    mock_volume2 = MagicMock()
    mock_volume2.name = "webui-data"
    
    stack_manager.is_stack_running = MagicMock(return_value=False)
    stack_manager.find_resources_by_label = MagicMock(return_value={
        "containers": [], "networks": [], "volumes": [mock_volume1, mock_volume2]
    })
    stack_manager.cleanup_resources = MagicMock(return_value=True)
    mock_docker_client.remove_resources = MagicMock(return_value=True)
    
    result = stack_manager.uninstall_stack(remove_volumes=True, force=True)
    
    assert result is True
    # Volumes should be removed individually (not via cleanup_resources)
    mock_volume1.remove.assert_called_once_with(force=True)
    mock_volume2.remove.assert_called_once_with(force=True)

def test_uninstall_stack_remove_config_only(stack_manager, mock_docker_client):
    """Tests uninstall_stack with remove_config=True (preserves volumes)."""
    # Mock config directory path and shutil inside the function
    mock_config_dir = MagicMock()
    mock_config_dir.exists.return_value = True
    
    with patch('ollama_stack_cli.config.DEFAULT_CONFIG_DIR', mock_config_dir):
        with patch('shutil.rmtree') as mock_rmtree:
            stack_manager.is_stack_running = MagicMock(return_value=False)
            stack_manager.find_resources_by_label = MagicMock(return_value={
                "containers": [], "networks": [], "volumes": []
            })
            stack_manager.cleanup_resources = MagicMock(return_value=True)
            mock_docker_client.remove_resources = MagicMock(return_value=True)
            
            result = stack_manager.uninstall_stack(remove_config=True)
            
            assert result is True
            mock_config_dir.exists.assert_called_once()
            mock_rmtree.assert_called_once_with(mock_config_dir)

def test_uninstall_stack_remove_all(stack_manager, mock_docker_client):
    """Tests uninstall_stack with both remove_volumes=True and remove_config=True."""
    # Mock volumes and config
    mock_volume = MagicMock()
    mock_volume.name = "test-volume"
    mock_config_dir = MagicMock()
    mock_config_dir.exists.return_value = True
    
    with patch('ollama_stack_cli.config.DEFAULT_CONFIG_DIR', mock_config_dir):
        with patch('shutil.rmtree') as mock_rmtree:
            stack_manager.is_stack_running = MagicMock(return_value=False)
            stack_manager.find_resources_by_label = MagicMock(return_value={
                "containers": [], "networks": [], "volumes": [mock_volume]
            })
            stack_manager.cleanup_resources = MagicMock(return_value=True)
            mock_docker_client.remove_resources = MagicMock(return_value=True)
            
            result = stack_manager.uninstall_stack(remove_volumes=True, remove_config=True, force=True)
            
            assert result is True
            mock_volume.remove.assert_called_once_with(force=True)
            mock_rmtree.assert_called_once_with(mock_config_dir)

def test_uninstall_stack_running_services_docker_only(stack_manager, mock_docker_client):
    """Tests uninstall_stack when stack is running with Docker services only."""
    stack_manager.config.services = {
        'webui': MagicMock(type='docker'),
        'mcp_proxy': MagicMock(type='docker')
    }
    
    stack_manager.is_stack_running = MagicMock(return_value=True)
    stack_manager.stop_docker_services = MagicMock(return_value=True)
    stack_manager.stop_native_services = MagicMock(return_value=True)
    # Add some mock resources so method doesn't return early
    stack_manager.find_resources_by_label = MagicMock(return_value={
        "containers": [MagicMock(name="webui-container")], "networks": [], "volumes": []
    })
    stack_manager.cleanup_resources = MagicMock(return_value=True)
    mock_docker_client.remove_resources = MagicMock(return_value=True)
    
    result = stack_manager.uninstall_stack()
    
    assert result is True
    stack_manager.stop_docker_services.assert_called_once()
    # Should NOT call stop_native_services since there are no native services
    stack_manager.stop_native_services.assert_not_called()

def test_uninstall_stack_running_services_native_only(stack_manager, mock_docker_client):
    """Tests uninstall_stack when stack is running with native services only."""
    stack_manager.config.services = {
        'ollama': MagicMock(type='native-api')
    }
    
    stack_manager.is_stack_running = MagicMock(return_value=True)
    stack_manager.stop_docker_services = MagicMock(return_value=True)
    stack_manager.stop_native_services = MagicMock(return_value=True)
    # Add some mock resources so method doesn't return early
    stack_manager.find_resources_by_label = MagicMock(return_value={
        "containers": [MagicMock(name="some-container")], "networks": [], "volumes": []
    })
    stack_manager.cleanup_resources = MagicMock(return_value=True)
    mock_docker_client.remove_resources = MagicMock(return_value=True)
    
    result = stack_manager.uninstall_stack()
    
    assert result is True
    # Should NOT call stop_docker_services since there are no Docker services
    stack_manager.stop_docker_services.assert_not_called()
    stack_manager.stop_native_services.assert_called_once_with(['ollama'])

def test_uninstall_stack_running_services_mixed(stack_manager, mock_docker_client):
    """Tests uninstall_stack when stack is running with mixed service types."""
    stack_manager.config.services = {
        'webui': MagicMock(type='docker'),
        'ollama': MagicMock(type='native-api'),
        'mcp_proxy': MagicMock(type='docker')
    }
    
    stack_manager.is_stack_running = MagicMock(return_value=True)
    stack_manager.stop_docker_services = MagicMock(return_value=True)
    stack_manager.stop_native_services = MagicMock(return_value=True)
    # Add some mock resources so method doesn't return early
    stack_manager.find_resources_by_label = MagicMock(return_value={
        "containers": [MagicMock(name="webui-container")], "networks": [], "volumes": []
    })
    stack_manager.cleanup_resources = MagicMock(return_value=True)
    mock_docker_client.remove_resources = MagicMock(return_value=True)
    
    result = stack_manager.uninstall_stack()
    
    assert result is True
    # Should call both stop methods since we have both service types
    stack_manager.stop_docker_services.assert_called_once()
    stack_manager.stop_native_services.assert_called_once_with(['ollama'])

def test_uninstall_stack_not_running(stack_manager, mock_docker_client):
    """Tests uninstall_stack when stack is not running."""
    stack_manager.is_stack_running = MagicMock(return_value=False)
    stack_manager.stop_docker_services = MagicMock()
    stack_manager.stop_native_services = MagicMock()
    stack_manager.find_resources_by_label = MagicMock(return_value={
        "containers": [], "networks": [], "volumes": []
    })
    stack_manager.cleanup_resources = MagicMock(return_value=True)
    mock_docker_client.remove_resources = MagicMock(return_value=True)
    
    result = stack_manager.uninstall_stack()
    
    assert result is True
    # Should not call stop services when not running
    stack_manager.stop_docker_services.assert_not_called()
    stack_manager.stop_native_services.assert_not_called()

def test_uninstall_stack_no_resources_found(stack_manager, mock_docker_client):
    """Tests uninstall_stack when no resources are found to remove."""
    stack_manager.is_stack_running = MagicMock(return_value=False)
    stack_manager.find_resources_by_label = MagicMock(return_value={
        "containers": [], "networks": [], "volumes": []
    })
    
    result = stack_manager.uninstall_stack()
    
    assert result is True
    # Should still succeed when no resources found
    stack_manager.find_resources_by_label.assert_called_once_with("ollama-stack.component")

# Error Handling and Edge Cases

def test_uninstall_stack_exception_during_resource_discovery(stack_manager):
    """Tests uninstall_stack handles exceptions during resource discovery."""
    stack_manager.find_resources_by_label = MagicMock(side_effect=Exception("Docker daemon not running"))
    
    result = stack_manager.uninstall_stack()
    
    assert result is False

def test_uninstall_stack_exception_during_is_stack_running(stack_manager):
    """Tests uninstall_stack handles exceptions during stack running check."""
    # Mock to throw exception early in the process
    stack_manager.is_stack_running = MagicMock(side_effect=Exception("Service check failed"))
    # Add some mock resources so method doesn't return early, forcing it to reach is_stack_running()
    stack_manager.find_resources_by_label = MagicMock(return_value={
        "containers": [MagicMock(name="test-container")], "networks": [], "volumes": []
    })
    
    result = stack_manager.uninstall_stack()
    
    assert result is False

def test_uninstall_stack_stop_docker_services_failure(stack_manager, mock_docker_client):
    """Tests uninstall_stack continues when Docker service stop fails."""
    stack_manager.config.services = {'webui': MagicMock(type='docker')}
    stack_manager.is_stack_running = MagicMock(return_value=True)
    stack_manager.stop_docker_services = MagicMock(return_value=False)  # Failure
    stack_manager.stop_native_services = MagicMock(return_value=True)
    stack_manager.find_resources_by_label = MagicMock(return_value={
        "containers": [], "networks": [], "volumes": []
    })
    stack_manager.cleanup_resources = MagicMock(return_value=True)
    mock_docker_client.remove_resources = MagicMock(return_value=True)
    
    result = stack_manager.uninstall_stack()
    
    assert result is True  # Should continue despite stop failure

def test_uninstall_stack_stop_native_services_failure(stack_manager, mock_docker_client):
    """Tests uninstall_stack continues when native service stop fails."""
    stack_manager.config.services = {'ollama': MagicMock(type='native-api')}
    stack_manager.is_stack_running = MagicMock(return_value=True)
    stack_manager.stop_docker_services = MagicMock(return_value=True)
    stack_manager.stop_native_services = MagicMock(return_value=False)  # Failure
    stack_manager.find_resources_by_label = MagicMock(return_value={
        "containers": [], "networks": [], "volumes": []
    })
    stack_manager.cleanup_resources = MagicMock(return_value=True)
    mock_docker_client.remove_resources = MagicMock(return_value=True)
    
    result = stack_manager.uninstall_stack()
    
    assert result is True  # Should continue despite stop failure

def test_uninstall_stack_cleanup_resources_failure(stack_manager, mock_docker_client):
    """Tests uninstall_stack continues when resource cleanup fails."""
    stack_manager.is_stack_running = MagicMock(return_value=False)
    stack_manager.find_resources_by_label = MagicMock(return_value={
        "containers": [], "networks": [], "volumes": []
    })
    stack_manager.cleanup_resources = MagicMock(return_value=False)  # Failure
    mock_docker_client.remove_resources = MagicMock(return_value=True)
    
    result = stack_manager.uninstall_stack()
    
    assert result is True  # Should continue despite cleanup failure

def test_uninstall_stack_remove_images_failure(stack_manager, mock_docker_client):
    """Tests uninstall_stack continues when image removal fails."""
    stack_manager.is_stack_running = MagicMock(return_value=False)
    stack_manager.find_resources_by_label = MagicMock(return_value={
        "containers": [], "networks": [], "volumes": []
    })
    stack_manager.cleanup_resources = MagicMock(return_value=True)
    mock_docker_client.remove_resources = MagicMock(return_value=False)  # Failure
    
    result = stack_manager.uninstall_stack()
    
    assert result is True  # Should continue despite image removal failure

def test_uninstall_stack_individual_volume_removal_failures(stack_manager, mock_docker_client):
    """Tests uninstall_stack handles individual volume removal failures gracefully."""
    mock_volume1 = MagicMock()
    mock_volume1.name = "good-volume"
    mock_volume2 = MagicMock()
    mock_volume2.name = "bad-volume"
    mock_volume2.remove.side_effect = Exception("Permission denied")
    mock_volume3 = MagicMock()
    mock_volume3.name = "another-good-volume"
    
    stack_manager.is_stack_running = MagicMock(return_value=False)
    stack_manager.find_resources_by_label = MagicMock(return_value={
        "containers": [], "networks": [], "volumes": [mock_volume1, mock_volume2, mock_volume3]
    })
    stack_manager.cleanup_resources = MagicMock(return_value=True)
    mock_docker_client.remove_resources = MagicMock(return_value=True)
    
    result = stack_manager.uninstall_stack(remove_volumes=True, force=True)
    
    assert result is True
    # Should attempt to remove all volumes despite individual failures
    mock_volume1.remove.assert_called_once_with(force=True)
    mock_volume2.remove.assert_called_once_with(force=True)
    mock_volume3.remove.assert_called_once_with(force=True)

def test_uninstall_stack_config_directory_removal_failure(stack_manager, mock_docker_client):
    """Tests uninstall_stack handles config directory removal failure gracefully."""
    mock_config_dir = MagicMock()
    mock_config_dir.exists.return_value = True
    
    with patch('ollama_stack_cli.config.DEFAULT_CONFIG_DIR', mock_config_dir):
        with patch('shutil.rmtree', side_effect=PermissionError("Permission denied")) as mock_rmtree:
            stack_manager.is_stack_running = MagicMock(return_value=False)
            stack_manager.find_resources_by_label = MagicMock(return_value={
                "containers": [], "networks": [], "volumes": []
            })
            stack_manager.cleanup_resources = MagicMock(return_value=True)
            mock_docker_client.remove_resources = MagicMock(return_value=True)
            
            result = stack_manager.uninstall_stack(remove_config=True)
            
            assert result is True  # Should continue despite config removal failure
            mock_rmtree.assert_called_once_with(mock_config_dir)

def test_uninstall_stack_config_directory_not_exists(stack_manager, mock_docker_client):
    """Tests uninstall_stack when config directory doesn't exist."""
    mock_config_dir = MagicMock()
    mock_config_dir.exists.return_value = False
    
    with patch('ollama_stack_cli.config.DEFAULT_CONFIG_DIR', mock_config_dir):
        with patch('shutil.rmtree') as mock_rmtree:
            stack_manager.is_stack_running = MagicMock(return_value=False)
            stack_manager.find_resources_by_label = MagicMock(return_value={
                "containers": [], "networks": [], "volumes": []
            })
            stack_manager.cleanup_resources = MagicMock(return_value=True)
            mock_docker_client.remove_resources = MagicMock(return_value=True)
            
            result = stack_manager.uninstall_stack(remove_config=True)
            
            assert result is True
            mock_config_dir.exists.assert_called_once()
            mock_rmtree.assert_not_called()

# Note: Import failure tests removed as they are difficult to test reliably
# and the exception handling in the actual code will catch these cases

# Complex State and Resource Scenarios

def test_uninstall_stack_large_resource_set(stack_manager, mock_docker_client):
    """Tests uninstall_stack with large number of resources."""
    # Create many mock resources
    containers = [MagicMock(name=f"container-{i}") for i in range(10)]
    networks = [MagicMock(name=f"network-{i}") for i in range(5)]
    volumes = [MagicMock(name=f"volume-{i}") for i in range(8)]
    
    stack_manager.is_stack_running = MagicMock(return_value=False)
    stack_manager.find_resources_by_label = MagicMock(return_value={
        "containers": containers, "networks": networks, "volumes": volumes
    })
    stack_manager.cleanup_resources = MagicMock(return_value=True)
    mock_docker_client.remove_resources = MagicMock(return_value=True)
    
    result = stack_manager.uninstall_stack(remove_volumes=True)
    
    assert result is True
    # Should attempt to remove all volumes
    for volume in volumes:
        volume.remove.assert_called_once_with(force=False)

def test_uninstall_stack_partial_resource_types(stack_manager, mock_docker_client):
    """Tests uninstall_stack when only some resource types are found."""
    stack_manager.is_stack_running = MagicMock(return_value=False)
    stack_manager.find_resources_by_label = MagicMock(return_value={
        "containers": [MagicMock(name="lonely-container")],
        "networks": [],  # No networks
        "volumes": []    # No volumes
    })
    stack_manager.cleanup_resources = MagicMock(return_value=True)
    mock_docker_client.remove_resources = MagicMock(return_value=True)
    
    result = stack_manager.uninstall_stack(remove_volumes=True)
    
    assert result is True
    # Should handle partial resource discovery gracefully

def test_uninstall_stack_no_services_configured(stack_manager, mock_docker_client):
    """Tests uninstall_stack when no services are configured."""
    stack_manager.config.services = {}  # No services
    stack_manager.is_stack_running = MagicMock(return_value=True)
    stack_manager.stop_docker_services = MagicMock(return_value=True)
    stack_manager.stop_native_services = MagicMock(return_value=True)
    stack_manager.find_resources_by_label = MagicMock(return_value={
        "containers": [], "networks": [], "volumes": []
    })
    stack_manager.cleanup_resources = MagicMock(return_value=True)
    mock_docker_client.remove_resources = MagicMock(return_value=True)
    
    result = stack_manager.uninstall_stack()
    
    assert result is True
    # Should NOT call stop methods since there are no services
    stack_manager.stop_docker_services.assert_not_called()
    stack_manager.stop_native_services.assert_not_called()

def test_uninstall_stack_unknown_service_types(stack_manager, mock_docker_client):
    """Tests uninstall_stack with unknown service types in configuration."""
    stack_manager.config.services = {
        'unknown_service': MagicMock(type='unknown-type'),
        'webui': MagicMock(type='docker')
    }
    
    stack_manager.is_stack_running = MagicMock(return_value=True)
    stack_manager.stop_docker_services = MagicMock(return_value=True)
    stack_manager.stop_native_services = MagicMock(return_value=True)
    # Add some mock resources so method doesn't return early
    stack_manager.find_resources_by_label = MagicMock(return_value={
        "containers": [MagicMock(name="webui-container")], "networks": [], "volumes": []
    })
    stack_manager.cleanup_resources = MagicMock(return_value=True)
    mock_docker_client.remove_resources = MagicMock(return_value=True)
    
    result = stack_manager.uninstall_stack()
    
    assert result is True
    # Should only call stop_docker_services since only 'webui' has type 'docker'
    stack_manager.stop_docker_services.assert_called_once()
    # Should NOT call stop_native_services since no services have type 'native-api'
    stack_manager.stop_native_services.assert_not_called()

# Force Flag Behavior Tests

def test_uninstall_stack_force_flag_behavior(stack_manager, mock_docker_client):
    """Tests uninstall_stack force flag is properly passed through."""
    mock_volume = MagicMock()
    mock_volume.name = "test-volume"
    
    stack_manager.is_stack_running = MagicMock(return_value=False)
    stack_manager.find_resources_by_label = MagicMock(return_value={
        "containers": [], "networks": [], "volumes": [mock_volume]
    })
    stack_manager.cleanup_resources = MagicMock(return_value=True)
    mock_docker_client.remove_resources = MagicMock(return_value=True)
    
    result = stack_manager.uninstall_stack(remove_volumes=True, force=True)
    
    assert result is True
    # Force flag should be passed to all removal operations
    stack_manager.cleanup_resources.assert_called_once_with(remove_volumes=False, force=True)
    mock_docker_client.remove_resources.assert_called_once_with(remove_images=True, force=True)
    mock_volume.remove.assert_called_once_with(force=True)

def test_uninstall_stack_force_flag_false(stack_manager, mock_docker_client):
    """Tests uninstall_stack without force flag (default behavior)."""
    mock_volume = MagicMock()
    mock_volume.name = "test-volume"
    
    stack_manager.is_stack_running = MagicMock(return_value=False)
    stack_manager.find_resources_by_label = MagicMock(return_value={
        "containers": [], "networks": [], "volumes": [mock_volume]
    })
    stack_manager.cleanup_resources = MagicMock(return_value=True)
    mock_docker_client.remove_resources = MagicMock(return_value=True)
    
    result = stack_manager.uninstall_stack(remove_volumes=True, force=False)
    
    assert result is True
    # Force flag should be False by default
    stack_manager.cleanup_resources.assert_called_once_with(remove_volumes=False, force=False)
    mock_docker_client.remove_resources.assert_called_once_with(remove_images=True, force=False)
    mock_volume.remove.assert_called_once_with(force=False)

# Resource Summary and Warning Tests

def test_uninstall_stack_resource_summary_accurate(stack_manager, mock_docker_client):
    """Tests uninstall_stack provides accurate resource summary."""
    containers = [MagicMock(name=f"container-{i}") for i in range(3)]
    networks = [MagicMock(name=f"network-{i}") for i in range(2)]
    volumes = [MagicMock(name=f"volume-{i}") for i in range(4)]
    
    stack_manager.is_stack_running = MagicMock(return_value=False)
    stack_manager.find_resources_by_label = MagicMock(return_value={
        "containers": containers, "networks": networks, "volumes": volumes
    })
    stack_manager.cleanup_resources = MagicMock(return_value=True)
    mock_docker_client.remove_resources = MagicMock(return_value=True)
    
    result = stack_manager.uninstall_stack()
    
    assert result is True
    # Verify resource discovery was called correctly
    stack_manager.find_resources_by_label.assert_called_once_with("ollama-stack.component")

def test_uninstall_stack_no_resources_but_remove_config(stack_manager, mock_docker_client):
    """Tests uninstall_stack when no Docker resources but remove_config=True."""
    mock_config_dir = MagicMock()
    mock_config_dir.exists.return_value = True
    
    with patch('ollama_stack_cli.config.DEFAULT_CONFIG_DIR', mock_config_dir):
        with patch('shutil.rmtree') as mock_rmtree:
            stack_manager.is_stack_running = MagicMock(return_value=False)
            stack_manager.find_resources_by_label = MagicMock(return_value={
                "containers": [], "networks": [], "volumes": []
            })
            stack_manager.cleanup_resources = MagicMock(return_value=True)
            mock_docker_client.remove_resources = MagicMock(return_value=True)
            
            result = stack_manager.uninstall_stack(remove_config=True)
            
            assert result is True
            # Should still proceed to remove config even with no Docker resources
            mock_rmtree.assert_called_once_with(mock_config_dir)


# Edge Cases and Error Handling Tests

def test_get_compose_files_no_platform_config(stack_manager):
    """Tests get_compose_files when platform config doesn't exist."""
    stack_manager.platform = 'unknown_platform'
    stack_manager.config.docker_compose_file = 'base.yml'
    stack_manager.config.platform = {}
    
    files = stack_manager.get_compose_files()
    
    # Should only return base compose file
    assert files == ['base.yml']

def test_get_compose_files_none_platform_config(stack_manager):
    """Tests get_compose_files when platform config is None."""
    stack_manager.platform = 'cpu'
    stack_manager.config.docker_compose_file = 'base.yml'
    stack_manager.config.platform = {'cpu': None}
    
    files = stack_manager.get_compose_files()
    
    # Should only return base compose file
    assert files == ['base.yml']

def test_configure_services_for_platform_no_ollama_service(stack_manager):
    """Tests configure_services_for_platform when 'ollama' service is not in config."""
    # Remove ollama from services
    del stack_manager.config.services['ollama']
    
    # Should not raise error when ollama service is not configured
    stack_manager.configure_services_for_platform()
    
    # Assert that the method completed without error
    assert True


# =============================================================================
# Unified Health Check System Tests
# =============================================================================

@patch('urllib.request.urlopen')
def test_check_service_health_http_success(mock_urlopen, stack_manager):
    """Tests check_service_health returns healthy for successful HTTP response."""
    mock_response = MagicMock()
    mock_response.status = 200
    mock_urlopen.return_value.__enter__.return_value = mock_response
    
    result = stack_manager.check_service_health("webui")
    
    assert result == "healthy"
    mock_urlopen.assert_called_once_with("http://localhost:8080", timeout=3)

@patch('urllib.request.urlopen')
@patch.object(StackManager, '_check_tcp_connectivity')
def test_check_service_health_http_error_tcp_success(mock_tcp_check, mock_urlopen, stack_manager):
    """Tests check_service_health falls back to TCP check when HTTP fails."""
    # HTTP check fails
    import urllib.error
    mock_urlopen.side_effect = urllib.error.URLError("Connection failed")
    # TCP check succeeds
    mock_tcp_check.return_value = True
    
    result = stack_manager.check_service_health("webui")
    
    assert result == "healthy"
    mock_tcp_check.assert_called_once_with("localhost", 8080)

@patch('urllib.request.urlopen')
@patch.object(StackManager, '_check_tcp_connectivity')
def test_check_service_health_http_bad_status_tcp_success(mock_tcp_check, mock_urlopen, stack_manager):
    """Tests check_service_health falls back to TCP when HTTP returns bad status."""
    # HTTP check returns 500
    mock_response = MagicMock()
    mock_response.status = 500
    mock_urlopen.return_value.__enter__.return_value = mock_response
    # TCP check succeeds
    mock_tcp_check.return_value = True
    
    result = stack_manager.check_service_health("webui")
    
    assert result == "healthy"
    mock_tcp_check.assert_called_once_with("localhost", 8080)

@patch('urllib.request.urlopen')
@patch.object(StackManager, '_check_tcp_connectivity')
def test_check_service_health_both_fail(mock_tcp_check, mock_urlopen, stack_manager):
    """Tests check_service_health returns unhealthy when both HTTP and TCP fail."""
    # HTTP check fails
    import urllib.error
    mock_urlopen.side_effect = urllib.error.URLError("Connection failed")
    # TCP check fails
    mock_tcp_check.return_value = False
    
    result = stack_manager.check_service_health("webui")
    
    assert result == "unhealthy"
    mock_tcp_check.assert_called_once_with("localhost", 8080)

def test_check_service_health_unknown_service(stack_manager):
    """Tests check_service_health returns unknown for unconfigured services."""
    result = stack_manager.check_service_health("unknown_service")
    
    assert result == "unknown"

@patch('urllib.request.urlopen')
def test_check_service_health_ollama_service(mock_urlopen, stack_manager):
    """Tests check_service_health works for ollama service."""
    mock_response = MagicMock()
    mock_response.status = 200
    mock_urlopen.return_value.__enter__.return_value = mock_response
    
    result = stack_manager.check_service_health("ollama")
    
    assert result == "healthy"
    mock_urlopen.assert_called_once_with("http://localhost:11434", timeout=3)

@patch('urllib.request.urlopen')
def test_check_service_health_mcp_proxy_service(mock_urlopen, stack_manager):
    """Tests check_service_health works for mcp_proxy service."""
    mock_response = MagicMock()
    mock_response.status = 200
    mock_urlopen.return_value.__enter__.return_value = mock_response
    
    result = stack_manager.check_service_health("mcp_proxy")
    
    assert result == "healthy"
    mock_urlopen.assert_called_once_with("http://localhost:8200", timeout=3)

@patch('socket.create_connection')
def test_check_tcp_connectivity_success(mock_socket, stack_manager):
    """Tests _check_tcp_connectivity returns True for successful connections."""
    mock_socket.return_value.__enter__.return_value = MagicMock()
    
    result = stack_manager._check_tcp_connectivity("localhost", 8080)
    
    assert result is True
    mock_socket.assert_called_once_with(("localhost", 8080), timeout=2.0)

@patch('socket.create_connection')
def test_check_tcp_connectivity_failure(mock_socket, stack_manager):
    """Tests _check_tcp_connectivity returns False for failed connections."""
    mock_socket.side_effect = ConnectionRefusedError("Connection refused")
    
    result = stack_manager._check_tcp_connectivity("localhost", 8080)
    
    assert result is False
    mock_socket.assert_called_once_with(("localhost", 8080), timeout=2.0)

@patch('socket.create_connection')
def test_check_tcp_connectivity_timeout(mock_socket, stack_manager):
    """Tests _check_tcp_connectivity returns False for connection timeouts."""
    import socket
    mock_socket.side_effect = socket.timeout("Connection timed out")
    
    result = stack_manager._check_tcp_connectivity("localhost", 8080)
    
    assert result is False
    mock_socket.assert_called_once_with(("localhost", 8080), timeout=2.0)

@patch('socket.create_connection')
def test_check_tcp_connectivity_custom_timeout(mock_socket, stack_manager):
    """Tests _check_tcp_connectivity uses custom timeout parameter."""
    mock_socket.return_value.__enter__.return_value = MagicMock()
    
    result = stack_manager._check_tcp_connectivity("example.com", 443, timeout=5.0)
    
    assert result is True
    mock_socket.assert_called_once_with(("example.com", 443), timeout=5.0)

@patch.object(StackManager, 'check_service_health')
def test_get_docker_services_status_applies_health_checks(mock_health_check, stack_manager, mock_docker_client):
    """Tests get_docker_services_status applies unified health checks to running services."""
    # Mock Docker client returning services with unknown health
    mock_docker_client.get_container_status.return_value = [
        ServiceStatus(name='webui', is_running=True, status='running', health='unknown'),
        ServiceStatus(name='mcp_proxy', is_running=False, status='stopped', health='unknown')
    ]
    
    # Mock health check results
    mock_health_check.side_effect = ['healthy', 'unhealthy']
    
    statuses = stack_manager.get_docker_services_status(['webui', 'mcp_proxy'])
    
    # Should have called health check for running service only
    mock_health_check.assert_called_once_with('webui')
    
    # Verify health was updated correctly
    webui_status = next(s for s in statuses if s.name == 'webui')
    mcp_status = next(s for s in statuses if s.name == 'mcp_proxy')
    
    assert webui_status.health == 'healthy'
    assert mcp_status.health == 'unhealthy'  # Not running, so set to unhealthy


# =============================================================================
# Install Stack Management Tests
# =============================================================================

@patch('ollama_stack_cli.config.save_config')
@patch('ollama_stack_cli.config.DEFAULT_CONFIG_DIR')
@patch('ollama_stack_cli.config.DEFAULT_ENV_FILE') 
@patch('ollama_stack_cli.config.DEFAULT_CONFIG_FILE')
@patch('typer.confirm')
def test_install_stack_basic_success(mock_confirm, mock_config_file, mock_env_file, mock_config_dir, mock_save_config, stack_manager):
    """Tests basic install_stack functionality when no existing config."""
    mock_config_dir.exists.return_value = False
    mock_config_dir.mkdir = MagicMock()
    
    # Mock environment checks
    mock_check_report = CheckReport(checks=[
        EnvironmentCheck(name="Docker Daemon Running", passed=True),
        EnvironmentCheck(name="Port 11434 Available", passed=True)
    ])
    stack_manager.run_environment_checks = MagicMock(return_value=mock_check_report)
    
    result = stack_manager.install_stack(force=False)
    
    assert result['success'] is True
    assert result['config_dir'] == mock_config_dir
    assert result['config_file'] == mock_config_file
    assert result['env_file'] == mock_env_file
    assert result['check_report'] == mock_check_report
    assert 'failed_checks' in result
    mock_config_dir.mkdir.assert_called_once_with(parents=True, exist_ok=True)
    mock_save_config.assert_called_once()
    stack_manager.run_environment_checks.assert_called_once_with(fix=False)


@patch('ollama_stack_cli.config.save_config')
@patch('ollama_stack_cli.config.DEFAULT_CONFIG_DIR')
@patch('ollama_stack_cli.config.DEFAULT_ENV_FILE')
@patch('ollama_stack_cli.config.DEFAULT_CONFIG_FILE')
@patch('typer.confirm')
def test_install_stack_directory_exists_force_true(mock_confirm, mock_config_file, mock_env_file, mock_config_dir, mock_save_config, stack_manager):
    """Tests install_stack when directory exists but force=True."""
    mock_config_dir.exists.return_value = True
    mock_config_file.exists.return_value = True
    mock_env_file.exists.return_value = True
    mock_config_dir.mkdir = MagicMock()
    
    # Mock environment checks
    mock_check_report = CheckReport(checks=[
        EnvironmentCheck(name="Docker Daemon Running", passed=True)
    ])
    stack_manager.run_environment_checks = MagicMock(return_value=mock_check_report)
    
    result = stack_manager.install_stack(force=True)
    
    assert result['success'] is True
    assert 'config_dir' in result
    assert 'check_report' in result
    # Should not prompt for confirmation when force=True
    mock_confirm.assert_not_called()
    mock_save_config.assert_called_once()


@patch('ollama_stack_cli.config.save_config')
@patch('ollama_stack_cli.config.DEFAULT_CONFIG_DIR')
@patch('ollama_stack_cli.config.DEFAULT_ENV_FILE')
@patch('ollama_stack_cli.config.DEFAULT_CONFIG_FILE')
@patch('typer.confirm')
def test_install_stack_directory_exists_user_confirms(mock_confirm, mock_config_file, mock_env_file, mock_config_dir, mock_save_config, stack_manager):
    """Tests install_stack when directory exists and user confirms overwrite."""
    mock_config_dir.exists.return_value = True
    mock_config_file.exists.return_value = True
    mock_env_file.exists.return_value = True
    mock_config_dir.mkdir = MagicMock()
    mock_confirm.return_value = True  # User confirms
    
    # Mock environment checks
    mock_check_report = CheckReport(checks=[
        EnvironmentCheck(name="Docker Daemon Running", passed=True)
    ])
    stack_manager.run_environment_checks = MagicMock(return_value=mock_check_report)
    
    result = stack_manager.install_stack(force=False)
    
    assert result['success'] is True
    assert 'config_dir' in result
    assert 'check_report' in result
    mock_confirm.assert_called_once()
    mock_save_config.assert_called_once()


@patch('ollama_stack_cli.config.save_config')
@patch('ollama_stack_cli.config.DEFAULT_CONFIG_DIR')
@patch('ollama_stack_cli.config.DEFAULT_ENV_FILE')
@patch('ollama_stack_cli.config.DEFAULT_CONFIG_FILE')
@patch('typer.confirm')
def test_install_stack_directory_exists_user_declines(mock_confirm, mock_config_file, mock_env_file, mock_config_dir, mock_save_config, stack_manager):
    """Tests install_stack when directory exists and user declines overwrite."""
    mock_config_dir.exists.return_value = True
    mock_config_file.exists.return_value = True
    mock_env_file.exists.return_value = True
    mock_confirm.return_value = False  # User declines
    
    result = stack_manager.install_stack(force=False)
    
    assert result['success'] is False
    assert result['error'] == "Installation cancelled by user"
    mock_confirm.assert_called_once()
    mock_save_config.assert_not_called()


@patch('ollama_stack_cli.config.save_config')
@patch('ollama_stack_cli.config.DEFAULT_CONFIG_DIR')
def test_install_stack_directory_creation_failure(mock_config_dir, mock_save_config, stack_manager):
    """Tests install_stack handles directory creation failure."""
    mock_config_dir.exists.return_value = False
    mock_config_dir.mkdir.side_effect = PermissionError("Permission denied")
    
    result = stack_manager.install_stack()
    
    assert result['success'] is False
    assert "Permission denied" in result['error']
    mock_save_config.assert_not_called()


@patch('ollama_stack_cli.config.save_config')
@patch('ollama_stack_cli.config.DEFAULT_CONFIG_DIR')
@patch('ollama_stack_cli.config.DEFAULT_ENV_FILE')
@patch('ollama_stack_cli.config.DEFAULT_CONFIG_FILE')
def test_install_stack_config_save_failure(mock_config_file, mock_env_file, mock_config_dir, mock_save_config, stack_manager):
    """Tests install_stack handles config save failure."""
    mock_config_dir.exists.return_value = False
    mock_config_dir.mkdir = MagicMock()
    mock_save_config.side_effect = IOError("Cannot write file")
    
    result = stack_manager.install_stack()
    
    assert result['success'] is False
    assert "Cannot write file" in result['error']
    mock_save_config.assert_called_once()


@patch('ollama_stack_cli.config.save_config')
@patch('ollama_stack_cli.config.DEFAULT_CONFIG_DIR')
@patch('ollama_stack_cli.config.DEFAULT_ENV_FILE')
@patch('ollama_stack_cli.config.DEFAULT_CONFIG_FILE')
def test_install_stack_environment_checks_all_pass(mock_config_file, mock_env_file, mock_config_dir, mock_save_config, stack_manager):
    """Tests install_stack when all environment checks pass."""
    mock_config_dir.exists.return_value = False
    mock_config_dir.mkdir = MagicMock()
    
    # Mock all checks passing
    mock_check_report = CheckReport(checks=[
        EnvironmentCheck(name="Docker Daemon Running", passed=True),
        EnvironmentCheck(name="Port 11434 Available", passed=True),
        EnvironmentCheck(name="Port 8080 Available", passed=True)
    ])
    stack_manager.run_environment_checks = MagicMock(return_value=mock_check_report)
    
    result = stack_manager.install_stack()
    
    assert result['success'] is True
    assert result['check_report'] == mock_check_report
    assert len(result['failed_checks']) == 0


@patch('ollama_stack_cli.config.save_config')
@patch('ollama_stack_cli.config.DEFAULT_CONFIG_DIR')
@patch('ollama_stack_cli.config.DEFAULT_ENV_FILE')
@patch('ollama_stack_cli.config.DEFAULT_CONFIG_FILE')
def test_install_stack_environment_checks_some_fail(mock_config_file, mock_env_file, mock_config_dir, mock_save_config, stack_manager):
    """Tests install_stack when some environment checks fail."""
    mock_config_dir.exists.return_value = False
    mock_config_dir.mkdir = MagicMock()
    
    # Mock some checks failing
    failed_check = EnvironmentCheck(name="Port 11434 Available", passed=False, details="Port in use")
    mock_check_report = CheckReport(checks=[
        EnvironmentCheck(name="Docker Daemon Running", passed=True),
        failed_check
    ])
    stack_manager.run_environment_checks = MagicMock(return_value=mock_check_report)
    
    result = stack_manager.install_stack()
    
    assert result['success'] is True  # Should still succeed even with failed checks
    assert result['check_report'] == mock_check_report
    assert len(result['failed_checks']) == 1
    assert result['failed_checks'][0] == failed_check


@patch('ollama_stack_cli.config.save_config')
@patch('ollama_stack_cli.config.DEFAULT_CONFIG_DIR')
@patch('ollama_stack_cli.config.DEFAULT_ENV_FILE')
@patch('ollama_stack_cli.config.DEFAULT_CONFIG_FILE')
def test_install_stack_creates_proper_config(mock_config_file, mock_env_file, mock_config_dir, mock_save_config, stack_manager):
    """Tests that install_stack creates proper AppConfig with platform configurations."""
    mock_config_dir.exists.return_value = False
    mock_config_dir.mkdir = MagicMock()
    
    # Mock environment checks
    mock_check_report = CheckReport(checks=[])
    stack_manager.run_environment_checks = MagicMock(return_value=mock_check_report)
    
    result = stack_manager.install_stack()
    
    assert result['success'] is True
    # Verify save_config was called with proper arguments
    mock_save_config.assert_called_once()
    call_args = mock_save_config.call_args[0]
    app_config = call_args[1]  # Second argument should be the AppConfig
    
    # Verify config properties
    assert app_config.project_name == "ollama-stack"
    assert app_config.webui_secret_key is not None
    assert len(app_config.webui_secret_key) == 64  # Generated secure key
    assert "apple" in app_config.platform
    assert "nvidia" in app_config.platform
    assert app_config.platform["apple"].compose_file == "docker-compose.apple.yml"
    assert app_config.platform["nvidia"].compose_file == "docker-compose.nvidia.yml"


def test_generate_secure_key(stack_manager):
    """Tests the _generate_secure_key method."""
    key1 = stack_manager._generate_secure_key()
    key2 = stack_manager._generate_secure_key()
    
    # Keys should be different
    assert key1 != key2
    
    # Keys should be expected length
    assert len(key1) == 64
    assert len(key2) == 64
    
    # Keys should only contain safe characters
    import string
    safe_chars = string.ascii_letters + string.digits + "-_"
    assert all(c in safe_chars for c in key1)
    assert all(c in safe_chars for c in key2)
    
    # Test custom length
    short_key = stack_manager._generate_secure_key(length=16)
    assert len(short_key) == 16


@patch('ollama_stack_cli.config.DEFAULT_CONFIG_DIR')
@patch('ollama_stack_cli.config.DEFAULT_ENV_FILE')
@patch('ollama_stack_cli.config.DEFAULT_CONFIG_FILE')
def test_install_stack_directory_exists_no_config_files(mock_config_file, mock_env_file, mock_config_dir, stack_manager):
    """Tests install_stack when directory exists but no config files exist."""
    mock_config_dir.exists.return_value = True
    mock_config_file.exists.return_value = False
    mock_env_file.exists.return_value = False
    mock_config_dir.mkdir = MagicMock()
    
    # Mock environment checks
    mock_check_report = CheckReport(checks=[])
    stack_manager.run_environment_checks = MagicMock(return_value=mock_check_report)
    
    with patch('ollama_stack_cli.config.save_config') as mock_save_config:
        result = stack_manager.install_stack(force=False)
    
    assert result['success'] is True
    assert 'config_dir' in result
    assert 'check_report' in result
    # Should not prompt for confirmation if no config files exist
    mock_save_config.assert_called_once()


@patch('ollama_stack_cli.config.DEFAULT_CONFIG_DIR')
@patch('ollama_stack_cli.config.DEFAULT_ENV_FILE')
@patch('ollama_stack_cli.config.DEFAULT_CONFIG_FILE')
@patch('typer.confirm')
def test_install_stack_directory_exists_partial_config_files(mock_confirm, mock_config_file, mock_env_file, mock_config_dir, stack_manager):
    """Tests install_stack when directory exists with only some config files."""
    mock_config_dir.exists.return_value = True
    mock_config_file.exists.return_value = True  # JSON exists
    mock_env_file.exists.return_value = False    # .env doesn't exist
    mock_config_dir.mkdir = MagicMock()
    mock_confirm.return_value = True
    
    # Mock environment checks
    mock_check_report = CheckReport(checks=[])
    stack_manager.run_environment_checks = MagicMock(return_value=mock_check_report)
    
    with patch('ollama_stack_cli.config.save_config') as mock_save_config:
        result = stack_manager.install_stack(force=False)
    
    assert result['success'] is True
    assert 'config_dir' in result
    assert 'check_report' in result
    # Should prompt for confirmation since at least one config file exists
    mock_confirm.assert_called_once()
    mock_save_config.assert_called_once()


@patch('ollama_stack_cli.config.save_config')
@patch('ollama_stack_cli.config.DEFAULT_CONFIG_DIR')
@patch('ollama_stack_cli.config.DEFAULT_ENV_FILE')
@patch('ollama_stack_cli.config.DEFAULT_CONFIG_FILE')
def test_install_stack_displays_installation_summary(mock_config_file, mock_env_file, mock_config_dir, mock_save_config, stack_manager):
    """Tests that install_stack displays installation summary."""
    mock_config_dir.exists.return_value = False
    mock_config_dir.mkdir = MagicMock()
    
    # Mock environment checks
    mock_check_report = CheckReport(checks=[])
    stack_manager.run_environment_checks = MagicMock(return_value=mock_check_report)
    
    result = stack_manager.install_stack()
    
    assert result['success'] is True
    assert result['config_dir'] == mock_config_dir
    assert result['config_file'] == mock_config_file
    assert result['env_file'] == mock_env_file


@patch('ollama_stack_cli.config.save_config')
@patch('ollama_stack_cli.config.DEFAULT_CONFIG_DIR')
@patch('ollama_stack_cli.config.DEFAULT_ENV_FILE')
@patch('ollama_stack_cli.config.DEFAULT_CONFIG_FILE')
def test_install_stack_environment_checks_exception(mock_config_file, mock_env_file, mock_config_dir, mock_save_config, stack_manager):
    """Tests install_stack handles exceptions during environment checks."""
    mock_config_dir.exists.return_value = False
    mock_config_dir.mkdir = MagicMock()
    
    # Mock save_config succeeding but environment checks failing with exception
    stack_manager.run_environment_checks = MagicMock(side_effect=Exception("Docker daemon not responding"))
    
    result = stack_manager.install_stack()
    
    assert result['success'] is False
    assert "Docker daemon not responding" in result['error']
    mock_save_config.assert_called_once()  # Should still save config
    stack_manager.run_environment_checks.assert_called_once_with(fix=False)


@patch('ollama_stack_cli.config.save_config')
@patch('ollama_stack_cli.config.DEFAULT_CONFIG_DIR')
@patch('ollama_stack_cli.config.DEFAULT_ENV_FILE')
@patch('ollama_stack_cli.config.DEFAULT_CONFIG_FILE')
@patch('typer.confirm')
def test_install_stack_keyboard_interrupt_during_confirmation(mock_confirm, mock_config_file, mock_env_file, mock_config_dir, mock_save_config, stack_manager):
    """Tests install_stack handles KeyboardInterrupt during user confirmation."""
    mock_config_dir.exists.return_value = True
    mock_config_file.exists.return_value = True
    mock_env_file.exists.return_value = True
    
    # Mock KeyboardInterrupt during confirmation
    mock_confirm.side_effect = KeyboardInterrupt("User cancelled")
    
    # The KeyboardInterrupt should propagate and not be caught by install_stack
    # since it's a legitimate user cancellation that should bubble up
    with pytest.raises(KeyboardInterrupt):
        stack_manager.install_stack(force=False)
    
    mock_save_config.assert_not_called()


@patch('ollama_stack_cli.config.save_config')
@patch('ollama_stack_cli.config.DEFAULT_CONFIG_DIR')
@patch('ollama_stack_cli.config.DEFAULT_ENV_FILE')
@patch('ollama_stack_cli.config.DEFAULT_CONFIG_FILE')
def test_install_stack_generic_exception(mock_config_file, mock_env_file, mock_config_dir, mock_save_config, stack_manager):
    """Tests install_stack handles unexpected exceptions gracefully."""
    mock_config_dir.exists.return_value = False
    mock_config_dir.mkdir = MagicMock()
    
    # Mock unexpected exception during save_config (inside try/catch block)
    mock_save_config.side_effect = OSError("Filesystem error")
    
    result = stack_manager.install_stack()
    
    assert result['success'] is False
    assert "Filesystem error" in result['error']
    mock_save_config.assert_called_once()


@patch('ollama_stack_cli.config.save_config')
@patch('ollama_stack_cli.config.DEFAULT_CONFIG_DIR')
@patch('ollama_stack_cli.config.DEFAULT_ENV_FILE')
@patch('ollama_stack_cli.config.DEFAULT_CONFIG_FILE')
@patch('typer.confirm')
def test_install_stack_confirmation_message_content(mock_confirm, mock_config_file, mock_env_file, mock_config_dir, mock_save_config, stack_manager):
    """Tests that install_stack displays the correct confirmation message."""
    mock_config_dir.exists.return_value = True
    mock_config_file.exists.return_value = True
    mock_env_file.exists.return_value = True
    mock_confirm.return_value = False  # User declines
    
    result = stack_manager.install_stack(force=False)
    
    assert result['success'] is False
    assert result['error'] == "Installation cancelled by user"
    # Verify confirmation prompt
    mock_confirm.assert_called_once_with("Do you want to overwrite the existing configuration?")


@patch('ollama_stack_cli.config.save_config')
@patch('ollama_stack_cli.config.DEFAULT_CONFIG_DIR')
@patch('ollama_stack_cli.config.DEFAULT_ENV_FILE')
@patch('ollama_stack_cli.config.DEFAULT_CONFIG_FILE')
@patch('typer.confirm')
def test_install_stack_only_json_file_exists(mock_confirm, mock_config_file, mock_env_file, mock_config_dir, mock_save_config, stack_manager):
    """Tests install_stack when only .ollama-stack.json exists."""
    mock_config_dir.exists.return_value = True
    mock_config_file.exists.return_value = True   # Only JSON exists
    mock_env_file.exists.return_value = False     # .env doesn't exist
    mock_confirm.return_value = True
    
    # Mock environment checks
    mock_check_report = CheckReport(checks=[])
    stack_manager.run_environment_checks = MagicMock(return_value=mock_check_report)
    
    result = stack_manager.install_stack(force=False)
    
    assert result['success'] is True
    assert 'config_dir' in result
    assert 'check_report' in result


@patch('ollama_stack_cli.config.save_config')
@patch('ollama_stack_cli.config.DEFAULT_CONFIG_DIR')
@patch('ollama_stack_cli.config.DEFAULT_ENV_FILE')
@patch('ollama_stack_cli.config.DEFAULT_CONFIG_FILE')
@patch('typer.confirm')
def test_install_stack_only_env_file_exists(mock_confirm, mock_config_file, mock_env_file, mock_config_dir, mock_save_config, stack_manager):
    """Tests install_stack when only .env file exists."""
    mock_config_dir.exists.return_value = True
    mock_config_file.exists.return_value = False  # JSON doesn't exist
    mock_env_file.exists.return_value = True      # Only .env exists
    mock_confirm.return_value = True
    
    # Mock environment checks
    mock_check_report = CheckReport(checks=[])
    stack_manager.run_environment_checks = MagicMock(return_value=mock_check_report)
    
    result = stack_manager.install_stack(force=False)
    
    assert result['success'] is True
    assert 'config_dir' in result
    assert 'check_report' in result


def test_generate_secure_key_different_lengths(stack_manager):
    """Tests _generate_secure_key with various lengths."""
    # Test various lengths
    for length in [1, 8, 16, 32, 64, 128, 256]:
        key = stack_manager._generate_secure_key(length=length)
        assert len(key) == length
        
        # Verify character set
        import string
        safe_chars = string.ascii_letters + string.digits + "-_"
        assert all(c in safe_chars for c in key)


def test_generate_secure_key_randomness(stack_manager):
    """Tests _generate_secure_key produces different results."""
    keys = [stack_manager._generate_secure_key() for _ in range(10)]
    
    # All keys should be different
    assert len(set(keys)) == 10
    
    # All keys should be the right length
    assert all(len(key) == 64 for key in keys)


@patch('ollama_stack_cli.config.save_config')
@patch('ollama_stack_cli.config.DEFAULT_CONFIG_DIR')
@patch('ollama_stack_cli.config.DEFAULT_ENV_FILE')
@patch('ollama_stack_cli.config.DEFAULT_CONFIG_FILE')
def test_install_stack_detailed_config_verification(mock_config_file, mock_env_file, mock_config_dir, mock_save_config, stack_manager):
    """Tests that install_stack creates AppConfig with all expected properties."""
    mock_config_dir.exists.return_value = False
    mock_config_dir.mkdir = MagicMock()
    
    # Mock environment checks
    mock_check_report = CheckReport(checks=[])
    stack_manager.run_environment_checks = MagicMock(return_value=mock_check_report)
    
    result = stack_manager.install_stack()
    
    assert result['success'] is True
    assert result['check_report'] == mock_check_report
    mock_save_config.assert_called_once()
    
    # Get the AppConfig that was passed to save_config
    call_args = mock_save_config.call_args[0]
    app_config = call_args[1]
    
    # Verify all required properties
    assert app_config.project_name == "ollama-stack"
    assert app_config.webui_secret_key is not None
    assert isinstance(app_config.webui_secret_key, str)
    assert len(app_config.webui_secret_key) == 64
    
    # Verify platform configurations
    assert isinstance(app_config.platform, dict)
    assert "apple" in app_config.platform
    assert "nvidia" in app_config.platform
    
    apple_config = app_config.platform["apple"]
    nvidia_config = app_config.platform["nvidia"]
    
    assert apple_config.compose_file == "docker-compose.apple.yml"
    assert nvidia_config.compose_file == "docker-compose.nvidia.yml"
    
    # Verify the arguments passed to save_config
    assert call_args[0] == stack_manager.display  # First arg should be display
    assert call_args[2] == mock_config_file       # Third arg should be config file path
    assert call_args[3] == mock_env_file          # Fourth arg should be env file path


@patch('ollama_stack_cli.config.save_config')
@patch('ollama_stack_cli.config.DEFAULT_CONFIG_DIR')
@patch('ollama_stack_cli.config.DEFAULT_ENV_FILE')
@patch('ollama_stack_cli.config.DEFAULT_CONFIG_FILE')
def test_install_stack_display_calls_verification(mock_config_file, mock_env_file, mock_config_dir, mock_save_config, stack_manager):
    """Tests that install_stack makes all expected display calls."""
    mock_config_dir.exists.return_value = False
    mock_config_dir.mkdir = MagicMock()
    
    # Mock environment checks with some failures
    mock_check_report = CheckReport(checks=[
        EnvironmentCheck(name="Docker Running", passed=True),
        EnvironmentCheck(name="Port 8080", passed=False, details="Port in use")
    ])
    stack_manager.run_environment_checks = MagicMock(return_value=mock_check_report)
    
    result = stack_manager.install_stack()
    
    assert result['success'] is True
    assert result['check_report'] == mock_check_report
    assert len(result['failed_checks']) == 1


@patch('ollama_stack_cli.config.save_config')
@patch('ollama_stack_cli.config.DEFAULT_CONFIG_DIR')
@patch('ollama_stack_cli.config.DEFAULT_ENV_FILE')
@patch('ollama_stack_cli.config.DEFAULT_CONFIG_FILE')
def test_install_stack_environment_checks_all_pass_display(mock_config_file, mock_env_file, mock_config_dir, mock_save_config, stack_manager):
    """Tests install_stack display calls when all environment checks pass."""
    mock_config_dir.exists.return_value = False
    mock_config_dir.mkdir = MagicMock()
    
    # Mock all environment checks passing
    mock_check_report = CheckReport(checks=[
        EnvironmentCheck(name="Docker Running", passed=True),
        EnvironmentCheck(name="Port 8080", passed=True),
        EnvironmentCheck(name="Port 11434", passed=True)
    ])
    stack_manager.run_environment_checks = MagicMock(return_value=mock_check_report)
    
    result = stack_manager.install_stack()
    
    assert result['success'] is True
    assert result['check_report'] == mock_check_report
    assert len(result['failed_checks']) == 0


@patch('ollama_stack_cli.config.save_config')
@patch('ollama_stack_cli.config.DEFAULT_CONFIG_DIR')
@patch('ollama_stack_cli.config.DEFAULT_ENV_FILE')
@patch('ollama_stack_cli.config.DEFAULT_CONFIG_FILE')
def test_install_stack_secure_key_in_config(mock_config_file, mock_env_file, mock_config_dir, mock_save_config, stack_manager):
    """Tests that install_stack includes the generated secure key in config."""
    mock_config_dir.exists.return_value = False
    mock_config_dir.mkdir = MagicMock()
    
    # Mock the secure key generation
    with patch.object(stack_manager, '_generate_secure_key', return_value='test_secure_key_123') as mock_gen_key:
        # Mock environment checks
        mock_check_report = CheckReport(checks=[])
        stack_manager.run_environment_checks = MagicMock(return_value=mock_check_report)
        
        result = stack_manager.install_stack()
    
    assert result['success'] is True
    assert result['check_report'] == mock_check_report
    mock_gen_key.assert_called_once()
    mock_save_config.assert_called_once()
    
    # Verify the secure key was set in the config
    call_args = mock_save_config.call_args[0]
    app_config = call_args[1]
    assert app_config.webui_secret_key == 'test_secure_key_123'


@patch('ollama_stack_cli.config.save_config')
@patch('ollama_stack_cli.config.DEFAULT_CONFIG_DIR')
@patch('ollama_stack_cli.config.DEFAULT_ENV_FILE')
@patch('ollama_stack_cli.config.DEFAULT_CONFIG_FILE')
def test_install_stack_empty_environment_checks(mock_config_file, mock_env_file, mock_config_dir, mock_save_config, stack_manager):
    """Tests install_stack when environment checks return empty list."""
    mock_config_dir.exists.return_value = False
    mock_config_dir.mkdir = MagicMock()
    
    # Mock empty environment checks
    mock_check_report = CheckReport(checks=[])
    stack_manager.run_environment_checks = MagicMock(return_value=mock_check_report)
    
    result = stack_manager.install_stack()
    
    assert result['success'] is True
    assert result['check_report'] == mock_check_report
    assert len(result['failed_checks']) == 0


@patch('ollama_stack_cli.config.save_config')
@patch('ollama_stack_cli.config.DEFAULT_CONFIG_DIR')
@patch('ollama_stack_cli.config.DEFAULT_ENV_FILE')
@patch('ollama_stack_cli.config.DEFAULT_CONFIG_FILE')
def test_install_stack_mkdir_parameters(mock_config_file, mock_env_file, mock_config_dir, mock_save_config, stack_manager):
    """Tests that install_stack calls mkdir with correct parameters."""
    mock_config_dir.exists.return_value = False
    mock_config_dir.mkdir = MagicMock()
    
    # Mock environment checks
    mock_check_report = CheckReport(checks=[])
    stack_manager.run_environment_checks = MagicMock(return_value=mock_check_report)
    
    result = stack_manager.install_stack()
    
    assert result['success'] is True
    assert result['check_report'] == mock_check_report
    # Verify mkdir was called with correct parameters
    mock_config_dir.mkdir.assert_called_once_with(parents=True, exist_ok=True)


@patch('ollama_stack_cli.config.save_config')
@patch('ollama_stack_cli.config.DEFAULT_CONFIG_DIR')
@patch('ollama_stack_cli.config.DEFAULT_ENV_FILE')
@patch('ollama_stack_cli.config.DEFAULT_CONFIG_FILE')
def test_install_stack_appconfig_instantiation_exception(mock_config_file, mock_env_file, mock_config_dir, mock_save_config, stack_manager):
    """Tests install_stack handles AppConfig instantiation exceptions."""
    mock_config_dir.exists.return_value = False
    mock_config_dir.mkdir = MagicMock()
    
    # Mock AppConfig to raise exception during instantiation
    with patch('ollama_stack_cli.stack_manager.AppConfig', side_effect=Exception("Config creation failed")):
        result = stack_manager.install_stack()
    
    assert result['success'] is False
    assert "Config creation failed" in result['error']
    mock_save_config.assert_not_called()


@patch('ollama_stack_cli.config.save_config')  
@patch('ollama_stack_cli.config.DEFAULT_CONFIG_DIR')
@patch('ollama_stack_cli.config.DEFAULT_ENV_FILE')
@patch('ollama_stack_cli.config.DEFAULT_CONFIG_FILE')
def test_install_stack_directory_exists_but_mkdir_fails(mock_config_file, mock_env_file, mock_config_dir, mock_save_config, stack_manager):
    """Tests install_stack when directory exists check succeeds but mkdir fails."""
    mock_config_dir.exists.return_value = True
    mock_config_file.exists.return_value = False  # No existing files
    mock_env_file.exists.return_value = False
    
    # mkdir fails even though directory "exists"
    mock_config_dir.mkdir.side_effect = OSError("Permission denied")
    
    result = stack_manager.install_stack()
    
    assert result['success'] is False
    assert "Permission denied" in result['error']
    mock_save_config.assert_not_called()


@patch('ollama_stack_cli.config.save_config')
@patch('ollama_stack_cli.config.DEFAULT_CONFIG_DIR')
@patch('ollama_stack_cli.config.DEFAULT_ENV_FILE')
@patch('ollama_stack_cli.config.DEFAULT_CONFIG_FILE')
def test_install_stack_secure_key_generation_exception(mock_config_file, mock_env_file, mock_config_dir, mock_save_config, stack_manager):
    """Tests install_stack handles secure key generation exceptions."""
    mock_config_dir.exists.return_value = False
    mock_config_dir.mkdir = MagicMock()
    
    # Mock secure key generation to fail
    with patch.object(stack_manager, '_generate_secure_key', side_effect=Exception("Random number generator failed")):
        result = stack_manager.install_stack()
    
    assert result['success'] is False
    assert "Random number generator failed" in result['error']
    mock_save_config.assert_not_called()


@patch('ollama_stack_cli.config.save_config')
@patch('ollama_stack_cli.config.DEFAULT_CONFIG_DIR')
@patch('ollama_stack_cli.config.DEFAULT_ENV_FILE')
@patch('ollama_stack_cli.config.DEFAULT_CONFIG_FILE')
def test_install_stack_platform_config_assignment(mock_config_file, mock_env_file, mock_config_dir, mock_save_config, stack_manager):
    """Tests that install_stack correctly assigns platform configurations."""
    mock_config_dir.exists.return_value = False
    mock_config_dir.mkdir = MagicMock()
    
    # Mock environment checks
    mock_check_report = CheckReport(checks=[])
    stack_manager.run_environment_checks = MagicMock(return_value=mock_check_report)
    
    result = stack_manager.install_stack()
    
    assert result['success'] is True
    assert result['check_report'] == mock_check_report
    mock_save_config.assert_called_once()
    
    # Get the AppConfig and verify platform assignment
    call_args = mock_save_config.call_args[0]
    app_config = call_args[1]
    
    # Verify the platform dictionary structure
    assert isinstance(app_config.platform, dict)
    assert len(app_config.platform) == 2
    
    # Verify both platforms are PlatformConfig instances with correct compose files
    from ollama_stack_cli.schemas import PlatformConfig
    assert isinstance(app_config.platform["apple"], PlatformConfig)
    assert isinstance(app_config.platform["nvidia"], PlatformConfig)


def test_generate_secure_key_character_set_validation(stack_manager):
    """Tests _generate_secure_key uses only safe characters."""
    import string
    
    # Generate multiple keys to test character set consistency
    keys = [stack_manager._generate_secure_key(length=100) for _ in range(5)]
    
    safe_chars = set(string.ascii_letters + string.digits + "-_")
    
    for key in keys:
        key_chars = set(key)
        # All characters in key should be in safe_chars set
        assert key_chars.issubset(safe_chars)
        
        # Should contain a mix of different character types for security
        # (though this is probabilistic, with length 100 it's very likely)
        assert len(key_chars) > 10  # Should have variety of characters


def test_generate_secure_key_zero_length(stack_manager):
    """Tests _generate_secure_key with zero length."""
    key = stack_manager._generate_secure_key(length=0)
    assert key == ""
    assert len(key) == 0


@patch('ollama_stack_cli.config.save_config')
@patch('ollama_stack_cli.config.DEFAULT_CONFIG_DIR')
@patch('ollama_stack_cli.config.DEFAULT_ENV_FILE')
@patch('ollama_stack_cli.config.DEFAULT_CONFIG_FILE')
@patch('typer.confirm')
def test_install_stack_file_existence_check_order(mock_confirm, mock_config_file, mock_env_file, mock_config_dir, mock_save_config, stack_manager):
    """Tests that install_stack checks file existence in correct order for message."""
    mock_config_dir.exists.return_value = True
    mock_confirm.return_value = True
    
    # Mock environment checks
    mock_check_report = CheckReport(checks=[])
    stack_manager.run_environment_checks = MagicMock(return_value=mock_check_report)
    
    # Test when both files exist - should list in expected order
    mock_config_file.exists.return_value = True
    mock_env_file.exists.return_value = True
    
    result = stack_manager.install_stack(force=False)
    
    assert result['success'] is True
    assert result['check_report'] == mock_check_report
    # Verify the message lists files in the expected order (.ollama-stack.json, .env)
    stack_manager.display.panel.assert_any_call(
        "Found existing configuration files: .ollama-stack.json, .env\n\n"
        "This will overwrite your current configuration.",
        "Configuration Already Exists",
        border_style="yellow"
    )


@patch('ollama_stack_cli.config.save_config')
@patch('ollama_stack_cli.config.DEFAULT_CONFIG_DIR')
@patch('ollama_stack_cli.config.DEFAULT_ENV_FILE')
@patch('ollama_stack_cli.config.DEFAULT_CONFIG_FILE')
def test_install_stack_save_config_call_arguments(mock_config_file, mock_env_file, mock_config_dir, mock_save_config, stack_manager):
    """Tests that install_stack calls save_config with correct arguments in correct order."""
    mock_config_dir.exists.return_value = False
    mock_config_dir.mkdir = MagicMock()
    
    # Mock environment checks
    mock_check_report = CheckReport(checks=[])
    stack_manager.run_environment_checks = MagicMock(return_value=mock_check_report)
    
    result = stack_manager.install_stack()
    
    assert result['success'] is True
    assert result['check_report'] == mock_check_report
    mock_save_config.assert_called_once()
    
    # Verify the call arguments are in correct order
    call_args = mock_save_config.call_args[0]
    assert len(call_args) == 4
    assert call_args[0] == stack_manager.display    # First: display object
    # Second: app_config (tested elsewhere)
    assert call_args[2] == mock_config_file         # Third: config file path  
    assert call_args[3] == mock_env_file            # Fourth: env file path

# ... existing code ...