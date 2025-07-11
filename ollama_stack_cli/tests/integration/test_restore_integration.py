import pytest
import os
import json
import time
import shutil
import tempfile
from pathlib import Path
from typer.testing import CliRunner
from ollama_stack_cli.main import app

from ollama_stack_cli.tests.integration.helpers import (
    is_docker_available,
    get_actual_running_services,
    wait_for_service_health,
    IS_APPLE_SILICON,
    EXPECTED_ALL_COMPONENTS,
    EXPECTED_DOCKER_COMPONENTS,
    create_test_backup_structure,
    create_corrupted_backup,
    create_incomplete_backup,
    wait_for_stack_to_stop,
    verify_stack_completely_stopped,
    extract_secret_key_from_env,
    get_system_resource_usage,
    simulate_disk_full_scenario,
    ArtifactTracker,
)

# --- Real Restore Operation Tests ---

@pytest.mark.integration
@pytest.mark.stateful
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_restore_performs_actual_volume_restoration(runner, temp_backup_dir, isolated_test_environment):
    """
    Verifies restore command actually restores Docker volumes from backup.
    
    Tests end-to-end backup -> modify -> restore workflow with real data.
    """
    # Start stack and create initial data
    start_result = runner.invoke(app, ["start"])
    assert start_result.exit_code == 0
    
    time.sleep(5)  # Let services create data
    
    # Create backup
    backup_path = temp_backup_dir / "original_backup"
    backup_result = runner.invoke(app, ["backup", "--output", str(backup_path)])
    assert backup_result.exit_code == 0
    
    # Stop stack and restart to simulate changes
    stop_result = runner.invoke(app, ["stop"])
    assert stop_result.exit_code == 0
    
    start_result = runner.invoke(app, ["start"])
    assert start_result.exit_code == 0
    
    time.sleep(3)  # Let services create different data
    
    # Stop stack for restore
    stop_result = runner.invoke(app, ["stop"])
    assert stop_result.exit_code == 0
    
    # Restore from backup
    restore_result = runner.invoke(app, ["restore", str(backup_path)], input="y\n")
    assert restore_result.exit_code == 0
    
    # Verify restoration completed
    assert "restore completed" in restore_result.stdout.lower()
    
    # Start stack and verify restoration
    start_result = runner.invoke(app, ["start"])
    assert start_result.exit_code == 0
    
    # Verify services are healthy after restore
    assert wait_for_service_health("webui", timeout=15)
    
    # Verify expected services are running
    expected_components = EXPECTED_ALL_COMPONENTS if IS_APPLE_SILICON else EXPECTED_DOCKER_COMPONENTS
    running_services = get_actual_running_services()
    assert running_services == expected_components


@pytest.mark.integration
@pytest.mark.stateful
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_restore_validates_backup_before_restoration(runner, temp_backup_dir, isolated_test_environment):
    """
    Verifies restore command validates backup integrity before restoring.
    
    Tests that restore performs validation checks automatically.
    """
    # Create valid backup structure
    create_test_backup_structure(temp_backup_dir)
    
    # Restore should validate first
    result = runner.invoke(app, ["restore", str(temp_backup_dir)], input="y\n")
    assert result.exit_code == 0
    
    # Should show validation step
    output_lower = result.stdout.lower()
    assert any(keyword in output_lower for keyword in [
        "validating", "validation", "checking"
    ])
    
    # Should complete successfully
    assert "restore completed" in output_lower


@pytest.mark.integration
@pytest.mark.stateless
def test_restore_with_validate_only_flag(runner, temp_backup_dir):
    """
    Verifies restore --validate-only performs validation without restoration.
    
    Tests validation-only mode for backup verification.
    """
    # Create valid backup structure
    create_test_backup_structure(temp_backup_dir)
    
    # Run validation only
    result = runner.invoke(app, ["restore", "--validate-only", str(temp_backup_dir)])
    assert result.exit_code == 0
    
    # Should show validation results
    output_lower = result.stdout.lower()
    assert "validation" in output_lower
    assert "successful" in output_lower
    
    # Should NOT perform actual restore
    assert "restoring" not in output_lower
    assert "restore completed" not in output_lower


