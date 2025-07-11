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
import os
import json
import tempfile
import signal
import psutil
from typing import List, Optional

# Import polling functions from helpers
from ollama_stack_cli.tests.integration.helpers import (
    poll_for_process_exit,
    poll_for_container_stop, 
    poll_for_file_deletion,
    poll_for_service_health
)

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

# --- Optimized Cleanup Functions ---

def _force_stop_all_stack_services():
    """Force stop all stack services including Docker containers and native processes."""
    from ollama_stack_cli.tests.integration.helpers import stop_native_ollama_if_running
    
    # Stop via CLI first
    runner = CliRunner()
    runner.invoke(app, ["stop"], catch_exceptions=True)
    
    # Force stop native Ollama
    stop_native_ollama_if_running()
    
    # Force kill any remaining native Ollama processes with polling
    try:
        subprocess.run(["pkill", "-f", "ollama serve"], check=False, timeout=5)
        poll_for_process_exit("ollama serve", timeout=10)
        
        subprocess.run(["pkill", "-f", "ollama"], check=False, timeout=3)
        poll_for_process_exit("ollama", timeout=5)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    
    # Force remove any stack Docker containers with polling
    try:
        client = docker.from_env()
        containers = client.containers.list(
            filters={"label": "ollama-stack.component"}, 
            all=True
        )
        for container in containers:
            try:
                container.remove(force=True)
                poll_for_container_stop(container.name, timeout=10)
            except Exception:
                pass
    except Exception:
        pass

def _cleanup_config_directory():
    """Clean up the configuration directory completely."""
    config_dir = os.path.expanduser("~/.ollama-stack")
    if os.path.exists(config_dir):
        try:
            shutil.rmtree(config_dir)
            poll_for_file_deletion(config_dir, timeout=5)
        except Exception:
            # If we can't remove the whole directory, try removing specific files
            for file_name in [".ollama-stack.json", ".env"]:
                file_path = os.path.join(config_dir, file_name)
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                        poll_for_file_deletion(file_path, timeout=3)
                    except Exception:
                        pass

def _cleanup_backup_artifacts():
    """Clean up any backup artifacts created during testing."""
    config_dir = os.path.expanduser("~/.ollama-stack")
    backups_dir = os.path.join(config_dir, "backups")
    if os.path.exists(backups_dir):
        try:
            shutil.rmtree(backups_dir)
            poll_for_file_deletion(backups_dir, timeout=5)
        except Exception:
            pass

def _stop_services_only():
    """Lightweight cleanup that only stops services without full config cleanup."""
    _force_stop_all_stack_services()
    time.sleep(1)  # Reduced wait time

def _cleanup_minimal():
    """Minimal cleanup for stateless tests."""
    _stop_services_only()

def _cleanup_full():
    """Full cleanup for stateful tests."""
    _force_stop_all_stack_services()
    _cleanup_config_directory()
    _cleanup_backup_artifacts()
    time.sleep(1)  # Reduced wait time

# --- Optimized Fixtures ---

@pytest.fixture(scope="session")
def runner():
    """Shared CLI runner for all integration tests."""
    return CliRunner()

@pytest.fixture(autouse=True)
def clean_stack_between_tests(request, runner):
    """
    Optimized fixture that provides conditional cleanup based on test markers.
    - @stateless tests get minimal cleanup (stop services only)
    - @stateful tests get full cleanup (stop services + config cleanup)
    - Default behavior is full cleanup for safety
    """
    # Determine cleanup strategy based on test markers
    is_stateless = request.node.get_closest_marker("stateless") is not None
    is_stateful = request.node.get_closest_marker("stateful") is not None
    
    # Pre-test cleanup
    if is_stateless:
        _cleanup_minimal()
    else:
        _cleanup_full()
    
    yield
    
    # Post-test cleanup
    if is_stateless:
        _cleanup_minimal()
    else:
        _cleanup_full()

