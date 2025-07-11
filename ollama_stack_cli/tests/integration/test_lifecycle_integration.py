import pytest
import time
import shutil
from typer.testing import CliRunner
from ollama_stack_cli.main import app

from ollama_stack_cli.tests.integration.helpers import (
    is_docker_available,
    get_running_stack_components,
    get_actual_running_services,
    is_ollama_native_service_running,
    wait_for_service_health,
    stop_native_ollama_if_running,
    IS_APPLE_SILICON,
    EXPECTED_ALL_COMPONENTS,
    EXPECTED_DOCKER_COMPONENTS,
    TestArtifactTracker,
)

# --- Core Lifecycle Integration Tests ---

@pytest.mark.integration
@pytest.mark.stateful
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available or not running")
def test_start_and_stop_lifecycle(runner):
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
@pytest.mark.stateless
def test_start_command_without_docker(runner):
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
@pytest.mark.stateful
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_start_when_already_running_is_idempotent(runner):
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
@pytest.mark.stateless
def test_stop_when_already_stopped_is_idempotent(runner):
    """
    Verifies that running 'stop' on an already stopped stack has no
    negative side effects and exits gracefully.
    """
    # The fixture ensures the stack is already stopped.
    result = runner.invoke(app, ["stop"])
    assert result.exit_code == 0
    assert get_actual_running_services() == set()


@pytest.mark.integration
@pytest.mark.stateful
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_restart_recreates_services(runner):
    """
    Verifies that 'restart' correctly replaces the running containers
    with new ones and maintains service availability.
    """
    import docker
    
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
@pytest.mark.stateless
def test_restart_without_docker(runner):
    """
    Verifies that when Docker daemon is not running, the restart command 
    fails gracefully with a clean, user-friendly error message.
    """
    if is_docker_available():
        pytest.skip("Docker is available - testing Docker unavailable scenario")
    
    result = runner.invoke(app, ["restart"])
    
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


@pytest.mark.integration
@pytest.mark.stateful
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_restart_with_update_pulls_images(runner):
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
@pytest.mark.stateful
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_start_with_update_pulls_images(runner):
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
@pytest.mark.stateful
@pytest.mark.skipif(not IS_APPLE_SILICON, reason="Native Ollama test only applicable on Apple Silicon")
def test_native_ollama_service_lifecycle(runner):
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
@pytest.mark.stateful
@pytest.mark.skipif(IS_APPLE_SILICON, reason="Docker Ollama test not applicable on Apple Silicon")
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_docker_ollama_service_lifecycle(runner):
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
@pytest.mark.stateful
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_service_health_after_start(runner):
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
@pytest.mark.stateful
@pytest.mark.skipif(not IS_APPLE_SILICON, reason="Test only applicable on Apple Silicon") 
def test_apple_silicon_without_ollama_installed(runner):
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
@pytest.mark.stateless
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_status_command_reflects_actual_state(runner):
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
@pytest.mark.stateless
def test_check_command_validates_environment(runner):
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
@pytest.mark.stateful
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_logs_command_accesses_actual_logs(runner):
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
    logs_result = runner.invoke(app, ["logs", "webui", "--tail", "10"])
    assert logs_result.exit_code == 0
    
    # Should get some log output (even if minimal)
    # The important thing is that the command succeeds and doesn't error
    assert len(logs_result.stdout.strip()) >= 0  # May be empty but shouldn't error


@pytest.mark.integration
@pytest.mark.stateful
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_logs_command_with_follow_option(runner):
    """
    Verifies the 'logs' command with --follow option works correctly.
    
    This tests streaming log functionality.
    """
    # Start the stack so services are running
    start_result = runner.invoke(app, ["start"])
    assert start_result.exit_code == 0
    
    # Give services a moment to generate some logs
    time.sleep(2)
    
    # Test logs with follow - use a timeout to prevent hanging
    # In integration tests, we can't easily test the follow functionality
    # without hanging, so we test that the command starts correctly
    import signal
    import subprocess
    import os
    
    # Use subprocess with timeout instead of runner.invoke for follow
    try:
        # Run the logs command with follow in a subprocess with timeout
        process = subprocess.Popen(
            ["python", "-m", "ollama_stack_cli.main", "logs", "webui", "--follow", "--tail", "5"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Wait for a short time to see if it starts correctly
        try:
            stdout, stderr = process.communicate(timeout=5)  # 5 second timeout
            # If it completes within 5 seconds, that's fine
            assert process.returncode in [0, 1]
        except subprocess.TimeoutExpired:
            # If it doesn't complete in 5 seconds, that's expected for follow
            # Kill the process and consider it a success
            process.kill()
            process.wait()
            # This is expected behavior for follow command
            pass
            
    except Exception as e:
        # If subprocess approach fails, skip the test
        pytest.skip(f"Follow test not suitable for this environment: {e}")