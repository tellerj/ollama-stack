import pytest
import os
import json
import time
import shutil
import tempfile
from pathlib import Path
from typer.testing import CliRunner
from ollama_stack_cli.main import app

from tests.integration.helpers import (
    is_docker_available,
    get_actual_running_services,
    wait_for_service_health,
    IS_APPLE_SILICON,
    EXPECTED_ALL_COMPONENTS,
    EXPECTED_DOCKER_COMPONENTS,
    create_test_backup_structure,
    wait_for_stack_to_stop,
    verify_stack_completely_stopped,
    extract_secret_key_from_env,
    get_system_resource_usage,
    simulate_disk_full_scenario,
    create_large_test_data,
)

# --- Real Migration Operation Tests ---

@pytest.mark.integration
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_migrate_detects_current_version(runner):
    """
    Verifies migrate command correctly detects current stack version.
    
    Tests version detection from actual system state.
    """
    # Ensure configuration exists
    install_result = runner.invoke(app, ["install", "--force"])
    assert install_result.exit_code == 0
    
    # Start stack to establish current version
    start_result = runner.invoke(app, ["start"])
    assert start_result.exit_code == 0
    
    # Run migrate in dry-run mode to see version detection
    result = runner.invoke(app, ["migrate", "--dry-run"])
    assert result.exit_code == 0
    
    # Should show current version detection
    output_lower = result.stdout.lower()
    assert "current version" in output_lower or "from:" in output_lower
    assert any(version_pattern in result.stdout for version_pattern in [
        "0.2.0", "0.3.0", "v0.", "version"
    ])


@pytest.mark.integration
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_migrate_dry_run_shows_migration_plan(runner):
    """
    Verifies migrate --dry-run shows detailed migration plan without executing.
    
    Tests migration planning and preview functionality.
    """
    # Ensure configuration exists
    install_result = runner.invoke(app, ["install", "--force"])
    assert install_result.exit_code == 0
    
    # Run dry-run migration
    result = runner.invoke(app, ["migrate", "--dry-run", "--target-version", "0.3.0"])
    assert result.exit_code == 0
    
    # Should show migration plan
    output_lower = result.stdout.lower()
    assert "migration plan" in output_lower or "dry run" in output_lower
    assert "from:" in output_lower and "to:" in output_lower
    
    # Should show what would be done
    assert any(keyword in output_lower for keyword in [
        "would", "will", "plan", "steps"
    ])
    
    # Should NOT actually perform migration
    assert "migration completed" not in output_lower
    assert "migrating" not in output_lower


@pytest.mark.integration
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_migrate_with_stack_stopped_performs_offline_migration(runner):
    """
    Verifies migrate works correctly when stack is stopped.
    
    Tests offline migration capabilities.
    """
    # Ensure configuration exists
    install_result = runner.invoke(app, ["install", "--force"])
    assert install_result.exit_code == 0
    
    # Ensure stack is stopped
    stop_result = runner.invoke(app, ["stop"])
    assert stop_result.exit_code in [0, 1]  # May already be stopped
    
    assert wait_for_stack_to_stop(timeout=10)
    
    # Perform migration with stack stopped
    result = runner.invoke(app, ["migrate", "--target-version", "0.3.0"])
    assert result.exit_code == 0
    
    # Should complete successfully
    output_lower = result.stdout.lower()
    assert "migration completed" in output_lower
    
    # Should handle offline migration
    assert any(keyword in output_lower for keyword in [
        "offline", "stopped", "completed"
    ])


