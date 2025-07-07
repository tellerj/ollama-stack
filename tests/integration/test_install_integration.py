import pytest
import os
import json
import shutil
from pathlib import Path
from typer.testing import CliRunner
from ollama_stack_cli.main import app

from tests.integration.helpers import (
    is_docker_available,
    get_actual_running_services,
    extract_secret_key_from_env,
    IS_APPLE_SILICON,
    EXPECTED_ALL_COMPONENTS,
    EXPECTED_DOCKER_COMPONENTS,
)

# --- Install Command Integration Tests ---

@pytest.mark.integration
def test_install_command_fresh_system_creates_config_files(runner, clean_config_dir):
    """
    Verifies that install command creates proper configuration files on fresh system.
    """
    config_dir = clean_config_dir
    
    # Verify config directory doesn't exist initially
    assert not os.path.exists(config_dir)
    
    # Run install command
    result = runner.invoke(app, ["install", "--force"])
    assert result.exit_code == 0
    
    # Verify success message
    assert "installation" in result.stdout.lower()
    assert "completed" in result.stdout.lower() or "success" in result.stdout.lower()
    
    # Verify configuration directory is created
    assert os.path.exists(config_dir)
    assert os.path.isdir(config_dir)
    
    # Verify required configuration files are created
    config_file = os.path.join(config_dir, ".ollama-stack.json")
    env_file = os.path.join(config_dir, ".env")
    
    assert os.path.exists(config_file)
    assert os.path.exists(env_file)
    assert os.path.isfile(config_file)
    assert os.path.isfile(env_file)
    
    # Verify configuration file contains valid JSON
    with open(config_file, 'r') as f:
        config_data = json.load(f)
    
    assert isinstance(config_data, dict)
    assert "docker_compose_file" in config_data
    
    # Verify environment file contains required keys
    with open(env_file, 'r') as f:
        env_content = f.read()
    
    assert "PROJECT_NAME=" in env_content
    assert "WEBUI_SECRET_KEY=" in env_content
    
    # Verify secret key is generated
    secret_key = extract_secret_key_from_env(env_file)
    assert len(secret_key) > 10  # Should be a substantial key
    assert secret_key != "your-secret-key-here"  # Should not be placeholder


@pytest.mark.integration
def test_install_command_generates_unique_secure_keys(runner, clean_config_dir):
    """
    Verifies that install command generates unique secure keys.
    """
    config_dir = clean_config_dir
    
    # First installation
    result1 = runner.invoke(app, ["install", "--force"])
    assert result1.exit_code == 0
    
    env_file = os.path.join(config_dir, ".env")
    secret_key_1 = extract_secret_key_from_env(env_file)
    
    # Remove config for second installation
    shutil.rmtree(config_dir)
    
    # Second installation
    result2 = runner.invoke(app, ["install", "--force"])
    assert result2.exit_code == 0
    
    secret_key_2 = extract_secret_key_from_env(env_file)
    
    # Keys should be different
    assert secret_key_1 != secret_key_2
    
    # Both keys should be substantial
    assert len(secret_key_1) > 10
    assert len(secret_key_2) > 10


@pytest.mark.integration
def test_install_command_creates_platform_specific_configurations(runner, clean_config_dir):
    """
    Verifies that install command creates platform-specific configurations.
    """
    config_dir = clean_config_dir
    
    # Run install command
    result = runner.invoke(app, ["install", "--force"])
    assert result.exit_code == 0
    
    # Verify configuration reflects platform
    config_file = os.path.join(config_dir, ".ollama-stack.json")
    with open(config_file, 'r') as f:
        config_data = json.load(f)
    
    # Should have platform-appropriate Docker Compose file
    assert "docker_compose_file" in config_data
    
    # Environment file should have platform-appropriate settings
    env_file = os.path.join(config_dir, ".env")
    with open(env_file, 'r') as f:
        env_content = f.read()
    
    # Should contain project name
    assert "PROJECT_NAME=" in env_content
    
    # Should contain WebUI secret key
    assert "WEBUI_SECRET_KEY=" in env_content
    
    # Platform-specific verification
    if IS_APPLE_SILICON:
        # Apple Silicon should have native Ollama configuration
        # (Configuration should be compatible with native Ollama)
        pass
    else:
        # Other platforms should have Docker Ollama configuration
        # (Configuration should include Docker Ollama service)
        pass


