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
from typing import List, Set, Optional
from contextlib import contextmanager

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

# --- Test Artifact Tracking ---

class TestArtifactTracker:
    """Tracks test artifacts for automatic cleanup."""
    
    def __init__(self):
        self.created_files: Set[str] = set()
        self.created_dirs: Set[str] = set()
        self.created_containers: Set[str] = set()
        self.modified_configs: Set[str] = set()
    
    def track_created_file(self, file_path: str):
        """Track a file that was created during the test."""
        self.created_files.add(file_path)
    
    def track_created_dir(self, dir_path: str):
        """Track a directory that was created during the test."""
        self.created_dirs.add(dir_path)
    
    def track_created_container(self, container_name: str):
        """Track a Docker container that was created during the test."""
        self.created_containers.add(container_name)
    
    def track_modified_config(self, config_path: str):
        """Track a config file that was modified during the test."""
        self.modified_configs.add(config_path)
    
    def cleanup_tracked_artifacts(self):
        """Clean up all tracked artifacts."""
        # Clean up created files
        for file_path in self.created_files:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception:
                pass
        
        # Clean up created directories
        for dir_path in self.created_dirs:
            try:
                if os.path.exists(dir_path):
                    shutil.rmtree(dir_path)
            except Exception:
                pass
        
        # Clean up created containers
        for container_name in self.created_containers:
            try:
                client = docker.from_env()
                containers = client.containers.list(
                    filters={"name": container_name}, 
                    all=True
                )
                for container in containers:
                    container.remove(force=True)
            except Exception:
                pass
        
        # Reset tracking
        self.created_files.clear()
        self.created_dirs.clear()
        self.created_containers.clear()
        self.modified_configs.clear()
    
    @contextmanager
    def track_artifacts(self):
        """Context manager for automatic artifact tracking and cleanup."""
        try:
            yield self
        finally:
            self.cleanup_tracked_artifacts()

# --- Enhanced Cleanup and State Management ---

def ensure_clean_test_environment():
    """
    Ensure the test environment is completely clean before starting a test.
    This should be called at the beginning of each test that requires a clean state.
    """
    # Force stop all services
    force_stop_all_stack_services()
    
    # Clean up config directory
    cleanup_config_directory()
    
    # Clean up backup artifacts
    cleanup_backup_artifacts()
    
    # Wait for cleanup to complete with polling
    time.sleep(1)
    
    # Verify clean state
    assert verify_clean_environment(), "Test environment is not clean"

def force_stop_all_stack_services():
    """Force stop all stack services including Docker containers and native processes."""
    # Stop via CLI first
    runner = CliRunner()
    runner.invoke(app, ["stop"], catch_exceptions=True)
    
    # Force stop native Ollama
    stop_native_ollama_if_running()
    
    # Force kill any remaining native Ollama processes with polling
    try:
        subprocess.run(["pkill", "-f", "ollama serve"], check=False, timeout=5)
        # Poll for process exit instead of fixed sleep
        start_time = time.time()
        while time.time() - start_time < 10:
            try:
                result = subprocess.run(
                    ["pgrep", "-f", "ollama serve"], 
                    capture_output=True, 
                    text=True, 
                    check=False
                )
                if result.returncode != 0:  # Process not found
                    break
            except (subprocess.TimeoutExpired, FileNotFoundError):
                break
            time.sleep(0.5)
        
        subprocess.run(["pkill", "-f", "ollama"], check=False, timeout=3)
        # Poll for process exit
        start_time = time.time()
        while time.time() - start_time < 5:
            try:
                result = subprocess.run(
                    ["pgrep", "-f", "ollama"], 
                    capture_output=True, 
                    text=True, 
                    check=False
                )
                if result.returncode != 0:  # Process not found
                    break
            except (subprocess.TimeoutExpired, FileNotFoundError):
                break
            time.sleep(0.5)
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
                # Poll for container stop
                start_time = time.time()
                while time.time() - start_time < 10:
                    try:
                        containers_check = client.containers.list(
                            filters={"name": container.name}, 
                            all=True
                        )
                        if not containers_check:
                            break
                        # Check if container is stopped
                        for cont in containers_check:
                            if cont.status == "exited":
                                break
                    except Exception:
                        break
                    time.sleep(0.5)
            except Exception:
                pass
    except Exception:
        pass