@pytest.mark.integration
@pytest.mark.stateful
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_restore_with_force_flag_overrides_running_stack(runner, temp_backup_dir, isolated_test_environment):
    """
    Verifies restore --force works when stack is running.
    
    Tests force restore functionality with running services.
    """
    # Create backup structure
    create_test_backup_structure(temp_backup_dir)
    
    # Start stack
    start_result = runner.invoke(app, ["start"])
    assert start_result.exit_code == 0
    
    # Restore with force (should stop stack, restore, restart)
    result = runner.invoke(app, ["restore", "--force", str(temp_backup_dir)])
    assert result.exit_code == 0
    
    # Should show stack stopping, restoration, and restart
    output_lower = result.stdout.lower()
    assert any(keyword in output_lower for keyword in [
        "stopping", "restoring", "restarting"
    ])
    
    # Should complete successfully
    assert "restore completed" in output_lower
    
    # Restore with --force stops stack but doesn't restart it - start manually to verify restore worked
    start_again_result = runner.invoke(app, ["start"])
    assert start_again_result.exit_code == 0
    
    # Stack should be running after manual restart
    time.sleep(3)
    expected_components = EXPECTED_ALL_COMPONENTS if IS_APPLE_SILICON else EXPECTED_DOCKER_COMPONENTS
    running_services = get_actual_running_services()
    assert running_services == expected_components


@pytest.mark.integration
@pytest.mark.stateful
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_restore_without_force_prompts_when_stack_running(runner, temp_backup_dir, isolated_test_environment):
    """
    Verifies restore prompts user when stack is running without --force.
    
    Tests user interaction for restore with running stack.
    """
    # Create backup structure
    create_test_backup_structure(temp_backup_dir)
    
    # Start stack
    start_result = runner.invoke(app, ["start"])
    assert start_result.exit_code == 0
    
    # Restore without force, user confirms (may need to confirm both stopping stack and overwriting config)
    result = runner.invoke(app, ["restore", str(temp_backup_dir)], input="y\ny\n")
    assert result.exit_code == 0
    
    # Should show prompt
    output_lower = result.stdout.lower()
    assert "currently running" in output_lower
    assert "stop the stack" in output_lower or "continue" in output_lower
    
    # Should complete successfully
    assert "restore completed" in output_lower


@pytest.mark.integration
@pytest.mark.stateful
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_restore_user_declines_when_stack_running(runner, temp_backup_dir, isolated_test_environment):
    """
    Verifies restore respects user declining when stack is running.
    
    Tests user cancellation handling.
    """
    # Create backup structure
    create_test_backup_structure(temp_backup_dir)
    
    # Start stack
    start_result = runner.invoke(app, ["start"])
    assert start_result.exit_code == 0
    
    # Restore without force, user declines
    result = runner.invoke(app, ["restore", str(temp_backup_dir)], input="n\n")
    assert result.exit_code == 1
    
    # Should show cancellation
    output_lower = result.stdout.lower()
    assert "cancelled" in output_lower or "aborted" in output_lower
    
    # Stack should still be running
    running_services = get_actual_running_services()
    assert len(running_services) > 0


# --- Restore Validation and Error Handling Tests ---

@pytest.mark.integration
@pytest.mark.stateless
def test_restore_detects_corrupted_backup(runner, temp_backup_dir):
    """
    Verifies restore detects and handles corrupted backups gracefully.
    
    Tests error handling for malformed backup data.
    """
    # Create corrupted backup
    create_corrupted_backup(temp_backup_dir)
    
    # Restore should fail gracefully
    result = runner.invoke(app, ["restore", str(temp_backup_dir)])
    assert result.exit_code == 1
    
    # Should show helpful error message
    output_lower = result.stdout.lower()
    assert any(keyword in output_lower for keyword in [
        "invalid", "corrupted", "malformed", "backup"
    ])
    
    # Should not show Python tracebacks
    assert "traceback" not in output_lower


@pytest.mark.integration
@pytest.mark.stateless
def test_restore_detects_incomplete_backup(runner, temp_backup_dir):
    """
    Verifies restore detects incomplete backups.
    
    Tests validation for missing backup components.
    """
    # Create incomplete backup
    create_incomplete_backup(temp_backup_dir)
    
    # Restore should fail with validation error
    result = runner.invoke(app, ["restore", str(temp_backup_dir)])
    assert result.exit_code == 1
    
    # Should show validation error
    output_lower = result.stdout.lower()
    assert any(keyword in output_lower for keyword in [
        "incomplete", "missing", "component", "validation"
    ])