@pytest.fixture(scope="module")
def module_cleanup(request):
    """
    Module-scoped cleanup for tests marked with @module_cleanup.
    Allows tests within a module to share setup/teardown for better performance.
    """
    has_module_cleanup = request.node.get_closest_marker("module_cleanup") is not None
    
    if has_module_cleanup:
        # Pre-module cleanup
        _cleanup_full()
        yield
        # Post-module cleanup
        _cleanup_full()
    else:
        yield

@pytest.fixture
def stop_services_only():
    """
    Lightweight fixture that only stops services without full config cleanup.
    Use for read-only tests that don't modify configuration.
    """
    _stop_services_only()
    yield
    _stop_services_only()

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
    config_dir = os.path.expanduser("~/.ollama-stack")
    
    # Clean up before test
    if os.path.exists(config_dir):
        shutil.rmtree(config_dir)
    
    # Ensure directory exists
    os.makedirs(config_dir, exist_ok=True)
    
    # Create .env file with correct project name to ensure consistent project naming
    env_file = os.path.join(config_dir, ".env")
    with open(env_file, "w") as f:
        f.write("PROJECT_NAME=ollama-stack\n")
        f.write("WEBUI_SECRET_KEY=test-secret-key\n")
    
    yield config_dir
    
    # Clean up after test
    if os.path.exists(config_dir):
        shutil.rmtree(config_dir)

@pytest.fixture(scope="session", autouse=True)
def ensure_docker_images():
    """
    Ensure Docker images are available for testing, using cache when possible.
    
    This is a transparent optimization that loads images from local cache
    instead of downloading from the internet, significantly speeding up
    integration tests without changing their behavior.
    """
    if not _is_docker_available():
        # If Docker isn't available, let individual tests handle it
        yield
        return
    
    try:
        from ollama_stack_cli.tests.integration.image_sandbox import load_test_images
        
        # Load images from cache at the start of the test session
        success = load_test_images()
        
        if not success:
            # If cache loading fails, tests will fall back to normal Docker behavior
            # This ensures tests don't break if cache is unavailable
            print("Warning: Failed to load cached Docker images, tests may be slower")
        
        yield
        
    except Exception as e:
        # If anything goes wrong with caching, let tests proceed normally
        print(f"Warning: Docker image cache unavailable ({e}), tests may be slower")
        yield

@pytest.fixture(scope="session", autouse=True)
def cleanup_ollama_stack_artifacts():
    """
    After the entire integration test session, remove all persistent ollama-stack artifacts
    (backups, data, config) to ensure a clean slate for future runs.
    """
    yield  # Run all tests first
    
    # Final cleanup after all tests
    _cleanup_full()

@pytest.fixture
def pin_stack_version(tmp_path, monkeypatch):
    """Pin the stack config to version 0.2.0 in a unique temp config dir for each test."""
    config_dir = tmp_path / ".ollama-stack"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_file = config_dir / ".ollama-stack.json"
    # Pin to old version
    config = {
        "version": "0.2.0",
        "services": {"ollama": {}, "webui": {}, "mcp_proxy": {}},
        "platform": {"default": {}}
    }
    with open(config_file, "w") as f:
        json.dump(config, f)
    
    # Create .env file
    env_file = config_dir / ".env"
    with open(env_file, "w") as f:
        f.write("PROJECT_NAME=ollama-stack\n")
        f.write("WEBUI_SECRET_KEY=test-secret-key\n")
    
    # Set env var so CLI uses this config dir
    monkeypatch.setenv("OLLAMA_STACK_CONFIG_DIR", str(config_dir))
    yield str(config_dir)
    # Cleanup handled by tmp_path

@pytest.fixture
def isolated_test_environment(tmp_path, monkeypatch):
    """
    Create a completely isolated test environment with its own config directory.
    This ensures tests don't interfere with each other or the user's actual config.
    """
    # Create isolated config directory
    config_dir = tmp_path / ".ollama-stack"
    config_dir.mkdir(parents=True, exist_ok=True)
    
    # Set env var so CLI uses this config dir
    monkeypatch.setenv("OLLAMA_STACK_CONFIG_DIR", str(config_dir))
    
    yield str(config_dir)
    
    # Cleanup handled by tmp_path

