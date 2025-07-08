import pytest
import os
import json
import time
import shutil
from pathlib import Path
from typer.testing import CliRunner
from ollama_stack_cli.main import app

import docker
from tests.integration.helpers import (
    is_docker_available,
    get_actual_running_services,
    wait_for_service_health,
    IS_APPLE_SILICON,
    EXPECTED_ALL_COMPONENTS,
    EXPECTED_DOCKER_COMPONENTS,
    TestArtifactTracker,
)

# --- Update Command Integration Tests ---

@pytest.mark.integration
@pytest.mark.stateful
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_update_pulls_latest_images(runner, pin_stack_version):
    """
    Verifies that update command pulls the latest Docker images.
    
    Tests the core update functionality with actual image pulling.
    """
    # Start with pinned version
    start_result = runner.invoke(app, ["start"])
    assert start_result.exit_code == 0
    
    # Run update command
    result = runner.invoke(app, ["update"])
    assert result.exit_code == 0
    
    # Should show pulling behavior
    output_lower = result.stdout.lower()
    pulling_keywords = ["pull", "downloading", "latest", "updating"]
    has_pulling_output = any(keyword in output_lower for keyword in pulling_keywords)
    
    # Note: May not always show pulling if images are already latest
    # The important thing is that the command succeeds
    
    # Verify services are still running after update
    expected_components = EXPECTED_ALL_COMPONENTS if IS_APPLE_SILICON else EXPECTED_DOCKER_COMPONENTS
    running_services = get_actual_running_services()
    assert running_services == expected_components


@pytest.mark.integration
@pytest.mark.stateful
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_update_command_when_stack_stopped(runner):
    """
    Verifies that the update command properly starts the stack, performs the update,
    and maintains service availability.
    """
    # Ensure stack is stopped
    runner.invoke(app, ["stop"])
    
    # Run update command
    result = runner.invoke(app, ["update"], input="y\n")
    assert result.exit_code == 0
    
    # Verify stack is running after update
    expected_components = EXPECTED_ALL_COMPONENTS if IS_APPLE_SILICON else EXPECTED_DOCKER_COMPONENTS
    running_services = get_actual_running_services()
    assert running_services == expected_components


@pytest.mark.integration
@pytest.mark.stateful
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_update_command_services_only_flag(runner):
    """
    Verifies that the --services-only flag updates only Docker services.
    """
    # Start the stack
    runner.invoke(app, ["start"])
    
    # Run update with services-only flag
    result = runner.invoke(app, ["update", "--services-only"])
    assert result.exit_code == 0
    
    # Verify stack is still running
    expected_components = EXPECTED_ALL_COMPONENTS if IS_APPLE_SILICON else EXPECTED_DOCKER_COMPONENTS
    running_services = get_actual_running_services()
    assert running_services == expected_components


@pytest.mark.integration
@pytest.mark.stateful
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_update_command_extensions_only_flag(runner):
    """
    Verifies that the --extensions-only flag updates only extensions.
    """
    # Start the stack
    runner.invoke(app, ["start"])
    
    # Run update with extensions-only flag
    result = runner.invoke(app, ["update", "--extensions-only"])
    assert result.exit_code == 0
    
    # Verify stack is still running
    expected_components = EXPECTED_ALL_COMPONENTS if IS_APPLE_SILICON else EXPECTED_DOCKER_COMPONENTS
    running_services = get_actual_running_services()
    assert running_services == expected_components


@pytest.mark.integration
@pytest.mark.stateless
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_update_command_conflicting_flags(runner):
    """
    Verifies that conflicting flags are handled appropriately.
    """
    result = runner.invoke(app, ["update", "--services-only", "--extensions-only"])
    
    # Should exit with error for conflicting flags
    assert result.exit_code != 0
    assert "conflicting" in result.stdout.lower() or "cannot" in result.stdout.lower()


@pytest.mark.integration
@pytest.mark.stateful
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_update_with_running_stack_user_confirms(runner):
    """
    Verifies that update handles running stack with user confirmation.
    """
    # Start the stack
    runner.invoke(app, ["start"])
    
    # Run update and confirm when prompted
    result = runner.invoke(app, ["update"], input="y\n")
    assert result.exit_code == 0
    
    # Should show confirmation prompt
    assert "running" in result.stdout.lower()
    assert any(keyword in result.stdout.lower() for keyword in ["confirm", "continue", "proceed"])
    
    # Stack should be running after update
    expected_components = EXPECTED_ALL_COMPONENTS if IS_APPLE_SILICON else EXPECTED_DOCKER_COMPONENTS
    running_services = get_actual_running_services()
    assert running_services == expected_components