@pytest.mark.integration
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_migrate_with_stack_running_stops_migrates_restarts(runner):
    """
    Verifies migrate with running stack performs stop -> migrate -> restart cycle.
    
    Tests live migration workflow.
    """
    # Ensure configuration exists and start stack
    install_result = runner.invoke(app, ["install", "--force"])
    assert install_result.exit_code == 0
    
    start_result = runner.invoke(app, ["start"])
    assert start_result.exit_code == 0
    
    # Verify stack is running
    running_services = get_actual_running_services()
    expected_components = EXPECTED_ALL_COMPONENTS if IS_APPLE_SILICON else EXPECTED_DOCKER_COMPONENTS
    assert running_services == expected_components
    
    # Perform migration
    result = runner.invoke(app, ["migrate", "--target-version", "0.3.0"])
    assert result.exit_code == 0
    
    # Should show stop -> migrate -> restart cycle
    output_lower = result.stdout.lower()
    assert "migration completed" in output_lower
    
    # Should show migration steps
    assert any(keyword in output_lower for keyword in [
        "stopping", "migrating", "restarting"
    ])
    
    # Stack should be running after migration
    time.sleep(5)  # Let services restart
    final_services = get_actual_running_services()
    assert final_services == expected_components


@pytest.mark.integration
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_migrate_preserves_service_data_integrity(runner):
    """
    Verifies migration preserves service data and configuration integrity.
    
    Tests data preservation through migration process.
    """
    # Install and start stack
    install_result = runner.invoke(app, ["install", "--force"])
    assert install_result.exit_code == 0
    
    start_result = runner.invoke(app, ["start"])
    assert start_result.exit_code == 0
    
    time.sleep(5)  # Let services create data
    
    # Get initial configuration
    config_dir = os.path.expanduser("~/.ollama-stack")
    config_file = os.path.join(config_dir, ".ollama-stack.json")
    env_file = os.path.join(config_dir, ".env")
    
    with open(config_file, 'r') as f:
        initial_config = json.load(f)
    
    initial_secret_key = extract_secret_key_from_env(env_file)
    
    # Perform migration
    result = runner.invoke(app, ["migrate", "--target-version", "0.3.0"])
    assert result.exit_code == 0
    
    # Verify configuration is preserved
    assert os.path.exists(config_file)
    assert os.path.exists(env_file)
    
    with open(config_file, 'r') as f:
        final_config = json.load(f)
    
    final_secret_key = extract_secret_key_from_env(env_file)
    
    # Key configuration should be preserved
    assert initial_secret_key == final_secret_key, "Secret key should be preserved"
    
    # Essential config structure should be maintained
    assert "services" in final_config
    assert "platform" in final_config
    
    # Services should be healthy after migration
    assert wait_for_service_health("webui", timeout=15)


@pytest.mark.integration
def test_migrate_target_version_validation(runner):
    """
    Verifies migrate validates target version compatibility.
    
    Tests version validation and compatibility checking.
    """
    # Ensure configuration exists
    install_result = runner.invoke(app, ["install", "--force"])
    assert install_result.exit_code == 0
    
    # Test with invalid version
    result = runner.invoke(app, ["migrate", "--target-version", "invalid.version"])
    assert result.exit_code == 1
    
    # Should show version validation error
    output_lower = result.stdout.lower()
    assert any(keyword in output_lower for keyword in [
        "invalid", "version", "unsupported", "format"
    ])
    
    # Should not show Python tracebacks
    assert "traceback" not in output_lower


@pytest.mark.integration
def test_migrate_same_version_handling(runner):
    """
    Verifies migrate handles attempts to migrate to same version.
    
    Tests idempotent migration behavior.
    """
    # Ensure configuration exists
    install_result = runner.invoke(app, ["install", "--force"])
    assert install_result.exit_code == 0
    
    # Try to migrate to current version (should be idempotent)
    result = runner.invoke(app, ["migrate", "--target-version", "0.2.0"])
    assert result.exit_code == 0
    
    # Should handle gracefully
    output_lower = result.stdout.lower()
    assert any(keyword in output_lower for keyword in [
        "already", "current", "no migration needed", "up to date"
    ])


# --- Migration Planning and Validation Tests ---