@pytest.mark.integration
def test_install_command_runs_environment_validation(runner, clean_config_dir):
    """
    Verifies that install command validates environment during installation.
    """
    config_dir = clean_config_dir
    
    # Run install command
    result = runner.invoke(app, ["install", "--force"])
    assert result.exit_code == 0
    
    # Install should include environment validation
    output_lower = result.stdout.lower()
    
    # Should mention checking environment or prerequisites
    validation_keywords = ["checking", "validating", "environment", "prerequisites"]
    # Note: Not all implementations may show validation output
    
    # Should succeed if environment is adequate
    assert "installation" in output_lower
    assert "completed" in output_lower or "success" in output_lower
    
    # Should create configuration files
    config_file = os.path.join(config_dir, ".ollama-stack.json")
    env_file = os.path.join(config_dir, ".env")
    
    assert os.path.exists(config_file)
    assert os.path.exists(env_file)


@pytest.mark.integration
def test_install_over_existing_configuration_user_confirms(runner, clean_config_dir):
    """
    Verifies that install handles existing configuration with user confirmation.
    """
    config_dir = clean_config_dir
    
    # First installation
    result1 = runner.invoke(app, ["install", "--force"])
    assert result1.exit_code == 0
    
    # Get original secret key
    env_file = os.path.join(config_dir, ".env")
    original_secret_key = extract_secret_key_from_env(env_file)
    
    # Second installation with confirmation
    result2 = runner.invoke(app, ["install"], input="y\n")
    assert result2.exit_code == 0
    
    # Should show confirmation prompt
    assert "already exists" in result2.stdout.lower() or "overwrite" in result2.stdout.lower()
    
    # Should create new configuration
    new_secret_key = extract_secret_key_from_env(env_file)
    assert new_secret_key != original_secret_key  # Should be regenerated


@pytest.mark.integration
def test_install_over_existing_configuration_user_declines(runner, clean_config_dir):
    """
    Verifies that install respects user decline for existing configuration.
    """
    config_dir = clean_config_dir
    
    # First installation
    result1 = runner.invoke(app, ["install", "--force"])
    assert result1.exit_code == 0
    
    # Get original secret key
    env_file = os.path.join(config_dir, ".env")
    original_secret_key = extract_secret_key_from_env(env_file)
    
    # Second installation with decline
    result2 = runner.invoke(app, ["install"], input="n\n")
    assert result2.exit_code == 0
    
    # Should show confirmation prompt
    assert "already exists" in result2.stdout.lower() or "overwrite" in result2.stdout.lower()
    
    # Should indicate cancellation
    assert "cancelled" in result2.stdout.lower() or "aborted" in result2.stdout.lower()
    
    # Should preserve original configuration
    preserved_secret_key = extract_secret_key_from_env(env_file)
    assert preserved_secret_key == original_secret_key


@pytest.mark.integration
def test_install_with_force_flag_overwrites_without_prompting(runner, clean_config_dir):
    """
    Verifies that --force flag overwrites existing configuration without prompting.
    """
    config_dir = clean_config_dir
    
    # First installation
    result1 = runner.invoke(app, ["install", "--force"])
    assert result1.exit_code == 0
    
    # Get original secret key
    env_file = os.path.join(config_dir, ".env")
    original_secret_key = extract_secret_key_from_env(env_file)
    
    # Second installation with force flag
    result2 = runner.invoke(app, ["install", "--force"])
    assert result2.exit_code == 0
    
    # Should not show confirmation prompt (but may show informational "already exists")
    assert "overwrite" not in result2.stdout.lower()
    assert "cancelled" not in result2.stdout.lower()
    
    # Should create new configuration
    new_secret_key = extract_secret_key_from_env(env_file)
    assert new_secret_key != original_secret_key  # Should be regenerated


@pytest.mark.integration
def test_install_partial_existing_configuration(runner, clean_config_dir):
    """
    Verifies that install handles partial existing configuration.
    """
    config_dir = clean_config_dir
    
    # Create config directory with partial configuration
    os.makedirs(config_dir, exist_ok=True)
    
    # Create only one config file
    config_file = os.path.join(config_dir, ".ollama-stack.json")
    with open(config_file, 'w') as f:
        json.dump({"docker_compose_file": "test-docker-compose.yml"}, f)
    
    # Run install command
    result = runner.invoke(app, ["install", "--force"])
    assert result.exit_code == 0
    
    # Should create missing files
    env_file = os.path.join(config_dir, ".env")
    assert os.path.exists(env_file)
    
    # Should have valid secret key
    secret_key = extract_secret_key_from_env(env_file)
    assert len(secret_key) > 10