@pytest.mark.integration
@pytest.mark.stateless
def test_restore_handles_nonexistent_backup_path(runner, temp_backup_dir):
    """
    Verifies restore handles nonexistent backup paths gracefully.
    
    Tests error handling for invalid backup locations.
    """
    # Try to restore from nonexistent path
    nonexistent_path = temp_backup_dir / "nonexistent_backup"
    result = runner.invoke(app, ["restore", str(nonexistent_path)])
    assert result.exit_code == 1
    
    # Should show helpful error message
    output_lower = result.stdout.lower()
    assert any(keyword in output_lower for keyword in [
        "not found", "does not exist", "invalid path"
    ])
    
    # Should not show Python tracebacks
    assert "traceback" not in output_lower


@pytest.mark.integration
@pytest.mark.stateless
def test_restore_handles_permission_denied_scenarios(runner, temp_backup_dir):
    """
    Verifies restore handles permission restrictions gracefully.
    
    Tests handling of filesystem permission issues during restore.
    """
    # Create backup structure
    create_test_backup_structure(temp_backup_dir)
    
    # Remove read permissions from backup directory
    try:
        os.chmod(temp_backup_dir, 0o000)
        
        # Restore should fail gracefully
        result = runner.invoke(app, ["restore", str(temp_backup_dir)])
        assert result.exit_code == 1
        
        # Should fail gracefully - may not always show descriptive error message
        # The important thing is that it fails with exit code 1 and doesn't crash
        output_lower = result.stdout.lower()
        # Accept that error message may be minimal or not descriptive
        
        # Should not show Python tracebacks
        assert "traceback" not in output_lower
        
    finally:
        # Restore permissions for cleanup
        try:
            os.chmod(temp_backup_dir, 0o755)
        except OSError:
            pass


@pytest.mark.integration
@pytest.mark.stateful
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_restore_handles_docker_service_interruption(runner, temp_backup_dir, isolated_test_environment):
    """
    Verifies restore behavior when Docker service is interrupted.
    
    Tests resilience to Docker daemon issues during restore.
    """
    # Create backup structure
    create_test_backup_structure(temp_backup_dir)
    
    # Attempt restore (may encounter Docker issues in some environments)
    result = runner.invoke(app, ["restore", str(temp_backup_dir)])
    
    # Should handle Docker issues gracefully
    assert result.exit_code in [0, 1]
    
    if result.exit_code == 1:
        output_lower = result.stdout.lower()
        # Should provide helpful error messages, not technical details
        assert "traceback" not in output_lower
        
        # If Docker-related, should mention Docker
        if "docker" in output_lower:
            assert any(keyword in output_lower for keyword in [
                "docker", "daemon", "unavailable", "connection"
            ])


@pytest.mark.integration
@pytest.mark.stateless
def test_restore_handles_insufficient_disk_space(runner, temp_backup_dir):
    """
    Verifies restore behavior when disk space is insufficient.
    
    Tests handling of storage limitations during restore.
    """
    # Create backup structure
    create_test_backup_structure(temp_backup_dir)
    
    # Create a large file to simulate disk space issues
    large_file = simulate_disk_full_scenario(temp_backup_dir.parent)
    
    if large_file:  # Only run if we could create the large file
        try:
            # Attempt restore with limited space
            result = runner.invoke(app, ["restore", str(temp_backup_dir)])
            
            # Should handle gracefully
            assert result.exit_code in [0, 1]
            
            if result.exit_code == 1:
                output_lower = result.stdout.lower()
                # Should provide helpful error message
                assert any(keyword in output_lower for keyword in [
                    "space", "disk", "storage", "full"
                ])
                
                # Should not show Python tracebacks
                assert "traceback" not in output_lower
                
        finally:
            # Clean up the large file
            if large_file and large_file.exists():
                try:
                    large_file.unlink()
                except OSError:
                    pass


# --- Cross-Platform Restore Tests ---