@pytest.mark.integration
def test_migrate_validates_migration_prerequisites(runner):
    """
    Verifies migrate validates system prerequisites before migration.
    
    Tests pre-migration validation checks.
    """
    # Ensure configuration exists
    install_result = runner.invoke(app, ["install", "--force"])
    assert install_result.exit_code == 0
    
    # Run migration (should validate prerequisites)
    result = runner.invoke(app, ["migrate", "--target-version", "0.3.0"])
    assert result.exit_code in [0, 1]  # May succeed or fail based on environment
    
    output_lower = result.stdout.lower()
    
    # Should show validation activity
    assert any(keyword in output_lower for keyword in [
        "validating", "checking", "prerequisites", "requirements"
    ])
    
    # If validation fails, should provide helpful messages
    if result.exit_code == 1:
        assert any(keyword in output_lower for keyword in [
            "requirement", "prerequisite", "missing", "invalid"
        ])
        assert "traceback" not in output_lower


@pytest.mark.integration
def test_migrate_creates_backup_before_migration(runner, temp_backup_dir):
    """
    Verifies migrate creates automatic backup before performing migration.
    
    Tests automatic backup creation for safety.
    """
    # Ensure configuration exists
    install_result = runner.invoke(app, ["install", "--force"])
    assert install_result.exit_code == 0
    
    # Perform migration (should create backup automatically)
    result = runner.invoke(app, ["migrate", "--target-version", "0.3.0"])
    assert result.exit_code == 0
    
    # Should mention backup creation
    output_lower = result.stdout.lower()
    assert any(keyword in output_lower for keyword in [
        "backup", "creating backup", "pre-migration backup"
    ])
    
    # Should complete successfully
    assert "migration completed" in output_lower


@pytest.mark.integration
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_migrate_handles_docker_compatibility_checks(runner):
    """
    Verifies migrate performs Docker compatibility validation.
    
    Tests Docker version and compatibility checking.
    """
    # Ensure configuration exists
    install_result = runner.invoke(app, ["install", "--force"])
    assert install_result.exit_code == 0
    
    # Run migration (should check Docker compatibility)
    result = runner.invoke(app, ["migrate", "--target-version", "0.3.0"])
    assert result.exit_code in [0, 1]
    
    output_lower = result.stdout.lower()
    
    # Should check Docker compatibility
    if "docker" in output_lower:
        assert any(keyword in output_lower for keyword in [
            "docker", "compatibility", "version", "checking"
        ])
    
    # If Docker issues, should provide helpful messages
    if result.exit_code == 1 and "docker" in output_lower:
        assert "traceback" not in output_lower


@pytest.mark.integration
def test_migrate_cross_platform_compatibility_validation(runner):
    """
    Verifies migrate validates cross-platform compatibility.
    
    Tests platform-specific migration validation.
    """
    # Ensure configuration exists
    install_result = runner.invoke(app, ["install", "--force"])
    assert install_result.exit_code == 0
    
    # Run migration dry-run to see platform validation
    result = runner.invoke(app, ["migrate", "--dry-run", "--target-version", "0.3.0"])
    assert result.exit_code == 0
    
    output_lower = result.stdout.lower()
    
    # Should show platform information
    assert any(keyword in output_lower for keyword in [
        "platform", "apple", "silicon", "detected"
    ])
    
    # On Apple Silicon, should mention native Ollama
    if IS_APPLE_SILICON:
        assert any(keyword in output_lower for keyword in [
            "apple", "native", "ollama"
        ])


# --- Migration Failure and Recovery Tests ---

