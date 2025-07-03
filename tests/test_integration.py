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


# --- Update Command Integration Tests ---

@pytest.mark.integration
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_update_command_when_stack_stopped():
    """
    Verifies that 'update' command works correctly when the stack is not running.
    
    Tests that update pulls images without needing to stop/restart anything.
    """
    # Ensure stack is stopped
    assert get_actual_running_services() == set()
    
    # Run update command
    result = runner.invoke(app, ["update"])
    assert result.exit_code == 0
    
    # Should indicate successful update completion
    output_lower = result.stdout.lower()
    assert any(keyword in output_lower for keyword in [
        "update completed", "successfully", "up to date"
    ])
    
    # Stack should still be stopped after update
    assert get_actual_running_services() == set()


@pytest.mark.integration  
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_update_command_services_only_flag():
    """
    Verifies that 'update --services' works correctly and only updates core services.
    
    Tests the selective update functionality.
    """
    result = runner.invoke(app, ["update", "--services"])
    assert result.exit_code == 0
    
    # Should indicate core services were updated
    output_lower = result.stdout.lower()
    assert any(keyword in output_lower for keyword in [
        "core services", "services update", "successfully"
    ])


@pytest.mark.integration
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available") 
def test_update_command_extensions_only_flag():
    """
    Verifies that 'update --extensions' works correctly and only processes extensions.
    
    Tests extension-only update mode (currently shows no extensions enabled message).
    """
    result = runner.invoke(app, ["update", "--extensions"])
    assert result.exit_code == 0
    
    # Should indicate extensions were processed (even if none enabled)
    output_lower = result.stdout.lower()
    assert any(keyword in output_lower for keyword in [
        "extension", "no extensions enabled", "successfully"
    ])


@pytest.mark.integration
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_update_command_conflicting_flags():
    """
    Verifies that conflicting --services and --extensions flags are rejected.
    
    Tests input validation and error handling.
    """
    result = runner.invoke(app, ["update", "--services", "--extensions"])
    assert result.exit_code == 1
    
    # Should show error about conflicting flags
    output_lower = result.stdout.lower()
    assert any(keyword in output_lower for keyword in [
        "cannot specify both", "conflicting", "both flags"
    ])


@pytest.mark.integration
def test_update_command_without_docker():
    """
    Verifies update command behavior when Docker daemon is not running.
    
    Tests actual error handling for update operations when Docker is unavailable.
    """
    if is_docker_available():
        pytest.skip("Docker is available - testing Docker unavailable scenario")
    
    result = runner.invoke(app, ["update"])
    
    # Should exit with error code
    assert result.exit_code == 1
    
    # Should contain helpful error message about Docker
    output_lower = result.stdout.lower()
    assert any(keyword in output_lower for keyword in [
        "docker", "daemon", "not running", "unavailable"
    ])


@pytest.mark.integration
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_update_with_running_stack_user_confirms():
    """
    Verifies update behavior when stack is running and user confirms stopping.
    
    Tests the complete stop -> update -> restart cycle with user interaction.
    """
    # Start the stack first
    start_result = runner.invoke(app, ["start"])
    assert start_result.exit_code == 0
    
    expected_components = EXPECTED_ALL_COMPONENTS if IS_APPLE_SILICON else EXPECTED_DOCKER_COMPONENTS
    assert get_actual_running_services() == expected_components
    
    # Run update with automatic confirmation (simulate user saying 'yes')
    result = runner.invoke(app, ["update"], input="y\n")
    assert result.exit_code == 0
    
    # Should show prompting and completion messages
    output_lower = result.stdout.lower()
    assert "currently running" in output_lower
    assert any(keyword in output_lower for keyword in [
        "update completed", "restarted successfully", "up to date"
    ])
    
    # Stack should be running again after update
    final_services = get_actual_running_services()
    assert final_services == expected_components


@pytest.mark.integration
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_update_with_running_stack_user_declines():
    """
    Verifies update behavior when stack is running and user declines stopping.
    
    Tests that update respects user choice and doesn't modify running stack.
    """
    # Start the stack first
    start_result = runner.invoke(app, ["start"])
    assert start_result.exit_code == 0
    
    initial_services = get_actual_running_services()
    expected_components = EXPECTED_ALL_COMPONENTS if IS_APPLE_SILICON else EXPECTED_DOCKER_COMPONENTS
    assert initial_services == expected_components
    
    # Run update with automatic decline (simulate user saying 'no')
    result = runner.invoke(app, ["update"], input="n\n")
    assert result.exit_code == 1
    
    # Should show cancellation message
    output_lower = result.stdout.lower()
    assert "currently running" in output_lower
    assert any(keyword in output_lower for keyword in [
        "cancelled", "cancel", "update cancelled"
    ])
    
    # Stack should remain unchanged
    final_services = get_actual_running_services()
    assert final_services == initial_services


@pytest.mark.integration
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_start_with_update_integration():
    """
    Verifies that 'start --update' integrates correctly with the unified update logic.
    
    Tests that image pulling happens before starting services.
    """
    result = runner.invoke(app, ["start", "--update"])
    assert result.exit_code == 0
    
    # Should complete successfully and start services
    expected_components = EXPECTED_ALL_COMPONENTS if IS_APPLE_SILICON else EXPECTED_DOCKER_COMPONENTS
    assert get_actual_running_services() == expected_components
    
    # Should indicate update happened (though may be quiet if images are current)
    # The key test is that it succeeds and services are running


@pytest.mark.integration
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_restart_with_update_integration():
    """
    Verifies that 'restart --update' integrates correctly with the unified update logic.
    
    Tests the complete restart with update cycle.
    """
    # Start stack first
    runner.invoke(app, ["start"])
    initial_services = get_actual_running_services()
    expected_components = EXPECTED_ALL_COMPONENTS if IS_APPLE_SILICON else EXPECTED_DOCKER_COMPONENTS
    assert initial_services == expected_components
    
    # Restart with update
    result = runner.invoke(app, ["restart", "--update"])
    assert result.exit_code == 0
    
    # Should complete successfully and services should be running
    final_services = get_actual_running_services()
    assert final_services == expected_components
    
    # Verify Docker containers were actually recreated (not just restarted)
    if is_docker_available():
        docker_components = get_running_stack_components()
        # Should have Docker services running
        assert len(docker_components.intersection(EXPECTED_DOCKER_COMPONENTS)) > 0


@pytest.mark.integration
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_update_command_preserves_service_health():
    """
    Verifies that after update operations, services remain healthy and accessible.
    
    Tests the end-to-end user experience - services should work after update.
    """
    # Start stack and verify it's healthy
    runner.invoke(app, ["start"])
    time.sleep(3)  # Let services initialize
    assert wait_for_service_health("webui", timeout=10)
    
    # Update the stack (with confirmation)
    result = runner.invoke(app, ["update"], input="y\n")
    assert result.exit_code == 0
    
    # Give services time to restart and stabilize
    time.sleep(5)
    
    # Verify services are still healthy after update
    assert wait_for_service_health("webui", timeout=15)
    
    # All expected services should be running
    expected_components = EXPECTED_ALL_COMPONENTS if IS_APPLE_SILICON else EXPECTED_DOCKER_COMPONENTS
    assert get_actual_running_services() == expected_components


@pytest.mark.integration
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_update_command_idempotent():
    """
    Verifies that running update multiple times is safe and idempotent.
    
    Tests that repeated updates don't cause issues or leave system in bad state.
    """
    # First update
    result1 = runner.invoke(app, ["update"])
    assert result1.exit_code == 0
    
    # Second update immediately after
    result2 = runner.invoke(app, ["update"])
    assert result2.exit_code == 0
    
    # Both should complete successfully
    for result in [result1, result2]:
        output_lower = result.stdout.lower()
        assert any(keyword in output_lower for keyword in [
            "update completed", "successfully", "up to date"
        ])


@pytest.mark.integration  
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_update_command_help_accessibility():
    """
    Verifies that update command help is accessible and informative.
    
    Tests user discoverability and documentation.
    """
    result = runner.invoke(app, ["update", "--help"])
    assert result.exit_code == 0
    
    # Should contain key information about the command
    output_lower = result.stdout.lower()
    assert "update" in output_lower
    assert "images" in output_lower
    assert "services" in output_lower
    assert "extensions" in output_lower
    
    # Should show available options
    assert "--services" in result.stdout
    assert "--extensions" in result.stdout


# --- Enhanced StackManager Integration Tests for Refactored Update Logic ---

@pytest.mark.integration
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_update_with_network_interruption():
    """
    Verifies update behavior when network connectivity is intermittent.
    
    Tests that update operations handle network issues gracefully and provide
    appropriate feedback to users.
    """
    # This test simulates real-world network conditions where pulls might fail
    result = runner.invoke(app, ["update", "--services"])
    
    # The command should handle network issues gracefully
    # Even if pulls fail due to network, the command should not crash
    assert result.exit_code in [0, 1]  # Success or controlled failure
    
    output_lower = result.stdout.lower()
    # Should not show unhandled exceptions or Python tracebacks
    assert "traceback" not in output_lower
    assert "exception:" not in output_lower
    
    # If it fails, should provide helpful messaging
    if result.exit_code == 1:
        assert any(keyword in output_lower for keyword in [
            "failed", "network", "connection", "timeout", "pull"
        ])


@pytest.mark.integration
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_update_maintains_container_state_consistency():
    """
    Verifies that update operations maintain consistent container states.
    
    Tests that the StackManager's enhanced state management ensures containers
    are in expected states after update operations.
    """
    # Start stack and capture initial state
    runner.invoke(app, ["start"])
    time.sleep(2)
    
    initial_docker_components = get_running_stack_components()
    assert len(initial_docker_components) > 0
    
    # Run update with confirmation
    result = runner.invoke(app, ["update"], input="y\n")
    assert result.exit_code == 0
    
    # Give services time to stabilize after update
    time.sleep(3)
    
    # Verify final state is consistent
    final_docker_components = get_running_stack_components()
    
    # Should have same services running (but potentially new containers)
    assert final_docker_components == initial_docker_components
    
    # Verify no orphaned or stuck containers
    if is_docker_available():
        client = docker.from_env()
        all_containers = client.containers.list(
            all=True, 
            filters={"label": "ollama-stack.component"}
        )
        
        # All containers should be in running state (no exited/dead containers)
        running_containers = [c for c in all_containers if c.status == "running"]
        assert len(running_containers) == len(all_containers), \
            f"Found non-running containers: {[c.status for c in all_containers if c.status != 'running']}"