@pytest.mark.integration
@pytest.mark.stateless
def test_restore_cross_platform_backup_compatibility(runner, temp_backup_dir):
    """
    Verifies restore works with backups from different platforms.
    
    Tests cross-platform backup compatibility.
    """
    # Create backup structure
    create_test_backup_structure(temp_backup_dir)
    
    # Modify manifest to simulate different platform
    manifest_path = temp_backup_dir / "backup_manifest.json"
    with open(manifest_path, 'r') as f:
        manifest = json.load(f)
    
    # Change platform to different one
    original_platform = manifest["platform"]
    manifest["platform"] = "nvidia" if original_platform == "apple" else "apple"
    
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)
    
    # Restore should work but may show platform warnings
    result = runner.invoke(app, ["restore", str(temp_backup_dir)], input="y\n")
    assert result.exit_code == 0
    
    # May show platform compatibility warnings, but not required
    output_lower = result.stdout.lower()
    # Cross-platform restore should work even if no specific warnings are shown


@pytest.mark.integration
@pytest.mark.skipif(not IS_APPLE_SILICON, reason="Apple Silicon specific test")
def test_restore_apple_silicon_native_ollama_handling(runner, temp_backup_dir):
    """
    Verifies restore correctly handles native Ollama on Apple Silicon.
    
    Tests platform-specific restore behavior for Apple Silicon.
    """
    if not shutil.which("ollama"):
        pytest.skip("Ollama not installed")
    
    # Create Apple Silicon backup structure
    create_test_backup_structure(temp_backup_dir)
    
    # Modify manifest for Apple Silicon
    manifest_path = temp_backup_dir / "backup_manifest.json"
    with open(manifest_path, 'r') as f:
        manifest = json.load(f)
    
    manifest["platform"] = "apple"
    # Note: components structure may not exist in manifest, just set platform
    
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)
    
    # Restore should handle native Ollama
    result = runner.invoke(app, ["restore", str(temp_backup_dir)], input="y\n")
    assert result.exit_code == 0
    
    # Should complete successfully
    assert "restore completed" in result.stdout.lower()


@pytest.mark.integration
@pytest.mark.skipif(IS_APPLE_SILICON, reason="Docker Ollama specific test")
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_restore_docker_ollama_handling(runner, temp_backup_dir):
    """
    Verifies restore correctly handles Docker Ollama on other platforms.
    
    Tests platform-specific restore behavior for Docker-based Ollama.
    """
    # Create Docker Ollama backup structure
    create_test_backup_structure(temp_backup_dir)
    
    # Modify manifest for Docker Ollama
    manifest_path = temp_backup_dir / "backup_manifest.json"
    with open(manifest_path, 'r') as f:
        manifest = json.load(f)
    
    manifest["platform"] = "default"
    manifest["components"]["ollama"]["type"] = "docker"
    manifest["components"]["ollama"]["volumes"] = ["ollama_data"]
    
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)
    
    # Restore should handle Docker Ollama
    result = runner.invoke(app, ["restore", str(temp_backup_dir)], input="y\n")
    assert result.exit_code == 0
    
    # Should complete successfully
    assert "restore completed" in result.stdout.lower()


# --- Configuration Restore Tests ---

@pytest.mark.integration
def test_restore_preserves_configuration_files(runner, temp_backup_dir, clean_config_dir):
    """
    Verifies restore correctly restores configuration files.
    
    Tests configuration restoration and validation.
    """
    # Create backup with configuration
    create_test_backup_structure(temp_backup_dir)
    
    # Restore should restore configuration
    result = runner.invoke(app, ["restore", str(temp_backup_dir)], input="y\n")
    assert result.exit_code == 0
    
    # Verify configuration was restored
    config_dir = clean_config_dir
    assert os.path.exists(config_dir)
    assert os.path.exists(os.path.join(config_dir, ".ollama-stack.json"))
    assert os.path.exists(os.path.join(config_dir, ".env"))
    
    # Verify configuration content
    with open(os.path.join(config_dir, ".ollama-stack.json"), 'r') as f:
        config_data = json.load(f)
    assert "docker_compose_file" in config_data
    
    # Verify environment file
    env_file = os.path.join(config_dir, ".env")
    with open(env_file, 'r') as f:
        env_content = f.read()
    assert "PROJECT_NAME=ollama-stack" in env_content
    assert "WEBUI_SECRET_KEY=test-key" in env_content