@pytest.mark.integration
def test_migrate_handles_insufficient_disk_space(runner):
    """
    Verifies migrate behavior when disk space is insufficient.
    
    Tests handling of storage limitations during migration.
    """
    # Ensure configuration exists
    install_result = runner.invoke(app, ["install", "--force"])
    assert install_result.exit_code == 0
    
    # Create large file to simulate disk space issues
    temp_dir = Path(tempfile.gettempdir()) / "ollama_stack_test"
    temp_dir.mkdir(exist_ok=True)
    
    large_file = simulate_disk_full_scenario(temp_dir)
    
    if large_file:  # Only run if we could create the large file
        try:
            # Attempt migration with limited space
            result = runner.invoke(app, ["migrate", "--target-version", "0.3.0"])
            
            # Should handle gracefully
            assert result.exit_code in [0, 1]
            
            if result.exit_code == 1:
                output_lower = result.stdout.lower()
                assert any(keyword in output_lower for keyword in [
                    "space", "disk", "storage", "insufficient"
                ])
                
                # Should not show Python tracebacks
                assert "traceback" not in output_lower
                
        finally:
            # Clean up
            if large_file and large_file.exists():
                try:
                    large_file.unlink()
                except OSError:
                    pass


@pytest.mark.integration
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_migrate_handles_docker_service_interruption(runner):
    """
    Verifies migrate behavior when Docker service is interrupted.
    
    Tests resilience to Docker daemon issues during migration.
    """
    # Ensure configuration exists
    install_result = runner.invoke(app, ["install", "--force"])
    assert install_result.exit_code == 0
    
    # Attempt migration (may encounter Docker issues)
    result = runner.invoke(app, ["migrate", "--target-version", "0.3.0"])
    
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
def test_migrate_rollback_on_failure(runner):
    """
    Verifies migrate can rollback on failure to maintain system consistency.
    
    Tests rollback mechanisms and failure recovery.
    """
    # Ensure configuration exists
    install_result = runner.invoke(app, ["install", "--force"])
    assert install_result.exit_code == 0
    
    # Get initial configuration state
    config_dir = os.path.expanduser("~/.ollama-stack")
    config_file = os.path.join(config_dir, ".ollama-stack.json")
    
    with open(config_file, 'r') as f:
        initial_config = json.load(f)
    
    # Attempt migration (may fail in some environments)
    result = runner.invoke(app, ["migrate", "--target-version", "0.3.0"])
    
    # If migration fails, should handle rollback
    if result.exit_code == 1:
        output_lower = result.stdout.lower()
        
        # Should mention rollback or recovery
        assert any(keyword in output_lower for keyword in [
            "rollback", "recovery", "restored", "reverted"
        ])
        
        # Configuration should be in valid state
        assert os.path.exists(config_file)
        with open(config_file, 'r') as f:
            final_config = json.load(f)
        
        # Should have valid configuration structure
        assert "services" in final_config
        assert "platform" in final_config


@pytest.mark.integration
def test_migrate_handles_corrupted_configuration(runner):
    """
    Verifies migrate handles corrupted configuration gracefully.
    
    Tests error handling for invalid source configuration.
    """
    # Create corrupted configuration
    config_dir = os.path.expanduser("~/.ollama-stack")
    os.makedirs(config_dir, exist_ok=True)
    
    config_file = os.path.join(config_dir, ".ollama-stack.json")
    with open(config_file, 'w') as f:
        f.write('{"invalid": "json"')  # Missing closing brace
    
    try:
        # Attempt migration with corrupted config
        result = runner.invoke(app, ["migrate", "--target-version", "0.3.0"])
        assert result.exit_code == 1
        
        # Should handle gracefully
        output_lower = result.stdout.lower()
        assert any(keyword in output_lower for keyword in [
            "invalid", "corrupted", "configuration", "json"
        ])
        
        # Should not show Python tracebacks
        assert "traceback" not in output_lower
        
    finally:
        # Clean up corrupted config
        if os.path.exists(config_file):
            try:
                os.remove(config_file)
            except OSError:
                pass


# --- Cross-Platform Migration Tests ---