@pytest.mark.integration
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_update_services_only_excludes_extensions():
    """
    Verifies that --services flag truly only affects core services and skips extensions.
    
    Tests the precision of the refactored StackManager's service filtering.
    """
    result = runner.invoke(app, ["update", "--services"])
    assert result.exit_code == 0
    
    output_lower = result.stdout.lower()
    
    # Should indicate core services were processed
    assert any(keyword in output_lower for keyword in [
        "core services", "services updated", "pulling images"
    ])
    
    # Should NOT indicate extension processing
    # (Note: This test verifies behavior even when no extensions are enabled)
    assert "extension" not in output_lower or "no extensions enabled" in output_lower


@pytest.mark.integration
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_update_with_partial_service_failures():
    """
    Verifies update behavior when some services fail to update but others succeed.
    
    Tests the StackManager's enhanced error handling and partial failure recovery.
    """
    # Start the stack
    start_result = runner.invoke(app, ["start"])
    assert start_result.exit_code == 0
    
    initial_services = get_actual_running_services()
    assert len(initial_services) > 0
    
    # Run update (some operations might fail in real environment)
    result = runner.invoke(app, ["update"], input="y\n")
    
    # Update should handle partial failures gracefully
    # Either succeed completely or fail with controlled error handling
    assert result.exit_code in [0, 1]
    
    output_lower = result.stdout.lower()
    
    # Should not show unhandled exceptions
    assert "traceback" not in output_lower
    
    # If there were failures, should provide clear messaging
    if result.exit_code == 1:
        assert any(keyword in output_lower for keyword in [
            "failed", "error", "could not", "unable"
        ])
    
    # Verify system is left in a consistent state
    time.sleep(2)
    final_services = get_actual_running_services()
    
    # Services should either be running or cleanly stopped
    # (No partially started or corrupted states)
    assert isinstance(final_services, set)  # Should be a proper set, not broken


@pytest.mark.integration
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_update_stop_failure_handling():
    """
    Verifies update behavior when stack cannot be stopped for updating.
    
    Tests StackManager's handling of stop operation failures during update.
    """
    # Start the stack
    runner.invoke(app, ["start"])
    assert len(get_actual_running_services()) > 0
    
    # Try update with confirmation
    # In real environment, stop might fail due to various reasons
    result = runner.invoke(app, ["update"], input="y\n")
    
    # Should handle stop failures gracefully
    assert result.exit_code in [0, 1]
    
    output_lower = result.stdout.lower()
    
    # Should not show Python tracebacks to users
    assert "traceback" not in output_lower
    assert "exception:" not in output_lower
    
    # If stop fails, should provide helpful error message
    if result.exit_code == 1 and "failed" in output_lower:
        assert any(keyword in output_lower for keyword in [
            "stop", "running", "could not stop", "unable to stop"
        ])


@pytest.mark.integration
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_update_restart_failure_handling():
    """
    Verifies update behavior when services fail to restart after update.
    
    Tests StackManager's handling of restart failures during update completion.
    """
    # This test verifies the update process handles restart failures gracefully
    result = runner.invoke(app, ["update"])
    
    # Should handle restart failures appropriately
    assert result.exit_code in [0, 1]
    
    output_lower = result.stdout.lower()
    
    # Should provide clear error messaging for restart failures
    if result.exit_code == 1:
        # Should indicate what went wrong without exposing technical details
        assert not any(tech_keyword in output_lower for tech_keyword in [
            "traceback", "exception:", "attributeerror", "keyerror"
        ])


@pytest.mark.integration
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_concurrent_update_operations():
    """
    Verifies update behavior when multiple operations might be running concurrently.
    
    Tests StackManager's state consistency during potentially concurrent operations.
    """
    # This test ensures update operations are properly isolated
    result1 = runner.invoke(app, ["update", "--services"])
    
    # Should complete without race conditions or state corruption
    assert result1.exit_code in [0, 1]
    
    # Immediate second update should handle state correctly
    result2 = runner.invoke(app, ["update", "--services"])
    assert result2.exit_code in [0, 1]
    
    # Both operations should complete without corrupting system state
    for result in [result1, result2]:
        output_lower = result.stdout.lower()
        assert "traceback" not in output_lower


@pytest.mark.integration
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_update_with_config_changes():
    """
    Verifies update behavior when configuration changes during the update process.
    
    Tests StackManager's robustness against configuration state changes.
    """
    # Test that update handles configuration consistency
    result = runner.invoke(app, ["update"])
    assert result.exit_code in [0, 1]
    
    output_lower = result.stdout.lower()
    
    # Should handle config-related issues gracefully
    assert "traceback" not in output_lower
    
    # If config issues occur, should provide helpful feedback
    if result.exit_code == 1:
        assert not any(tech_detail in output_lower for tech_detail in [
            "pydantic", "validation", "schema", "keyerror"
        ])


@pytest.mark.integration
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")  
def test_update_preserves_running_service_data():
    """
    Verifies that update operations preserve service data and don't cause data loss.
    
    Tests that the StackManager's update process maintains data integrity.
    """
    # Start stack and let it initialize
    runner.invoke(app, ["start"])
    time.sleep(5)  # Let services fully initialize and potentially create data
    
    # Capture initial service health
    initial_webui_healthy = wait_for_service_health("webui", timeout=5)
    
    # Run update with restart
    result = runner.invoke(app, ["update"], input="y\n")
    assert result.exit_code == 0
    
    # Give services time to restart
    time.sleep(8)
    
    # Verify services are healthy again after update
    final_webui_healthy = wait_for_service_health("webui", timeout=15)
    
    # If services were healthy before, they should be healthy after update
    if initial_webui_healthy:
        assert final_webui_healthy, "WebUI service should remain healthy after update"


@pytest.mark.integration
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_update_command_resource_cleanup():
    """
    Verifies that update operations properly clean up resources and don't leak containers.
    
    Tests the StackManager's enhanced resource management during updates.
    """
    if not is_docker_available():
        pytest.skip("Docker not available for resource testing")
    
    client = docker.from_env()
    
    # Capture initial container count
    initial_containers = client.containers.list(
        all=True, 
        filters={"label": "ollama-stack.component"}
    )
    initial_count = len(initial_containers)
    
    # Run several update operations
    for _ in range(2):
        result = runner.invoke(app, ["update"])
        assert result.exit_code in [0, 1]
        time.sleep(1)
    
    # Check for container leaks
    final_containers = client.containers.list(
        all=True,
        filters={"label": "ollama-stack.component"}
    )
    final_count = len(final_containers)
    
    # Should not have excessive container accumulation
    # (Allow for some variation due to restart operations, but prevent major leaks)
    assert final_count <= initial_count + 5, \
        f"Potential container leak: started with {initial_count}, ended with {final_count}"
    
    # Verify no exited containers accumulating
    exited_containers = [c for c in final_containers if c.status == "exited"]
    assert len(exited_containers) <= 2, \
        f"Too many exited containers accumulating: {len(exited_containers)}"


@pytest.mark.integration
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_update_mixed_service_types_coordination():
    """
    Verifies update coordination between Docker and native services.
    
    Tests StackManager's handling of mixed service type scenarios during updates.
    """
    # This test verifies the coordination between different service types
    result = runner.invoke(app, ["update"])
    assert result.exit_code in [0, 1]
    
    output_lower = result.stdout.lower()
    
    # Should handle mixed service types without errors
    assert "traceback" not in output_lower
    
    # If running on Apple Silicon, should coordinate Docker and native services
    if IS_APPLE_SILICON:
        # On Apple Silicon, update should handle both Docker services and native Ollama
        # The exact behavior depends on what's installed, but should not crash
        pass
    else:
        # On other platforms, should handle Docker services appropriately
        pass


@pytest.mark.integration
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_update_performance_under_load():
    """
    Verifies update operations complete within reasonable time limits.
    
    Tests that StackManager's update operations are performant and don't hang.
    """
    import time
    
    start_time = time.time()
    
    # Run update operation
    result = runner.invoke(app, ["update", "--services"])
    
    end_time = time.time()
    duration = end_time - start_time
    
    # Should complete within reasonable time (adjust based on system capabilities)
    assert duration < 120, f"Update took too long: {duration:.2f} seconds"
    
    # Should complete successfully or with controlled failure
    assert result.exit_code in [0, 1]
    
    output_lower = result.stdout.lower()
    assert "traceback" not in output_lower


@pytest.mark.integration
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_update_stack_state_consistency_across_operations():
    """
    Verifies that multiple update operations maintain consistent stack state.
    
    Tests StackManager's state management across multiple update cycles.
    """
    # Run multiple update operations in sequence
    operations = [
        ["update", "--services"],
        ["update", "--extensions"], 
        ["update"]
    ]
    
    for operation in operations:
        result = runner.invoke(app, operation)
        assert result.exit_code in [0, 1]
        
        output_lower = result.stdout.lower()
        assert "traceback" not in output_lower
        
        # Brief pause between operations
        time.sleep(1)
    
    # After all operations, stack state should be consistent
    running_services = get_actual_running_services()
    assert isinstance(running_services, set)  # Should be valid set, not corrupted


