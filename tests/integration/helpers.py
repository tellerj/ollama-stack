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