import pytest
from unittest.mock import MagicMock

from ollama_stack_cli.schemas import (
    StackStatus, ServiceStatus, CheckReport, EnvironmentCheck, ExtensionsConfig
)


@pytest.fixture
def mock_app_context():
    """Fixture to mock the AppContext and its components."""
    mock_context = MagicMock()
    mock_context.stack_manager = MagicMock()
    mock_context.display = MagicMock()
    mock_context.config = MagicMock()
    mock_context.config.fell_back_to_defaults = False
    mock_context.config.app_config.extensions = ExtensionsConfig(enabled=[])
    return mock_context


@pytest.fixture
def mock_stack_status():
    """Fixture for a sample StackStatus object."""
    return StackStatus(
        core_services=[
            ServiceStatus(name='webui', is_running=True),
            ServiceStatus(name='ollama', is_running=True)
        ],
        extensions=[]
    )


@pytest.fixture
def mock_check_report():
    """Fixture for a sample CheckReport object."""
    return CheckReport(checks=[
        EnvironmentCheck(name="Docker Daemon Running", passed=True),
        EnvironmentCheck(name="Port 11434 Available", passed=True)
    ])


@pytest.fixture
def mock_services_config():
    """Fixture for sample services configuration."""
    return {
        'webui': MagicMock(type='docker'),
        'ollama': MagicMock(type='native-api')
    } 