def cleanup_config_directory():
    """Clean up the configuration directory completely."""
    config_dir = os.path.expanduser("~/.ollama-stack")
    if os.path.exists(config_dir):
        try:
            shutil.rmtree(config_dir)
            # Poll for directory deletion
            start_time = time.time()
            while time.time() - start_time < 5:
                if not os.path.exists(config_dir):
                    break
                time.sleep(0.2)
        except Exception:
            # If we can't remove the whole directory, try removing specific files
            for file_name in [".ollama-stack.json", ".env"]:
                file_path = os.path.join(config_dir, file_name)
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                        # Poll for file deletion
                        start_time = time.time()
                        while time.time() - start_time < 3:
                            if not os.path.exists(file_path):
                                break
                            time.sleep(0.2)
                    except Exception:
                        pass

def cleanup_backup_artifacts():
    """Clean up any backup artifacts created during testing."""
    config_dir = os.path.expanduser("~/.ollama-stack")
    backups_dir = os.path.join(config_dir, "backups")
    if os.path.exists(backups_dir):
        try:
            shutil.rmtree(backups_dir)
            # Poll for directory deletion
            start_time = time.time()
            while time.time() - start_time < 5:
                if not os.path.exists(backups_dir):
                    break
                time.sleep(0.2)
        except Exception:
            pass

def cleanup_minimal():
    """Minimal cleanup for stateless tests - only stops services."""
    force_stop_all_stack_services()
    time.sleep(1)

def cleanup_full():
    """Full cleanup for stateful tests - stops services and cleans config."""
    force_stop_all_stack_services()
    cleanup_config_directory()
    cleanup_backup_artifacts()
    time.sleep(1)

def verify_clean_environment():
    """
    Verify that the environment is completely clean.
    Returns True if clean, False otherwise.
    """
    # Check for running services
    running_services = get_actual_running_services()
    if running_services:
        return False
    
    # Check for config files
    config_dir = os.path.expanduser("~/.ollama-stack")
    
    if os.path.exists(config_dir):
        config_files = [".ollama-stack.json", ".env"]
        for file_name in config_files:
            file_path = os.path.join(config_dir, file_name)
            if os.path.exists(file_path):
                return False
    
    # Check for backup artifacts
    backups_dir = os.path.join(config_dir, "backups")
    if os.path.exists(backups_dir):
        return False
    
    return True

def cleanup_test_artifacts(artifacts_list):
    """
    Clean up a list of test artifacts (files, directories, etc.).
    
    Args:
        artifacts_list: List of paths to clean up
    """
    for artifact_path in artifacts_list:
        try:
            if os.path.isfile(artifact_path):
                os.remove(artifact_path)
            elif os.path.isdir(artifact_path):
                shutil.rmtree(artifact_path)
        except Exception:
            pass  # Ignore cleanup errors

# --- Helper Functions ---

def is_docker_available() -> bool:
    """Check if Docker is available and running."""
    try:
        client = docker.from_env()
        client.ping()
        return True
    except Exception:
        return False


def get_running_stack_components() -> set:
    """
    Connects to Docker to find all running containers with the stack's component
    label and returns a set of the component names.
    Returns empty set if Docker is not available.
    """
    if not is_docker_available():
        return set()
    
    try:
        client = docker.from_env()
        containers = client.containers.list(filters={"label": "ollama-stack.component", "status": "running"})
        return {c.labels.get("ollama-stack.component") for c in containers if c.labels.get("ollama-stack.component")}
    except Exception:
        return set()