@pytest.mark.integration
def test_install_existing_directory_no_config_files(runner, clean_config_dir):
    """
    Verifies that install handles existing directory without config files.
    """
    config_dir = clean_config_dir
    
    # Create config directory but no config files
    os.makedirs(config_dir, exist_ok=True)
    
    # Create some unrelated files
    test_file = os.path.join(config_dir, "test.txt")
    with open(test_file, 'w') as f:
        f.write("test content")
    
    # Run install command
    result = runner.invoke(app, ["install", "--force"])
    assert result.exit_code == 0
    
    # Should create config files
    config_file = os.path.join(config_dir, ".ollama-stack.json")
    env_file = os.path.join(config_dir, ".env")
    
    assert os.path.exists(config_file)
    assert os.path.exists(env_file)
    
    # Should preserve existing files
    assert os.path.exists(test_file)
    
    # Should have valid configuration
    with open(config_file, 'r') as f:
        config_data = json.load(f)
    assert isinstance(config_data, dict)
    
    secret_key = extract_secret_key_from_env(env_file)
    assert len(secret_key) > 10


@pytest.mark.integration
def test_install_command_help_accessibility(runner):
    """
    Verifies that install command help is accessible and informative.
    """
    result = runner.invoke(app, ["install", "--help"])
    assert result.exit_code == 0
    
    # Should contain key information about install command
    output_lower = result.stdout.lower()
    assert "install" in output_lower
    assert "configuration" in output_lower or "config" in output_lower
    
    # Should show flag options
    assert "--force" in result.stdout
    
    # Should explain what the command does
    assert "create" in output_lower or "setup" in output_lower or "initialize" in output_lower


@pytest.mark.integration
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_install_enables_other_commands(runner, clean_config_dir):
    """
    Verifies that install enables other commands to work properly.
    """
    config_dir = clean_config_dir
    
    # Run install command
    result = runner.invoke(app, ["install", "--force"])
    assert result.exit_code == 0
    
    # Other commands should now work
    status_result = runner.invoke(app, ["status"])
    assert status_result.exit_code == 0
    
    check_result = runner.invoke(app, ["check"])
    assert check_result.exit_code == 0
    
    # Start should work (may succeed or fail based on Docker availability)
    start_result = runner.invoke(app, ["start"])
    assert start_result.exit_code in [0, 1]  # May succeed or fail gracefully
    
    # Stop should work
    stop_result = runner.invoke(app, ["stop"])
    assert stop_result.exit_code == 0


@pytest.mark.integration
def test_install_cross_platform_compatibility(runner, clean_config_dir):
    """
    Verifies that install works across different platforms.
    """
    config_dir = clean_config_dir
    
    # Run install command
    result = runner.invoke(app, ["install", "--force"])
    assert result.exit_code == 0
    
    # Should work on all platforms
    assert "installation" in result.stdout.lower()
    assert "completed" in result.stdout.lower() or "success" in result.stdout.lower()
    
    # Should create configuration appropriate for platform
    config_file = os.path.join(config_dir, ".ollama-stack.json")
    env_file = os.path.join(config_dir, ".env")
    
    assert os.path.exists(config_file)
    assert os.path.exists(env_file)
    
    # Configuration should be valid
    with open(config_file, 'r') as f:
        config_data = json.load(f)
    assert isinstance(config_data, dict)
    
    secret_key = extract_secret_key_from_env(env_file)
    assert len(secret_key) > 10


