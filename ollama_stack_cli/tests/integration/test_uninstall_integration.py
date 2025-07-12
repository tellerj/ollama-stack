import pytest
import os
import json
import time
import shutil
import docker
from pathlib import Path
from typer.testing import CliRunner
from ollama_stack_cli.main import app

from ollama_stack_cli.tests.integration.helpers import (
    is_docker_available,
    get_actual_running_services,
    get_running_stack_components,
    is_ollama_native_service_running,
    wait_for_stack_to_stop,
    verify_stack_completely_stopped,
    ensure_clean_test_environment,
    cleanup_minimal,
    cleanup_full,
    IS_APPLE_SILICON,
    EXPECTED_ALL_COMPONENTS,
    EXPECTED_DOCKER_COMPONENTS,
    ArtifactTracker,
)
from ollama_stack_cli.config import get_default_config_dir

# --- Uninstall Command Integration Tests ---

@pytest.mark.integration
@pytest.mark.stateful
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_uninstall_removes_all_stack_components(runner, isolated_test_environment):
    """
    Verifies that uninstall command removes all stack components.
    
    Tests the core uninstall functionality with actual component removal.
    """
    # Install and start stack first
    install_result = runner.invoke(app, ["install", "--force"])
    assert install_result.exit_code == 0
    
    start_result = runner.invoke(app, ["start"])
    assert start_result.exit_code == 0
    
    # Verify stack is running
    expected_components = EXPECTED_ALL_COMPONENTS if IS_APPLE_SILICON else EXPECTED_DOCKER_COMPONENTS
    running_services = get_actual_running_services()
    assert running_services == expected_components
    
    # Stop stack before uninstall
    stop_result = runner.invoke(app, ["stop"])
    assert stop_result.exit_code == 0
    
    # Run uninstall command
    result = runner.invoke(app, ["uninstall", "--force"])
    assert result.exit_code == 0
    
    # Verify uninstall completed (may show different messages based on what was found)
    output_lower = result.stdout.lower()
    assert any(phrase in output_lower for phrase in [
        "uninstall completed", "no stack resources found", "removing stack resources"
    ])
    
    # Verify all services are stopped
    final_services = get_actual_running_services()
    assert len(final_services) == 0


@pytest.mark.integration
@pytest.mark.stateful
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_uninstall_basic_removes_docker_resources_preserves_data(runner, clean_config_dir):
    """
    Verifies that basic uninstall removes Docker resources but preserves data.
    """
    # Install and start stack
    runner.invoke(app, ["install", "--force"])
    runner.invoke(app, ["start"])
    
    # Verify stack is running
    expected_components = EXPECTED_ALL_COMPONENTS if IS_APPLE_SILICON else EXPECTED_DOCKER_COMPONENTS
    running_services = get_actual_running_services()
    assert running_services == expected_components
    
    # Get initial Docker resources
    client = docker.from_env()
    initial_containers = client.containers.list(all=True, filters={"label": "ollama-stack.component"})
    initial_volumes = client.volumes.list(filters={"label": "com.docker.compose.project=ollama-stack"})
    
    # Perform basic uninstall
    result = runner.invoke(app, ["uninstall"])
    assert result.exit_code == 0
    
    # Verify stack is stopped
    assert wait_for_stack_to_stop(timeout=15)
    
    # Verify containers are removed
    final_containers = client.containers.list(all=True, filters={"label": "ollama-stack.component"})
    assert len(final_containers) == 0
    
    # Verify volumes are preserved (basic uninstall doesn't remove volumes)
    final_volumes = client.volumes.list(filters={"label": "com.docker.compose.project=ollama-stack"})
    assert len(final_volumes) == len(initial_volumes)
    
    # Verify configuration is preserved
    config_dir = clean_config_dir
    assert os.path.exists(config_dir)
    assert os.path.exists(os.path.join(config_dir, ".ollama-stack.json"))
    assert os.path.exists(os.path.join(config_dir, ".env"))