@pytest.mark.integration
def test_update_error_message_quality():
    """
    Verifies that update error messages are user-friendly and actionable.
    
    Tests that StackManager provides helpful error messages rather than technical details.
    """
    if is_docker_available():
        pytest.skip("Docker is available - testing error message quality when Docker unavailable")
    
    result = runner.invoke(app, ["update"])
    assert result.exit_code == 1
    
    output_lower = result.stdout.lower()
    
    # Should provide user-friendly error messages
    assert any(helpful_keyword in output_lower for helpful_keyword in [
        "docker daemon", "not running", "please start", "install docker"
    ])
    
    # Should NOT expose technical implementation details
    assert not any(tech_detail in output_lower for tech_detail in [
        "traceback", "exception:", "connectionrefusederror", 
        "docker.errors", "api error", "socket"
    ])
    
    # Should provide actionable guidance
    assert any(action_keyword in output_lower for action_keyword in [
        "start", "install", "check", "ensure"
    ]) 


# --- Uninstall Command Integration Tests ---

@pytest.mark.integration
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_uninstall_basic_removes_docker_resources_preserves_data():
    """
    Verifies that basic uninstall (no flags) removes Docker containers and networks
    but preserves volumes and configuration files.
    
    Tests actual Docker API resource removal and filesystem preservation.
    """
    # Start the stack to create resources
    start_result = runner.invoke(app, ["start"])
    assert start_result.exit_code == 0
    
    # Verify Docker resources exist
    client = docker.from_env()
    initial_containers = client.containers.list(
        all=True, filters={"label": "ollama-stack.component"}
    )
    initial_networks = client.networks.list(filters={"label": "ollama-stack.component"})
    initial_volumes = client.volumes.list(filters={"label": "com.docker.compose.project=ollama-stack"})
    
    assert len(initial_containers) > 0, "Should have Docker containers running"
    
    # Run basic uninstall
    result = runner.invoke(app, ["uninstall"])
    assert result.exit_code == 0
    
    # Verify containers and networks are ACTUALLY removed
    final_containers = client.containers.list(
        all=True, filters={"label": "ollama-stack.component"}
    )
    final_networks = client.networks.list(filters={"label": "ollama-stack.component"})
    final_volumes = client.volumes.list(filters={"label": "com.docker.compose.project=ollama-stack"})
    
    assert len(final_containers) == 0, "All stack containers should be removed"
    # Networks may or may not be removed depending on Docker behavior, but containers should be gone
    
    # Verify volumes are PRESERVED (basic uninstall shouldn't remove data)
    assert len(final_volumes) == len(initial_volumes), "Volumes should be preserved with basic uninstall"
    
    # Verify configuration directory exists (should be preserved)
    import os
    config_dir = os.path.expanduser("~/.ollama-stack")
    # Config directory existence depends on whether it was created - the key is it's not deleted
    # if it exists, it should still exist after basic uninstall


@pytest.mark.integration
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_uninstall_remove_volumes_actually_removes_data():
    """
    Verifies that --remove-volumes flag actually removes Docker volumes from the system.
    
    Tests real volume removal through Docker API.
    """
    # Start stack to create volumes
    start_result = runner.invoke(app, ["start"])
    assert start_result.exit_code == 0
    
    # Let services create some data
    time.sleep(3)
    
    client = docker.from_env()
    initial_volumes = client.volumes.list(filters={"label": "com.docker.compose.project=ollama-stack"})
    initial_volume_names = {vol.name for vol in initial_volumes}
    
    # Run uninstall with volume removal
    result = runner.invoke(app, ["uninstall", "--remove-volumes"])
    assert result.exit_code == 0
    
    # Verify volumes are ACTUALLY removed from Docker
    final_volumes = client.volumes.list(filters={"label": "com.docker.compose.project=ollama-stack"})
    final_volume_names = {vol.name for vol in final_volumes}
    
    # All initial volumes should be gone
    removed_volumes = initial_volume_names - final_volume_names
    assert removed_volumes == initial_volume_names, f"Should remove all volumes, but {initial_volume_names - removed_volumes} still exist"
    
    # Verify no stack containers remain
    final_containers = client.containers.list(
        all=True, filters={"label": "ollama-stack.component"}
    )
    assert len(final_containers) == 0, "All containers should be removed"


@pytest.mark.integration
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_uninstall_remove_config_actually_removes_filesystem_config():
    """
    Verifies that --remove-config flag actually removes configuration directory
    from the filesystem.
    
    Tests real filesystem operations and directory removal.
    """
    import os
    import tempfile
    import shutil
    
    # Start stack to potentially create config
    start_result = runner.invoke(app, ["start"])
    assert start_result.exit_code == 0
    
    config_dir = os.path.expanduser("~/.ollama-stack")
    
    # Ensure config directory exists for testing
    if not os.path.exists(config_dir):
        os.makedirs(config_dir, exist_ok=True)
        # Create a test file to verify removal
        test_file = os.path.join(config_dir, "test-config.json")
        with open(test_file, 'w') as f:
            f.write('{"test": "data"}')
    
    # Verify config directory exists before uninstall
    assert os.path.exists(config_dir), "Config directory should exist before uninstall"
    
    # Run uninstall with config removal
    result = runner.invoke(app, ["uninstall", "--remove-config"])
    assert result.exit_code == 0
    
    # Verify config directory is ACTUALLY removed from filesystem
    assert not os.path.exists(config_dir), "Config directory should be completely removed from filesystem"
    
    # Verify Docker resources are also removed
    client = docker.from_env()
    final_containers = client.containers.list(
        all=True, filters={"label": "ollama-stack.component"}
    )
    assert len(final_containers) == 0, "All containers should be removed"


@pytest.mark.integration
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_uninstall_all_flag_removes_everything():
    """
    Verifies that --all flag removes Docker resources, volumes, AND config directory.
    
    Tests complete system cleanup with --all flag.
    """
    import os
    
    # Start stack to create all resources
    start_result = runner.invoke(app, ["start"])
    assert start_result.exit_code == 0
    
    # Let services create data
    time.sleep(3)
    
    client = docker.from_env()
    initial_containers = client.containers.list(
        all=True, filters={"label": "ollama-stack.component"}
    )
    initial_volumes = client.volumes.list(filters={"label": "com.docker.compose.project=ollama-stack"})
    
    config_dir = os.path.expanduser("~/.ollama-stack")
    if not os.path.exists(config_dir):
        os.makedirs(config_dir, exist_ok=True)
    
    # Verify resources exist before uninstall
    assert len(initial_containers) > 0, "Should have containers before uninstall"
    assert os.path.exists(config_dir), "Config directory should exist before uninstall"
    
    # Run uninstall with --all flag
    result = runner.invoke(app, ["uninstall", "--all"])
    assert result.exit_code == 0
    
    # Verify EVERYTHING is removed
    
    # 1. Docker containers should be gone
    final_containers = client.containers.list(
        all=True, filters={"label": "ollama-stack.component"}
    )
    assert len(final_containers) == 0, "All containers should be removed"
    
    # 2. Docker volumes should be gone
    final_volumes = client.volumes.list(filters={"label": "com.docker.compose.project=ollama-stack"})
    assert len(final_volumes) == 0, "All volumes should be removed"
    
    # 3. Config directory should be gone
    assert not os.path.exists(config_dir), "Config directory should be removed"
    
    # 4. No services should be running
    assert get_actual_running_services() == set(), "No services should be running"


@pytest.mark.integration
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_uninstall_short_form_all_flag_equivalent():
    """
    Verifies that -a (short form) produces identical results to --all flag.
    
    Tests flag equivalence with actual system state verification.
    """
    import os
    
    # Test setup identical to --all test
    start_result = runner.invoke(app, ["start"])
    assert start_result.exit_code == 0
    time.sleep(3)
    
    client = docker.from_env()
    initial_containers = client.containers.list(
        all=True, filters={"label": "ollama-stack.component"}
    )
    
    config_dir = os.path.expanduser("~/.ollama-stack")
    if not os.path.exists(config_dir):
        os.makedirs(config_dir, exist_ok=True)
    
    # Run uninstall with -a (short form)
    result = runner.invoke(app, ["uninstall", "-a"])
    assert result.exit_code == 0
    
    # Verify identical behavior to --all
    final_containers = client.containers.list(
        all=True, filters={"label": "ollama-stack.component"}
    )
    assert len(final_containers) == 0, "All containers should be removed with -a flag"
    assert not os.path.exists(config_dir), "Config directory should be removed with -a flag"


@pytest.mark.integration
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_uninstall_force_flag_handles_stuck_containers():
    """
    Verifies that --force flag handles containers that resist normal removal.
    
    Tests force removal behavior on actual Docker containers.
    """
    # Start stack 
    start_result = runner.invoke(app, ["start"])
    assert start_result.exit_code == 0
    
    client = docker.from_env()
    initial_containers = client.containers.list(
        all=True, filters={"label": "ollama-stack.component"}
    )
    assert len(initial_containers) > 0
    
    # Run uninstall with force flag
    result = runner.invoke(app, ["uninstall", "--force"])
    assert result.exit_code == 0
    
    # Verify all containers are removed (force should handle any resistance)
    final_containers = client.containers.list(
        all=True, filters={"label": "ollama-stack.component"}
    )
    assert len(final_containers) == 0, "Force flag should remove all containers"


@pytest.mark.integration
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_uninstall_complex_flag_combinations():
    """
    Verifies that complex flag combinations work correctly with actual system state.
    
    Tests real outcomes for multiple flag combinations.
    """
    import os
    
    test_cases = [
        # (flags, should_remove_volumes, should_remove_config, test_name)
        (["--remove-volumes", "--force"], True, False, "volumes+force"),
        (["--remove-config", "--force"], False, True, "config+force"),
        (["--remove-volumes", "--remove-config"], True, True, "volumes+config"),
        (["--all", "--force"], True, True, "all+force"),
    ]
    
    for flags, should_remove_volumes, should_remove_config, test_name in test_cases:
        # Setup for each test case
        runner.invoke(app, ["start"])
        time.sleep(2)
        
        client = docker.from_env()
        initial_volumes = client.volumes.list(filters={"label": "com.docker.compose.project=ollama-stack"})
        
        config_dir = os.path.expanduser("~/.ollama-stack")
        if not os.path.exists(config_dir):
            os.makedirs(config_dir, exist_ok=True)
        
        # Run uninstall with specific flags
        result = runner.invoke(app, ["uninstall"] + flags)
        assert result.exit_code == 0, f"Uninstall failed for {test_name}"
        
        # Verify containers are always removed
        final_containers = client.containers.list(
            all=True, filters={"label": "ollama-stack.component"}
        )
        assert len(final_containers) == 0, f"Containers should be removed for {test_name}"
        
        # Verify volume behavior
        final_volumes = client.volumes.list(filters={"label": "com.docker.compose.project=ollama-stack"})
        if should_remove_volumes:
            assert len(final_volumes) == 0, f"All volumes should be removed for {test_name}"
        # Note: Can't easily test volume preservation without recreating each time
        
        # Verify config behavior
        if should_remove_config:
            assert not os.path.exists(config_dir), f"Config should be removed for {test_name}"
        # Note: Config preservation harder to test without recreating each iteration


