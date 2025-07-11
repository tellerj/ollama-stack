"""
Template for writing integration tests with proper state management.

This file demonstrates the correct patterns for:
1. Ensuring clean test environment
2. Proper setup and teardown
3. Explicit cleanup of test artifacts
4. State verification
"""

import pytest
import os
import tempfile
from pathlib import Path
from typer.testing import CliRunner
from ollama_stack_cli.main import app

from ollama_stack_cli.tests.integration.helpers import (
    ensure_clean_test_environment,
    cleanup_test_artifacts,
    verify_clean_environment,
    is_docker_available,
    get_actual_running_services,
    wait_for_service_health,
    IS_APPLE_SILICON,
    EXPECTED_ALL_COMPONENTS,
    EXPECTED_DOCKER_COMPONENTS,
)

# --- Test Template Examples ---

@pytest.mark.integration
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_template_with_clean_state_management(runner, isolated_test_environment):
    """
    Template showing proper integration test structure with clean state management.
    
    This demonstrates the recommended pattern for integration tests.
    """
    # 1. Ensure clean environment at start
    ensure_clean_test_environment()
    
    # 2. Track test artifacts for cleanup
    test_artifacts = []
    
    try:
        # 3. Test setup
        # Create any temporary files/directories needed for the test
        temp_file = Path(isolated_test_environment) / "test_file.txt"
        temp_file.write_text("test content")
        test_artifacts.append(temp_file)
        
        # 4. Perform test operations
        result = runner.invoke(app, ["install", "--force"])
        assert result.exit_code == 0
        
        # 5. Verify test results
        assert "installation completed" in result.stdout.lower()
        
    finally:
        # 6. Clean up test artifacts
        cleanup_test_artifacts(test_artifacts)
        
        # 7. Verify clean state after test
        assert verify_clean_environment(), "Test did not clean up properly"


@pytest.mark.integration
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_template_with_stack_operations(runner, isolated_test_environment):
    """
    Template for tests that involve stack operations (start/stop/install).
    
    Shows proper handling of stack state and verification.
    """
    # Ensure clean environment
    ensure_clean_test_environment()
    
    test_artifacts = []
    
    try:
        # Install stack
        install_result = runner.invoke(app, ["install", "--force"])
        assert install_result.exit_code == 0
        
        # Start stack
        start_result = runner.invoke(app, ["start"])
        assert start_result.exit_code == 0
        
        # Wait for services to be healthy
        assert wait_for_service_health("webui", timeout=15)
        
        # Verify expected services are running
        expected_components = EXPECTED_ALL_COMPONENTS if IS_APPLE_SILICON else EXPECTED_DOCKER_COMPONENTS
        running_services = get_actual_running_services()
        assert running_services == expected_components
        
        # Perform test-specific operations here
        # ...
        
    finally:
        # Clean up
        cleanup_test_artifacts(test_artifacts)
        
        # Stop stack
        runner.invoke(app, ["stop"], catch_exceptions=True)
        
        # Verify clean state
        assert verify_clean_environment()


@pytest.mark.integration
def test_template_with_backup_operations(runner, temp_backup_dir, isolated_test_environment):
    """
    Template for tests involving backup/restore operations.
    
    Shows proper handling of backup artifacts and cleanup.
    """
    ensure_clean_test_environment()
    
    test_artifacts = []
    backup_artifacts = []
    
    try:
        # Create backup
        backup_path = temp_backup_dir / "test_backup"
        backup_result = runner.invoke(app, ["backup", "--output", str(backup_path)])
        assert backup_result.exit_code == 0
        
        backup_artifacts.append(backup_path)
        
        # Verify backup was created
        assert backup_path.exists()
        assert (backup_path / "backup_manifest.json").exists()
        
        # Perform test-specific operations
        # ...
        
    finally:
        # Clean up backup artifacts
        cleanup_test_artifacts(backup_artifacts)
        cleanup_test_artifacts(test_artifacts)
        
        # Verify clean state
        assert verify_clean_environment()


@pytest.mark.integration
def test_template_with_error_handling(runner, isolated_test_environment):
    """
    Template for tests that verify error handling and edge cases.
    
    Shows proper cleanup even when tests fail or encounter errors.
    """
    ensure_clean_test_environment()
    
    test_artifacts = []
    
    try:
        # Test error conditions
        # Try to run a non-existent command
        result = runner.invoke(app, ["nonexistent-command"])
        
        # Verify expected error behavior
        assert result.exit_code != 0
        assert "error" in result.stdout.lower() or "not found" in result.stdout.lower()
        
    finally:
        # Always clean up, even if test fails
        cleanup_test_artifacts(test_artifacts)
        assert verify_clean_environment()


# --- Helper Functions for Test Templates ---

def create_test_data_file(file_path: Path, content: str = "test data"):
    """Helper to create test data files."""
    file_path.write_text(content)
    return file_path

def verify_file_content(file_path: Path, expected_content: str):
    """Helper to verify file content."""
    assert file_path.exists()
    assert file_path.read_text() == expected_content

def wait_for_condition(condition_func, timeout: int = 30, interval: float = 1.0):
    """
    Wait for a condition to be true within a timeout.
    
    Args:
        condition_func: Function that returns True when condition is met
        timeout: Maximum time to wait in seconds
        interval: Time between checks in seconds
    
    Returns:
        True if condition was met, False if timeout exceeded
    """
    import time
    start_time = time.time()
    while time.time() - start_time < timeout:
        if condition_func():
            return True
        time.sleep(interval)
    return False 