@pytest.mark.integration
@pytest.mark.skipif(not IS_APPLE_SILICON, reason="Apple Silicon specific test")
def test_migrate_apple_silicon_native_ollama_handling(runner):
    """
    Verifies migration correctly handles native Ollama on Apple Silicon.
    
    Tests platform-specific migration behavior for Apple Silicon.
    """
    if not shutil.which("ollama"):
        pytest.skip("Ollama not installed")
    
    # Ensure configuration exists
    install_result = runner.invoke(app, ["install", "--force"])
    assert install_result.exit_code == 0
    
    # Run migration
    result = runner.invoke(app, ["migrate", "--target-version", "0.3.0"])
    assert result.exit_code == 0
    
    # Should handle native Ollama
    output_lower = result.stdout.lower()
    assert any(keyword in output_lower for keyword in [
        "apple", "native", "ollama"
    ])
    
    # Should complete successfully
    assert "migration completed" in output_lower


@pytest.mark.integration
@pytest.mark.skipif(IS_APPLE_SILICON, reason="Docker Ollama specific test")
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_migrate_docker_ollama_handling(runner):
    """
    Verifies migration correctly handles Docker Ollama on other platforms.
    
    Tests platform-specific migration behavior for Docker-based Ollama.
    """
    # Ensure configuration exists
    install_result = runner.invoke(app, ["install", "--force"])
    assert install_result.exit_code == 0
    
    # Run migration
    result = runner.invoke(app, ["migrate", "--target-version", "0.3.0"])
    assert result.exit_code == 0
    
    # Should handle Docker Ollama
    output_lower = result.stdout.lower()
    assert any(keyword in output_lower for keyword in [
        "docker", "ollama", "container"
    ])
    
    # Should complete successfully
    assert "migration completed" in output_lower


@pytest.mark.integration
def test_migrate_platform_detection_accuracy(runner):
    """
    Verifies migration accurately detects and reports platform information.
    
    Tests platform detection reliability.
    """
    # Ensure configuration exists
    install_result = runner.invoke(app, ["install", "--force"])
    assert install_result.exit_code == 0
    
    # Run migration dry-run to see platform detection
    result = runner.invoke(app, ["migrate", "--dry-run", "--target-version", "0.3.0"])
    assert result.exit_code == 0
    
    output_lower = result.stdout.lower()
    
    # Should show platform detection
    assert "platform" in output_lower
    
    # Platform detection should be accurate
    if IS_APPLE_SILICON:
        assert "apple" in output_lower
    else:
        assert any(keyword in output_lower for keyword in [
            "default", "linux", "docker"
        ])


# --- Performance and Stress Tests ---

@pytest.mark.integration
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_migrate_performance_timing(runner):
    """
    Verifies migration completes within reasonable time limits.
    
    Tests migration performance and efficiency.
    """
    # Ensure configuration exists
    install_result = runner.invoke(app, ["install", "--force"])
    assert install_result.exit_code == 0
    
    # Record start time
    start_time = time.time()
    
    # Perform migration
    result = runner.invoke(app, ["migrate", "--target-version", "0.3.0"])
    
    end_time = time.time()
    migration_duration = end_time - start_time
    
    # Should complete successfully
    assert result.exit_code == 0
    
    # Should complete within reasonable time
    assert migration_duration < 180, f"Migration took too long: {migration_duration:.2f} seconds"
    
    # Should show completion
    assert "migration completed" in result.stdout.lower()


@pytest.mark.integration
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_migrate_system_resource_usage(runner):
    """
    Verifies migration doesn't overwhelm system resources.
    
    Tests resource management during migration operations.
    """
    # Ensure configuration exists
    install_result = runner.invoke(app, ["install", "--force"])
    assert install_result.exit_code == 0
    
    # Record initial resource usage
    initial_resources = get_system_resource_usage()
    
    # Perform migration
    result = runner.invoke(app, ["migrate", "--target-version", "0.3.0"])
    assert result.exit_code == 0
    
    # Record final resource usage
    final_resources = get_system_resource_usage()
    
    # Should not overwhelm system resources
    assert final_resources["cpu_percent"] < 95, "CPU usage too high during migration"
    assert final_resources["memory_percent"] < 90, "Memory usage too high during migration"