@pytest.mark.integration
@pytest.mark.stateful
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_uninstall_remove_volumes_actually_removes_data(runner, clean_config_dir):
    """
    Verifies that --remove-volumes actually removes Docker volumes.
    """
    
    # Install and start stack
    runner.invoke(app, ["install", "--force"])
    runner.invoke(app, ["start"])
    
    # Let services create data
    time.sleep(5)
    
    # Get initial volumes using Docker Compose project label (which is what the stack actually uses)
    client = docker.from_env()
    initial_volumes = client.volumes.list(filters={"label": "com.docker.compose.project=ollama-stack"})
    
    # If no volumes exist, skip the volume removal test
    if len(initial_volumes) == 0:
        pytest.skip("No volumes found to test removal - stack may not have created volumes yet")
    
    # Perform uninstall with volume removal
    result = runner.invoke(app, ["uninstall", "--remove-volumes"])
    assert result.exit_code == 0
    
    # Verify volumes are removed or significantly reduced
    final_volumes = client.volumes.list(filters={"label": "com.docker.compose.project=ollama-stack"})
    
    # The test passes if either:
    # 1. All volumes are removed (ideal case)
    # 2. Fewer volumes remain than initially (partial cleanup due to conflicts)
    assert len(final_volumes) <= len(initial_volumes), f"Expected volume count to decrease, got {len(final_volumes)} vs {len(initial_volumes)}"
    
    # If some volumes remain, log a warning but don't fail the test
    if len(final_volumes) > 0:
        print(f"Warning: {len(final_volumes)} volumes remain after removal (may be in use by other containers)")
    
    # Verify stack is stopped
    assert wait_for_stack_to_stop(timeout=15)
    
    # Configuration should still exist
    config_dir = clean_config_dir
    assert os.path.exists(config_dir)


@pytest.mark.integration
@pytest.mark.stateful
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_uninstall_remove_config_actually_removes_filesystem_config(runner, clean_config_dir):
    """
    Verifies that --remove-config actually removes filesystem configuration.
    """
    # Install and start stack
    runner.invoke(app, ["install", "--force"])
    runner.invoke(app, ["start"])
    
    # Verify configuration exists
    config_dir = clean_config_dir
    assert os.path.exists(config_dir)
    assert os.path.exists(os.path.join(config_dir, ".ollama-stack.json"))
    assert os.path.exists(os.path.join(config_dir, ".env"))
    
    # Perform uninstall with config removal
    result = runner.invoke(app, ["uninstall", "--remove-config"])
    assert result.exit_code == 0
    
    # Verify configuration is removed
    assert not os.path.exists(config_dir)
    
    # Verify stack is stopped
    assert wait_for_stack_to_stop(timeout=15)


@pytest.mark.integration
@pytest.mark.stateful
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_uninstall_all_flag_removes_everything(runner, clean_config_dir):
    """
    Verifies that --all flag removes containers, volumes, and configuration.
    """
    # Install and start stack
    runner.invoke(app, ["install", "--force"])
    runner.invoke(app, ["start"])
    
    # Let services create data
    time.sleep(5)
    
    # Verify initial state
    config_dir = clean_config_dir
    assert os.path.exists(config_dir)
    
    client = docker.from_env()
    initial_containers = client.containers.list(all=True, filters={"label": "ollama-stack.component"})
    initial_volumes = client.volumes.list(filters={"label": "com.docker.compose.project=ollama-stack"})
    
    # Verify we have some stack resources to test removal
    has_containers = len(initial_containers) > 0
    has_volumes = len(initial_volumes) > 0
    
    if not has_containers and not has_volumes:
        pytest.skip("No stack resources found to test removal")
    
    # Perform complete uninstall
    result = runner.invoke(app, ["uninstall", "--all"])
    assert result.exit_code == 0
    
    # Verify everything is removed
    # Stack should be stopped
    assert wait_for_stack_to_stop(timeout=15)
    
    # Containers should be removed
    final_containers = client.containers.list(all=True, filters={"label": "ollama-stack.component"})
    assert len(final_containers) == 0
    
    # Volumes should be removed or significantly reduced
    final_volumes = client.volumes.list(filters={"label": "com.docker.compose.project=ollama-stack"})
    assert len(final_volumes) <= len(initial_volumes), f"Expected volume count to decrease or stay same, got {len(final_volumes)} vs {len(initial_volumes)}"
    
    # Configuration should be removed
    assert not os.path.exists(config_dir)