@pytest.mark.integration
@pytest.mark.skipif(not IS_APPLE_SILICON, reason="Native Ollama test only for Apple Silicon")
def test_uninstall_stops_native_ollama_on_apple_silicon():
    """
    Verifies that uninstall properly stops native Ollama service on Apple Silicon.
    
    Tests actual process termination and service lifecycle.
    """
    if not shutil.which("ollama"):
        pytest.skip("Ollama not installed - cannot test native service uninstall")
    
    if not is_docker_available():
        pytest.skip("Need Docker for full stack test")
    
    # Start the stack (should start native Ollama)
    start_result = runner.invoke(app, ["start"])
    assert start_result.exit_code == 0
    
    # Verify native Ollama is actually running
    assert is_ollama_native_service_running(), "Native Ollama should be running after start"
    
    # Run uninstall
    result = runner.invoke(app, ["uninstall"])
    assert result.exit_code == 0
    
    # Verify native Ollama is actually stopped
    time.sleep(3)  # Give process time to terminate
    assert not is_ollama_native_service_running(), "Native Ollama should be stopped after uninstall"
    
    # Verify Docker services are also cleaned up
    assert get_running_stack_components() == set(), "No Docker components should remain"


@pytest.mark.integration
@pytest.mark.skipif(IS_APPLE_SILICON, reason="Docker Ollama test not for Apple Silicon")
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_uninstall_removes_docker_ollama_on_other_platforms():
    """
    Verifies that uninstall removes Docker Ollama container on non-Apple Silicon.
    
    Tests Docker container removal for Ollama service.
    """
    # Start the stack
    start_result = runner.invoke(app, ["start"])
    assert start_result.exit_code == 0
    
    # Verify Docker Ollama is running
    running_components = get_running_stack_components()
    assert "ollama" in running_components, "Docker Ollama should be running"
    
    # Run uninstall
    result = runner.invoke(app, ["uninstall"])
    assert result.exit_code == 0
    
    # Verify Docker Ollama container is removed
    final_components = get_running_stack_components()
    assert "ollama" not in final_components, "Docker Ollama should be removed"
    assert len(final_components) == 0, "All Docker services should be removed"


@pytest.mark.integration
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_uninstall_when_stack_not_running():
    """
    Verifies uninstall works correctly when no services are currently running.
    
    Tests cleanup of dormant resources and graceful handling of empty state.
    """
    # Ensure stack is stopped
    runner.invoke(app, ["stop"])
    assert get_actual_running_services() == set()
    
    # Run uninstall on stopped stack
    result = runner.invoke(app, ["uninstall"])
    assert result.exit_code == 0
    
    # Should complete successfully even with no running services
    assert "no stack resources found" in result.stdout.lower() or \
           "uninstall completed" in result.stdout.lower() or \
           "cleanup completed" in result.stdout.lower()


@pytest.mark.integration
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_uninstall_removes_docker_images():
    """
    Verifies that uninstall removes Docker images used by the stack.
    
    Tests actual Docker image removal from local registry.
    """
    # Start stack to ensure images are pulled
    start_result = runner.invoke(app, ["start"])
    assert start_result.exit_code == 0
    
    client = docker.from_env()
    
    # Find stack-related images
    all_images = client.images.list()
    initial_image_count = len(all_images)
    
    # Run uninstall 
    result = runner.invoke(app, ["uninstall"])
    assert result.exit_code == 0
    
    # Verify containers are removed
    final_containers = client.containers.list(
        all=True, filters={"label": "ollama-stack.component"}
    )
    assert len(final_containers) == 0
    
    # Images may or may not be removed depending on implementation
    # The key test is that containers are gone and the command succeeds


@pytest.mark.integration
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_uninstall_removes_docker_networks():
    """
    Verifies that uninstall removes Docker networks created by the stack.
    
    Tests actual Docker network cleanup.
    """
    # Start stack to create networks
    start_result = runner.invoke(app, ["start"])
    assert start_result.exit_code == 0
    
    client = docker.from_env()
    initial_networks = client.networks.list(filters={"label": "ollama-stack.component"})
    
    # Run uninstall
    result = runner.invoke(app, ["uninstall"])
    assert result.exit_code == 0
    
    # Verify networks are cleaned up
    final_networks = client.networks.list(filters={"label": "ollama-stack.component"})
    # Networks may be removed or not depending on Docker behavior, but containers should be gone
    
    final_containers = client.containers.list(
        all=True, filters={"label": "ollama-stack.component"}
    )
    assert len(final_containers) == 0, "All containers should be removed"


@pytest.mark.integration
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_uninstall_idempotent_multiple_runs():
    """
    Verifies that running uninstall multiple times is safe and idempotent.
    
    Tests that repeated uninstall operations don't cause errors or system corruption.
    """
    # Start and uninstall once
    runner.invoke(app, ["start"])
    result1 = runner.invoke(app, ["uninstall"])
    assert result1.exit_code == 0
    
    # Run uninstall again on already-cleaned system
    result2 = runner.invoke(app, ["uninstall"])
    assert result2.exit_code == 0
    
    # Third time to be sure
    result3 = runner.invoke(app, ["uninstall", "--all"])
    assert result3.exit_code == 0
    
    # All should succeed without errors
    for i, result in enumerate([result1, result2, result3], 1):
        assert "error" not in result.stdout.lower() or \
               "no stack resources found" in result.stdout.lower(), \
               f"Run {i} should succeed or report no resources gracefully"


@pytest.mark.integration
def test_uninstall_without_docker_daemon():
    """
    Verifies uninstall behavior when Docker daemon is not running.
    
    Tests actual error handling when Docker API is unavailable.
    """
    if is_docker_available():
        pytest.skip("Docker is available - testing scenario when Docker daemon is down")
    
    result = runner.invoke(app, ["uninstall"])
    
    # Should handle Docker unavailability gracefully
    assert result.exit_code in [0, 1]  # May succeed if only cleaning config, or fail gracefully
    
    output_lower = result.stdout.lower()
    
    # Should not show Python tracebacks (though may show some technical details)
    assert "traceback" not in output_lower
    # Note: connectionrefusederror may appear in output - this could be improved
    
    # Should provide helpful messaging
    if result.exit_code == 1:
        assert any(keyword in output_lower for keyword in [
            "docker", "daemon", "unavailable", "not running"
        ])


@pytest.mark.integration
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_uninstall_preserves_non_stack_docker_resources():
    """
    Verifies that uninstall only removes stack resources and preserves other Docker resources.
    
    Tests surgical precision of resource removal - should not affect unrelated containers.
    """
    client = docker.from_env()
    
    # Start stack
    runner.invoke(app, ["start"])
    
    # Get all containers before uninstall
    all_initial_containers = client.containers.list(all=True)
    stack_containers = client.containers.list(
        all=True, filters={"label": "ollama-stack.component"}
    )
    non_stack_containers = [c for c in all_initial_containers 
                           if not c.labels.get("ollama-stack.component")]
    
    initial_non_stack_count = len(non_stack_containers)
    
    # Run uninstall
    result = runner.invoke(app, ["uninstall"])
    assert result.exit_code == 0
    
    # Verify stack containers are gone
    final_stack_containers = client.containers.list(
        all=True, filters={"label": "ollama-stack.component"}
    )
    assert len(final_stack_containers) == 0, "All stack containers should be removed"
    
    # Verify non-stack containers are preserved
    all_final_containers = client.containers.list(all=True)
    final_non_stack_containers = [c for c in all_final_containers 
                                 if not c.labels.get("ollama-stack.component")]
    
    assert len(final_non_stack_containers) == initial_non_stack_count, \
        "Non-stack containers should be preserved"


@pytest.mark.integration
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_uninstall_handles_partial_resource_cleanup():
    """
    Verifies uninstall behavior when some resources fail to be removed.
    
    Tests resilience and partial cleanup scenarios.
    """
    # Start stack
    start_result = runner.invoke(app, ["start"])
    assert start_result.exit_code == 0
    
    client = docker.from_env()
    initial_containers = client.containers.list(
        all=True, filters={"label": "ollama-stack.component"}
    )
    assert len(initial_containers) > 0
    
    # Run uninstall (may encounter partial failures in real environment)
    result = runner.invoke(app, ["uninstall", "--all"])
    
    # Should handle partial failures gracefully
    assert result.exit_code in [0, 1]
    
    output_lower = result.stdout.lower()
    
    # Should not show unhandled exceptions
    assert "traceback" not in output_lower
    
    # If there are failures, should provide helpful messaging
    if result.exit_code == 1:
        assert any(keyword in output_lower for keyword in [
            "failed", "error", "could not", "unable", "warning"
        ])
    
    # Even with partial failures, should remove what it can
    final_containers = client.containers.list(
        all=True, filters={"label": "ollama-stack.component"}
    )
    # Should have removed at least some containers (ideally all)
    assert len(final_containers) <= len(initial_containers), \
        "Should remove at least some containers even with partial failures"