def is_ollama_native_service_running() -> bool:
    """Check if native Ollama service is running (for Apple Silicon)."""
    if not shutil.which("ollama"):
        return False
    try:
        result = subprocess.run(
            ["pgrep", "-f", "ollama serve"],
            capture_output=True,
            text=True,
            timeout=3
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def _check_tcp_connectivity(host: str, port: int, timeout: float = 2.0) -> bool:
    """
    Test TCP connectivity to a host and port.
    
    This matches Docker's health check approach which uses TCP socket tests.
    """
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (socket.error, socket.timeout, ConnectionRefusedError):
        return False


def wait_for_service_health(service_name: str, timeout: int = 30) -> bool:
    """
    Wait for a service to become healthy within timeout seconds.
    
    Uses a two-tier approach matching the production health check:
    1. Try HTTP health check first (more comprehensive)
    2. Fall back to TCP connectivity check (matches Docker's health check)
    """
    url = HEALTH_CHECK_URLS.get(service_name)
    if not url:
        return True  # Assume healthy if no health check URL
    
    # Extract port from URL for TCP fallback
    import urllib.parse
    parsed_url = urllib.parse.urlparse(url)
    port = parsed_url.port or (80 if parsed_url.scheme == 'http' else 443)
    
    start_time = time.time()
    while time.time() - start_time < timeout:
        # First, try HTTP health check (more comprehensive)
        try:
            with urllib.request.urlopen(url, timeout=3) as response:
                if 200 <= response.status < 300:
                    return True
                # HTTP responded but with error status, fall back to TCP check
        except (urllib.error.URLError, ConnectionRefusedError, TimeoutError, socket.timeout, socket.error):
            # HTTP failed, fall back to TCP check
            pass

        # Fall back to TCP connectivity check (matches Docker's approach)
        if _check_tcp_connectivity("localhost", port):
            return True
        
        time.sleep(1)
    
    return False


def get_actual_running_services() -> set:
    """Get all actually running services (Docker + native)."""
    running_services = get_running_stack_components()
    
    # Add native ollama if running on Apple Silicon
    if IS_APPLE_SILICON and is_ollama_native_service_running():
        running_services.add("ollama")
    
    return running_services


def stop_native_ollama_if_running():
    """Helper to stop native Ollama if it's running."""
    if IS_APPLE_SILICON and is_ollama_native_service_running():
        try:
            subprocess.run(["pkill", "-f", "ollama serve"], check=False, timeout=10)
            time.sleep(2)  # Give it time to stop
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass


def create_test_backup_structure(backup_dir):
    """Create a realistic backup directory structure for testing."""
    import json
    import os
    import tarfile
    
    # Create manifest with proper BackupManifest structure
    manifest = {
        "backup_id": "test-backup-12345",
        "created_at": "2024-01-01T00:00:00Z",
        "stack_version": "0.3.0",
        "cli_version": "0.3.0",
        "platform": "apple" if IS_APPLE_SILICON else "default",
        "backup_config": {
            "include_volumes": True,
            "include_config": True,
            "include_extensions": True,
            "compression": True,
            "encryption": False,
            "exclude_patterns": []
        },
        "volumes": ["ollama-stack_webui_data", "ollama-stack_mcp_data", "ollama-stack_ollama_data"],
        "config_files": [".ollama-stack.json", ".env"],
        "extensions": [],
        "checksum": None,
        "size_bytes": None,
        "description": None
    }
    
    manifest_path = backup_dir / "backup_manifest.json"
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)
    
    # Create mock volume data as .tar.gz files
    volumes_dir = backup_dir / "volumes"
    volumes_dir.mkdir()
    
    for volume_name in ["ollama-stack_webui_data", "ollama-stack_mcp_data", "ollama-stack_ollama_data"]:
        # Create a proper .tar.gz file for each volume
        volume_file = volumes_dir / f"{volume_name}.tar.gz"
        
        # Create a simple tar.gz file with some dummy data
        import tarfile
        import io
        
        # Create file content in memory
        file_content = b'{"test": "data"}'
        
        # Create tar.gz file
        with tarfile.open(volume_file, "w:gz") as tar:
            # Add a test file to the tar
            tarinfo = tarfile.TarInfo(name="config.json")
            tarinfo.size = len(file_content)
            tar.addfile(tarinfo, io.BytesIO(file_content))
            
            # Add another test file
            data_content = b"test volume data"
            tarinfo2 = tarfile.TarInfo(name="data.txt")
            tarinfo2.size = len(data_content)
            tar.addfile(tarinfo2, io.BytesIO(data_content))
    
    # Create configuration backup
    config_dir = backup_dir / "config"
    config_dir.mkdir()
    
    (config_dir / ".ollama-stack.json").write_text('{"docker_compose_file": "docker-compose.yml"}')
    (config_dir / ".env").write_text('PROJECT_NAME=ollama-stack\nWEBUI_SECRET_KEY=test-key')
    
    return manifest_path