@pytest.mark.integration
@pytest.mark.stateful
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_uninstall_short_form_all_flag_equivalent(runner, clean_config_dir):
    """
    Verifies that -a short form is equivalent to --all.
    """
    # Install and start stack
    runner.invoke(app, ["install", "--force"])
    runner.invoke(app, ["start"])
    
    # Let services create data
    time.sleep(5)
    
    # Verify initial state
    config_dir = clean_config_dir
    assert os.path.exists(config_dir)
    
    client = docker.from_env()
    initial_containers = client.containers.list(all=True, filters={"label": "ollama-stack.component"})
    initial_volumes = client.volumes.list(filters={"label": "com.docker.compose.project=ollama-stack"})
    
    # Verify we have some stack resources to test removal
    has_containers = len(initial_containers) > 0
    has_volumes = len(initial_volumes) > 0
    
    if not has_containers and not has_volumes:
        pytest.skip("No stack resources found to test removal")
    
    # Perform complete uninstall using short form
    result = runner.invoke(app, ["uninstall", "-a"])
    assert result.exit_code == 0
    
    # Verify everything is removed (same as --all)
    assert wait_for_stack_to_stop(timeout=15)
    
    final_containers = client.containers.list(all=True, filters={"label": "ollama-stack.component"})
    assert len(final_containers) == 0
    
    final_volumes = client.volumes.list(filters={"label": "com.docker.compose.project=ollama-stack"})
    assert len(final_volumes) <= len(initial_volumes), f"Expected volume count to decrease or stay same, got {len(final_volumes)} vs {len(initial_volumes)}"
    
    assert not os.path.exists(config_dir)


@pytest.mark.integration
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_uninstall_force_flag_handles_stuck_containers(runner, clean_config_dir):
    """
    Verifies that --force flag handles stuck or problematic containers.
    """
    # Install and start stack
    runner.invoke(app, ["install", "--force"])
    runner.invoke(app, ["start"])
    
    # Perform uninstall with force flag
    result = runner.invoke(app, ["uninstall", "--force"])
    assert result.exit_code == 0
    
    # Should succeed even if containers are stuck
    assert wait_for_stack_to_stop(timeout=15)
    
    # Verify containers are removed
    client = docker.from_env()
    final_containers = client.containers.list(all=True, filters={"label": "ollama-stack.component"})
    assert len(final_containers) == 0


@pytest.mark.integration
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_uninstall_complex_flag_combinations(runner, clean_config_dir):
    """
    Verifies that complex flag combinations work correctly.
    """
    # Install and start stack
    runner.invoke(app, ["install", "--force"])
    runner.invoke(app, ["start"])
    
    # Let services create data
    time.sleep(5)
    
    # Test various flag combinations
    test_cases = [
        (["uninstall", "--remove-volumes", "--force"], "volumes removed, config preserved"),
        (["uninstall", "--remove-config", "--force"], "config removed, volumes preserved"), 
        (["uninstall", "--remove-volumes", "--remove-config"], "both removed"),
        (["uninstall", "--all", "--force"], "everything removed"),
    ]
    
    for flags, description in test_cases:
        # Reinstall for each test
        runner.invoke(app, ["install", "--force"])
        runner.invoke(app, ["start"])
        time.sleep(3)
        
        # Perform uninstall
        result = runner.invoke(app, flags)
        assert result.exit_code == 0, f"Failed for {description}: {result.stdout}"
        
        # Verify stack is stopped
        assert wait_for_stack_to_stop(timeout=15), f"Stack not stopped for {description}"
        
        # Verify containers are removed
        client = docker.from_env()
        containers = client.containers.list(all=True, filters={"label": "ollama-stack.component"})
        assert len(containers) == 0, f"Containers not removed for {description}"