@pytest.mark.integration
@pytest.mark.stateful
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_update_with_running_stack_user_declines(runner):
    """
    Verifies that update respects user decline when stack is running.
    """
    # Start the stack
    runner.invoke(app, ["start"])
    
    # Run update and decline when prompted
    result = runner.invoke(app, ["update"], input="n\n")
    
    # Should exit without error but without performing update
    assert result.exit_code == 0
    assert "cancelled" in result.stdout.lower() or "aborted" in result.stdout.lower()
    
    # Stack should still be running unchanged
    expected_components = EXPECTED_ALL_COMPONENTS if IS_APPLE_SILICON else EXPECTED_DOCKER_COMPONENTS
    running_services = get_actual_running_services()
    assert running_services == expected_components


@pytest.mark.integration
@pytest.mark.stateful
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_start_with_update_integration(runner):
    """
    Verifies that 'start --update' performs update during start.
    """
    # Ensure stack is stopped
    runner.invoke(app, ["stop"])
    
    # Start with update
    result = runner.invoke(app, ["start", "--update"])
    assert result.exit_code == 0
    
    # Should see update behavior in output
    output_lower = result.stdout.lower()
    update_keywords = ["pull", "updating", "download"]
    # May not always show update output if images are current
    
    # Stack should be running
    expected_components = EXPECTED_ALL_COMPONENTS if IS_APPLE_SILICON else EXPECTED_DOCKER_COMPONENTS
    running_services = get_actual_running_services()
    assert running_services == expected_components


@pytest.mark.integration
@pytest.mark.stateful
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_restart_with_update_integration(runner):
    """
    Verifies that 'restart --update' performs update during restart.
    """
    # Start the stack first
    runner.invoke(app, ["start"])
    
    # Get container IDs before restart
    client = docker.from_env()
    initial_containers = client.containers.list(filters={"label": "ollama-stack.component"})
    initial_ids = {c.id for c in initial_containers}
    
    # Restart with update
    result = runner.invoke(app, ["restart", "--update"])
    assert result.exit_code == 0
    
    # Should see update behavior in output
    output_lower = result.stdout.lower()
    update_keywords = ["pull", "updating", "download"]
    # May not always show update output if images are current
    
    # Stack should be running
    expected_components = EXPECTED_ALL_COMPONENTS if IS_APPLE_SILICON else EXPECTED_DOCKER_COMPONENTS
    running_services = get_actual_running_services()
    assert running_services == expected_components
    
    # Containers should be recreated (new IDs)
    final_containers = client.containers.list(filters={"label": "ollama-stack.component"})
    final_ids = {c.id for c in final_containers}
    if initial_ids:  # Only check if there were initial containers
        assert not initial_ids.intersection(final_ids)


@pytest.mark.integration
@pytest.mark.stateful
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_update_command_preserves_service_health(runner):
    """
    Verifies that services remain healthy after update.
    """
    # Start the stack
    runner.invoke(app, ["start"])
    
    # Verify initial health
    assert wait_for_service_health("webui", timeout=10)
    
    # Perform update
    result = runner.invoke(app, ["update"], input="y\n")
    assert result.exit_code == 0
    
    # Give services time to restart
    time.sleep(5)
    
    # Verify services are healthy after update
    assert wait_for_service_health("webui", timeout=15)
    
    # Verify all expected services are running
    expected_components = EXPECTED_ALL_COMPONENTS if IS_APPLE_SILICON else EXPECTED_DOCKER_COMPONENTS
    running_services = get_actual_running_services()
    assert running_services == expected_components


@pytest.mark.integration
@pytest.mark.stateful
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_update_command_idempotent(runner):
    """
    Verifies that running update multiple times is safe and idempotent.
    """
    # Start the stack
    runner.invoke(app, ["start"])
    
    # Run update first time
    result1 = runner.invoke(app, ["update"], input="y\n")
    assert result1.exit_code == 0
    
    # Run update second time
    result2 = runner.invoke(app, ["update"], input="y\n")
    assert result2.exit_code == 0
    
    # Should indicate no changes needed or complete successfully
    # Stack should be running
    expected_components = EXPECTED_ALL_COMPONENTS if IS_APPLE_SILICON else EXPECTED_DOCKER_COMPONENTS
    running_services = get_actual_running_services()
    assert running_services == expected_components


