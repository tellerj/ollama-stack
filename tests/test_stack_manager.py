import pytest
from unittest.mock import MagicMock, patch, call
from pathlib import Path

from ollama_stack_cli.stack_manager import StackManager
from ollama_stack_cli.schemas import AppConfig, PlatformConfig, ServiceStatus, StackStatus, CheckReport, ResourceUsage, ServiceConfig, ExtensionsConfig

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
    mock_docker_client.client.volumes.list.assert_called_once_with(filters=expected_filter)
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
# Phase 5.1 New Methods Tests - Stack Uninstall
# =============================================================================

@patch('ollama_stack_cli.stack_manager.Path')
def test_uninstall_stack_complete_uninstall(mock_path, stack_manager, mock_docker_client):
    """Tests uninstall_stack complete uninstall process."""
    # Mock stack running and successful stops
    stack_manager.is_stack_running = MagicMock(return_value=True)
    stack_manager.stop_docker_services = MagicMock(return_value=True)
    stack_manager.stop_native_services = MagicMock(return_value=True)
    stack_manager.cleanup_resources = MagicMock(return_value=True)
    mock_docker_client.remove_resources = MagicMock(return_value=True)
    
    # Mock services configuration
    stack_manager.config.services = {'ollama': MagicMock(type='native-api')}
    
    # Mock file operations
    mock_env_file = MagicMock()
    mock_config_file = MagicMock()
    mock_env_file.exists.return_value = True
    mock_config_file.exists.return_value = True
    
    mock_path.side_effect = lambda name: mock_env_file if name == ".env" else mock_config_file
    
    result = stack_manager.uninstall_stack()
    
    assert result is True
    stack_manager.stop_docker_services.assert_called_once()
    stack_manager.stop_native_services.assert_called_once_with(['ollama'])
    stack_manager.cleanup_resources.assert_called_once_with(remove_volumes=False, force=False)
    mock_docker_client.remove_resources.assert_called_once_with(remove_images=True, force=False)
    mock_env_file.unlink.assert_called_once()
    mock_config_file.unlink.assert_called_once()

@patch('ollama_stack_cli.stack_manager.Path')
def test_uninstall_stack_keep_config(mock_path, stack_manager, mock_docker_client):
    """Tests uninstall_stack with keep_config=True."""
    # Mock minimal setup
    stack_manager.is_stack_running = MagicMock(return_value=False)
    stack_manager.cleanup_resources = MagicMock(return_value=True)
    mock_docker_client.remove_resources = MagicMock(return_value=True)
    
    result = stack_manager.uninstall_stack(keep_config=True)
    
    assert result is True
    # Should not call Path operations when keeping config
    mock_path.assert_not_called()

@patch('ollama_stack_cli.stack_manager.Path')
def test_uninstall_stack_remove_volumes(mock_path, stack_manager, mock_docker_client):
    """Tests uninstall_stack with remove_volumes=True."""
    # Mock minimal setup
    stack_manager.is_stack_running = MagicMock(return_value=False)
    stack_manager.cleanup_resources = MagicMock(return_value=True)
    mock_docker_client.remove_resources = MagicMock(return_value=True)
    
    # Mock file operations
    mock_env_file = MagicMock()
    mock_config_file = MagicMock()
    mock_env_file.exists.return_value = False
    mock_config_file.exists.return_value = False
    
    mock_path.side_effect = lambda name: mock_env_file if name == ".env" else mock_config_file
    
    result = stack_manager.uninstall_stack(remove_volumes=True, force=True)
    
    assert result is True
    stack_manager.cleanup_resources.assert_called_once_with(remove_volumes=True, force=True)
    mock_docker_client.remove_resources.assert_called_once_with(remove_images=True, force=True)

def test_uninstall_stack_stop_services_failure(stack_manager, mock_docker_client):
    """Tests uninstall_stack continues when stop services fails."""
    # Mock stack running with stop failures
    stack_manager.is_stack_running = MagicMock(return_value=True)
    stack_manager.stop_docker_services = MagicMock(return_value=False)
    stack_manager.stop_native_services = MagicMock(return_value=False)
    stack_manager.cleanup_resources = MagicMock(return_value=True)
    mock_docker_client.remove_resources = MagicMock(return_value=True)
    
    # Mock services configuration  
    stack_manager.config.services = {'ollama': MagicMock(type='native-api')}
    
    result = stack_manager.uninstall_stack(keep_config=True)
    
    assert result is True  # Should continue despite stop failures

def test_uninstall_stack_cleanup_resources_failure(stack_manager, mock_docker_client):
    """Tests uninstall_stack continues when resource cleanup fails."""
    # Mock cleanup failure
    stack_manager.is_stack_running = MagicMock(return_value=False)
    stack_manager.cleanup_resources = MagicMock(return_value=False)
    mock_docker_client.remove_resources = MagicMock(return_value=True)
    
    result = stack_manager.uninstall_stack(keep_config=True)
    
    assert result is True  # Should continue despite cleanup failure

def test_uninstall_stack_remove_images_failure(stack_manager, mock_docker_client):
    """Tests uninstall_stack continues when image removal fails."""
    # Mock image removal failure
    stack_manager.is_stack_running = MagicMock(return_value=False)
    stack_manager.cleanup_resources = MagicMock(return_value=True)
    mock_docker_client.remove_resources = MagicMock(return_value=False)
    
    result = stack_manager.uninstall_stack(keep_config=True)
    
    assert result is True  # Should continue despite image removal failure

@patch('ollama_stack_cli.stack_manager.Path')
def test_uninstall_stack_file_removal_failure(mock_path, stack_manager, mock_docker_client):
    """Tests uninstall_stack handles file removal failures gracefully."""
    # Mock minimal setup
    stack_manager.is_stack_running = MagicMock(return_value=False)
    stack_manager.cleanup_resources = MagicMock(return_value=True)
    mock_docker_client.remove_resources = MagicMock(return_value=True)
    
    # Mock file operations with failure
    mock_env_file = MagicMock()
    mock_env_file.exists.return_value = True
    mock_env_file.unlink.side_effect = PermissionError("Permission denied")
    
    mock_config_file = MagicMock()
    mock_config_file.exists.return_value = True
    
    mock_path.side_effect = lambda name: mock_env_file if name == ".env" else mock_config_file
    
    result = stack_manager.uninstall_stack()
    
    assert result is True  # Should succeed despite file removal failure

@patch('ollama_stack_cli.stack_manager.Path')
def test_uninstall_stack_files_not_exist(mock_path, stack_manager, mock_docker_client):
    """Tests uninstall_stack when config files don't exist."""
    # Mock minimal setup
    stack_manager.is_stack_running = MagicMock(return_value=False)
    stack_manager.cleanup_resources = MagicMock(return_value=True)
    mock_docker_client.remove_resources = MagicMock(return_value=True)
    
    # Mock files don't exist
    mock_env_file = MagicMock()
    mock_config_file = MagicMock()
    mock_env_file.exists.return_value = False
    mock_config_file.exists.return_value = False
    
    mock_path.side_effect = lambda name: mock_env_file if name == ".env" else mock_config_file
    
    result = stack_manager.uninstall_stack()
    
    assert result is True
    mock_env_file.unlink.assert_not_called()
    mock_config_file.unlink.assert_not_called()

def test_uninstall_stack_exception_handling(stack_manager):
    """Tests uninstall_stack handles exceptions gracefully."""
    # Mock exception during is_stack_running
    stack_manager.is_stack_running = MagicMock(side_effect=Exception("Docker daemon not running"))
    
    result = stack_manager.uninstall_stack()
    
    assert result is False


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