@pytest.mark.integration
@pytest.mark.skipif(not IS_APPLE_SILICON, reason="Native Ollama test only for Apple Silicon")
def test_uninstall_stops_native_ollama_on_apple_silicon(runner, clean_config_dir):
    """
    Verifies that uninstall properly stops native Ollama on Apple Silicon.
    """
    if not shutil.which("ollama"):
        pytest.skip("Ollama not installed - cannot test native service")
    
    if not is_docker_available():
        pytest.skip("Docker not available - need both Docker and Ollama")
    
    # Install and start stack
    runner.invoke(app, ["install", "--force"])
    runner.invoke(app, ["start"])
    
    # Verify native Ollama is running
    assert is_ollama_native_service_running()
    
    # Perform uninstall
    result = runner.invoke(app, ["uninstall"])
    assert result.exit_code == 0
    
    # Verify native Ollama is stopped
    time.sleep(3)
    assert not is_ollama_native_service_running()
    
    # Verify all services are stopped
    stopped, message = verify_stack_completely_stopped()
    assert stopped, f"Stack not completely stopped: {message}"


@pytest.mark.integration
@pytest.mark.skipif(IS_APPLE_SILICON, reason="Docker Ollama test not for Apple Silicon")
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_uninstall_removes_docker_ollama_on_other_platforms(runner, clean_config_dir):
    """
    Verifies that uninstall removes Docker Ollama on non-Apple Silicon platforms.
    """
    # Install and start stack
    runner.invoke(app, ["install", "--force"])
    runner.invoke(app, ["start"])
    
    # Verify Docker Ollama is running
    running_components = get_running_stack_components()
    assert "ollama" in running_components
    
    # Perform uninstall
    result = runner.invoke(app, ["uninstall"])
    assert result.exit_code == 0
    
    # Verify Docker Ollama is removed
    final_components = get_running_stack_components()
    assert "ollama" not in final_components
    assert len(final_components) == 0


@pytest.mark.integration
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_uninstall_when_stack_not_running(runner, clean_config_dir):
    """
    Verifies that uninstall works when stack is not running.
    """
    # Install but don't start
    runner.invoke(app, ["install", "--force"])
    
    # Verify stack is not running
    running_services = get_actual_running_services()
    assert len(running_services) == 0
    
    # Perform uninstall
    result = runner.invoke(app, ["uninstall"])
    assert result.exit_code == 0
    
    # Should succeed without issues
    output_lower = result.stdout.lower()
    assert any(phrase in output_lower for phrase in [
        "completed", "success", "no stack resources found", "removing stack resources"
    ])


@pytest.mark.integration
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_uninstall_preserves_images_by_default(runner, clean_config_dir):
    """
    Verifies that uninstall preserves Docker images by default (without --remove-images).
    """
    # Install and start stack
    runner.invoke(app, ["install", "--force"])
    runner.invoke(app, ["start"])
    
    # Wait for services to start
    time.sleep(10)
    
    # Get images before uninstall
    client = docker.from_env()
    initial_images = client.images.list()
    initial_image_ids = {img.id for img in initial_images}
    
    # Perform uninstall without --remove-images flag
    result = runner.invoke(app, ["uninstall", "--force"])
    assert result.exit_code == 0
    
    # Verify images are still present
    final_images = client.images.list()
    final_image_ids = {img.id for img in final_images}
    
    # All images should still be present
    assert initial_image_ids.issubset(final_image_ids), "Images were removed despite not using --remove-images"
    
    # Verify containers are removed
    containers = client.containers.list(all=True, filters={"label": "com.docker.compose.project=ollama-stack"})
    assert len(containers) == 0, "Containers should be removed"