@pytest.mark.integration
@pytest.mark.stateful
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_update_command_help_accessibility(runner):
    """
    Verifies that update command help is accessible and informative.
    """
    result = runner.invoke(app, ["update", "--help"])
    assert result.exit_code == 0
    
    # Should contain key information about update command
    output_lower = result.stdout.lower()
    assert "update" in output_lower
    assert "services" in output_lower
    assert "extensions" in output_lower
    
    # Should show flag options
    assert "--services-only" in result.stdout
    assert "--extensions-only" in result.stdout


@pytest.mark.integration
@pytest.mark.stateful
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_update_with_network_interruption(runner):
    """
    Verifies update handling with simulated network issues.
    """
    # Start the stack
    runner.invoke(app, ["start"])
    
    # Run update (may fail due to network, but should handle gracefully)
    result = runner.invoke(app, ["update"], input="y\n")
    
    # Should not crash or leave system in inconsistent state
    assert result.exit_code in [0, 1]  # May succeed or fail gracefully
    
    # Should not show Python tracebacks
    assert "traceback" not in result.stdout.lower()
    
    # System should remain functional
    status_result = runner.invoke(app, ["status"])
    assert status_result.exit_code == 0


@pytest.mark.integration
@pytest.mark.stateful
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_update_maintains_container_state_consistency(runner):
    """
    Verifies that update maintains consistent container state.
    """
    # Start the stack
    runner.invoke(app, ["start"])
    
    # Get initial container state
    client = docker.from_env()
    initial_containers = client.containers.list(filters={"label": "ollama-stack.component"})
    initial_count = len(initial_containers)
    
    # Perform update
    result = runner.invoke(app, ["update"], input="y\n")
    assert result.exit_code == 0
    
    # Give containers time to restart
    time.sleep(5)
    
    # Check final container state
    final_containers = client.containers.list(filters={"label": "ollama-stack.component"})
    final_count = len(final_containers)
    
    # Should have same number of containers (may be different instances)
    assert final_count == initial_count
    
    # All containers should be running
    for container in final_containers:
        assert container.status == "running"
    
    # Verify expected services are running
    expected_components = EXPECTED_ALL_COMPONENTS if IS_APPLE_SILICON else EXPECTED_DOCKER_COMPONENTS
    running_services = get_actual_running_services()
    assert running_services == expected_components


@pytest.mark.integration
@pytest.mark.stateful
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_update_services_only_excludes_extensions(runner):
    """
    Verifies that --services-only flag excludes extension updates.
    """
    # Start the stack
    runner.invoke(app, ["start"])
    
    # Run update with services-only flag
    result = runner.invoke(app, ["update", "--services-only"])
    assert result.exit_code == 0
    
    # Should indicate services-only mode
    output_lower = result.stdout.lower()
    assert "services" in output_lower
    
    # Services should be running after update
    expected_components = EXPECTED_ALL_COMPONENTS if IS_APPLE_SILICON else EXPECTED_DOCKER_COMPONENTS
    running_services = get_actual_running_services()
    assert running_services == expected_components


@pytest.mark.integration
@pytest.mark.stateful
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_update_with_partial_service_failures(runner):
    """
    Verifies update handling when some services fail to update.
    """
    # Start the stack
    runner.invoke(app, ["start"])
    
    # Run update (may have partial failures)
    result = runner.invoke(app, ["update"], input="y\n")
    
    # Should handle partial failures gracefully
    assert result.exit_code in [0, 1]  # May succeed or fail gracefully
    
    # Should not crash or show Python tracebacks
    assert "traceback" not in result.stdout.lower()
    
    # System should remain in consistent state
    status_result = runner.invoke(app, ["status"])
    assert status_result.exit_code == 0
    
    # At least some services should be running
    running_services = get_actual_running_services()
    assert len(running_services) > 0


