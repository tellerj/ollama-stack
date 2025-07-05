import pytest
import docker
import platform
import subprocess
import shutil
import socket
import time
import urllib.request
import urllib.error
from typer.testing import CliRunner
from ollama_stack_cli.main import app

# --- Test Configuration ---

IS_APPLE_SILICON = platform.system() == "Darwin" and platform.machine() == "arm64"
EXPECTED_DOCKER_COMPONENTS = {"webui", "mcp_proxy"}
EXPECTED_ALL_COMPONENTS = {"webui", "mcp_proxy", "ollama"}

# Service health check URLs
HEALTH_CHECK_URLS = {
    "webui": "http://localhost:8080",
    "mcp_proxy": "http://localhost:8200",
    "ollama": "http://localhost:11434"
}

# --- Shared Fixtures ---

@pytest.fixture(scope="session")
def runner():
    """Shared CLI runner for all integration tests."""
    return CliRunner()

@pytest.fixture(autouse=True)
def clean_stack_between_tests(runner):
    """
    A fixture that ensures the stack is stopped before and after each integration test,
    providing a clean, isolated environment.
    """
    from tests.integration.helpers import stop_native_ollama_if_running
    
    runner.invoke(app, ["stop"])
    stop_native_ollama_if_running()
    time.sleep(1)  # Allow services to fully stop
    yield
    runner.invoke(app, ["stop"])
    stop_native_ollama_if_running()

@pytest.fixture(scope="session")
def docker_client():
    """Shared Docker client for integration tests."""
    if not _is_docker_available():
        pytest.skip("Docker not available")
    return docker.from_env()

@pytest.fixture
def temp_backup_dir(tmp_path):
    """Create a temporary directory for backup testing."""
    backup_dir = tmp_path / "backup"
    backup_dir.mkdir()
    return backup_dir

@pytest.fixture
def clean_config_dir():
    """Ensure clean configuration directory for tests."""
    import os
    import shutil
    
    config_dir = os.path.expanduser("~/.ollama-stack")
    
    # Clean up before test
    if os.path.exists(config_dir):
        shutil.rmtree(config_dir)
    
    yield config_dir
    
    # Clean up after test
    if os.path.exists(config_dir):
        shutil.rmtree(config_dir)

# --- Helper Functions (duplicated from main integration file for now) ---

def _is_docker_available() -> bool:
    """Check if Docker is available and running."""
    try:
        client = docker.from_env()
        client.ping()
        return True
    except Exception:
        return False

# Export commonly used functions
def is_docker_available():
    """Public interface for Docker availability check."""
    return _is_docker_available() 