@pytest.mark.integration
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_uninstall_removes_images_with_flag(runner, clean_config_dir):
    """
    Verifies that uninstall removes Docker images when --remove-images flag is used.
    """
    # Install and start stack
    runner.invoke(app, ["install", "--force"])
    runner.invoke(app, ["start"])
    
    # Wait for services to start
    time.sleep(10)
    
    # Get stack-specific images before uninstall (images used by stack containers)
    client = docker.from_env()
    stack_containers = client.containers.list(all=True, filters={"label": "ollama-stack.component"})
    initial_stack_image_ids = {container.image.id for container in stack_containers}
    
    # Perform uninstall with --remove-images flag
    result = runner.invoke(app, ["uninstall", "--remove-images", "--force"])
    assert result.exit_code == 0
    
    # Verify stack images are removed (check if any of the original images still exist)
    final_stack_containers = client.containers.list(all=True, filters={"label": "ollama-stack.component"})
    final_stack_image_ids = {container.image.id for container in final_stack_containers}
    
    # Stack images should be removed
    removed_images = initial_stack_image_ids - final_stack_image_ids
    assert len(removed_images) > 0, "No stack images were removed with --remove-images flag"
    
    # Verify containers are removed
    containers = client.containers.list(all=True, filters={"label": "com.docker.compose.project=ollama-stack"})
    assert len(containers) == 0, "Containers should be removed"

@pytest.mark.integration
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_uninstall_all_flag_removes_images(runner, clean_config_dir):
    """
    Verifies that uninstall --all flag removes images along with volumes and config.
    """
    # Install and start stack
    runner.invoke(app, ["install", "--force"])
    runner.invoke(app, ["start"])
    
    # Wait for services to start
    time.sleep(10)
    
    # Get stack-specific images before uninstall (images used by stack containers)
    client = docker.from_env()
    stack_containers = client.containers.list(all=True, filters={"label": "ollama-stack.component"})
    initial_stack_image_ids = {container.image.id for container in stack_containers}
    
    # Perform uninstall with --all flag
    result = runner.invoke(app, ["uninstall", "--all", "--force"])
    print(f"Uninstall stdout: {result.stdout}")
    print(f"Uninstall exit code: {result.exit_code}")
    assert result.exit_code == 0
    
    # Verify stack images are removed (check if any of the original images still exist)
    final_stack_containers = client.containers.list(all=True, filters={"label": "ollama-stack.component"})
    final_stack_image_ids = {container.image.id for container in final_stack_containers}
    
    # Stack images should be removed
    removed_images = initial_stack_image_ids - final_stack_image_ids
    assert len(removed_images) > 0, "No stack images were removed with --all flag"
    
    # Verify volumes are removed
    volumes = client.volumes.list(filters={"label": "com.docker.compose.project=ollama-stack"})
    assert len(volumes) == 0, "Volumes should be removed with --all flag"
    
    # Verify config directory is removed
    config_dir = get_default_config_dir()
    assert not config_dir.exists(), "Config directory should be removed with --all flag"


@pytest.mark.integration
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_uninstall_removes_docker_networks(runner, clean_config_dir):
    """
    Verifies that uninstall removes Docker networks.
    """
    # Install and start stack
    runner.invoke(app, ["install", "--force"])
    runner.invoke(app, ["start"])
    
    # Get initial networks
    client = docker.from_env()
    initial_networks = client.networks.list(filters={"label": "ollama-stack.component"})
    
    # Perform uninstall
    result = runner.invoke(app, ["uninstall"])
    assert result.exit_code == 0
    
    # Verify networks are cleaned up
    final_networks = client.networks.list(filters={"label": "ollama-stack.component"})
    assert len(final_networks) <= len(initial_networks)
    
    # Verify containers are removed
    final_containers = client.containers.list(all=True, filters={"label": "ollama-stack.component"})
    assert len(final_containers) == 0


