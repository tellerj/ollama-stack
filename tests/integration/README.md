# Integration Test Suite

This directory contains comprehensive integration tests for the ollama-stack CLI, organized by functionality and workflow patterns.

## Test Isolation and State Management

### Guaranteed Clean State

All integration tests are designed to run from a completely clean, consistent starting point. The test framework ensures:

1. **Complete Service Cleanup**: All Docker containers and native processes are stopped before each test
2. **Config Directory Isolation**: Configuration files are cleaned up between tests
3. **Backup Artifact Cleanup**: Backup files created during tests are removed
4. **State Verification**: Tests verify clean state before and after execution

### Test Environment Setup

The test framework provides several fixtures for clean state management:

- `clean_stack_between_tests` (autouse): Ensures complete cleanup before/after each test
- `isolated_test_environment`: Creates isolated config directory for each test
- `clean_config_dir`: Provides clean configuration directory
- `temp_backup_dir`: Temporary directory for backup testing

### Best Practices for Writing Tests

1. **Always use `ensure_clean_test_environment()`** at the start of tests that require clean state
2. **Track test artifacts** and clean them up in `finally` blocks
3. **Use `verify_clean_environment()`** to verify state after tests
4. **Handle cleanup even when tests fail** using try/finally patterns

See `test_template_example.py` for complete examples of proper test patterns.

## Structure

### Core Test Files

- `conftest.py` - Shared fixtures and configuration with enhanced cleanup
- `helpers.py` - Common helper functions and state management utilities
- `pytest.ini` - Test configuration and isolation settings
- `test_template_example.py` - Template showing proper test patterns

### Command-Specific Tests

- `test_backup_integration.py` - Backup command integration tests
- `test_restore_integration.py` - Restore command integration tests  
- `test_lifecycle_integration.py` - Core lifecycle tests (start/stop/restart/status/check/logs)
- `test_update_integration.py` - Update command integration tests
- `test_uninstall_integration.py` - Uninstall command integration tests
- `test_install_integration.py` - Install command integration tests

### Workflow Tests

- `test_workflow_integration.py` - Cross-command workflows and complex scenarios

## Running Tests

### Run All Integration Tests
```bash
pytest tests/integration/
```

### Run Specific Test Categories
```bash
# Core lifecycle functionality
pytest tests/integration/ -m lifecycle

# Update functionality
pytest tests/integration/ -m update

# Uninstall functionality
pytest tests/integration/ -m uninstall

# Install functionality
pytest tests/integration/ -m install

# Backup functionality
pytest tests/integration/ -m backup

# Docker-dependent tests
pytest tests/integration/ -m docker_required

# Apple Silicon specific tests
pytest tests/integration/ -m apple_silicon

# Performance tests
pytest tests/integration/ -m performance

# Workflow tests
pytest tests/integration/ -m workflow
```

### Run Specific Test Files
```bash
# Core lifecycle tests (start/stop/restart/status/check/logs)
pytest tests/integration/test_lifecycle_integration.py

# Update command tests
pytest tests/integration/test_update_integration.py

# Uninstall command tests
pytest tests/integration/test_uninstall_integration.py

# Install command tests
pytest tests/integration/test_install_integration.py

# Backup tests only
pytest tests/integration/test_backup_integration.py

# Restore tests only
pytest tests/integration/test_restore_integration.py

# Workflow tests only
pytest tests/integration/test_workflow_integration.py
```

### Run Tests with Specific Conditions
```bash
# Only tests that don't require Docker
pytest tests/integration/ -m "not docker_required"

# Only Apple Silicon tests (when on Apple Silicon)
pytest tests/integration/ -m apple_silicon

# Only failure scenario tests
pytest tests/integration/ -m failure_scenario
```

## Test Categories

### Lifecycle Integration Tests (`test_lifecycle_integration.py`)

- **Basic Lifecycle**: Tests start/stop/restart workflows
- **Service Health**: Tests service availability and health checks
- **Platform Compatibility**: Tests Apple Silicon vs Docker platform behavior
- **Error Handling**: Tests graceful failure when Docker unavailable
- **Status/Check Commands**: Tests environment validation and status reporting
- **Logs Access**: Tests log retrieval and streaming functionality

### Update Integration Tests (`test_update_integration.py`)

- **Update Operations**: Tests update with various flags and scenarios
- **Running Stack Updates**: Tests update with stack running/stopped
- **Service Coordination**: Tests update coordination across mixed service types
- **Failure Recovery**: Tests update failure handling and rollback
- **Performance**: Tests update performance under load
- **Resource Management**: Tests resource cleanup during updates

### Uninstall Integration Tests (`test_uninstall_integration.py`)

- **Resource Cleanup**: Tests removal of containers, volumes, and configuration
- **Selective Removal**: Tests --remove-volumes, --remove-config, --all flags
- **Cross-Platform**: Tests uninstall on Apple Silicon vs Docker platforms
- **Complete Cleanup**: Tests system state verification after uninstall
- **Idempotent Operations**: Tests multiple uninstall runs
- **Error Handling**: Tests graceful handling of cleanup failures