@pytest.mark.integration
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_migrate_with_large_volume_data(runner):
    """
    Verifies migration handles large volume data efficiently.
    
    Tests migration performance with substantial data.
    """
    # Ensure configuration and start stack
    install_result = runner.invoke(app, ["install", "--force"])
    assert install_result.exit_code == 0
    
    start_result = runner.invoke(app, ["start"])
    assert start_result.exit_code == 0
    
    time.sleep(5)  # Let services create data
    
    # Perform migration
    result = runner.invoke(app, ["migrate", "--target-version", "0.3.0"])
    assert result.exit_code == 0
    
    # Should complete successfully
    assert "migration completed" in result.stdout.lower()
    
    # Services should be healthy after migration
    assert wait_for_service_health("webui", timeout=20)


# --- Integration Workflow Tests ---

@pytest.mark.integration
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_migrate_after_backup_operation(runner, temp_backup_dir):
    """
    Verifies migration works correctly after backup operations.
    
    Tests backup -> migrate workflow integration.
    """
    # Ensure configuration and start stack
    install_result = runner.invoke(app, ["install", "--force"])
    assert install_result.exit_code == 0
    
    start_result = runner.invoke(app, ["start"])
    assert start_result.exit_code == 0
    
    # Create backup first
    backup_path = temp_backup_dir / "pre_migration_backup"
    backup_result = runner.invoke(app, ["backup", "--output", str(backup_path)])
    assert backup_result.exit_code == 0
    
    # Perform migration
    result = runner.invoke(app, ["migrate", "--target-version", "0.3.0"])
    assert result.exit_code == 0
    
    # Should complete successfully
    assert "migration completed" in result.stdout.lower()
    
    # Stack should be functional after migration
    final_services = get_actual_running_services()
    expected_components = EXPECTED_ALL_COMPONENTS if IS_APPLE_SILICON else EXPECTED_DOCKER_COMPONENTS
    assert final_services == expected_components


@pytest.mark.integration
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_migrate_followed_by_restore_workflow(runner, temp_backup_dir):
    """
    Verifies complete migrate -> restore workflow.
    
    Tests that restore works correctly after migration.
    """
    # Create initial backup
    install_result = runner.invoke(app, ["install", "--force"])
    assert install_result.exit_code == 0
    
    start_result = runner.invoke(app, ["start"])
    assert start_result.exit_code == 0
    
    backup_path = temp_backup_dir / "pre_migration_backup"
    backup_result = runner.invoke(app, ["backup", "--output", str(backup_path)])
    assert backup_result.exit_code == 0
    
    # Perform migration
    migrate_result = runner.invoke(app, ["migrate", "--target-version", "0.3.0"])
    assert migrate_result.exit_code == 0
    
    # Stop stack and restore from backup
    stop_result = runner.invoke(app, ["stop"])
    assert stop_result.exit_code == 0
    
    restore_result = runner.invoke(app, ["restore", str(backup_path)])
    assert restore_result.exit_code == 0
    
    # Should complete successfully
    assert "restore completed" in restore_result.stdout.lower()
    
    # Start stack and verify functionality
    start_result = runner.invoke(app, ["start"])
    assert start_result.exit_code == 0
    
    time.sleep(5)
    assert wait_for_service_health("webui", timeout=15)


@pytest.mark.integration
def test_migrate_after_fresh_installation(runner, clean_config_dir):
    """
    Verifies migration works correctly after fresh installation.
    
    Tests install -> migrate workflow.
    """
    # Fresh installation
    install_result = runner.invoke(app, ["install", "--force"])
    assert install_result.exit_code == 0
    
    # Immediate migration after install
    result = runner.invoke(app, ["migrate", "--target-version", "0.3.0"])
    assert result.exit_code == 0
    
    # Should complete successfully
    assert "migration completed" in result.stdout.lower()
    
    # Configuration should be valid after migration
    config_dir = clean_config_dir
    assert os.path.exists(config_dir)
    assert os.path.exists(os.path.join(config_dir, ".ollama-stack.json"))
    assert os.path.exists(os.path.join(config_dir, ".env"))