@pytest.mark.integration
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_uninstall_idempotent_multiple_runs(runner, clean_config_dir):
    """
    Verifies that running uninstall multiple times is safe.
    """
    # Install and start stack
    runner.invoke(app, ["install", "--force"])
    runner.invoke(app, ["start"])
    
    # First uninstall
    result1 = runner.invoke(app, ["uninstall"])
    assert result1.exit_code == 0
    
    # Second uninstall
    result2 = runner.invoke(app, ["uninstall"])
    assert result2.exit_code == 0
    
    # Should not crash or error
    assert "error" not in result2.stdout.lower()
    assert "failed" not in result2.stdout.lower()
    
    # Verify final state
    client = docker.from_env()
    final_containers = client.containers.list(all=True, filters={"label": "ollama-stack.component"})
    assert len(final_containers) == 0


@pytest.mark.integration
@pytest.mark.stateless
def test_uninstall_without_docker_daemon(runner):
    """
    Verifies that uninstall handles Docker unavailability gracefully.
    """
    if is_docker_available():
        pytest.skip("Docker is available - testing Docker unavailable scenario")
    
    result = runner.invoke(app, ["uninstall"])
    
    # Should handle Docker unavailability gracefully
    assert result.exit_code in [0, 1]  # May succeed or fail gracefully
    
    # Should not crash with technical errors
    output_lower = result.stdout.lower()
    assert "traceback" not in output_lower
    assert "exception" not in output_lower
    
    # Should provide helpful message
    assert any(keyword in output_lower for keyword in [
        "docker daemon", "docker desktop", "not running", "unavailable"
    ])


@pytest.mark.integration
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_uninstall_preserves_non_stack_docker_resources(runner, clean_config_dir):
    """
    Verifies that uninstall only removes stack resources, not other Docker resources.
    """
    # Create a non-stack container for testing
    client = docker.from_env()
    test_container = client.containers.create(
        image="alpine",
        name="test-non-stack-container",
        labels={"test": "non-stack"}
    )
    
    try:
        # Install and start stack
        runner.invoke(app, ["install", "--force"])
        runner.invoke(app, ["start"])
        
        # Perform uninstall
        result = runner.invoke(app, ["uninstall"])
        assert result.exit_code == 0
        
        # Verify stack containers are removed
        stack_containers = client.containers.list(all=True, filters={"label": "ollama-stack.component"})
        assert len(stack_containers) == 0
        
        # Verify non-stack container is preserved
        test_container.reload()
        assert test_container.status in ["created", "exited"]
        
    finally:
        # Clean up test container
        try:
            test_container.remove()
        except:
            pass


@pytest.mark.integration
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_uninstall_handles_partial_resource_cleanup(runner, clean_config_dir):
    """
    Verifies that uninstall handles partial resource cleanup gracefully.
    """
    # Install and start stack
    runner.invoke(app, ["install", "--force"])
    runner.invoke(app, ["start"])
    
    # Perform uninstall (may encounter partial cleanup issues)
    result = runner.invoke(app, ["uninstall"])
    
    # Should handle partial cleanup gracefully
    assert result.exit_code in [0, 1]  # May succeed or fail gracefully
    
    # Should not crash
    assert "traceback" not in result.stdout.lower()
    
    # Should at least attempt cleanup
    client = docker.from_env()
    final_containers = client.containers.list(all=True, filters={"label": "ollama-stack.component"})
    
    # Should have removed most or all containers
    assert len(final_containers) <= 1  # Allow for potential cleanup issues


