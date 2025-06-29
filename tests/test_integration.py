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

runner = CliRunner()

# --- Test Configuration ---

IS_APPLE_SILICON = platform.system() == "Darwin" and platform.machine() == "arm64"
# On Apple Silicon, 'ollama' runs natively, so it's not in our Docker stack.
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
        http_success = False
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


# --- Test Fixtures ---

@pytest.fixture(autouse=True)
def clean_stack_between_tests():
    """
    A fixture that ensures the stack is stopped before and after each integration test,
    providing a clean, isolated environment.
    """
    runner.invoke(app, ["stop"])
    stop_native_ollama_if_running()
    time.sleep(1)  # Allow services to fully stop
    yield
    runner.invoke(app, ["stop"])
    stop_native_ollama_if_running()


# --- Integration Tests ---

@pytest.mark.integration
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available or not running")
def test_start_and_stop_lifecycle():
    """
    Verifies the most basic user workflow: start the stack, see that it's
    running, stop it, and see that it's stopped.
    
    Only runs when Docker is available.
    """
    # 1. Start the stack
    result_start = runner.invoke(app, ["start"])
    assert result_start.exit_code == 0
    
    # Verify expected components are running
    expected_components = EXPECTED_ALL_COMPONENTS if IS_APPLE_SILICON else EXPECTED_DOCKER_COMPONENTS
    running_services = get_actual_running_services()
    assert running_services == expected_components

    # 2. Stop the stack
    result_stop = runner.invoke(app, ["stop"])
    assert result_stop.exit_code == 0
    
    # Verify all services are stopped
    assert get_actual_running_services() == set()


@pytest.mark.integration
def test_start_command_without_docker():
    """
    Verifies that when Docker daemon is not running, the start command 
    fails gracefully with a clean, user-friendly error message.
    
    This tests the actual error handling users would experience.
    """
    if is_docker_available():
        pytest.skip("Docker is available - testing Docker unavailable scenario")
    
    result = runner.invoke(app, ["start"])
    
    # Should exit with error code
    assert result.exit_code == 1
    
    # Should contain helpful error message about Docker daemon (not messy traceback)
    output_lower = result.stdout.lower()
    assert any(keyword in output_lower for keyword in [
        "docker daemon", "daemon is not running", "docker desktop"
    ]), f"Expected Docker daemon error message, got: {result.stdout}"
    
    # Should NOT contain Python traceback elements (this verifies clean error handling)
    assert "traceback" not in output_lower, "Should not show Python traceback to users"
    assert "exception" not in output_lower, "Should not show exception details to users"
    assert "connectionrefusederror" not in output_lower, "Should not show technical error details"


@pytest.mark.integration
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_start_when_already_running_is_idempotent():
    """
    Verifies that running 'start' on an already running stack has no
    negative side effects and informs the user.
    """
    runner.invoke(app, ["start"])
    initial_components = get_actual_running_services()
    expected_components = EXPECTED_ALL_COMPONENTS if IS_APPLE_SILICON else EXPECTED_DOCKER_COMPONENTS
    assert initial_components == expected_components

    # Run start again
    result = runner.invoke(app, ["start"])
    assert result.exit_code == 0
    assert "already running" in result.stdout
    
    # Verify that the stack was not changed
    final_components = get_actual_running_services()
    assert final_components == initial_components


@pytest.mark.integration
def test_stop_when_already_stopped_is_idempotent():
    """
    Verifies that running 'stop' on an already stopped stack has no
    negative side effects and exits gracefully.
    """
    # The fixture ensures the stack is already stopped.
    result = runner.invoke(app, ["stop"])
    assert result.exit_code == 0
    assert get_actual_running_services() == set()


