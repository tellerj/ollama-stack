# Integration Test Suite

This directory contains comprehensive integration tests for the ollama-stack CLI, organized by functionality and workflow patterns.

## Structure

### Core Test Files

- `conftest.py` - Shared fixtures and configuration
- `helpers.py` - Common helper functions and utilities
- `pytest.ini` - Test configuration and markers

### Command-Specific Tests

- `test_backup_integration.py` - Backup command integration tests
- `test_restore_integration.py` - Restore command integration tests  
- `test_migrate_integration.py` - Migrate command integration tests

### Workflow Tests

- `test_workflow_integration.py` - Cross-command workflows and complex scenarios

## Running Tests

### Run All Integration Tests
```bash
pytest tests/integration/
```

### Run Specific Test Categories
```bash
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
# Backup tests only
pytest tests/integration/test_backup_integration.py

# Restore tests only
pytest tests/integration/test_restore_integration.py

# Migration tests only
pytest tests/integration/test_migrate_integration.py

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

### Migration Integration Tests (`test_migrate_integration.py`)

- **Version Migrations**: Tests actual version detection and migration execution
- **Migration Planning**: Tests dry run mode, validation, compatibility checks
- **Failure Scenarios**: Tests interrupted migrations, incompatible versions
- **Rollback**: Tests handling failed migrations and system recovery
- **Cross-Platform**: Tests migrations across different platforms

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
- `@pytest.mark.backup` - Backup functionality
- `@pytest.mark.restore` - Restore functionality
- `@pytest.mark.migrate` - Migration functionality
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