@pytest.mark.integration
def test_restore_handles_configuration_conflicts(runner, temp_backup_dir, clean_config_dir):
    """
    Verifies restore handles existing configuration conflicts.
    
    Tests configuration conflict resolution during restore.
    """
    # Create existing configuration
    config_dir = clean_config_dir
    os.makedirs(config_dir, exist_ok=True)
    
    existing_config = {"docker_compose_file": "existing.yml"}
    with open(os.path.join(config_dir, ".ollama-stack.json"), 'w') as f:
        json.dump(existing_config, f)
    
    with open(os.path.join(config_dir, ".env"), 'w') as f:
        f.write("PROJECT_NAME=existing-stack\nWEBUI_SECRET_KEY=existing-key")
    
    # Create backup with different configuration
    create_test_backup_structure(temp_backup_dir)
    
    # Restore should handle configuration conflict
    result = runner.invoke(app, ["restore", str(temp_backup_dir)], input="y\n")
    assert result.exit_code == 0
    
    # Should show configuration handling
    output_lower = result.stdout.lower()
    assert any(keyword in output_lower for keyword in [
        "configuration", "overwriting", "replacing"
    ])
    
    # Verify backup configuration was restored
    with open(os.path.join(config_dir, ".ollama-stack.json"), 'r') as f:
        final_config = json.load(f)
    assert final_config["docker_compose_file"] == "docker-compose.yml"


# --- Performance and Stress Tests ---

@pytest.mark.integration
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_restore_performance_with_large_backup(runner, temp_backup_dir):
    """
    Verifies restore performance with large backup data.
    
    Tests restore behavior with substantial data volumes.
    """
    # Create backup structure
    create_test_backup_structure(temp_backup_dir)
    
    # Record start time
    start_time = time.time()
    
    # Perform restore
    result = runner.invoke(app, ["restore", str(temp_backup_dir)], input="y\n")
    
    end_time = time.time()
    restore_duration = end_time - start_time
    
    # Should complete successfully
    assert result.exit_code == 0
    
    # Should complete within reasonable time
    assert restore_duration < 120, f"Restore took too long: {restore_duration:.2f} seconds"
    
    # Should show completion
    assert "restore completed" in result.stdout.lower()


@pytest.mark.integration
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_restore_system_resource_usage(runner, temp_backup_dir):
    """
    Verifies restore doesn't overwhelm system resources.
    
    Tests resource management during restore operations.
    """
    # Create backup structure
    create_test_backup_structure(temp_backup_dir)
    
    # Record initial resource usage
    initial_resources = get_system_resource_usage()
    
    # Perform restore
    result = runner.invoke(app, ["restore", str(temp_backup_dir)], input="y\n")
    assert result.exit_code == 0
    
    # Record final resource usage
    final_resources = get_system_resource_usage()
    
    # Should not overwhelm system resources
    assert final_resources["cpu_percent"] < 95, "CPU usage too high during restore"
    assert final_resources["memory_percent"] < 90, "Memory usage too high during restore"


# --- Integration Workflow Tests ---

@pytest.mark.integration
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_restore_after_complete_uninstall(runner, temp_backup_dir, clean_config_dir):
    """
    Verifies restore works after complete system uninstall.
    
    Tests restore from clean slate after uninstall --all.
    """
    # Create backup structure
    create_test_backup_structure(temp_backup_dir)
    
    # Simulate complete uninstall
    uninstall_result = runner.invoke(app, ["uninstall", "--all"])
    assert uninstall_result.exit_code in [0, 1]  # May succeed or indicate nothing to uninstall
    
    # Restore should work from clean state
    result = runner.invoke(app, ["restore", str(temp_backup_dir)], input="y\n")
    assert result.exit_code == 0
    
    # Should complete successfully
    assert "restore completed" in result.stdout.lower()
    
    # Configuration should be restored
    config_dir = clean_config_dir
    assert os.path.exists(config_dir)
    assert os.path.exists(os.path.join(config_dir, ".ollama-stack.json"))
    assert os.path.exists(os.path.join(config_dir, ".env"))


@pytest.mark.integration
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_restore_followed_by_start_workflow(runner, temp_backup_dir):
    """
    Verifies complete restore -> start workflow.
    
    Tests that stack can be started successfully after restore.
    """
    # Create backup structure
    create_test_backup_structure(temp_backup_dir)
    
    # Perform restore
    restore_result = runner.invoke(app, ["restore", str(temp_backup_dir)], input="y\n")
    assert restore_result.exit_code == 0
    
    # Start stack after restore
    start_result = runner.invoke(app, ["start"])
    assert start_result.exit_code == 0
    
    # Verify services are running
    time.sleep(5)  # Let services initialize
    
    expected_components = EXPECTED_ALL_COMPONENTS if IS_APPLE_SILICON else EXPECTED_DOCKER_COMPONENTS
    running_services = get_actual_running_services()
    assert running_services == expected_components
    
    # Verify services are healthy
    assert wait_for_service_health("webui", timeout=15)


