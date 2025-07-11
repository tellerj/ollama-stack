import pytest
import os
import json
import time
import shutil
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
    wait_for_stack_to_stop,
    extract_secret_key_from_env,
    get_system_resource_usage,
    ArtifactTracker,
)

# --- Complete Lifecycle Workflow Tests ---

@pytest.mark.integration
@pytest.mark.stateful
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_complete_stack_lifecycle_workflow(runner, clean_config_dir):
    """
    Verifies complete stack lifecycle: install -> start -> update -> backup -> stop -> uninstall.
    
    Tests the most common user workflow from initial setup to cleanup.
    """
    # 1. Fresh installation
    install_result = runner.invoke(app, ["install", "--force"])
    assert install_result.exit_code == 0
    assert "installation" in install_result.stdout.lower()
    
    # Verify configuration was created
    config_dir = clean_config_dir
    assert os.path.exists(config_dir)
    assert os.path.exists(os.path.join(config_dir, ".ollama-stack.json"))
    assert os.path.exists(os.path.join(config_dir, ".env"))
    
    # 2. Start stack
    start_result = runner.invoke(app, ["start"])
    assert start_result.exit_code == 0
    
    # Verify services are running
    time.sleep(5)
    expected_components = EXPECTED_ALL_COMPONENTS if IS_APPLE_SILICON else EXPECTED_DOCKER_COMPONENTS
    running_services = get_actual_running_services()
    assert running_services == expected_components
    
    # 3. Check status
    status_result = runner.invoke(app, ["status"])
    assert status_result.exit_code == 0
    assert "running" in status_result.stdout.lower()
    
    # 4. Update stack
    update_result = runner.invoke(app, ["update"], input="y\n")
    assert update_result.exit_code == 0
    
    # Verify stack is still running after update
    time.sleep(3)
    updated_services = get_actual_running_services()
    assert updated_services == expected_components
    
    # 5. Create backup
    backup_dir = Path(config_dir).parent / "test_backup"
    backup_result = runner.invoke(app, ["backup", "--output", str(backup_dir)])
    assert backup_result.exit_code == 0
    assert backup_dir.exists()
    
    # 6. Stop stack
    stop_result = runner.invoke(app, ["stop"])
    assert stop_result.exit_code == 0
    
    # Verify stack is stopped
    assert wait_for_stack_to_stop(timeout=15)
    
    # 7. Complete uninstall
    uninstall_result = runner.invoke(app, ["uninstall", "--all"])
    assert uninstall_result.exit_code == 0
    
    # Verify complete cleanup
    assert not os.path.exists(config_dir)
    assert get_actual_running_services() == set()


@pytest.mark.integration
@pytest.mark.stateful
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_backup_restore_migration_workflow(runner, temp_backup_dir, clean_config_dir):
    """
    Verifies backup -> migrate -> restore workflow for version management.
    
    Tests complex version management scenario with data preservation.
    """
    # 1. Install and start stack
    install_result = runner.invoke(app, ["install", "--force"])
    assert install_result.exit_code == 0
    
    start_result = runner.invoke(app, ["start"])
    assert start_result.exit_code == 0
    
    time.sleep(5)  # Let services create initial data
    
    # 2. Create backup of initial state
    initial_backup_path = temp_backup_dir / "initial_backup"
    backup_result = runner.invoke(app, ["backup", "--output", str(initial_backup_path)])
    assert backup_result.exit_code == 0
    
    # Get initial configuration
    config_dir = clean_config_dir
    env_file = os.path.join(config_dir, ".env")
    initial_secret_key = extract_secret_key_from_env(env_file)
    
    # 3. Perform migration
    migrate_result = runner.invoke(app, ["migrate", "--target-version", "0.3.0"])
    assert migrate_result.exit_code == 0
    
    # Verify migration completed
    assert "migration completed" in migrate_result.stdout.lower()
    
    # 4. Create backup after migration
    post_migration_backup_path = temp_backup_dir / "post_migration_backup"
    backup_result = runner.invoke(app, ["backup", "--output", str(post_migration_backup_path)])
    assert backup_result.exit_code == 0
    
    # 5. Restore from initial backup (rollback scenario)
    stop_result = runner.invoke(app, ["stop"])
    assert stop_result.exit_code == 0
    
    restore_result = runner.invoke(app, ["restore", str(initial_backup_path)])
    assert restore_result.exit_code == 0
    
    # Verify restoration preserved original data
    restored_secret_key = extract_secret_key_from_env(env_file)
    assert restored_secret_key == initial_secret_key
    
    # 6. Start stack and verify functionality
    start_result = runner.invoke(app, ["start"])
    assert start_result.exit_code == 0
    
    time.sleep(5)
    expected_components = EXPECTED_ALL_COMPONENTS if IS_APPLE_SILICON else EXPECTED_DOCKER_COMPONENTS
    final_services = get_actual_running_services()
    assert final_services == expected_components
    
    # Verify services are healthy
    assert wait_for_service_health("webui", timeout=15)