@pytest.fixture
def stack_with_volumes(runner, clean_config_dir):
    """
    Fixture that ensures the stack is installed and started with volumes created.
    This is useful for tests that need to verify volume removal functionality.
    """
    # Install and start the stack to ensure volumes are created
    result = runner.invoke(app, ["install", "--force"])
    assert result.exit_code == 0, f"Install failed: {result.stdout}"
    
    result = runner.invoke(app, ["start"])
    assert result.exit_code == 0, f"Start failed: {result.stdout}"
    
    # Wait a moment for services to fully start and create volumes
    time.sleep(3)
    
    # Verify that volumes were created with the correct project name
    client = docker.from_env()
    volumes = client.volumes.list(filters={"label": "com.docker.compose.project=ollama-stack"})
    
    # If no volumes found, try alternative project names that might be used
    if len(volumes) == 0:
        # Check for volumes with different project name patterns
        all_volumes = client.volumes.list()
        for volume in all_volumes:
            if volume.attrs and volume.attrs.get("Labels", {}).get("com.docker.compose.project"):
                project_name = volume.attrs["Labels"]["com.docker.compose.project"]
                if "ollama" in project_name.lower():
                    print(f"Found volumes with project name: {project_name}")
                    # Update the test to use the actual project name
                    volumes = client.volumes.list(filters={"label": f"com.docker.compose.project={project_name}"})
                    break
    
    yield {
        "config_dir": clean_config_dir,
        "volumes": volumes,
        "volume_names": [vol.name for vol in volumes]
    }
    
    # Cleanup is handled by the clean_config_dir fixture

# --- Context Managers for Resource Management ---

class TemporaryConfigDir:
    """Context manager for temporary configuration directories."""
    
    def __init__(self, tmp_path, monkeypatch):
        self.tmp_path = tmp_path
        self.monkeypatch = monkeypatch
        self.config_dir = None
        self.original_env = None
    
    def __enter__(self):
        self.config_dir = self.tmp_path / ".ollama-stack"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        # Store original env var
        self.original_env = os.environ.get("OLLAMA_STACK_CONFIG_DIR")
        
        # Set new env var
        self.monkeypatch.setenv("OLLAMA_STACK_CONFIG_DIR", str(self.config_dir))
        
        return str(self.config_dir)
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Restore original env var
        if self.original_env is not None:
            self.monkeypatch.setenv("OLLAMA_STACK_CONFIG_DIR", self.original_env)
        else:
            self.monkeypatch.delenv("OLLAMA_STACK_CONFIG_DIR", raising=False)

class ArtifactTracker:
    """Context manager for tracking and cleaning up test artifacts."""
    
    def __init__(self):
        self.artifacts: List[str] = []
    
    def track_file(self, file_path: str):
        """Track a file for cleanup."""
        self.artifacts.append(file_path)
    
    def track_dir(self, dir_path: str):
        """Track a directory for cleanup."""
        self.artifacts.append(dir_path)
    
    def cleanup(self):
        """Clean up all tracked artifacts."""
        for artifact in self.artifacts:
            try:
                if os.path.isfile(artifact):
                    os.remove(artifact)
                elif os.path.isdir(artifact):
                    shutil.rmtree(artifact)
            except Exception:
                pass
        self.artifacts.clear()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()

# --- Utility Functions ---

def _is_docker_available() -> bool:
    """Check if Docker is available and running."""
    try:
        client = docker.from_env()
        client.ping()
        return True
    except Exception:
        return False

def is_docker_available():
    """Check if Docker is available and running."""
    return _is_docker_available() 

# Note: Docker image caching is now handled transparently by the
# ensure_docker_images session fixture above 