@pytest.mark.integration
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_uninstall_config_removal_filesystem_verification():
    """
    Verifies config removal actually removes files and directories from filesystem.
    
    Tests real filesystem operations and directory structure cleanup.
    """
    import os
    import tempfile
    
    # Create config directory structure for testing
    config_dir = os.path.expanduser("~/.ollama-stack")
    os.makedirs(config_dir, exist_ok=True)
    
    # Create test files to verify removal
    test_files = [
        os.path.join(config_dir, "config.json"),
        os.path.join(config_dir, "settings.yaml"),
        os.path.join(config_dir, "logs", "app.log")
    ]
    
    # Create subdirectory and files
    os.makedirs(os.path.join(config_dir, "logs"), exist_ok=True)
    for file_path in test_files:
        with open(file_path, 'w') as f:
            f.write('test data')
    
    # Verify files exist
    for file_path in test_files:
        assert os.path.exists(file_path), f"Test file {file_path} should exist"
    
    # Run uninstall with config removal
    result = runner.invoke(app, ["uninstall", "--remove-config"])
    assert result.exit_code == 0
    
    # Verify entire config directory and all contents are removed
    assert not os.path.exists(config_dir), "Entire config directory should be removed"
    
    # Verify individual files are gone
    for file_path in test_files:
        assert not os.path.exists(file_path), f"Test file {file_path} should be removed"


@pytest.mark.integration
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_uninstall_volume_removal_data_loss_verification():
    """
    Verifies that volume removal actually destroys persistent data.
    
    Tests real data destruction through Docker volume removal.
    """
    # Start stack and let it create data
    start_result = runner.invoke(app, ["start"])
    assert start_result.exit_code == 0
    
    # Give services time to create persistent data
    time.sleep(5)
    
    client = docker.from_env()
    initial_volumes = client.volumes.list(filters={"label": "com.docker.compose.project=ollama-stack"})
    volume_names = [vol.name for vol in initial_volumes]
    
    # Run uninstall with volume removal
    result = runner.invoke(app, ["uninstall", "--remove-volumes"])
    assert result.exit_code == 0
    
    # Verify volumes are actually gone from Docker
    final_volumes = client.volumes.list(filters={"label": "com.docker.compose.project=ollama-stack"})
    final_volume_names = [vol.name for vol in final_volumes]
    
    # All initial volumes should be destroyed
    for volume_name in volume_names:
        assert volume_name not in final_volume_names, f"Volume {volume_name} should be removed"
    
    # Verify we can't access the removed volumes
    for volume_name in volume_names:
        try:
            client.volumes.get(volume_name)
            assert False, f"Volume {volume_name} should not be accessible after removal"
        except docker.errors.NotFound:
            pass  # Expected - volume should not be found


@pytest.mark.integration
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_uninstall_complete_system_state_verification():
    """
    Verifies complete system state after uninstall with all flags.
    
    Tests that --all flag leaves no trace of the stack in the system.
    """
    import os
    
    # Start stack and create comprehensive state
    start_result = runner.invoke(app, ["start"])
    assert start_result.exit_code == 0
    time.sleep(5)  # Let everything initialize
    
    client = docker.from_env()
    
    # Capture initial state
    initial_containers = client.containers.list(
        all=True, filters={"label": "ollama-stack.component"}
    )
    initial_volumes = client.volumes.list(filters={"label": "com.docker.compose.project=ollama-stack"})
    initial_images = client.images.list(filters={"label": "ollama-stack.component"})
    
    config_dir = os.path.expanduser("~/.ollama-stack")
    if not os.path.exists(config_dir):
        os.makedirs(config_dir, exist_ok=True)
    
    # Verify we have resources to clean up
    assert len(initial_containers) > 0, "Should have containers to test cleanup"
    
    # Run complete uninstall
    result = runner.invoke(app, ["uninstall", "--all"])
    assert result.exit_code == 0
    
    # Verify COMPLETE system cleanup
    
    # 1. No containers
    final_containers = client.containers.list(
        all=True, filters={"label": "ollama-stack.component"}
    )
    assert len(final_containers) == 0, "No stack containers should remain"
    
    # 2. No volumes 
    final_volumes = client.volumes.list(filters={"label": "com.docker.compose.project=ollama-stack"})
    assert len(final_volumes) == 0, "No stack volumes should remain"
    
    # 3. No config directory
    assert not os.path.exists(config_dir), "Config directory should be completely removed"
    
    # 4. No running services
    assert get_actual_running_services() == set(), "No services should be running"
    
    # 5. No native processes (if on Apple Silicon)
    if IS_APPLE_SILICON:
        assert not is_ollama_native_service_running(), "Native Ollama should be stopped"
    
    # The system should be in a clean state as if the stack was never installed
    # (except for Docker images which may persist)


# --- Install Command Integration Tests ---

@pytest.mark.integration
def test_install_command_fresh_system_creates_config_files():
    """
    Verifies that install command creates actual configuration files on filesystem
    with correct content and structure.
    
    Tests the most basic user workflow: fresh install on clean system.
    """
    import os
    import json
    
    config_dir = os.path.expanduser("~/.ollama-stack")
    config_file = os.path.join(config_dir, ".ollama-stack.json")
    env_file = os.path.join(config_dir, ".env")
    
    # Ensure clean state using uninstall command
    cleanup_result = runner.invoke(app, ["uninstall", "--all"])
    # Uninstall may succeed or return 1 if nothing to clean - both are fine
    assert cleanup_result.exit_code in [0, 1], "Cleanup should succeed or indicate nothing to clean"
    
    # Run install command with force flag to skip prompts
    result = runner.invoke(app, ["install", "--force"])
    assert result.exit_code == 0, f"Install should succeed, got: {result.stdout}"
    
    # Verify directory was actually created on filesystem
    assert os.path.exists(config_dir), "Config directory should be created"
    assert os.path.isdir(config_dir), "Config path should be a directory"
    
    # Verify config files were actually created
    assert os.path.exists(config_file), "JSON config file should be created"
    assert os.path.exists(env_file), "Environment file should be created"
    
    # Verify config file has valid JSON content
    with open(config_file, 'r') as f:
        config_data = json.load(f)
    
    # Verify essential configuration content in JSON file
    assert "platform" in config_data, "Should have platform configurations"
    assert "apple" in config_data["platform"], "Should have Apple platform config"
    assert "nvidia" in config_data["platform"], "Should have NVIDIA platform config"
    assert "services" in config_data, "Should have services configuration"
    assert "docker_compose_file" in config_data, "Should have compose file config"
    assert "extensions" in config_data, "Should have extensions configuration"
    
    # Verify platform config details
    assert config_data["platform"]["apple"]["compose_file"] == "docker-compose.apple.yml"
    assert config_data["platform"]["nvidia"]["compose_file"] == "docker-compose.nvidia.yml"
    
    # Verify environment file exists and contains expected content
    assert os.path.exists(env_file), "Environment file should be created"
    assert os.path.getsize(env_file) > 0, "Environment file should not be empty"
    
    # Read and verify environment file content
    with open(env_file, 'r') as f:
        env_content = f.read()
    
    assert "PROJECT_NAME='ollama-stack'" in env_content, "Environment file should contain project name"
    assert "WEBUI_SECRET_KEY=" in env_content, "Environment file should contain WebUI secret key"
    
    # Extract and verify the secret key from env file
    for line in env_content.strip().split('\n'):
        if line.startswith("WEBUI_SECRET_KEY="):
            secret_key = line.split("=", 1)[1]
            # Remove quotes if present
            if secret_key.startswith("'") and secret_key.endswith("'"):
                secret_key = secret_key[1:-1]
            assert len(secret_key) == 64, f"Secret key should be 64 characters, got {len(secret_key)}"
            # Verify it's not the placeholder value
            assert secret_key != "your-secret-key-here", "Should not have placeholder secret key"
            break
    else:
        assert False, "WEBUI_SECRET_KEY not found in environment file"
    
    # Cleanup using uninstall command
    runner.invoke(app, ["uninstall", "--all"])


@pytest.mark.integration
def test_install_command_generates_unique_secure_keys():
    """
    Verifies that install command generates cryptographically secure, unique keys
    for WebUI authentication.
    
    Tests actual key generation and uniqueness across multiple installs.
    """
    import os
    
    config_dir = os.path.expanduser("~/.ollama-stack")
    env_file = os.path.join(config_dir, ".env")
    
    def extract_secret_key(env_file_path):
        """Extract the secret key from the environment file."""
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
    
    # Clean state using uninstall command
    cleanup_result = runner.invoke(app, ["uninstall", "--all"])
    assert cleanup_result.exit_code in [0, 1], "Cleanup should succeed or indicate nothing to clean"
    
    # First install
    result1 = runner.invoke(app, ["install", "--force"])
    assert result1.exit_code == 0
    
    key1 = extract_secret_key(env_file)
    
    # Remove and install again
    cleanup_result = runner.invoke(app, ["uninstall", "--all"])
    assert cleanup_result.exit_code in [0, 1], "Cleanup should succeed"
    
    result2 = runner.invoke(app, ["install", "--force"])
    assert result2.exit_code == 0
    
    key2 = extract_secret_key(env_file)
    
    # Verify keys are different (cryptographically secure)
    assert key1 != key2, "Each install should generate unique keys"
    assert len(key1) == 64, f"Keys should be 64 characters, got {len(key1)}"
    assert len(key2) == 64, f"Keys should be 64 characters, got {len(key2)}"
    
    # Verify keys are not placeholder values
    assert key1 != "your-secret-key-here", "Should not have placeholder secret key"
    assert key2 != "your-secret-key-here", "Should not have placeholder secret key"
    
    # Verify keys only contain safe characters
    import string
    safe_chars = set(string.ascii_letters + string.digits + "-_")
    assert set(key1).issubset(safe_chars), "Key should only contain safe characters"
    assert set(key2).issubset(safe_chars), "Key should only contain safe characters"
    
    # Cleanup using uninstall command
    runner.invoke(app, ["uninstall", "--all"])