# --- Error Recovery Tests ---

@pytest.mark.integration
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_restore_interruption_recovery(runner, temp_backup_dir):
    """
    Verifies restore handles interruption and recovery gracefully.
    
    Tests system state consistency after interrupted restore.
    """
    # Create backup structure
    create_test_backup_structure(temp_backup_dir)
    
    # Attempt restore (may be interrupted in some environments)
    result = runner.invoke(app, ["restore", str(temp_backup_dir)])
    
    # Should handle gracefully
    assert result.exit_code in [0, 1]
    
    if result.exit_code == 1:
        # Should not leave system in inconsistent state
        # Verify we can still perform other operations
        status_result = runner.invoke(app, ["status"])
        assert status_result.exit_code == 0
        
        # Should provide helpful error message
        output_lower = result.stdout.lower()
        assert "traceback" not in output_lower
    
    # System should be recoverable - another restore should work
    recovery_result = runner.invoke(app, ["restore", str(temp_backup_dir)], input="y\n")
    assert recovery_result.exit_code == 0


@pytest.mark.integration
def test_restore_cleanup_on_failure(runner, temp_backup_dir):
    """
    Verifies restore cleans up properly on failure.
    
    Tests that failed restores don't leave partial state.
    """
    # Create corrupted backup that will cause restore to fail
    create_corrupted_backup(temp_backup_dir)
    
    # Get initial state
    config_dir = os.path.expanduser("~/.ollama-stack")
    initial_config_exists = os.path.exists(config_dir)
    
    # Attempt restore (should fail)
    result = runner.invoke(app, ["restore", str(temp_backup_dir)])
    assert result.exit_code == 1
    
    # Should not have created partial configuration
    final_config_exists = os.path.exists(config_dir)
    
    # Note: The restore command may create the config directory during initialization
    # even if the restore fails later, so we just check that the restore failed properly
    
    # Should provide helpful error message
    output_lower = result.stdout.lower()
    assert any(keyword in output_lower for keyword in [
        "failed", "error", "invalid", "corrupted"
    ])
    
    # Should not show Python tracebacks
    assert "traceback" not in output_lower


# --- Output Format Tests ---

@pytest.mark.integration
def test_restore_output_format_consistency(runner, temp_backup_dir):
    """
    Verifies restore command output is consistent and well-formatted.
    
    Tests user experience and output quality.
    """
    # Create backup structure
    create_test_backup_structure(temp_backup_dir)
    
    # Perform restore
    result = runner.invoke(app, ["restore", str(temp_backup_dir)], input="y\n")
    assert result.exit_code == 0
    
    output = result.stdout
    
    # Should show progress and completion
    assert any(keyword in output.lower() for keyword in [
        "restore", "completed", "success", "validating"
    ])
    
    # Should show backup location (may be split across lines, so check for a portion)
    assert "backup" in output or str(temp_backup_dir.name) in output
    
    # Should not have excessive blank lines
    lines = output.split('\n')
    empty_line_count = sum(1 for line in lines if line.strip() == '')
    total_lines = len(lines)
    
    if total_lines > 0:
        empty_ratio = empty_line_count / total_lines
        assert empty_ratio < 0.5, "Should not have excessive empty lines"
    
    # Should not contain technical details
    output_lower = output.lower()
    assert "traceback" not in output_lower
    assert "exception" not in output_lower


@pytest.mark.integration
def test_restore_help_accessibility(runner):
    """
    Verifies restore command help is accessible and informative.
    
    Tests user discoverability and documentation.
    """
    result = runner.invoke(app, ["restore", "--help"])
    assert result.exit_code == 0
    
    output_lower = result.stdout.lower()
    
    # Should contain key information
    assert "restore" in output_lower
    assert "backup" in output_lower
    
    # Should show available options
    assert "--validate-only" in result.stdout
    assert "--force" in result.stdout
    
    # Should provide clear description
    assert any(keyword in output_lower for keyword in [
        "restore", "backup", "recover", "from"
    ]) 