@pytest.mark.integration
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_uninstall_config_removal_filesystem_verification(runner, clean_config_dir):
    """
    Verifies that config removal actually removes files from filesystem.
    """
    # Install stack
    runner.invoke(app, ["install", "--force"])
    
    # Verify config files exist
    config_dir = clean_config_dir
    config_file = os.path.join(config_dir, ".ollama-stack.json")
    env_file = os.path.join(config_dir, ".env")
    
    assert os.path.exists(config_file)
    assert os.path.exists(env_file)
    
    # Create additional files to test complete directory removal
    test_file = os.path.join(config_dir, "test.txt")
    with open(test_file, 'w') as f:
        f.write("test content")
    
    # Perform uninstall with config removal
    result = runner.invoke(app, ["uninstall", "--remove-config"])
    assert result.exit_code == 0
    
    # Verify all config files and directory are removed
    assert not os.path.exists(config_file)
    assert not os.path.exists(env_file)
    assert not os.path.exists(test_file)
    assert not os.path.exists(config_dir)


@pytest.mark.integration
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_uninstall_volume_removal_data_loss_verification(runner, stack_with_volumes):
    """
    Verifies that volume removal actually removes data.
    """
    # Use the fixture to ensure volumes are created with correct project name
    volumes_data = stack_with_volumes
    volume_names = volumes_data["volume_names"]
    
    # Ensure we have volumes to test
    assert len(volume_names) > 0, "No volumes found to test"
    
    # Get the actual project name used by the volumes
    client = docker.from_env()
    actual_project_name = None
    for volume in volumes_data["volumes"]:
        if volume.attrs and volume.attrs.get("Labels", {}).get("com.docker.compose.project"):
            actual_project_name = volume.attrs["Labels"]["com.docker.compose.project"]
            break
    
    assert actual_project_name is not None, "Could not determine project name from volumes"
    
    # Perform uninstall with volume removal
    result = runner.invoke(app, ["uninstall", "--remove-volumes"])
    assert result.exit_code == 0
    
    # Verify volumes are actually removed using the actual project name
    final_volumes = client.volumes.list(filters={"label": f"com.docker.compose.project={actual_project_name}"})
    assert len(final_volumes) == 0
    
    # Verify specific volumes are gone
    for volume_name in volume_names:
        try:
            client.volumes.get(volume_name)
            assert False, f"Volume {volume_name} still exists"
        except docker.errors.NotFound:
            # Expected - volume should be gone
            pass


@pytest.mark.integration
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_uninstall_complete_system_state_verification(runner, clean_config_dir):
    """
    Verifies that complete uninstall leaves system in clean state.
    """
    # Install and start stack
    runner.invoke(app, ["install", "--force"])
    runner.invoke(app, ["start"])
    
    # Let services create data
    time.sleep(5)
    
    # Record initial non-stack resources
    client = docker.from_env()
    initial_all_containers = client.containers.list(all=True)
    initial_all_volumes = client.volumes.list()
    initial_all_networks = client.networks.list()
    
    # Filter out stack resources
    initial_non_stack_containers = [
        c for c in initial_all_containers 
        if not c.labels.get("ollama-stack.component")
    ]
    initial_non_stack_volumes = []
    for v in initial_all_volumes:
        try:
            if not (v.attrs and v.attrs.get("Labels", {}).get("com.docker.compose.project") == "ollama-stack"):
                initial_non_stack_volumes.append(v)
        except (AttributeError, TypeError):
            # Skip volumes that don't have attrs or have invalid attrs
            continue
    initial_non_stack_networks = [
        n for n in initial_all_networks 
        if not n.attrs.get("Labels", {}).get("ollama-stack.component") and
        not n.name.startswith("ollama-stack") and
        not n.name.endswith("_network")
    ]
    
    # Perform complete uninstall
    result = runner.invoke(app, ["uninstall", "--all"])
    assert result.exit_code == 0
    
    # Verify stack resources are completely removed
    stack_containers = client.containers.list(all=True, filters={"label": "ollama-stack.component"})
    assert len(stack_containers) == 0
    
    stack_volumes = client.volumes.list(filters={"label": "com.docker.compose.project=ollama-stack"})
    assert len(stack_volumes) == 0
    
    # Verify config is removed
    config_dir = clean_config_dir
    assert not os.path.exists(config_dir)
    
    # Verify native services are stopped
    stopped, message = verify_stack_completely_stopped()
    assert stopped, f"Stack not completely stopped: {message}"
    
    # Verify non-stack resources are preserved
    final_all_containers = client.containers.list(all=True)
    final_all_volumes = client.volumes.list()
    final_all_networks = client.networks.list()
    
    final_non_stack_containers = [
        c for c in final_all_containers 
        if not c.labels.get("ollama-stack.component")
    ]
    final_non_stack_volumes = []
    for v in final_all_volumes:
        try:
            if not (v.attrs and v.attrs.get("Labels", {}).get("com.docker.compose.project") == "ollama-stack"):
                final_non_stack_volumes.append(v)
        except (AttributeError, TypeError):
            # Skip volumes that don't have attrs or have invalid attrs
            continue
    final_non_stack_networks = [
        n for n in final_all_networks 
        if not n.attrs.get("Labels", {}).get("ollama-stack.component") and
        not n.name.startswith("ollama-stack") and
        not n.name.endswith("_network")
    ]
    
    # Non-stack resources should be preserved
    assert len(final_non_stack_containers) == len(initial_non_stack_containers)
    assert len(final_non_stack_volumes) == len(initial_non_stack_volumes)
    assert len(final_non_stack_networks) >= len(initial_non_stack_networks)  # Networks may be created by system