@pytest.mark.integration
@pytest.mark.stateful
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_disaster_recovery_workflow(runner, temp_backup_dir, clean_config_dir):
    """
    Verifies disaster recovery: backup -> uninstall -> restore -> start.
    
    Tests complete system recovery from backup after total failure.
    """
    # 1. Install and configure stack
    install_result = runner.invoke(app, ["install", "--force"])
    assert install_result.exit_code == 0
    
    start_result = runner.invoke(app, ["start"])
    assert start_result.exit_code == 0
    
    time.sleep(5)  # Let services create data
    
    # 2. Create comprehensive backup
    backup_path = temp_backup_dir / "disaster_recovery_backup"
    backup_result = runner.invoke(app, ["backup", "--output", str(backup_path)])
    assert backup_result.exit_code == 0
    
    # Verify backup contains all necessary components
    assert (backup_path / "manifest.json").exists()
    assert (backup_path / "config").exists()
    assert (backup_path / "volumes").exists()
    
    # Get backup configuration for verification
    config_backup_path = backup_path / "config" / ".env"
    original_secret_key = extract_secret_key_from_env(str(config_backup_path))
    
    # 3. Simulate disaster - complete uninstall
    uninstall_result = runner.invoke(app, ["uninstall", "--all"])
    assert uninstall_result.exit_code == 0
    
    # Verify everything is gone
    config_dir = clean_config_dir
    assert not os.path.exists(config_dir)
    assert get_actual_running_services() == set()
    
    # 4. Disaster recovery - restore from backup
    restore_result = runner.invoke(app, ["restore", str(backup_path)])
    assert restore_result.exit_code == 0
    
    # Verify configuration was restored
    assert os.path.exists(config_dir)
    assert os.path.exists(os.path.join(config_dir, ".ollama-stack.json"))
    assert os.path.exists(os.path.join(config_dir, ".env"))
    
    # Verify data integrity
    restored_env_file = os.path.join(config_dir, ".env")
    restored_secret_key = extract_secret_key_from_env(restored_env_file)
    assert restored_secret_key == original_secret_key
    
    # 5. Start stack and verify full recovery
    start_result = runner.invoke(app, ["start"])
    assert start_result.exit_code == 0
    
    time.sleep(8)  # Extra time for full recovery
    
    # Verify all services are running
    expected_components = EXPECTED_ALL_COMPONENTS if IS_APPLE_SILICON else EXPECTED_DOCKER_COMPONENTS
    recovered_services = get_actual_running_services()
    assert recovered_services == expected_components
    
    # Verify services are healthy
    assert wait_for_service_health("webui", timeout=20)
    
    # 6. Verify system is fully functional
    status_result = runner.invoke(app, ["status"])
    assert status_result.exit_code == 0
    assert "running" in status_result.stdout.lower()


@pytest.mark.integration
@pytest.mark.stateful
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_development_workflow_with_restarts(runner, clean_config_dir):
    """
    Verifies typical development workflow with frequent restarts and updates.
    
    Tests stack resilience under development usage patterns.
    """
    # 1. Initial setup
    install_result = runner.invoke(app, ["install", "--force"])
    assert install_result.exit_code == 0
    
    # 2. Development cycle: start -> stop -> start -> restart -> update
    for cycle in range(3):
        # Start stack
        start_result = runner.invoke(app, ["start"])
        assert start_result.exit_code == 0
        
        time.sleep(3)  # Brief operation time
        
        # Check status
        status_result = runner.invoke(app, ["status"])
        assert status_result.exit_code == 0
        
        # Restart stack
        restart_result = runner.invoke(app, ["restart"])
        assert restart_result.exit_code == 0
        
        time.sleep(3)
        
        # Verify services are running after restart
        running_services = get_actual_running_services()
        expected_components = EXPECTED_ALL_COMPONENTS if IS_APPLE_SILICON else EXPECTED_DOCKER_COMPONENTS
        assert running_services == expected_components
        
        # Stop stack
        stop_result = runner.invoke(app, ["stop"])
        assert stop_result.exit_code == 0
        
        # Verify stack is stopped
        assert wait_for_stack_to_stop(timeout=10)
    
    # 3. Final start and update
    start_result = runner.invoke(app, ["start"])
    assert start_result.exit_code == 0
    
    # Perform update
    update_result = runner.invoke(app, ["update"], input="y\n")
    assert update_result.exit_code == 0
    
    # Verify stack is still functional after all operations
    time.sleep(5)
    final_services = get_actual_running_services()
    expected_components = EXPECTED_ALL_COMPONENTS if IS_APPLE_SILICON else EXPECTED_DOCKER_COMPONENTS
    assert final_services == expected_components