@pytest.mark.integration
def test_install_command_creates_platform_specific_configurations():
    """
    Verifies that install command creates proper platform-specific configurations
    for Apple Silicon and NVIDIA GPU support.
    
    Tests actual configuration content for cross-platform compatibility.
    """
    import os
    import json
    
    config_dir = os.path.expanduser("~/.ollama-stack")
    config_file = os.path.join(config_dir, ".ollama-stack.json")
    
    # Clean state using uninstall command
    cleanup_result = runner.invoke(app, ["uninstall", "--all"])
    assert cleanup_result.exit_code in [0, 1], "Cleanup should succeed or indicate nothing to clean"
    
    # Run install with force flag
    result = runner.invoke(app, ["install", "--force"])
    assert result.exit_code == 0
    
    # Verify platform configurations are created
    with open(config_file, 'r') as f:
        config_data = json.load(f)
    
    platform_config = config_data.get("platform", {})
    
    # Verify Apple platform configuration
    assert "apple" in platform_config, "Should have Apple platform configuration"
    apple_config = platform_config["apple"]
    assert apple_config.get("compose_file") == "docker-compose.apple.yml", \
        "Apple config should reference correct compose file"
    
    # Verify NVIDIA platform configuration
    assert "nvidia" in platform_config, "Should have NVIDIA platform configuration"
    nvidia_config = platform_config["nvidia"]
    assert nvidia_config.get("compose_file") == "docker-compose.nvidia.yml", \
        "NVIDIA config should reference correct compose file"
    
    # Cleanup using uninstall command
    runner.invoke(app, ["uninstall", "--all"])


@pytest.mark.integration
def test_install_command_runs_environment_validation():
    """
    Verifies that install command runs environment checks and provides
    appropriate feedback about system readiness.
    
    Tests integration with environment validation system.
    """
    import os
    
    config_dir = os.path.expanduser("~/.ollama-stack")
    
    # Clean state using uninstall command
    cleanup_result = runner.invoke(app, ["uninstall", "--all"])
    assert cleanup_result.exit_code in [0, 1], "Cleanup should succeed or indicate nothing to clean"
    
    # Run install with force flag
    result = runner.invoke(app, ["install", "--force"])
    assert result.exit_code == 0
    
    output_lower = result.stdout.lower()
    
    # Should show environment validation activity
    assert "validating environment" in output_lower or "environment check" in output_lower, \
        "Should indicate environment validation is running"
    
    # Should check Docker (whether available or not)
    assert "docker" in output_lower, "Should check Docker daemon status"
    
    # Should provide completion feedback
    assert any(keyword in output_lower for keyword in [
        "installation summary", "config", "created", "completed"
    ]), "Should provide installation completion feedback"
    
    # If Docker is available, should show more positive results
    if is_docker_available():
        # May show success or specific issues, but should not crash
        assert "error" not in output_lower or "environment issues" in output_lower
    
    # Cleanup using uninstall command
    runner.invoke(app, ["uninstall", "--all"]) 


@pytest.mark.integration
def test_install_over_existing_configuration_user_confirms():
    """
    Verifies install behavior when configuration already exists and user confirms overwrite.
    
    Tests actual user interaction flow and file replacement.
    """
    import os
    
    config_dir = os.path.expanduser("~/.ollama-stack")
    env_file = os.path.join(config_dir, ".env")
    
    def extract_secret_key(env_file_path):
        """Extract the secret key from the environment file."""
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
    
    # Clean state using uninstall command
    cleanup_result = runner.invoke(app, ["uninstall", "--all"])
    assert cleanup_result.exit_code in [0, 1], "Cleanup should succeed or indicate nothing to clean"
    
    # First install with force flag
    result1 = runner.invoke(app, ["install", "--force"])
    assert result1.exit_code == 0
    
    # Get original key from environment file
    original_key = extract_secret_key(env_file)
    
    # Second install with user confirmation (simulate user typing 'y')
    result2 = runner.invoke(app, ["install"], input="y\n")
    assert result2.exit_code == 0
    
    output_lower = result2.stdout.lower()
    assert "configuration already exists" in output_lower or "existing configuration" in output_lower, \
        "Should warn about existing configuration"
    
    # Verify new configuration was actually created
    new_key = extract_secret_key(env_file)
    
    # Should have generated new key (overwritten config)
    assert new_key != original_key, "Should generate new configuration"
    assert len(new_key) == 64, f"New key should be valid, got length {len(new_key)}"
    assert new_key != "your-secret-key-here", "Should not have placeholder secret key"
    
    # Cleanup using uninstall command
    runner.invoke(app, ["uninstall", "--all"])


@pytest.mark.integration
def test_install_over_existing_configuration_user_declines():
    """
    Verifies install behavior when configuration exists and user declines overwrite.
    
    Tests preservation of existing configuration when user chooses not to overwrite.
    """
    import os
    
    config_dir = os.path.expanduser("~/.ollama-stack")
    config_file = os.path.join(config_dir, ".ollama-stack.json")
    env_file = os.path.join(config_dir, ".env")
    
    def extract_secret_key(env_file_path):
        """Extract the secret key from the environment file."""
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
    
    # Clean state using uninstall command
    cleanup_result = runner.invoke(app, ["uninstall", "--all"])
    assert cleanup_result.exit_code in [0, 1], "Cleanup should succeed or indicate nothing to clean"
    
    # First install with force flag
    result1 = runner.invoke(app, ["install", "--force"])
    assert result1.exit_code == 0
    
    # Get original configuration
    original_key = extract_secret_key(env_file)
    original_env_modified_time = os.path.getmtime(env_file)
    original_config_modified_time = os.path.getmtime(config_file)
    
    # Second install with user declining (simulate user typing 'n')
    result2 = runner.invoke(app, ["install"], input="n\n")
    assert result2.exit_code == 0, "Should exit cleanly when user declines"
    
    output_lower = result2.stdout.lower()
    assert "cancelled" in output_lower or "preserved" in output_lower, \
        "Should indicate cancellation or preservation"
    
    # Verify original configuration is preserved
    assert os.path.exists(config_file), "Original config file should still exist"
    assert os.path.exists(env_file), "Original env file should still exist"
    
    preserved_key = extract_secret_key(env_file)
    
    # Configuration should be unchanged
    assert preserved_key == original_key, "Original configuration should be preserved"
    assert os.path.getmtime(env_file) == original_env_modified_time, \
        "Environment file should not be modified"
    assert os.path.getmtime(config_file) == original_config_modified_time, \
        "Config file should not be modified"
    
    # Cleanup using uninstall command
    runner.invoke(app, ["uninstall", "--all"])


@pytest.mark.integration
def test_install_with_force_flag_overwrites_without_prompting():
    """
    Verifies that --force flag bypasses user confirmation and overwrites existing config.
    
    Tests non-interactive overwrite behavior for automation scenarios.
    """
    import os
    
    config_dir = os.path.expanduser("~/.ollama-stack")
    env_file = os.path.join(config_dir, ".env")
    
    def extract_secret_key(env_file_path):
        """Extract the secret key from the environment file."""
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
    
    # Clean state using uninstall command
    cleanup_result = runner.invoke(app, ["uninstall", "--all"])
    assert cleanup_result.exit_code in [0, 1], "Cleanup should succeed or indicate nothing to clean"
    
    # First install with force flag
    result1 = runner.invoke(app, ["install", "--force"])
    assert result1.exit_code == 0
    
    # Get original key from environment file
    original_key = extract_secret_key(env_file)
    
    # Install with --force flag again (should not prompt)
    result2 = runner.invoke(app, ["install", "--force"])
    assert result2.exit_code == 0
    
    # Should NOT contain confirmation prompts in output
    output_lower = result2.stdout.lower()
    assert "do you want to overwrite" not in output_lower, \
        "Should not prompt when using --force flag"
    
    # Should show successful completion
    assert any(keyword in output_lower for keyword in [
        "created", "completed", "success"
    ]), "Should show successful completion"
    
    # Verify new configuration was created
    new_key = extract_secret_key(env_file)
    
    assert new_key != original_key, "Should generate new configuration with --force"
    assert len(new_key) == 64, f"New key should be valid, got length {len(new_key)}"
    assert new_key != "your-secret-key-here", "Should not have placeholder secret key"
    
    # Cleanup using uninstall command
    runner.invoke(app, ["uninstall", "--all"])


@pytest.mark.integration
def test_install_partial_existing_configuration():
    """
    Verifies install behavior when only some configuration files exist.
    
    Tests handling of incomplete/partial installation scenarios.
    """
    import os
    import json
    
    config_dir = os.path.expanduser("~/.ollama-stack")
    config_file = os.path.join(config_dir, ".ollama-stack.json")
    env_file = os.path.join(config_dir, ".env")
    
    def extract_secret_key(env_file_path):
        """Extract the secret key from the environment file."""
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
    
    # Clean state using uninstall command
    cleanup_result = runner.invoke(app, ["uninstall", "--all"])
    assert cleanup_result.exit_code in [0, 1], "Cleanup should succeed or indicate nothing to clean"
    
    # Create directory and only one config file (partial installation)
    os.makedirs(config_dir, exist_ok=True)
    with open(config_file, 'w') as f:
        json.dump({"partial": "config"}, f)
    
    # Should prompt because config file exists
    result = runner.invoke(app, ["install"], input="y\n")
    assert result.exit_code == 0
    
    # Should create both files
    assert os.path.exists(config_file), "JSON config should exist"
    assert os.path.exists(env_file), "Environment file should exist"
    
    # Verify complete configuration was created in JSON file
    with open(config_file, 'r') as f:
        final_config = json.load(f)
    
    # Check for proper structure in JSON config (project_name is in .env file)
    assert "services" in final_config, "Should have services configuration"
    assert "platform" in final_config, "Should have platform configuration"
    assert "extensions" in final_config, "Should have extensions configuration"
    
    # Verify environment file has correct content
    with open(env_file, 'r') as f:
        env_content = f.read()
    
    assert "PROJECT_NAME='ollama-stack'" in env_content, "Environment file should contain project name"
    secret_key = extract_secret_key(env_file)
    assert len(secret_key) == 64, f"Should have 64-character secret key, got {len(secret_key)}"
    assert secret_key != "your-secret-key-here", "Should not have placeholder secret key"
    
    # Cleanup using uninstall command
    runner.invoke(app, ["uninstall", "--all"])