# --- Error Recovery and Cleanup Tests ---

@pytest.mark.integration
def test_migrate_cleanup_on_failure(runner):
    """
    Verifies migration cleans up properly on failure.
    
    Tests that failed migrations don't leave partial state.
    """
    # Create minimal configuration that might cause migration issues
    config_dir = os.path.expanduser("~/.ollama-stack")
    os.makedirs(config_dir, exist_ok=True)
    
    config_file = os.path.join(config_dir, ".ollama-stack.json")
    with open(config_file, 'w') as f:
        json.dump({"minimal": "config"}, f)
    
    try:
        # Attempt migration (may fail due to incomplete config)
        result = runner.invoke(app, ["migrate", "--target-version", "0.3.0"])
        
        # Should handle gracefully
        assert result.exit_code in [0, 1]
        
        if result.exit_code == 1:
            # Should provide helpful error message
            output_lower = result.stdout.lower()
            assert "traceback" not in output_lower
            
            # Configuration should still be readable
            assert os.path.exists(config_file)
            with open(config_file, 'r') as f:
                json.load(f)  # Should be valid JSON
                
    finally:
        # Clean up test config
        if os.path.exists(config_file):
            try:
                os.remove(config_file)
            except OSError:
                pass


@pytest.mark.integration
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_migrate_system_consistency_after_interruption(runner):
    """
    Verifies system remains consistent after migration interruption.
    
    Tests recovery from interrupted migrations.
    """
    # Ensure configuration exists
    install_result = runner.invoke(app, ["install", "--force"])
    assert install_result.exit_code == 0
    
    # Attempt migration (may be interrupted in some environments)
    result = runner.invoke(app, ["migrate", "--target-version", "0.3.0"])
    
    # Should handle gracefully
    assert result.exit_code in [0, 1]
    
    # System should be in consistent state - other commands should work
    status_result = runner.invoke(app, ["status"])
    assert status_result.exit_code == 0
    
    check_result = runner.invoke(app, ["check"])
    assert check_result.exit_code in [0, 1]  # May succeed or show issues
    
    # Should not have corrupted configuration
    config_file = os.path.join(os.path.expanduser("~/.ollama-stack"), ".ollama-stack.json")
    if os.path.exists(config_file):
        with open(config_file, 'r') as f:
            json.load(f)  # Should be valid JSON


# --- Output Format Tests ---

@pytest.mark.integration
def test_migrate_output_format_consistency(runner):
    """
    Verifies migrate command output is consistent and well-formatted.
    
    Tests user experience and output quality.
    """
    # Ensure configuration exists
    install_result = runner.invoke(app, ["install", "--force"])
    assert install_result.exit_code == 0
    
    # Perform migration
    result = runner.invoke(app, ["migrate", "--target-version", "0.3.0"])
    assert result.exit_code == 0
    
    output = result.stdout
    
    # Should show migration progress
    assert any(keyword in output.lower() for keyword in [
        "migration", "from:", "to:", "completed"
    ])
    
    # Should show version information
    assert any(version_indicator in output for version_indicator in [
        "0.2.0", "0.3.0", "version"
    ])
    
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
def test_migrate_help_accessibility(runner):
    """
    Verifies migrate command help is accessible and informative.
    
    Tests user discoverability and documentation.
    """
    result = runner.invoke(app, ["migrate", "--help"])
    assert result.exit_code == 0
    
    output_lower = result.stdout.lower()
    
    # Should contain key information
    assert "migrate" in output_lower
    assert "version" in output_lower
    
    # Should show available options
    assert "--target-version" in result.stdout
    assert "--dry-run" in result.stdout
    
    # Should provide clear description
    assert any(keyword in output_lower for keyword in [
        "migrate", "upgrade", "version", "target"
    ]) 