# --- Multi-Command Error Recovery Tests ---

@pytest.mark.integration
@pytest.mark.stateful
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_error_recovery_across_commands(runner, clean_config_dir):
    """
    Verifies system recovery when errors occur across multiple commands.
    
    Tests resilience and recovery in error scenarios.
    """
    # 1. Start with successful installation
    install_result = runner.invoke(app, ["install", "--force"])
    assert install_result.exit_code == 0
    
    # 2. Attempt operations that might fail
    start_result = runner.invoke(app, ["start"])
    # May succeed or fail depending on environment
    
    # 3. System should be recoverable regardless of start outcome
    status_result = runner.invoke(app, ["status"])
    assert status_result.exit_code == 0
    
    # 4. Check command should provide system state
    check_result = runner.invoke(app, ["check"])
    assert check_result.exit_code in [0, 1]  # May show issues but shouldn't crash
    
    # 5. Stop should be safe even if start failed
    stop_result = runner.invoke(app, ["stop"])
    assert stop_result.exit_code == 0
    
    # 6. System should remain in consistent state
    final_status_result = runner.invoke(app, ["status"])
    assert final_status_result.exit_code == 0
    
    # Configuration should still be valid
    config_dir = clean_config_dir
    config_file = os.path.join(config_dir, ".ollama-stack.json")
    if os.path.exists(config_file):
        with open(config_file, 'r') as f:
            json.load(f)  # Should be valid JSON


@pytest.mark.integration
@pytest.mark.stateful
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_concurrent_operation_handling(runner, clean_config_dir):
    """
    Verifies system handles rapid sequential operations gracefully.
    
    Tests system stability under rapid command execution.
    """
    # Install stack
    install_result = runner.invoke(app, ["install", "--force"])
    assert install_result.exit_code == 0
    
    # Rapid sequence of operations
    operations = [
        ["status"],
        ["check"],
        ["start"],
        ["status"],
        ["logs", "webui", "--tail", "5"],
        ["restart"],
        ["status"],
        ["stop"],
        ["status"]
    ]
    
    for operation in operations:
        result = runner.invoke(app, operation)
        # Operations should complete without crashing
        assert result.exit_code in [0, 1]
        
        # Should not show Python tracebacks
        assert "traceback" not in result.stdout.lower()
        
        # Brief pause between operations
        time.sleep(0.5)
    
    # System should be in consistent state after rapid operations
    final_status = runner.invoke(app, ["status"])
    assert final_status.exit_code == 0


# --- Performance Workflow Tests ---

@pytest.mark.integration
@pytest.mark.stateful
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_performance_under_load_workflow(runner, temp_backup_dir, clean_config_dir):
    """
    Verifies system performance under load with multiple operations.
    
    Tests performance characteristics in realistic usage scenarios.
    """
    # Record initial resource usage
    initial_resources = get_system_resource_usage()
    
    # Install and start
    install_result = runner.invoke(app, ["install", "--force"])
    assert install_result.exit_code == 0
    
    start_time = time.time()
    
    start_result = runner.invoke(app, ["start"])
    assert start_result.exit_code == 0
    
    # Perform multiple operations under load
    operations_completed = 0
    
    # Create backup
    backup_path = temp_backup_dir / "performance_backup"
    backup_result = runner.invoke(app, ["backup", "--output", str(backup_path)])
    if backup_result.exit_code == 0:
        operations_completed += 1
    
    # Update stack
    update_result = runner.invoke(app, ["update"], input="y\n")
    if update_result.exit_code == 0:
        operations_completed += 1
    
    # Restart stack
    restart_result = runner.invoke(app, ["restart"])
    if restart_result.exit_code == 0:
        operations_completed += 1
    
    end_time = time.time()
    total_duration = end_time - start_time
    
    # Record final resource usage
    final_resources = get_system_resource_usage()
    
    # Performance assertions
    assert total_duration < 300, f"Operations took too long: {total_duration:.2f} seconds"
    assert operations_completed >= 2, "Should complete most operations successfully"
    
    # Resource usage should be reasonable
    assert final_resources["cpu_percent"] < 95, "CPU usage too high"
    assert final_resources["memory_percent"] < 90, "Memory usage too high"
    
    # System should still be functional
    final_status = runner.invoke(app, ["status"])
    assert final_status.exit_code == 0