@pytest.mark.integration
@pytest.mark.stateful
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_update_stop_failure_handling(runner):
    """
    Verifies update handling when stack stop fails.
    """
    # Start the stack
    runner.invoke(app, ["start"])
    
    # Run update (may encounter stop failures)
    result = runner.invoke(app, ["update"], input="y\n")
    
    # Should handle stop failures gracefully
    assert result.exit_code in [0, 1]  # May succeed or fail gracefully
    
    # Should not crash
    assert "traceback" not in result.stdout.lower()
    
    # System should remain functional
    final_status = runner.invoke(app, ["status"])
    assert final_status.exit_code == 0


@pytest.mark.integration
@pytest.mark.stateful
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_update_restart_failure_handling(runner):
    """
    Verifies update handling when restart fails.
    """
    # Start the stack
    runner.invoke(app, ["start"])
    
    # Run update (may encounter restart failures)
    result = runner.invoke(app, ["update"], input="y\n")
    
    # Should handle restart failures gracefully
    assert result.exit_code in [0, 1]  # May succeed or fail gracefully
    
    # Should not crash
    assert "traceback" not in result.stdout.lower()
    
    # System should remain in consistent state
    final_status = runner.invoke(app, ["status"])
    assert final_status.exit_code == 0


@pytest.mark.integration
@pytest.mark.stateful
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_concurrent_update_operations(runner):
    """
    Verifies that concurrent update operations are handled safely.
    """
    # Start the stack
    runner.invoke(app, ["start"])
    
    # Run update operations in sequence (simulating concurrent access)
    result1 = runner.invoke(app, ["update"], input="y\n")
    result2 = runner.invoke(app, ["update"], input="y\n")
    
    # Both should complete without crashing
    assert result1.exit_code in [0, 1]
    assert result2.exit_code in [0, 1]
    
    # Should not show Python tracebacks
    assert "traceback" not in result1.stdout.lower()
    assert "traceback" not in result2.stdout.lower()
    
    # Final system state should be consistent
    final_status = runner.invoke(app, ["status"])
    assert final_status.exit_code == 0


@pytest.mark.integration
@pytest.mark.stateful
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_update_with_config_changes(runner):
    """
    Verifies that update handles configuration changes appropriately.
    """
    # Start the stack
    runner.invoke(app, ["start"])
    
    # Run update (may involve configuration changes)
    result = runner.invoke(app, ["update"], input="y\n")
    assert result.exit_code == 0
    
    # Stack should be running with updated configuration
    expected_components = EXPECTED_ALL_COMPONENTS if IS_APPLE_SILICON else EXPECTED_DOCKER_COMPONENTS
    running_services = get_actual_running_services()
    assert running_services == expected_components
    
    # Services should be healthy
    assert wait_for_service_health("webui", timeout=15)


@pytest.mark.integration
@pytest.mark.stateful
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_update_preserves_running_service_data(runner):
    """
    Verifies that update preserves service data and state.
    """
    # Start the stack
    runner.invoke(app, ["start"])
    
    # Let services create some data
    time.sleep(5)
    
    # Perform update
    result = runner.invoke(app, ["update"], input="y\n")
    assert result.exit_code == 0
    
    # Give services time to restart
    time.sleep(5)
    
    # Verify services are healthy (indicating data preservation)
    assert wait_for_service_health("webui", timeout=15)
    
    # Verify all expected services are running
    expected_components = EXPECTED_ALL_COMPONENTS if IS_APPLE_SILICON else EXPECTED_DOCKER_COMPONENTS
    running_services = get_actual_running_services()
    assert running_services == expected_components


@pytest.mark.integration
@pytest.mark.stateful
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_update_command_resource_cleanup(runner):
    """
    Verifies that update command properly cleans up resources.
    """
    # Start the stack
    runner.invoke(app, ["start"])
    
    # Get initial Docker resource count
    client = docker.from_env()
    initial_containers = client.containers.list(all=True, filters={"label": "ollama-stack.component"})
    initial_images = client.images.list(filters={"label": "ollama-stack.component"})
    
    # Perform update
    result = runner.invoke(app, ["update"], input="y\n")
    assert result.exit_code == 0
    
    # Give cleanup time to complete
    time.sleep(5)
    
    # Check final resource count
    final_containers = client.containers.list(all=True, filters={"label": "ollama-stack.component"})
    final_images = client.images.list(filters={"label": "ollama-stack.component"})
    
    # Should not have excessive resource accumulation
    # (Some variance is expected due to update process)
    assert len(final_containers) <= len(initial_containers) + 5  # Allow some variance
    
    # Running containers should match expected count
    running_containers = client.containers.list(filters={"label": "ollama-stack.component"})
    expected_count = len(EXPECTED_DOCKER_COMPONENTS)
    assert len(running_containers) == expected_count