def extract_secret_key_from_env(env_file_path):
    """Extract the secret key from an environment file."""
    with open(env_file_path, 'r') as f:
        content = f.read()
    for line in content.strip().split('\n'):
        if line.startswith("WEBUI_SECRET_KEY="):
            key = line.split("=", 1)[1]
            # Remove quotes if present
            if key.startswith("'") and key.endswith("'"):
                key = key[1:-1]
            return key
    raise AssertionError("WEBUI_SECRET_KEY not found in environment file")


def verify_stack_completely_stopped():
    """Verify that absolutely no stack services are running."""
    # Check Docker services
    docker_services = get_running_stack_components()
    if docker_services:
        return False, f"Docker services still running: {docker_services}"
    
    # Check native Ollama (if on Apple Silicon)
    if IS_APPLE_SILICON and is_ollama_native_service_running():
        return False, "Native Ollama service still running"
    
    return True, "All services stopped"


def wait_for_stack_to_stop(timeout: int = 30) -> bool:
    """Wait for the stack to completely stop."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        stopped, message = verify_stack_completely_stopped()
        if stopped:
            return True
        time.sleep(1)
    return False


def get_docker_container_logs(container_name: str, tail: int = 100) -> str:
    """Get logs from a Docker container."""
    if not is_docker_available():
        return ""
    
    try:
        client = docker.from_env()
        containers = client.containers.list(
            filters={"label": "ollama-stack.component", "name": container_name}
        )
        if containers:
            return containers[0].logs(tail=tail).decode('utf-8')
        return ""
    except Exception:
        return ""


def simulate_disk_full_scenario(directory):
    """Simulate a disk full scenario for testing failure handling."""
    import os
    
    # Create a large file to fill up space in the test directory
    try:
        large_file = directory / "large_file.tmp"
        # Create a file that takes up significant space
        with open(large_file, 'wb') as f:
            f.write(b'0' * (100 * 1024 * 1024))  # 100MB
        return large_file
    except OSError:
        # If we can't create the file, return None
        return None


def cleanup_test_files(file_list):
    """Clean up test files created during testing."""
    import os
    
    for file_path in file_list:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except OSError:
            pass  # Ignore cleanup errors


def create_corrupted_backup(backup_dir):
    """Create a backup with corrupted manifest for testing error handling."""
    import json
    
    # Create corrupted manifest
    manifest_path = backup_dir / "backup_manifest.json"
    with open(manifest_path, 'w') as f:
        f.write('{"invalid": "json"')  # Missing closing brace
    
    return manifest_path


def create_incomplete_backup(backup_dir):
    """Create a backup with missing components for testing validation."""
    import json
    
    # Create manifest but missing volume data
    manifest = {
        "backup_id": "test-incomplete-backup-12345",
        "created_at": "2024-01-01T00:00:00Z",
        "stack_version": "0.3.0",
        "cli_version": "0.3.0",
        "platform": "apple" if IS_APPLE_SILICON else "default",
        "backup_config": {
            "include_volumes": True,
            "include_config": True,
            "include_extensions": True,
            "compression": True,
            "encryption": False,
            "exclude_patterns": []
        },
        "volumes": ["ollama-stack_webui_data", "ollama-stack_mcp_data"],
        "config_files": [".ollama-stack.json", ".env"],
        "extensions": [],
        "checksum": None,
        "size_bytes": None,
        "description": None
    }
    
    manifest_path = backup_dir / "backup_manifest.json"
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)
    
    # Don't create volume data - this makes it incomplete
    return manifest_path


def simulate_network_interruption():
    """Simulate network interruption for testing resilience."""
    # This could be implemented with network manipulation tools
    # For now, it's a placeholder for more sophisticated network testing
    pass


def get_system_resource_usage():
    """Get current system resource usage for performance testing."""
    try:
        import psutil
        return {
            "cpu_percent": psutil.cpu_percent(interval=1),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_usage": psutil.disk_usage("/").percent
        }
    except ImportError:
        # psutil not available, return dummy values
        return {
            "cpu_percent": 0,
            "memory_percent": 0,
            "disk_usage": 0
        }


def create_large_test_data(directory, size_mb: int = 100):
    """Create large test data for performance testing."""
    import os
    
    test_file = directory / f"large_test_data_{size_mb}mb.bin"
    
    try:
        with open(test_file, 'wb') as f:
            chunk_size = 1024 * 1024  # 1MB chunks
            for _ in range(size_mb):
                f.write(b'0' * chunk_size)
        return test_file
    except OSError:
        return None 

def poll_for_process_exit(process_name: str, timeout: int = 30) -> bool:
    """Poll for a process to exit, returning True if it exits within timeout."""
    import subprocess, time
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            result = subprocess.run(
                ["pgrep", "-f", process_name], 
                capture_output=True, 
                text=True, 
                check=False
            )
            if result.returncode != 0:  # Process not found
                return True
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return True
        time.sleep(0.5)
    return False

def poll_for_container_stop(container_name: str, timeout: int = 30) -> bool:
    """Poll for a Docker container to stop, returning True if it stops within timeout."""
    import docker, time
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            client = docker.from_env()
            containers = client.containers.list(
                filters={"name": container_name}, 
                all=True
            )
            if not containers:
                return True
            for container in containers:
                if container.status == "exited":
                    return True
        except Exception:
            return True
        time.sleep(0.5)
    return False

def poll_for_file_deletion(file_path: str, timeout: int = 10) -> bool:
    """Poll for a file to be deleted, returning True if it's deleted within timeout."""
    import os, time
    start_time = time.time()
    while time.time() - start_time < timeout:
        if not os.path.exists(file_path):
            return True
        time.sleep(0.2)
    return False