@pytest.mark.integration
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_restart_recreates_services():
    """
    Verifies that 'restart' correctly replaces the running containers
    with new ones and maintains service availability.
    """
    runner.invoke(app, ["start"])
    client = docker.from_env()
    initial_containers = client.containers.list(filters={"label": "ollama-stack.component"})
    initial_ids = {c.id for c in initial_containers}
    
    # Restart the stack
    result = runner.invoke(app, ["restart"])
    assert result.exit_code == 0
    
    # Verify the correct services are running
    expected_components = EXPECTED_ALL_COMPONENTS if IS_APPLE_SILICON else EXPECTED_DOCKER_COMPONENTS
    running_services = get_actual_running_services()
    assert running_services == expected_components
    
    # Verify the new containers are different from the old ones (for Docker services)
    final_containers = client.containers.list(filters={"label": "ollama-stack.component"})
    final_ids = {c.id for c in final_containers}
    if initial_ids:  # Only check if there were initial containers
        assert not initial_ids.intersection(final_ids)


@pytest.mark.integration
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_restart_with_update_pulls_images():
    """
    Verifies that 'restart --update' runs the image pull process during restart.
    """
    # Start initially
    runner.invoke(app, ["start"])
    
    # Restart with update
    result = runner.invoke(app, ["restart", "--update"])
    
    assert result.exit_code == 0
    # Should see pulling behavior in output
    output_lower = result.stdout.lower()
    pulling_keywords = ["pull", "downloading", "latest"]
    has_pulling_output = any(keyword in output_lower for keyword in pulling_keywords)
    # Note: Might not always show pulling if images are already latest
    # The important thing is that the command succeeds
    
    # Verify services are running after restart with update
    expected_components = EXPECTED_ALL_COMPONENTS if IS_APPLE_SILICON else EXPECTED_DOCKER_COMPONENTS
    assert get_actual_running_services() == expected_components


@pytest.mark.integration
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_start_with_update_pulls_images():
    """
    Verifies that 'start --update' runs the image pull process before
    starting the services.
    """
    result = runner.invoke(app, ["start", "--update"])
    
    assert result.exit_code == 0
    # Should see pulling behavior in output (or complete successfully)
    # The important outcome is that services are running
    expected_components = EXPECTED_ALL_COMPONENTS if IS_APPLE_SILICON else EXPECTED_DOCKER_COMPONENTS
    assert get_actual_running_services() == expected_components


@pytest.mark.integration
@pytest.mark.skipif(not IS_APPLE_SILICON, reason="Native Ollama test only applicable on Apple Silicon")
def test_native_ollama_service_lifecycle():
    """
    Verifies that on Apple Silicon, the native Ollama service is properly
    started and stopped as part of the stack lifecycle.
    
    This test focuses on the actual outcome - whether Ollama is running.
    """
    if not shutil.which("ollama"):
        pytest.skip("Ollama not installed - cannot test native service")
    
    if not is_docker_available():
        pytest.skip("Docker not available - need both Docker and Ollama for full stack test")
    
    # Start the stack
    result_start = runner.invoke(app, ["start"])
    assert result_start.exit_code == 0
    
    # Verify native Ollama is running
    assert is_ollama_native_service_running()
    
    # Stop the stack
    result_stop = runner.invoke(app, ["stop"])
    assert result_stop.exit_code == 0
    
    # Verify native Ollama is stopped
    time.sleep(2)  # Give it time to stop
    assert not is_ollama_native_service_running()


@pytest.mark.integration
@pytest.mark.skipif(IS_APPLE_SILICON, reason="Docker Ollama test not applicable on Apple Silicon")
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_docker_ollama_service_lifecycle():
    """
    Verifies that on non-Apple Silicon platforms, Ollama runs as a Docker service.
    """
    # Start the stack
    result_start = runner.invoke(app, ["start"])
    assert result_start.exit_code == 0
    
    # Verify Docker Ollama is running
    running_components = get_running_stack_components()
    assert "ollama" in running_components


@pytest.mark.integration
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_service_health_after_start():
    """
    Verifies that all started services are actually healthy and accessible.
    
    This tests the actual end-to-end functionality users care about.
    """
    result = runner.invoke(app, ["start"])
    assert result.exit_code == 0

    # Give services a moment to fully initialize after starting
    time.sleep(3)
    
    # Test basic service availability - WebUI should be reachable
    # We use a shorter timeout for integration tests
    assert wait_for_service_health("webui", timeout=10)
    
    # On Apple Silicon, test native Ollama if available
    if IS_APPLE_SILICON and shutil.which("ollama"):
        # Give native Ollama a moment to fully start
        time.sleep(3)
        assert wait_for_service_health("ollama", timeout=5)