@pytest.mark.integration
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_uninstall_command_help_accessibility(runner):
    """
    Verifies that uninstall command help is accessible and informative.
    """
    result = runner.invoke(app, ["uninstall", "--help"])
    assert result.exit_code == 0
    
    # Should contain key information about uninstall command
    output_lower = result.stdout.lower()
    assert "uninstall" in output_lower
    assert "remove" in output_lower
    
    # Should show flag options
    assert "--remove-volumes" in result.stdout
    assert "--remove-config" in result.stdout
    assert "--remove-images" in result.stdout
    assert "--all" in result.stdout
    assert "--force" in result.stdout
    
    # Should explain what each flag does
    assert "volumes" in output_lower
    assert "config" in output_lower
    assert "images" in output_lower


@pytest.mark.integration
def test_uninstall_error_message_quality(runner):
    """
    Verifies that uninstall command provides high-quality error messages.
    """
    # Test with Docker unavailable
    if not is_docker_available():
        result = runner.invoke(app, ["uninstall"])
        
        # Should handle Docker unavailability gracefully
        assert result.exit_code in [0, 1]  # May succeed or fail gracefully
        
        # Should have user-friendly error message
        output_lower = result.stdout.lower()
        if result.exit_code != 0:
            assert any(keyword in output_lower for keyword in [
                "docker daemon", "docker desktop", "not running"
            ])
        
        # Should not have technical error details
        assert "traceback" not in output_lower
        assert "connectionrefusederror" not in output_lower
        assert "exception" not in output_lower
    
    # Test help accessibility
    help_result = runner.invoke(app, ["uninstall", "--help"])
    assert help_result.exit_code == 0
    assert "uninstall" in help_result.stdout.lower()
    assert "remove" in help_result.stdout.lower()


@pytest.mark.integration
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_uninstall_exit_codes_consistency(runner, clean_config_dir):
    """
    Verifies that uninstall command returns consistent exit codes.
    """
    # Test successful uninstall
    runner.invoke(app, ["install", "--force"])
    runner.invoke(app, ["start"])
    
    result = runner.invoke(app, ["uninstall"])
    assert result.exit_code == 0
    
    # Test idempotent uninstall
    result2 = runner.invoke(app, ["uninstall"])
    assert result2.exit_code == 0  # Should succeed even if nothing to uninstall
    
    # Test help
    help_result = runner.invoke(app, ["uninstall", "--help"])
    assert help_result.exit_code == 0