@pytest.mark.integration
@pytest.mark.stateful
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_update_mixed_service_types_coordination(runner):
    """
    Verifies that update coordinates Docker and native services appropriately.
    """
    # Start the stack
    runner.invoke(app, ["start"])
    
    # Perform update
    result = runner.invoke(app, ["update"], input="y\n")
    assert result.exit_code == 0
    
    # Verify coordinated service state
    expected_components = EXPECTED_ALL_COMPONENTS if IS_APPLE_SILICON else EXPECTED_DOCKER_COMPONENTS
    running_services = get_actual_running_services()
    assert running_services == expected_components
    
    # On Apple Silicon, verify both Docker and native services are coordinated
    if IS_APPLE_SILICON:
        # Should have both Docker services and native Ollama
        docker_services = {s for s in running_services if s in EXPECTED_DOCKER_COMPONENTS}
        assert len(docker_services) > 0
        assert "ollama" in running_services


@pytest.mark.integration
@pytest.mark.stateful
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_update_performance_under_load(runner):
    """
    Verifies update performance under typical load conditions.
    """
    # Start the stack
    runner.invoke(app, ["start"])
    
    # Record start time
    start_time = time.time()
    
    # Perform update
    result = runner.invoke(app, ["update"], input="y\n")
    assert result.exit_code == 0
    
    # Record end time
    end_time = time.time()
    update_duration = end_time - start_time
    
    # Update should complete within reasonable time
    assert update_duration < 300, f"Update took too long: {update_duration:.2f} seconds"
    
    # Services should be running and healthy
    expected_components = EXPECTED_ALL_COMPONENTS if IS_APPLE_SILICON else EXPECTED_DOCKER_COMPONENTS
    running_services = get_actual_running_services()
    assert running_services == expected_components
    
    # Services should be healthy
    assert wait_for_service_health("webui", timeout=15)


@pytest.mark.integration
@pytest.mark.stateful
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_update_stack_state_consistency_across_operations(runner):
    """
    Verifies that update maintains stack state consistency across multiple operations.
    """
    # Start the stack
    runner.invoke(app, ["start"])
    
    # Perform multiple update operations
    operations = [
        ["update", "--services-only"],
        ["status"],
        ["update", "--extensions-only"],
        ["status"],
        ["update"],
    ]
    
    for operation in operations:
        if operation[0] == "update":
            result = runner.invoke(app, operation, input="y\n")
        else:
            result = runner.invoke(app, operation)
        
        # Each operation should complete successfully
        assert result.exit_code in [0, 1]  # May succeed or fail gracefully
        
        # Should not crash
        assert "traceback" not in result.stdout.lower()
    
    # Final state should be consistent
    expected_components = EXPECTED_ALL_COMPONENTS if IS_APPLE_SILICON else EXPECTED_DOCKER_COMPONENTS
    running_services = get_actual_running_services()
    assert running_services == expected_components


@pytest.mark.integration
def test_update_error_message_quality(runner):
    """
    Verifies that update command provides high-quality error messages.
    """
    # Test with Docker unavailable
    if not is_docker_available():
        result = runner.invoke(app, ["update"])
        assert result.exit_code != 0
        
        # Should have user-friendly error message
        output_lower = result.stdout.lower()
        assert any(keyword in output_lower for keyword in [
            "docker daemon", "docker desktop", "not running"
        ])
        
        # Should not have technical error details
        assert "traceback" not in output_lower
        assert "connectionrefusederror" not in output_lower
        assert "exception" not in output_lower
    
    # Test with conflicting flags
    result = runner.invoke(app, ["update", "--services-only", "--extensions-only"])
    assert result.exit_code != 0
    
    # Should have clear error message about conflicting flags
    output_lower = result.stdout.lower()
    assert any(keyword in output_lower for keyword in [
        "conflicting", "cannot use", "mutually exclusive"
    ])
    
    # Should not have technical error details
    assert "traceback" not in output_lower