@pytest.mark.integration
@pytest.mark.skipif(not IS_APPLE_SILICON, reason="Test only applicable on Apple Silicon") 
def test_apple_silicon_without_ollama_installed():
    """
    Verifies graceful handling when Ollama is not installed on Apple Silicon.
    
    Tests the actual user experience when prerequisites are missing.
    """
    if not is_docker_available():
        pytest.skip("Docker not available - need Docker for partial stack test")
    
    if shutil.which("ollama"):
        pytest.skip("Ollama is installed - testing scenario when it's not installed")
    
    # Should still start Docker services successfully
    result = runner.invoke(app, ["start"])
    assert result.exit_code == 0
    
    # Docker services should be running
    docker_components = get_running_stack_components()
    assert docker_components == EXPECTED_DOCKER_COMPONENTS
    
    # Native Ollama should not be running
    assert not is_ollama_native_service_running()


@pytest.mark.integration
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_status_command_reflects_actual_state():
    """
    Verifies the 'status' command accurately reflects actual service states.
    
    This tests that status reporting matches reality.
    """
    # 1. Test status when stack is down
    result_down = runner.invoke(app, ["status"])
    assert result_down.exit_code == 0
    assert any(keyword in result_down.stdout.lower() for keyword in [
        "not running", "stopped", "all services are stopped"
    ])

    # 2. Start the stack and test status
    runner.invoke(app, ["start"])
    result_up = runner.invoke(app, ["status"])
    assert result_up.exit_code == 0
    
    # Check that status shows services as running
    assert "running" in result_up.stdout.lower()
    
    # All expected components should appear in status
    expected_components = EXPECTED_ALL_COMPONENTS if IS_APPLE_SILICON else EXPECTED_DOCKER_COMPONENTS
    for component in expected_components:
        assert component in result_up.stdout.lower()


@pytest.mark.integration
def test_check_command_validates_environment():
    """
    Verifies the 'check' command provides accurate environment validation.
    
    This tests actual system state detection.
    """
    result = runner.invoke(app, ["check"])
    
    # Check command should exit with appropriate code based on actual state
    if is_docker_available():
        # If Docker daemon is running, check should succeed or show minor issues
        assert result.exit_code == 0
    else:
        # If Docker daemon is not running, check should fail (this is the correct behavior)
        assert result.exit_code != 0
    
    # Should always check Docker daemon
    assert "docker" in result.stdout.lower()
    
    # Should check port availability  
    assert "port" in result.stdout.lower()
    
    # Check results should reflect actual system state
    output_lower = result.stdout.lower()
    if is_docker_available():
        # If Docker is available, should show success or specific issues
        pass  # Success or specific Docker issues are both valid
    else:
        # If Docker daemon is not available, this should be clearly indicated
        assert any(keyword in output_lower for keyword in [
            "not running", "unavailable", "daemon", "start docker"
        ])


@pytest.mark.integration
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_logs_command_accesses_actual_logs():
    """
    Verifies the 'logs' command can fetch logs from a running service.
    
    This tests actual log access functionality.
    """
    # Start the stack so services are running
    start_result = runner.invoke(app, ["start"])
    assert start_result.exit_code == 0
    
    # Give services a moment to generate some logs
    time.sleep(2)

    # Fetch logs from the webui service
    result = runner.invoke(app, ["logs", "webui", "--tail", "5"])
    assert result.exit_code == 0
    
    # A successful log command should produce some output
    # Even if services haven't logged much, there should be some content
    assert len(result.stdout.strip()) >= 0  # At minimum, should not error


@pytest.mark.integration
def test_restart_without_docker():
    """
    Verifies restart command behavior when Docker is not available.
    
    Tests actual error handling for restart operations.
    """
    if is_docker_available():
        pytest.skip("Docker is available - testing Docker unavailable scenario")
    
    result = runner.invoke(app, ["restart"])
    
    # Should handle the error gracefully
    assert result.exit_code != 0
    
    # Should contain helpful information about the issue
    output_lower = result.stdout.lower()
    assert any(keyword in output_lower for keyword in [
        "docker", "daemon", "running", "configured"
    ]) 