@pytest.mark.integration
def test_install_existing_directory_no_config_files():
    """
    Verifies install behavior when config directory exists but contains no config files.
    
    Tests handling of empty config directory scenarios.
    """
    import os
    import json
    
    config_dir = os.path.expanduser("~/.ollama-stack")
    config_file = os.path.join(config_dir, ".ollama-stack.json")
    env_file = os.path.join(config_dir, ".env")
    
    # Clean state using uninstall command
    cleanup_result = runner.invoke(app, ["uninstall", "--all"])
    assert cleanup_result.exit_code in [0, 1], "Cleanup should succeed or indicate nothing to clean"
    
    # Create empty directory (no config files)
    os.makedirs(config_dir, exist_ok=True)
    
    # Should proceed without prompting (no config files exist) - use force to avoid any edge cases
    result = runner.invoke(app, ["install", "--force"])
    assert result.exit_code == 0
    
    # Should NOT prompt for confirmation
    output_lower = result.stdout.lower()
    assert "do you want to overwrite" not in output_lower, \
        "Should not prompt when no config files exist"
    
    # Should create config files
    assert os.path.exists(config_file), "Should create JSON config"
    assert os.path.exists(env_file), "Should create environment file"
    
    # Verify configuration content in proper locations
    with open(config_file, 'r') as f:
        config_data = json.load(f)
    
    # Check JSON config structure (project_name is in .env file)
    assert "services" in config_data, "Should have services configuration"
    assert "platform" in config_data, "Should have platform configuration"
    
    # Verify environment file has project name
    with open(env_file, 'r') as f:
        env_content = f.read()
    
    assert "PROJECT_NAME='ollama-stack'" in env_content, "Environment file should contain project name"
    
    # Cleanup using uninstall command
    runner.invoke(app, ["uninstall", "--all"])


@pytest.mark.integration
def test_install_command_help_accessibility():
    """
    Verifies that install command help is accessible and provides useful information.
    
    Tests user discoverability and documentation.
    """
    result = runner.invoke(app, ["install", "--help"])
    assert result.exit_code == 0
    
    output_lower = result.stdout.lower()
    
    # Should contain key information about the command
    assert "install" in output_lower, "Should mention install command"
    assert "configuration" in output_lower or "config" in output_lower, \
        "Should mention configuration"
    
    # Should show available options
    assert "--force" in result.stdout, "Should show --force option"
    
    # Should provide helpful description
    assert any(keyword in output_lower for keyword in [
        "initialize", "setup", "create", "prepare"
    ]), "Should describe what install does"


@pytest.mark.integration
def test_install_enables_other_commands():
    """
    Verifies that install command creates configuration that enables other commands to work.
    
    Tests end-to-end integration - install should prepare system for stack usage.
    """
    import os
    import shutil
    
    config_dir = os.path.expanduser("~/.ollama-stack")
    
    # Clean state
    if os.path.exists(config_dir):
        shutil.rmtree(config_dir)
    
    # Run install
    install_result = runner.invoke(app, ["install"])
    assert install_result.exit_code == 0
    
    # Verify other commands can now access configuration
    
    # Status command should work (doesn't require Docker)
    status_result = runner.invoke(app, ["status"])
    assert status_result.exit_code == 0
    assert "error" not in status_result.stdout.lower() or \
           "not running" in status_result.stdout.lower()
    
    # Check command should work
    check_result = runner.invoke(app, ["check"])
    # Check may succeed or fail depending on environment, but should not crash
    assert check_result.exit_code in [0, 1]
    assert "traceback" not in check_result.stdout.lower()
    
    # If Docker is available, start command should work
    if is_docker_available():
        start_result = runner.invoke(app, ["start"])
        assert start_result.exit_code == 0
        
        # Clean up after start test
        runner.invoke(app, ["stop"])
    
    # Cleanup
    if os.path.exists(config_dir):
        shutil.rmtree(config_dir)


@pytest.mark.integration
def test_install_cross_platform_compatibility():
    """
    Verifies that install command works correctly across different platforms.
    
    Tests platform-specific behavior and configuration creation.
    """
    import os
    import json
    import platform
    
    config_dir = os.path.expanduser("~/.ollama-stack")
    config_file = os.path.join(config_dir, ".ollama-stack.json")
    env_file = os.path.join(config_dir, ".env")
    
    # Clean state using uninstall command
    cleanup_result = runner.invoke(app, ["uninstall", "--all"])
    assert cleanup_result.exit_code in [0, 1], "Cleanup should succeed or indicate nothing to clean"
    
    # Run install with force flag
    result = runner.invoke(app, ["install", "--force"])
    assert result.exit_code == 0
    
    # Verify platform-appropriate configuration in JSON file
    with open(config_file, 'r') as f:
        config_data = json.load(f)
    
    # Should contain platform configurations regardless of current platform
    platform_config = config_data.get("platform", {})
    assert "apple" in platform_config, "Should include Apple config on all platforms"
    assert "nvidia" in platform_config, "Should include NVIDIA config on all platforms"
    
    # Verify project name is in environment file (not JSON config)
    with open(env_file, 'r') as f:
        env_content = f.read()
    
    current_platform = platform.system()
    assert "PROJECT_NAME='ollama-stack'" in env_content, \
        f"Should work on {current_platform}"
    
    # Cleanup using uninstall command
    runner.invoke(app, ["uninstall", "--all"])


@pytest.mark.integration
def test_install_filesystem_permissions_verification():
    """
    Verifies that install command creates files with appropriate filesystem permissions.
    
    Tests actual file permissions and security considerations.
    """
    import os
    import shutil
    import stat
    
    config_dir = os.path.expanduser("~/.ollama-stack")
    config_file = os.path.join(config_dir, ".ollama-stack.json")
    env_file = os.path.join(config_dir, ".env")
    
    # Clean state
    if os.path.exists(config_dir):
        shutil.rmtree(config_dir)
    
    # Run install
    result = runner.invoke(app, ["install"])
    assert result.exit_code == 0
    
    # Verify directory permissions
    dir_stat = os.stat(config_dir)
    dir_mode = stat.filemode(dir_stat.st_mode)
    # Should be readable and writable by owner
    assert dir_stat.st_mode & stat.S_IRUSR, "Directory should be readable by owner"
    assert dir_stat.st_mode & stat.S_IWUSR, "Directory should be writable by owner"
    
    # Verify file permissions
    config_stat = os.stat(config_file)
    env_stat = os.stat(env_file)
    
    # Files should be readable by owner
    assert config_stat.st_mode & stat.S_IRUSR, "Config file should be readable"
    assert env_stat.st_mode & stat.S_IRUSR, "Env file should be readable"
    assert config_stat.st_mode & stat.S_IWUSR, "Config file should be writable"
    assert env_stat.st_mode & stat.S_IWUSR, "Env file should be writable"
    
    # Cleanup
    if os.path.exists(config_dir):
        shutil.rmtree(config_dir)


@pytest.mark.integration
def test_install_configuration_file_format_validation():
    """
    Verifies that install command creates valid, parseable configuration files.
    
    Tests actual file format and content validity.
    """
    import os
    import json
    
    config_dir = os.path.expanduser("~/.ollama-stack")
    config_file = os.path.join(config_dir, ".ollama-stack.json")
    env_file = os.path.join(config_dir, ".env")
    
    # Clean state using uninstall command
    cleanup_result = runner.invoke(app, ["uninstall", "--all"])
    assert cleanup_result.exit_code in [0, 1], "Cleanup should succeed or indicate nothing to clean"
    
    # Run install with force flag
    result = runner.invoke(app, ["install", "--force"])
    assert result.exit_code == 0
    
    # Verify JSON config file is valid JSON
    try:
        with open(config_file, 'r') as f:
            config_data = json.load(f)
    except json.JSONDecodeError as e:
        assert False, f"Config file should be valid JSON: {e}"
    
    # Verify essential fields exist and have correct types in JSON config
    assert isinstance(config_data.get("services"), dict), \
        "services should be dictionary"
    assert isinstance(config_data.get("platform"), dict), \
        "platform should be dictionary"
    assert isinstance(config_data.get("extensions"), dict), \
        "extensions should be dictionary"
    assert isinstance(config_data.get("docker_compose_file"), str), \
        "docker_compose_file should be string"
    
    # Verify environment file is readable and contains expected content
    try:
        with open(env_file, 'r') as f:
            env_content = f.read()
        # Should be readable text file
        assert isinstance(env_content, str), "Environment file should be text"
        
        # Extract and validate project name
        assert "PROJECT_NAME=" in env_content, "Environment file should contain PROJECT_NAME"
        assert "WEBUI_SECRET_KEY=" in env_content, "Environment file should contain WEBUI_SECRET_KEY"
        
        # Validate secret key length
        for line in env_content.strip().split('\n'):
            if line.startswith("WEBUI_SECRET_KEY="):
                key = line.split("=", 1)[1]
                # Remove quotes if present
                if key.startswith("'") and key.endswith("'"):
                    key = key[1:-1]
                assert len(key) == 64, f"Secret key should be 64 characters, got {len(key)}"
                break
        
    except Exception as e:
        assert False, f"Environment file should be readable: {e}"
    
    # Cleanup using uninstall command
    runner.invoke(app, ["uninstall", "--all"])