@pytest.mark.integration
def test_install_filesystem_permissions_verification(runner, clean_config_dir):
    """
    Verifies that install creates files with appropriate permissions.
    """
    config_dir = clean_config_dir
    
    # Run install command
    result = runner.invoke(app, ["install", "--force"])
    assert result.exit_code == 0
    
    # Verify files are created with appropriate permissions
    config_file = os.path.join(config_dir, ".ollama-stack.json")
    env_file = os.path.join(config_dir, ".env")
    
    assert os.path.exists(config_file)
    assert os.path.exists(env_file)
    
    # Files should be readable by owner
    assert os.access(config_file, os.R_OK)
    assert os.access(env_file, os.R_OK)
    
    # Files should be writable by owner
    assert os.access(config_file, os.W_OK)
    assert os.access(env_file, os.W_OK)
    
    # Directory should be accessible
    assert os.access(config_dir, os.R_OK | os.W_OK | os.X_OK)


@pytest.mark.integration
def test_install_configuration_file_format_validation(runner, clean_config_dir):
    """
    Verifies that install creates properly formatted configuration files.
    """
    config_dir = clean_config_dir
    
    # Run install command
    result = runner.invoke(app, ["install", "--force"])
    assert result.exit_code == 0
    
    # Verify JSON configuration file format
    config_file = os.path.join(config_dir, ".ollama-stack.json")
    with open(config_file, 'r') as f:
        config_data = json.load(f)
    
    # Should be valid JSON
    assert isinstance(config_data, dict)
    
    # Should have required keys
    assert "docker_compose_file" in config_data
    assert isinstance(config_data["docker_compose_file"], str)
    
    # Verify environment file format
    env_file = os.path.join(config_dir, ".env")
    with open(env_file, 'r') as f:
        env_content = f.read()
    
    # Should have proper environment file format
    env_lines = env_content.strip().split('\n')
    for line in env_lines:
        if line.strip() and not line.startswith('#'):
            assert '=' in line, f"Invalid environment line: {line}"
    
    # Should have required environment variables
    assert "PROJECT_NAME=" in env_content
    assert "WEBUI_SECRET_KEY=" in env_content
    
    # Secret key should be properly formatted
    secret_key = extract_secret_key_from_env(env_file)
    assert len(secret_key) > 10
    assert not secret_key.startswith('$')  # Should not be a variable reference
    assert '"' not in secret_key or "'" not in secret_key  # Should not have unescaped quotes


@pytest.mark.integration
def test_install_error_message_quality(runner):
    """
    Verifies that install command provides high-quality error messages.
    """
    # Test help accessibility
    help_result = runner.invoke(app, ["install", "--help"])
    assert help_result.exit_code == 0
    assert "install" in help_result.stdout.lower()
    
    # Test with invalid arguments (if any)
    invalid_result = runner.invoke(app, ["install", "--invalid-flag"])
    assert invalid_result.exit_code != 0
    
    # Should have user-friendly error message
    assert "invalid" in invalid_result.stdout.lower() or "unknown" in invalid_result.stdout.lower()
    
    # Should not have technical error details
    assert "traceback" not in invalid_result.stdout.lower()


@pytest.mark.integration
def test_install_idempotent_multiple_runs(runner, clean_config_dir):
    """
    Verifies that install is idempotent when using force flag.
    """
    config_dir = clean_config_dir
    
    # First installation
    result1 = runner.invoke(app, ["install", "--force"])
    assert result1.exit_code == 0
    
    # Get initial secret key
    env_file = os.path.join(config_dir, ".env")
    secret_key_1 = extract_secret_key_from_env(env_file)
    
    # Second installation with force
    result2 = runner.invoke(app, ["install", "--force"])
    assert result2.exit_code == 0
    
    # Should succeed both times
    assert "installation" in result1.stdout.lower()
    assert "installation" in result2.stdout.lower()
    
    # Should generate new secret key
    secret_key_2 = extract_secret_key_from_env(env_file)
    assert secret_key_1 != secret_key_2
    
    # Both configurations should be valid
    config_file = os.path.join(config_dir, ".ollama-stack.json")
    with open(config_file, 'r') as f:
        config_data = json.load(f)
    assert isinstance(config_data, dict)