### Install Integration Tests (`test_install_integration.py`)

- **Fresh Installation**: Tests configuration creation on clean systems
- **Configuration Management**: Tests secure key generation and file creation
- **Platform-Specific Setup**: Tests Apple Silicon vs Docker platform configuration
- **Existing Config Handling**: Tests install over existing configuration
- **File Permissions**: Tests filesystem permissions and access
- **Integration Enablement**: Tests that install enables other commands

### Backup Integration Tests (`test_backup_integration.py`)

- **Real Backup Operations**: Tests actual Docker volume backup with real data
- **Backup Validation**: Tests manifest validation and backup integrity checks
- **Failure Scenarios**: Tests disk space, permissions, corruption, interruption
- **Cross-Platform**: Tests Apple Silicon vs Docker platform behavior
- **Performance**: Tests large volumes, concurrent operations

### Restore Integration Tests (`test_restore_integration.py`)

- **Real Restore Operations**: Tests actual volume restoration from backups
- **Restore Validation**: Tests backup validation before restoration
- **Failure Recovery**: Tests corrupted backups, missing files, permissions
- **State Management**: Tests restore with stack running/stopped
- **Cross-Platform**: Tests restoring backups across different platforms

### Workflow Integration Tests (`test_workflow_integration.py`)

- **Complete Lifecycles**: Tests install → start → backup → stop → uninstall
- **Disaster Recovery**: Tests backup → uninstall → restore → start
- **Development Workflows**: Tests frequent restarts and updates
- **Error Recovery**: Tests system recovery across multiple commands
- **Performance**: Tests system behavior under load

## Test Markers

The integration tests use pytest markers to categorize and filter tests:

- `@pytest.mark.integration` - All integration tests
- `@pytest.mark.docker_required` - Requires Docker daemon
- `@pytest.mark.apple_silicon` - Apple Silicon specific
- `@pytest.mark.lifecycle` - Core lifecycle functionality (start/stop/restart/status/check/logs)
- `@pytest.mark.update` - Update functionality
- `@pytest.mark.uninstall` - Uninstall functionality
- `@pytest.mark.install` - Install functionality
- `@pytest.mark.backup` - Backup functionality
- `@pytest.mark.restore` - Restore functionality
- `@pytest.mark.workflow` - Cross-command workflows
- `@pytest.mark.performance` - Performance and load tests
- `@pytest.mark.failure_scenario` - Error and failure handling

## Prerequisites

### Required

- Docker Desktop or Docker daemon running (for most tests)
- Sufficient disk space for backup/restore operations
- Network connectivity for update operations

### Platform-Specific

- **Apple Silicon**: Native Ollama installation (for Apple Silicon specific tests)
- **Other platforms**: Docker-based Ollama (automatically handled)

## Test Data Management

### Temporary Directories

Tests use pytest's `tmp_path` fixture and custom fixtures:
- `temp_backup_dir` - For backup/restore operations
- `clean_config_dir` - For configuration management

### Cleanup

All tests include automatic cleanup:
- Stack services are stopped before/after each test
- Temporary files and directories are removed
- Configuration is cleaned up between tests

## Performance Considerations

### Resource Usage

Integration tests are resource-intensive:
- May use significant CPU during Docker operations
- Require disk space for backups and volume data
- May take several minutes to complete

### Parallel Execution

Currently not recommended:
- Tests may interfere with shared Docker resources
- Stack state changes affect other tests
- Consider running tests sequentially for reliability

## Debugging

### Verbose Output
```bash
pytest tests/integration/ -v -s
```

### Stop on First Failure
```bash
pytest tests/integration/ -x
```

### Run Specific Test
```bash
pytest tests/integration/test_backup_integration.py::test_backup_creates_real_docker_volume_backup -v -s
```

### Check Test Prerequisites
```bash
# Verify Docker is available
docker ps

# Check available disk space
df -h

# On Apple Silicon, check Ollama
ollama --version
```

## Contributing

When adding new integration tests:

1. **Follow naming conventions**: `test_<functionality>_<scenario>.py`
2. **Use appropriate markers**: Mark tests with relevant pytest markers
3. **Include cleanup**: Ensure tests clean up after themselves
4. **Document requirements**: Note any special requirements or prerequisites
5. **Test cross-platform**: Consider Apple Silicon vs other platforms
6. **Handle failures gracefully**: Tests should not leave system in bad state

### Example Test Structure

```python
@pytest.mark.integration
@pytest.mark.docker_required
def test_new_functionality(runner, temp_backup_dir):
    """
    Test description explaining what is being tested and why.
    
    Tests specific behavior with clear assertions.
    """
    # Setup
    setup_result = runner.invoke(app, ["setup_command"])
    assert setup_result.exit_code == 0
    
    # Test operation
    result = runner.invoke(app, ["test_command"])
    assert result.exit_code == 0
    
    # Verify results
    assert "expected_output" in result.stdout.lower()
    
    # Cleanup is handled by fixtures
``` 