@pytest.mark.integration
@pytest.mark.stateful
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_long_running_stability_workflow(runner, clean_config_dir):
    """
    Verifies system stability over extended operation periods.
    
    Tests long-term stability and resource management.
    """
    # Install and start stack
    install_result = runner.invoke(app, ["install", "--force"])
    assert install_result.exit_code == 0
    
    start_result = runner.invoke(app, ["start"])
    assert start_result.exit_code == 0
    
    # Let stack run for extended period
    time.sleep(10)  # Simulate longer operation
    
    # Perform periodic health checks
    for check_round in range(3):
        # Status check
        status_result = runner.invoke(app, ["status"])
        assert status_result.exit_code == 0
        
        # Verify services are still running
        running_services = get_actual_running_services()
        assert len(running_services) > 0
        
        # Log check
        logs_result = runner.invoke(app, ["logs", "webui", "--tail", "5"])
        assert logs_result.exit_code == 0
        
        time.sleep(2)  # Wait between checks
    
    # System should remain stable
    expected_components = EXPECTED_ALL_COMPONENTS if IS_APPLE_SILICON else EXPECTED_DOCKER_COMPONENTS
    final_services = get_actual_running_services()
    assert final_services == expected_components
    
    # Services should still be healthy
    assert wait_for_service_health("webui", timeout=10)


# --- Complex Configuration Workflow Tests ---

@pytest.mark.integration
@pytest.mark.stateful
def test_configuration_persistence_across_operations(runner, clean_config_dir):
    """
    Verifies configuration persistence through various operations.
    
    Tests that configuration remains consistent across command sequences.
    """
    # Install with custom configuration
    install_result = runner.invoke(app, ["install", "--force"])
    assert install_result.exit_code == 0
    
    # Get initial configuration
    config_dir = clean_config_dir
    config_file = os.path.join(config_dir, ".ollama-stack.json")
    env_file = os.path.join(config_dir, ".env")
    
    with open(config_file, 'r') as f:
        initial_config = json.load(f)
    
    initial_secret_key = extract_secret_key_from_env(env_file)
    
    # Perform various operations
    operations = [
        ["status"],
        ["check"],
    ]
    
    if is_docker_available():
        operations.extend([
            ["start"],
            ["restart"],
            ["stop"]
        ])
    
    for operation in operations:
        result = runner.invoke(app, operation)
        # Operations should not corrupt configuration
        assert result.exit_code in [0, 1]
        
        # Verify configuration files still exist and are valid
        assert os.path.exists(config_file)
        assert os.path.exists(env_file)
        
        with open(config_file, 'r') as f:
            current_config = json.load(f)
        
        current_secret_key = extract_secret_key_from_env(env_file)
        
        # Core configuration should remain unchanged
        assert current_secret_key == initial_secret_key
        assert current_config["services"] == initial_config["services"]
        assert current_config["platform"] == initial_config["platform"]


# --- User Experience Workflow Tests ---

@pytest.mark.integration
@pytest.mark.stateful
def test_user_friendly_error_messages_workflow(runner):
    """
    Verifies user-friendly error messages across command workflows.
    
    Tests that error messages are helpful and not technical.
    """
    # Test commands without installation
    commands_to_test = [
        ["start"],
        ["stop"],
        ["restart"],
        ["status"],
        ["backup", "--output", "/tmp/test_backup"],
        ["restore", "/nonexistent/backup"],
        ["migrate", "--target-version", "0.3.0"]
    ]
    
    for command in commands_to_test:
        result = runner.invoke(app, command)
        
        # Commands may fail without installation, but should fail gracefully
        assert result.exit_code in [0, 1]
        
        output_lower = result.stdout.lower()
        
        # Should not show Python technical details
        assert "traceback" not in output_lower
        assert "exception:" not in output_lower
        assert "attributeerror" not in output_lower
        assert "keyerror" not in output_lower
        
        # If showing errors, should be user-friendly
        if result.exit_code == 1:
            assert any(helpful_keyword in output_lower for helpful_keyword in [
                "install", "configuration", "not found", "run", "please"
            ])


@pytest.mark.integration
@pytest.mark.stateful
def test_help_accessibility_workflow(runner):
    """
    Verifies help system accessibility across all commands.
    
    Tests that help documentation is comprehensive and accessible.
    """
    # Test help for all main commands
    commands = [
        "install", "start", "stop", "restart", "status", "check",
        "logs", "update", "uninstall", "backup", "restore", "migrate"
    ]
    
    for command in commands:
        help_result = runner.invoke(app, [command, "--help"])
        assert help_result.exit_code == 0
        
        output_lower = help_result.stdout.lower()
        
        # Should contain command name
        assert command in output_lower
        
        # Should contain usage information
        assert "usage" in output_lower or "options" in output_lower
        
        # Should provide meaningful description
        assert len(help_result.stdout.strip()) > 50  # Substantial help content
    
    # Test main help
    main_help_result = runner.invoke(app, ["--help"])
    assert main_help_result.exit_code == 0
    
    main_output_lower = main_help_result.stdout.lower()
    
    # Should list all commands
    for command in commands:
        assert command in main_output_lower 