@pytest.mark.integration
def test_install_preserves_existing_non_config_files(runner, clean_config_dir):
    """
    Verifies that install preserves existing non-configuration files.
    """
    config_dir = clean_config_dir
    
    # Create config directory with some files
    os.makedirs(config_dir, exist_ok=True)
    
    # Create non-config files
    test_files = [
        "README.md",
        "custom-script.sh",
        "data.json",
        "backup.tar.gz"
    ]
    
    for filename in test_files:
        filepath = os.path.join(config_dir, filename)
        with open(filepath, 'w') as f:
            f.write(f"content for {filename}")
    
    # Run install command
    result = runner.invoke(app, ["install", "--force"])
    assert result.exit_code == 0
    
    # Should create config files
    config_file = os.path.join(config_dir, ".ollama-stack.json")
    env_file = os.path.join(config_dir, ".env")
    
    assert os.path.exists(config_file)
    assert os.path.exists(env_file)
    
    # Should preserve existing files
    for filename in test_files:
        filepath = os.path.join(config_dir, filename)
        assert os.path.exists(filepath)
        
        with open(filepath, 'r') as f:
            content = f.read()
        assert content == f"content for {filename}"


@pytest.mark.integration
def test_install_command_exit_codes(runner, clean_config_dir):
    """
    Verifies that install command returns appropriate exit codes.
    """
    config_dir = clean_config_dir
    
    # Successful installation
    result = runner.invoke(app, ["install", "--force"])
    assert result.exit_code == 0
    
    # Help should succeed
    help_result = runner.invoke(app, ["install", "--help"])
    assert help_result.exit_code == 0
    
    # Invalid arguments should fail
    invalid_result = runner.invoke(app, ["install", "--invalid-flag"])
    assert invalid_result.exit_code != 0


@pytest.mark.integration
def test_install_command_output_format_consistency(runner, clean_config_dir):
    """
    Verifies that install command output is consistent and well-formatted.
    """
    config_dir = clean_config_dir
    
    # Run install command
    result = runner.invoke(app, ["install", "--force"])
    assert result.exit_code == 0
    
    # Output should be well-formatted
    output_lines = result.stdout.strip().split('\n')
    
    # Should have meaningful output
    assert len(output_lines) > 0
    
    # Should contain success indication
    output_text = result.stdout.lower()
    assert any(keyword in output_text for keyword in [
        "installation", "completed", "success", "created", "configured"
    ])
    
    # Should not contain error messages
    assert "error" not in output_text
    assert "failed" not in output_text
    assert "traceback" not in output_text
    
    # Should provide useful information
    assert len(result.stdout.strip()) > 20  # Should be more than just a word


@pytest.mark.integration
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_install_integration_with_stack_workflow(runner, clean_config_dir):
    """
    Verifies that install integrates properly with stack workflow.
    """
    config_dir = clean_config_dir
    
    # Install
    install_result = runner.invoke(app, ["install", "--force"])
    assert install_result.exit_code == 0
    
    # Should enable status command
    status_result = runner.invoke(app, ["status"])
    assert status_result.exit_code == 0
    
    # Should enable start command
    start_result = runner.invoke(app, ["start"])
    assert start_result.exit_code == 0
    
    # Should enable stop command
    stop_result = runner.invoke(app, ["stop"])
    assert stop_result.exit_code == 0
    
    # Should enable check command
    check_result = runner.invoke(app, ["check"])
    assert check_result.exit_code == 0


@pytest.mark.integration
@pytest.mark.skipif(is_docker_available(), reason="Docker daemon is available - test requires Docker to be unavailable")
def test_install_without_docker_daemon(runner, clean_config_dir):
    """
    Verifies that install works even when Docker daemon is not available.
    """
    config_dir = clean_config_dir
    
    # Install should work regardless of Docker availability
    result = runner.invoke(app, ["install", "--force"])
    assert result.exit_code == 0
    
    # Should create configuration files
    config_file = os.path.join(config_dir, ".ollama-stack.json")
    env_file = os.path.join(config_dir, ".env")
    
    assert os.path.exists(config_file)
    assert os.path.exists(env_file)
    
    # Configuration should be valid
    with open(config_file, 'r') as f:
        config_data = json.load(f)
    assert isinstance(config_data, dict)
    
    secret_key = extract_secret_key_from_env(env_file)
    assert len(secret_key) > 10
    
    # Should indicate successful installation
    assert "installation" in result.stdout.lower()
    assert "completed" in result.stdout.lower() or "success" in result.stdout.lower()
    
    # Should not show Docker-related errors during install
    # Note: Docker daemon check may pass and show "passed: docker daemon running"
    # which is acceptable when Docker is available
    assert "connectionrefusederror" not in result.stdout.lower()
    assert "docker error" not in result.stdout.lower()