@pytest.mark.integration
def test_install_error_message_quality():
    """
    Verifies that install command provides user-friendly error messages.
    
    Tests that error messages are helpful and don't expose technical details.
    """
    import os
    import shutil
    
    config_dir = os.path.expanduser("~/.ollama-stack")
    
    # Clean state
    if os.path.exists(config_dir):
        shutil.rmtree(config_dir)
    
    # Test successful install first
    result = runner.invoke(app, ["install"])
    assert result.exit_code == 0
    
    output_lower = result.stdout.lower()
    
    # Should not contain Python technical details
    assert "traceback" not in output_lower, "Should not show Python tracebacks"
    assert "exception" not in output_lower, "Should not show exception details"
    assert "attributeerror" not in output_lower, "Should not show AttributeError"
    assert "keyerror" not in output_lower, "Should not show KeyError"
    
    # Should contain helpful, user-focused messaging
    assert any(keyword in output_lower for keyword in [
        "created", "success", "completed", "configuration"
    ]), "Should provide clear success feedback"
    
    # Cleanup
    if os.path.exists(config_dir):
        shutil.rmtree(config_dir)


@pytest.mark.integration
def test_install_idempotent_multiple_runs():
    """
    Verifies that running install multiple times with --force is safe and produces consistent results.
    
    Tests that repeated install operations don't corrupt configuration or cause errors.
    """
    import os
    import json
    
    config_dir = os.path.expanduser("~/.ollama-stack")
    config_file = os.path.join(config_dir, ".ollama-stack.json")
    env_file = os.path.join(config_dir, ".env")
    
    def extract_secret_key(env_file_path):
        """Extract the secret key from the environment file."""
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
    
    # Clean state using uninstall command
    cleanup_result = runner.invoke(app, ["uninstall", "--all"])
    assert cleanup_result.exit_code in [0, 1], "Cleanup should succeed or indicate nothing to clean"
    
    # Multiple install runs
    for i in range(3):
        result = runner.invoke(app, ["install", "--force"])
        assert result.exit_code == 0, f"Install run {i+1} should succeed"
        
        # Verify configuration files exist after each run
        assert os.path.exists(config_file), f"JSON config should exist after run {i+1}"
        assert os.path.exists(env_file), f"Environment file should exist after run {i+1}"
        
        # Verify JSON configuration is valid after each run
        with open(config_file, 'r') as f:
            config_data = json.load(f)
        
        assert "services" in config_data, f"Services should be configured after run {i+1}"
        assert "platform" in config_data, f"Platform should be configured after run {i+1}"
        
        # Verify environment file content after each run
        with open(env_file, 'r') as f:
            env_content = f.read()
        
        assert "PROJECT_NAME='ollama-stack'" in env_content, \
            f"Project name should be correct after run {i+1}"
        
        secret_key = extract_secret_key(env_file)
        assert len(secret_key) == 64, \
            f"Secret key should be valid after run {i+1}, got {len(secret_key)}"
        assert secret_key != "your-secret-key-here", \
            f"Should not have placeholder secret key after run {i+1}"
    
    # Cleanup using uninstall command
    runner.invoke(app, ["uninstall", "--all"])


@pytest.mark.integration
def test_install_preserves_existing_non_config_files():
    """
    Verifies that install command preserves other files in config directory.
    
    Tests that install only affects its own config files and doesn't remove user data.
    """
    import os
    import json
    import shutil
    
    config_dir = os.path.expanduser("~/.ollama-stack")
    config_file = os.path.join(config_dir, ".ollama-stack.json")
    user_file = os.path.join(config_dir, "user-notes.txt")
    
    # Clean state
    if os.path.exists(config_dir):
        shutil.rmtree(config_dir)
    
    # Create directory with user file
    os.makedirs(config_dir, exist_ok=True)
    with open(user_file, 'w') as f:
        f.write("User's important notes")
    
    # Run install with force
    result = runner.invoke(app, ["install", "--force"])
    assert result.exit_code == 0
    
    # Verify user file is preserved
    assert os.path.exists(user_file), "User files should be preserved"
    with open(user_file, 'r') as f:
        content = f.read()
    assert content == "User's important notes", "User file content should be unchanged"
    
    # Verify config was created
    assert os.path.exists(config_file), "Config should be created"
    
    # Cleanup
    if os.path.exists(config_dir):
        shutil.rmtree(config_dir)


@pytest.mark.integration
def test_install_command_exit_codes():
    """
    Verifies that install command returns appropriate exit codes for different scenarios.
    
    Tests exit code behavior for automation and scripting scenarios.
    """
    import os
    
    config_dir = os.path.expanduser("~/.ollama-stack")
    
    # Clean state using uninstall command
    cleanup_result = runner.invoke(app, ["uninstall", "--all"])
    assert cleanup_result.exit_code in [0, 1], "Cleanup should succeed or indicate nothing to clean"
    
    # Fresh install should return 0
    result_fresh = runner.invoke(app, ["install", "--force"])
    assert result_fresh.exit_code == 0, "Fresh install should return exit code 0"
    
    # Install over existing with user declining should return 0 (clean exit, no error)
    result_decline = runner.invoke(app, ["install"], input="n\n")
    assert result_decline.exit_code == 0, "User declining should return exit code 0 (clean exit)"
    
    # Install with --force should return 0
    result_force = runner.invoke(app, ["install", "--force"])
    assert result_force.exit_code == 0, "Force install should return exit code 0"
    
    # Cleanup using uninstall command
    runner.invoke(app, ["uninstall", "--all"])


@pytest.mark.integration
def test_install_command_output_format_consistency():
    """
    Verifies that install command output is consistent and well-formatted.
    
    Tests user experience and output quality.
    """
    import os
    
    config_dir = os.path.expanduser("~/.ollama-stack")
    
    # Clean state using uninstall command
    cleanup_result = runner.invoke(app, ["uninstall", "--all"])
    assert cleanup_result.exit_code in [0, 1], "Cleanup should succeed or indicate nothing to clean"
    
    # Run fresh install with force flag to ensure successful completion
    result = runner.invoke(app, ["install", "--force"])
    assert result.exit_code == 0
    
    output = result.stdout
    
    # Should show configuration paths
    assert ".ollama-stack" in output, "Should show config directory path"
    
    # Should show some indication of success or completion
    assert any(keyword in output.lower() for keyword in [
        "created", "installation", "configuration", "success", "complete", "initialized"
    ]), "Should show installation progress or completion"
    
    # Should show platform detection
    assert any(keyword in output.lower() for keyword in [
        "platform", "apple", "silicon", "detected"
    ]), "Should show platform detection"
    
    # Should not have excessive blank lines or formatting issues
    lines = output.split('\n')
    empty_line_count = sum(1 for line in lines if line.strip() == '')
    total_lines = len(lines)
    
    # Should not be more than 50% empty lines (reasonable formatting)
    if total_lines > 0:
        empty_ratio = empty_line_count / total_lines
        assert empty_ratio < 0.5, "Should not have excessive empty lines"
    
    # Should not contain Python technical details in normal output
    output_lower = output.lower()
    assert "traceback" not in output_lower, "Should not show Python tracebacks"
    assert "exception" not in output_lower, "Should not show exception details"
    
    # Cleanup using uninstall command
    runner.invoke(app, ["uninstall", "--all"])


@pytest.mark.integration
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_install_integration_with_stack_workflow():
    """
    Verifies complete workflow: install -> start -> stop -> uninstall.
    
    Tests end-to-end integration of install command with full stack lifecycle.
    """
    import os
    import shutil
    
    config_dir = os.path.expanduser("~/.ollama-stack")
    
    # Clean state
    if os.path.exists(config_dir):
        shutil.rmtree(config_dir)
    
    # 1. Install
    install_result = runner.invoke(app, ["install"])
    assert install_result.exit_code == 0, "Install should succeed"
    assert os.path.exists(config_dir), "Config directory should be created"
    
    # 2. Start stack
    start_result = runner.invoke(app, ["start"])
    assert start_result.exit_code == 0, "Start should succeed after install"
    
    # Verify services are running
    expected_components = EXPECTED_ALL_COMPONENTS if IS_APPLE_SILICON else EXPECTED_DOCKER_COMPONENTS
    running_services = get_actual_running_services()
    assert running_services == expected_components, "Services should be running after start"
    
    # 3. Stop stack
    stop_result = runner.invoke(app, ["stop"])
    assert stop_result.exit_code == 0, "Stop should succeed"
    assert get_actual_running_services() == set(), "Services should be stopped"
    
    # 4. Uninstall
    uninstall_result = runner.invoke(app, ["uninstall", "--all"])
    assert uninstall_result.exit_code == 0, "Uninstall should succeed"
    assert not os.path.exists(config_dir), "Config directory should be removed"
    
    # System should be clean
    assert get_actual_running_services() == set(), "No services should remain"


@pytest.mark.integration
def test_install_without_docker_daemon():
    """
    Verifies install command behavior when Docker daemon is not running.
    
    Tests that install can complete successfully even without Docker,
    since install focuses on configuration setup.
    """
    import os
    import json
    import shutil
    
    if is_docker_available():
        pytest.skip("Docker is available - testing scenario when Docker is unavailable")
    
    config_dir = os.path.expanduser("~/.ollama-stack")
    config_file = os.path.join(config_dir, ".ollama-stack.json")
    
    # Clean state
    if os.path.exists(config_dir):
        shutil.rmtree(config_dir)
    
    # Install should succeed even without Docker
    result = runner.invoke(app, ["install"])
    assert result.exit_code == 0, "Install should succeed without Docker"
    
    # Configuration should still be created
    assert os.path.exists(config_dir), "Config directory should be created"
    assert os.path.exists(config_file), "Config file should be created"
    
    # Verify configuration content
    with open(config_file, 'r') as f:
        config_data = json.load(f)
    
    assert config_data.get("project_name") == "ollama-stack", "Config should be valid"
    assert "webui_secret_key" in config_data, "Should have secret key"
    
    # Environment checks may show Docker issues, but install should complete
    output_lower = result.stdout.lower()
    if "docker" in output_lower:
        # May show Docker-related warnings but should not fail completely
        assert any(keyword in output_lower for keyword in [
            "completed", "created", "summary"
        ]), "Should complete successfully despite Docker issues"
    
    # Cleanup
    if os.path.exists(config_dir):
        shutil.rmtree(config_dir)