def poll_for_service_health(service_name: str, timeout: int = 30) -> bool:
    """Poll for a service to become healthy, returning True if healthy within timeout."""
    import urllib.request, urllib.error, socket, time
    HEALTH_CHECK_URLS = {
        "webui": "http://localhost:8080",
        "mcp_proxy": "http://localhost:8200",
        "ollama": "http://localhost:11434"
    }
    if service_name not in HEALTH_CHECK_URLS:
        return False
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            response = urllib.request.urlopen(HEALTH_CHECK_URLS[service_name], timeout=2)
            if response.getcode() == 200:
                return True
        except (urllib.error.URLError, urllib.error.HTTPError, socket.timeout):
            pass
        time.sleep(1)
    return False 

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
        self.original_env = os.environ.get("OLLAMA_STACK_CONFIG_DIR")
        self.monkeypatch.setenv("OLLAMA_STACK_CONFIG_DIR", str(self.config_dir))
        return str(self.config_dir)
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.original_env is not None:
            self.monkeypatch.setenv("OLLAMA_STACK_CONFIG_DIR", self.original_env)
        else:
            self.monkeypatch.delenv("OLLAMA_STACK_CONFIG_DIR", raising=False)

class TemporaryBackupDir:
    """Context manager for temporary backup directories."""
    def __init__(self, tmp_path):
        self.tmp_path = tmp_path
        self.backup_dir = None
    def __enter__(self):
        self.backup_dir = self.tmp_path / "backup"
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        return str(self.backup_dir)
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.backup_dir and os.path.exists(self.backup_dir):
            shutil.rmtree(self.backup_dir, ignore_errors=True)

class StackServiceManager:
    """Context manager for starting/stopping stack services for a test."""
    def __init__(self, runner):
        self.runner = runner
    def __enter__(self):
        result = self.runner.invoke(app, ["start"])
        assert result.exit_code == 0
        return self
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.runner.invoke(app, ["stop"])

class ArtifactTracker:
    """Context manager for tracking and cleaning up test artifacts."""
    def __init__(self):
        self.artifacts = []
    def track_file(self, file_path):
        self.artifacts.append(file_path)
    def track_dir(self, dir_path):
        self.artifacts.append(dir_path)
    def cleanup(self):
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