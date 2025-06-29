import pytest
from unittest.mock import MagicMock, patch, call

from ollama_stack_cli.stack_manager import StackManager
from ollama_stack_cli.schemas import AppConfig, PlatformConfig, ServiceStatus, StackStatus, CheckReport, ResourceUsage, ServiceConfig

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
    """Tests configure_services_for_platform when ollama service doesn't exist."""
    stack_manager.platform = 'apple'
    stack_manager.config.services = {
        'webui': ServiceConfig(name='webui', type='docker'),
        'other_service': ServiceConfig(name='other_service', type='docker'),
    }
    
    # Should not raise exception when ollama service doesn't exist
    stack_manager.configure_services_for_platform()
    
    # Other services should remain unchanged
    assert stack_manager.config.services['webui'].type == 'docker'
    assert stack_manager.config.services['other_service'].type == 'docker' 