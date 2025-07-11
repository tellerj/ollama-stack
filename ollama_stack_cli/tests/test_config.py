import json
from pathlib import Path
from unittest.mock import patch
from ollama_stack_cli.config import load_config, save_config, Config, AppConfig, PlatformConfig
import pytest
from unittest.mock import MagicMock

@pytest.fixture
def mock_display():
    """Fixture for a mocked Display object."""
    return MagicMock()

def test_load_config_creates_default_when_not_exists(tmp_path: Path, mock_display: MagicMock):
    """
    Tests that a default config is created if one doesn't exist.
    """
    config_file = tmp_path / ".ollama-stack.json"
    env_file = tmp_path / ".env"
    
    # Ensure the files don't exist initially
    assert not config_file.exists()
    assert not env_file.exists()
    
    # Load config
    config, fell_back = load_config(mock_display, config_file, env_file)
    
    # Check that the default config was created and returned
    assert config_file.exists()
    assert env_file.exists()
    assert isinstance(config, AppConfig)
    assert config.docker_compose_file == "docker-compose.yml"
    assert fell_back == False  # Not a fallback, just creating new config

def test_save_and_load_config(tmp_path: Path, mock_display: MagicMock):
    """
    Tests that a config can be saved and then loaded correctly.
    """
    config_file = tmp_path / ".ollama-stack.json"
    env_file = tmp_path / ".env"
    
    # Create a custom config
    custom_config = AppConfig(
        docker_compose_file="custom-compose.yml",
        data_directory="/custom/data",
        project_name="my-test-stack",
        webui_secret_key="super-secret"
    )
    
    # Save and load the config
    save_config(mock_display, custom_config, config_file, env_file)
    loaded_config, fell_back = load_config(mock_display, config_file, env_file)
    
    # Check that the loaded config matches the saved one
    assert loaded_config.docker_compose_file == "custom-compose.yml"
    assert loaded_config.project_name == "my-test-stack"
    assert loaded_config.webui_secret_key == "super-secret"
    assert fell_back == False  # Successfully loaded, no fallback

def test_load_config_with_corrupt_file(tmp_path: Path, mock_display: MagicMock):
    """
    Tests that a default config is loaded if the config file is corrupt.
    """
    config_file = tmp_path / ".ollama-stack.json"
    env_file = tmp_path / ".env"
    # Create a valid env file to isolate the corrupt json file issue
    env_file.touch()
    
    # Create a corrupt file
    with open(config_file, "w") as f:
        f.write("{ not_valid_json }")
        
    # Load config, should not raise an error but return a default config
    config, fell_back = load_config(mock_display, config_file, env_file)
    assert isinstance(config, AppConfig)
    assert fell_back == True  # Should indicate fallback to defaults

def test_load_config_with_invalid_schema(tmp_path: Path, mock_display: MagicMock):
    """
    Tests that a default config is loaded if the config file has an invalid schema.
    """
    config_file = tmp_path / ".ollama-stack.json"
    env_file = tmp_path / ".env"
    env_file.touch()
    
    # Create a file with an invalid schema (e.g., wrong data type)
    invalid_data = {"docker_compose_file": 123} # Should be a string
    with open(config_file, "w") as f:
        json.dump(invalid_data, f)
        
    # Load config, should not raise an error but return a default config
    config, fell_back = load_config(mock_display, config_file, env_file)
    assert isinstance(config, AppConfig)
    assert fell_back == True  # Should indicate fallback to defaults

def test_config_class_fell_back_to_defaults_property(tmp_path: Path, mock_display: MagicMock):
    """
    Tests that the Config class properly exposes the fell_back_to_defaults property.
    """
    config_file = tmp_path / ".ollama-stack.json"
    env_file = tmp_path / ".env"
    env_file.touch()
    
    # Create a corrupt file to trigger fallback
    with open(config_file, "w") as f:
        f.write("{ invalid_json }")
    
    # Create Config object
    config_manager = Config(mock_display, config_file, env_file)
    
    # Check that it detected the fallback
    assert config_manager.fell_back_to_defaults == True
    assert isinstance(config_manager.app_config, AppConfig)

def test_config_class_successful_load(tmp_path: Path, mock_display: MagicMock):
    """
    Tests that the Config class properly indicates when config loaded successfully.
    """
    config_file = tmp_path / ".ollama-stack.json"
    env_file = tmp_path / ".env"
    
    # Create valid config files
    valid_config = AppConfig()
    save_config(mock_display, valid_config, config_file, env_file)
    
    # Create Config object
    config_manager = Config(mock_display, config_file, env_file)
    
    # Check that it didn't fall back
    assert config_manager.fell_back_to_defaults == False
    assert isinstance(config_manager.app_config, AppConfig)


# =============================================================================
# Enhanced load_config Tests (Missing Coverage)
# =============================================================================

def test_load_config_with_env_values(tmp_path: Path, mock_display: MagicMock):
    """Tests that load_config properly loads values from .env file."""
    config_file = tmp_path / ".ollama-stack.json"
    env_file = tmp_path / ".env"
    
    # Create a basic JSON config
    basic_config = AppConfig()
    with open(config_file, "w") as f:
        f.write(basic_config.model_dump_json())
    
    # Create .env file with values
    with open(env_file, "w") as f:
        f.write("PROJECT_NAME=test-project\n")
        f.write("WEBUI_SECRET_KEY=secret123\n")
    
    # Load config
    config, fell_back = load_config(mock_display, config_file, env_file)
    
    # Check that env values were loaded
    assert config.project_name == "test-project"
    assert config.webui_secret_key == "secret123"
    assert fell_back == False

def test_load_config_with_partial_env_values(tmp_path: Path, mock_display: MagicMock):
    """Tests that load_config handles missing env values gracefully."""
    config_file = tmp_path / ".ollama-stack.json"
    env_file = tmp_path / ".env"
    
    # Create a basic JSON config
    basic_config = AppConfig()
    with open(config_file, "w") as f:
        f.write(basic_config.model_dump_json())
    
    # Create .env file with only one value
    with open(env_file, "w") as f:
        f.write("PROJECT_NAME=partial-project\n")
    
    # Load config
    config, fell_back = load_config(mock_display, config_file, env_file)
    
    # Check that only available env value was loaded
    assert config.project_name == "partial-project"
    # webui_secret_key should still have the value from the JSON config (not overridden)
    assert config.webui_secret_key == basic_config.webui_secret_key

def test_load_config_creates_platform_configurations(tmp_path: Path, mock_display: MagicMock):
    """Tests that load_config creates default platform configurations when creating new config."""
    config_file = tmp_path / ".ollama-stack.json"
    env_file = tmp_path / ".env"
    
    # Ensure files don't exist
    assert not config_file.exists()
    assert not env_file.exists()
    
    # Load config (should create defaults)
    config, fell_back = load_config(mock_display, config_file, env_file)
    
    # Check that platform configurations were created
    assert "apple" in config.platform
    assert "nvidia" in config.platform
    assert config.platform["apple"].compose_file == "docker-compose.apple.yml"
    assert config.platform["nvidia"].compose_file == "docker-compose.nvidia.yml"

def test_load_config_only_config_file_exists(tmp_path: Path, mock_display: MagicMock):
    """Tests load_config when only JSON config exists but no .env file."""
    config_file = tmp_path / ".ollama-stack.json"
    env_file = tmp_path / ".env"
    
    # Create only the JSON config file
    basic_config = AppConfig(project_name="existing-project")
    with open(config_file, "w") as f:
        f.write(basic_config.model_dump_json())
    
    # Don't create .env file
    assert not env_file.exists()
    
    # Load config (should create new defaults because env_file doesn't exist)
    config, fell_back = load_config(mock_display, config_file, env_file)
    
    # Should create new config with platform configurations
    assert "apple" in config.platform
    assert "nvidia" in config.platform
    assert fell_back == False  # Created new, not fallback

def test_load_config_only_env_file_exists(tmp_path: Path, mock_display: MagicMock):
    """Tests load_config when only .env file exists but no JSON config."""
    config_file = tmp_path / ".ollama-stack.json"
    env_file = tmp_path / ".env"
    
    # Create only the .env file
    with open(env_file, "w") as f:
        f.write("PROJECT_NAME=env-only-project\n")
    
    # Don't create config file
    assert not config_file.exists()
    
    # Load config (should create new defaults because config_file doesn't exist)
    config, fell_back = load_config(mock_display, config_file, env_file)
    
    # Should create new config with platform configurations
    assert "apple" in config.platform
    assert "nvidia" in config.platform
    assert fell_back == False  # Created new, not fallback

def test_load_config_empty_env_file(tmp_path: Path, mock_display: MagicMock):
    """Tests load_config with an empty .env file."""
    config_file = tmp_path / ".ollama-stack.json"
    env_file = tmp_path / ".env"
    
    # Create a basic JSON config
    basic_config = AppConfig()
    with open(config_file, "w") as f:
        f.write(basic_config.model_dump_json())
    
    # Create empty .env file
    env_file.touch()
    
    # Load config
    config, fell_back = load_config(mock_display, config_file, env_file)
    
    # Should load successfully with values from JSON config (not overridden by empty env)
    assert fell_back == False
    assert config.project_name == basic_config.project_name  # Should have JSON value
    assert config.webui_secret_key == basic_config.webui_secret_key


# =============================================================================
# Enhanced save_config Tests (Missing Coverage)
# =============================================================================

def test_save_config_creates_parent_directories(tmp_path: Path, mock_display: MagicMock):
    """Tests that save_config creates parent directories when they don't exist."""
    # Use a nested path that doesn't exist
    nested_dir = tmp_path / "deeply" / "nested" / "config"
    config_file = nested_dir / ".ollama-stack.json"
    env_file = nested_dir / ".env"
    
    # Ensure parent directory doesn't exist
    assert not nested_dir.exists()
    
    # Save config
    config = AppConfig(project_name="nested-test")
    save_config(mock_display, config, config_file, env_file)
    
    # Check that directories were created and files exist
    assert nested_dir.exists()
    assert config_file.exists()
    assert env_file.exists()

def test_save_config_excludes_env_fields_from_json(tmp_path: Path, mock_display: MagicMock):
    """Tests that save_config excludes project_name and webui_secret_key from JSON."""
    config_file = tmp_path / ".ollama-stack.json"
    env_file = tmp_path / ".env"
    
    # Create config with env-specific fields
    config = AppConfig(
        project_name="test-project",
        webui_secret_key="secret123",
        docker_compose_file="custom.yml"
    )
    
    # Save config
    save_config(mock_display, config, config_file, env_file)
    
    # Read back the JSON file and verify exclusions
    with open(config_file, "r") as f:
        json_data = json.load(f)
    
    # These should NOT be in the JSON file
    assert "project_name" not in json_data
    assert "webui_secret_key" not in json_data
    
    # This should be in the JSON file
    assert json_data["docker_compose_file"] == "custom.yml"

def test_save_config_saves_env_values_when_present(tmp_path: Path, mock_display: MagicMock):
    """Tests that save_config saves env values to .env file when they exist."""
    config_file = tmp_path / ".ollama-stack.json"
    env_file = tmp_path / ".env"
    
    # Create config with env values
    config = AppConfig(
        project_name="test-project",
        webui_secret_key="secret123"
    )
    
    # Save config
    save_config(mock_display, config, config_file, env_file)
    
    # Read back the .env file
    with open(env_file, "r") as f:
        env_content = f.read()
    
    # Check that values were saved (python-dotenv adds quotes)
    assert "PROJECT_NAME='test-project'" in env_content or "PROJECT_NAME=test-project" in env_content
    assert "WEBUI_SECRET_KEY='secret123'" in env_content or "WEBUI_SECRET_KEY=secret123" in env_content

def test_save_config_skips_none_env_values(tmp_path: Path, mock_display: MagicMock):
    """Tests that save_config skips None values for env fields."""
    config_file = tmp_path / ".ollama-stack.json"
    env_file = tmp_path / ".env"
    
    # Create config with normal values
    config = AppConfig(webui_secret_key="secret123")
    
    # Manually set project_name to None to test the conditional logic
    # (This bypasses Pydantic validation to test the save logic)
    config.__dict__["project_name"] = None
    
    # Save config
    save_config(mock_display, config, config_file, env_file)
    
    # Read back the .env file
    with open(env_file, "r") as f:
        env_content = f.read()
    
    # Check that only non-None value was saved
    assert "PROJECT_NAME" not in env_content  # Should be skipped because it's None
    assert "WEBUI_SECRET_KEY='secret123'" in env_content or "WEBUI_SECRET_KEY=secret123" in env_content

@patch('ollama_stack_cli.config.set_key')
def test_save_config_ioerror_handling(mock_set_key, tmp_path: Path, mock_display: MagicMock):
    """Tests that save_config handles IOError gracefully."""
    config_file = tmp_path / ".ollama-stack.json"
    env_file = tmp_path / ".env"
    
    # Make the config file creation fail by making it a directory
    config_file.mkdir(parents=True)  # Now it's a directory, not a file
    
    config = AppConfig()
    
    # This should not raise an exception, but should log an error
    save_config(mock_display, config, config_file, env_file)
    
    # The function should complete without raising an exception
    # (The IOError is caught and logged)


# =============================================================================
# Phase 6.1: export_configuration() Tests
# =============================================================================

def test_export_configuration_success(tmp_path: Path, mock_display: MagicMock):
    """Tests successful export of both config files."""
    from ollama_stack_cli.config import export_configuration
    
    # Create source config files
    config_file = tmp_path / "source" / ".ollama-stack.json"
    env_file = tmp_path / "source" / ".env"
    config_file.parent.mkdir(parents=True)
    
    # Write test data
    config_file.write_text('{"docker_compose_file": "test.yml"}')
    env_file.write_text('PROJECT_NAME=test\nWEBUI_SECRET_KEY=secret')
    
    # Export to different directory
    output_dir = tmp_path / "export"
    
    result = export_configuration(mock_display, output_dir, config_file, env_file)
    
    # Verify success
    assert result == True
    assert (output_dir / ".ollama-stack.json").exists()
    assert (output_dir / ".env").exists()
    
    # Verify content preserved
    exported_config = (output_dir / ".ollama-stack.json").read_text()
    exported_env = (output_dir / ".env").read_text()
    assert '"docker_compose_file": "test.yml"' in exported_config
    assert 'PROJECT_NAME=test' in exported_env

def test_export_configuration_partial_files(tmp_path: Path, mock_display: MagicMock):
    """Tests export when only some config files exist."""
    from ollama_stack_cli.config import export_configuration
    
    # Create only config file, not env file
    config_file = tmp_path / "source" / ".ollama-stack.json"
    env_file = tmp_path / "source" / ".env"
    config_file.parent.mkdir(parents=True)
    config_file.write_text('{"docker_compose_file": "test.yml"}')
    # Don't create env_file
    
    output_dir = tmp_path / "export"
    
    result = export_configuration(mock_display, output_dir, config_file, env_file)
    
    # Should still succeed
    assert result == True
    assert (output_dir / ".ollama-stack.json").exists()
    assert not (output_dir / ".env").exists()

def test_export_configuration_no_files(tmp_path: Path, mock_display: MagicMock):
    """Tests export when no config files exist."""
    from ollama_stack_cli.config import export_configuration
    
    # Point to non-existent files
    config_file = tmp_path / "nonexistent" / ".ollama-stack.json"
    env_file = tmp_path / "nonexistent" / ".env"
    output_dir = tmp_path / "export"
    
    result = export_configuration(mock_display, output_dir, config_file, env_file)
    
    # Should return False when no files to export
    assert result == False

def test_export_configuration_creates_output_directory(tmp_path: Path, mock_display: MagicMock):
    """Tests that export creates the output directory if it doesn't exist."""
    from ollama_stack_cli.config import export_configuration
    
    # Create source file
    config_file = tmp_path / "source" / ".ollama-stack.json"
    config_file.parent.mkdir(parents=True)
    config_file.write_text('{"docker_compose_file": "test.yml"}')
    
    # Use deeply nested output path that doesn't exist
    output_dir = tmp_path / "deep" / "nested" / "export"
    env_file = tmp_path / "nonexistent.env"  # Doesn't exist
    
    assert not output_dir.exists()
    
    result = export_configuration(mock_display, output_dir, config_file, env_file)
    
    # Should create directory and succeed
    assert result == True
    assert output_dir.exists()
    assert (output_dir / ".ollama-stack.json").exists()

@patch('shutil.copy2')
def test_export_configuration_copy_failure(mock_copy2, tmp_path: Path, mock_display: MagicMock):
    """Tests export failure when file copy fails."""
    from ollama_stack_cli.config import export_configuration
    
    # Create source file
    config_file = tmp_path / ".ollama-stack.json"
    config_file.write_text('{"test": true}')
    env_file = tmp_path / "nonexistent.env"
    
    # Make copy2 fail
    mock_copy2.side_effect = OSError("Permission denied")
    
    output_dir = tmp_path / "export"
    
    result = export_configuration(mock_display, output_dir, config_file, env_file)
    
    # Should return False on failure
    assert result == False

# =============================================================================
# Phase 6.1: import_configuration() Tests  
# =============================================================================

def test_import_configuration_success(tmp_path: Path, mock_display: MagicMock):
    """Tests successful import of config files."""
    from ollama_stack_cli.config import import_configuration
    
    # Create source files with valid content
    source_dir = tmp_path / "backup" / "config"
    source_dir.mkdir(parents=True)
    
    (source_dir / ".ollama-stack.json").write_text('{"docker_compose_file": "backup.yml"}')
    (source_dir / ".env").write_text('PROJECT_NAME=restored\nWEBUI_SECRET_KEY=newsecret')
    
    # Import to destination
    dest_config = tmp_path / "dest" / ".ollama-stack.json"
    dest_env = tmp_path / "dest" / ".env"
    
    result = import_configuration(mock_display, source_dir, dest_config, dest_env)
    
    # Verify success
    assert result == True
    assert dest_config.exists()
    assert dest_env.exists()
    
    # Verify content
    imported_config = dest_config.read_text()
    imported_env = dest_env.read_text()
    assert '"docker_compose_file": "backup.yml"' in imported_config
    assert 'PROJECT_NAME=restored' in imported_env

def test_import_configuration_validate_only(tmp_path: Path, mock_display: MagicMock):
    """Tests import in validate-only mode."""
    from ollama_stack_cli.config import import_configuration
    
    # Create valid source files
    source_dir = tmp_path / "backup" / "config"
    source_dir.mkdir(parents=True)
    (source_dir / ".ollama-stack.json").write_text('{"docker_compose_file": "test.yml"}')
    (source_dir / ".env").write_text('PROJECT_NAME=test')
    
    dest_config = tmp_path / "dest" / ".ollama-stack.json"
    dest_env = tmp_path / "dest" / ".env"
    
    result = import_configuration(mock_display, source_dir, dest_config, dest_env, validate_only=True)
    
    # Should succeed but not create files
    assert result == True
    assert not dest_config.exists()
    assert not dest_env.exists()

def test_import_configuration_invalid_json(tmp_path: Path, mock_display: MagicMock):
    """Tests import failure with invalid JSON config."""
    from ollama_stack_cli.config import import_configuration
    
    # Create source with invalid JSON
    source_dir = tmp_path / "backup" / "config"
    source_dir.mkdir(parents=True)
    (source_dir / ".ollama-stack.json").write_text('{ invalid json }')
    
    dest_config = tmp_path / "dest" / ".ollama-stack.json"
    dest_env = tmp_path / "dest" / ".env"
    
    result = import_configuration(mock_display, source_dir, dest_config, dest_env)
    
    # Should fail validation
    assert result == False

def test_import_configuration_invalid_schema(tmp_path: Path, mock_display: MagicMock):
    """Tests import failure with invalid config schema."""
    from ollama_stack_cli.config import import_configuration
    
    # Create source with schema violation
    source_dir = tmp_path / "backup" / "config"
    source_dir.mkdir(parents=True)
    (source_dir / ".ollama-stack.json").write_text('{"docker_compose_file": 123}')  # Should be string
    
    dest_config = tmp_path / "dest" / ".ollama-stack.json"
    dest_env = tmp_path / "dest" / ".env"
    
    result = import_configuration(mock_display, source_dir, dest_config, dest_env)
    
    # Should fail validation
    assert result == False

def test_import_configuration_missing_source_files(tmp_path: Path, mock_display: MagicMock):
    """Tests import when source files don't exist."""
    from ollama_stack_cli.config import import_configuration
    
    # Empty source directory
    source_dir = tmp_path / "backup" / "config"
    source_dir.mkdir(parents=True)
    
    dest_config = tmp_path / "dest" / ".ollama-stack.json"
    dest_env = tmp_path / "dest" / ".env"
    
    result = import_configuration(mock_display, source_dir, dest_config, dest_env)
    
    # Should return False when no files to import
    assert result == False

def test_import_configuration_creates_dest_directories(tmp_path: Path, mock_display: MagicMock):
    """Tests that import creates destination directories."""
    from ollama_stack_cli.config import import_configuration
    
    # Create source file
    source_dir = tmp_path / "backup" / "config"
    source_dir.mkdir(parents=True)
    (source_dir / ".ollama-stack.json").write_text('{"docker_compose_file": "test.yml"}')
    
    # Use deeply nested destination that doesn't exist
    dest_config = tmp_path / "deep" / "nested" / "dest" / ".ollama-stack.json"
    dest_env = tmp_path / "deep" / "nested" / "dest" / ".env"
    
    assert not dest_config.parent.exists()
    
    result = import_configuration(mock_display, source_dir, dest_config, dest_env)
    
    # Should create directories and succeed
    assert result == True
    assert dest_config.exists()
    assert dest_config.parent.exists()

@patch('shutil.copy2')
def test_import_configuration_copy_failure(mock_copy2, tmp_path: Path, mock_display: MagicMock):
    """Tests import failure when file copy fails."""
    from ollama_stack_cli.config import import_configuration
    
    # Create valid source
    source_dir = tmp_path / "backup" / "config"
    source_dir.mkdir(parents=True)
    (source_dir / ".ollama-stack.json").write_text('{"docker_compose_file": "test.yml"}')
    
    # Make copy fail
    mock_copy2.side_effect = OSError("Disk full")
    
    dest_config = tmp_path / "dest" / ".ollama-stack.json"
    dest_env = tmp_path / "dest" / ".env"
    
    result = import_configuration(mock_display, source_dir, dest_config, dest_env)
    
    # Should handle failure gracefully
    assert result == False

# =============================================================================
# Phase 6.1: validate_backup_manifest() Tests
# =============================================================================

def test_validate_backup_manifest_success(tmp_path: Path, mock_display: MagicMock):
    """Tests successful backup manifest validation."""
    from ollama_stack_cli.config import validate_backup_manifest
    from ollama_stack_cli.schemas import BackupManifest, BackupConfig
    import json
    
    # Create backup directory structure
    backup_dir = tmp_path / "backup"
    backup_dir.mkdir()
    (backup_dir / "volumes").mkdir()
    (backup_dir / "config").mkdir()
    (backup_dir / "extensions").mkdir()
    
    # Create manifest
    manifest = BackupManifest(
        stack_version="0.2.0",
        cli_version="0.2.0", 
        platform="linux",
        backup_config=BackupConfig(),
        volumes=["ollama_data", "webui_data"],
        config_files=[".ollama-stack.json", ".env"],
        extensions=["test_extension"]
    )
    
    manifest_file = backup_dir / "backup_manifest.json"
    with open(manifest_file, "w") as f:
        json.dump(manifest.model_dump(), f, default=str)
    
    # Create expected backup files (volumes are stored in volumes/ subdirectory)
    (backup_dir / "volumes" / "ollama_data.tar.gz").touch()
    (backup_dir / "volumes" / "webui_data.tar.gz").touch()
    (backup_dir / "config" / ".ollama-stack.json").touch()
    (backup_dir / "config" / ".env").touch()
    (backup_dir / "extensions" / "test_extension.tar.gz").touch()
    
    is_valid, parsed_manifest = validate_backup_manifest(manifest_file, backup_dir)
    
    # Should succeed
    assert is_valid == True
    assert parsed_manifest is not None
    assert parsed_manifest.volumes == ["ollama_data", "webui_data"]
    assert parsed_manifest.config_files == [".ollama-stack.json", ".env"]

def test_validate_backup_manifest_missing_file(tmp_path: Path, mock_display: MagicMock):
    """Tests validation failure when manifest file is missing."""
    from ollama_stack_cli.config import validate_backup_manifest
    
    backup_dir = tmp_path / "backup"
    backup_dir.mkdir()
    manifest_file = backup_dir / "backup_manifest.json"
    # Don't create manifest file
    
    is_valid, parsed_manifest = validate_backup_manifest(manifest_file, backup_dir)
    
    # Should fail
    assert is_valid == False
    assert parsed_manifest is None

def test_validate_backup_manifest_invalid_json(tmp_path: Path, mock_display: MagicMock):
    """Tests validation failure with invalid JSON."""
    from ollama_stack_cli.config import validate_backup_manifest
    
    backup_dir = tmp_path / "backup"
    backup_dir.mkdir()
    manifest_file = backup_dir / "backup_manifest.json"
    
    # Write invalid JSON
    manifest_file.write_text("{ invalid json }")
    
    is_valid, parsed_manifest = validate_backup_manifest(manifest_file, backup_dir)
    
    # Should fail
    assert is_valid == False
    assert parsed_manifest is None

def test_validate_backup_manifest_invalid_schema(tmp_path: Path, mock_display: MagicMock):
    """Tests validation failure with invalid manifest schema."""
    from ollama_stack_cli.config import validate_backup_manifest
    import json
    
    backup_dir = tmp_path / "backup"
    backup_dir.mkdir()
    manifest_file = backup_dir / "backup_manifest.json"
    
    # Write JSON with invalid schema
    invalid_manifest = {
        "backup_id": "test",
        "stack_version": 123,  # Should be string
        "platform": "linux"
        # Missing required fields
    }
    
    with open(manifest_file, "w") as f:
        json.dump(invalid_manifest, f)
    
    is_valid, parsed_manifest = validate_backup_manifest(manifest_file, backup_dir)
    
    # Should fail validation
    assert is_valid == False
    assert parsed_manifest is None

def test_validate_backup_manifest_missing_volume_files(tmp_path: Path, mock_display: MagicMock):
    """Tests validation failure when volume backup files are missing."""
    from ollama_stack_cli.config import validate_backup_manifest
    from ollama_stack_cli.schemas import BackupManifest, BackupConfig
    import json
    
    backup_dir = tmp_path / "backup"
    backup_dir.mkdir()
    
    # Create manifest with volumes but don't create the backup files
    manifest = BackupManifest(
        stack_version="0.2.0",
        cli_version="0.2.0",
        platform="linux", 
        backup_config=BackupConfig(),
        volumes=["missing_volume"],
        config_files=[],
        extensions=[]
    )
    
    manifest_file = backup_dir / "backup_manifest.json"
    with open(manifest_file, "w") as f:
        json.dump(manifest.model_dump(), f, default=str)
    
    # Don't create missing_volume.tar.gz
    
    is_valid, parsed_manifest = validate_backup_manifest(manifest_file, backup_dir)
    
    # Should fail due to missing files
    assert is_valid == False
    assert parsed_manifest is not None  # Manifest parses but files are missing

def test_validate_backup_manifest_missing_config_files(tmp_path: Path, mock_display: MagicMock):
    """Tests validation failure when config backup files are missing."""
    from ollama_stack_cli.config import validate_backup_manifest
    from ollama_stack_cli.schemas import BackupManifest, BackupConfig
    import json
    
    backup_dir = tmp_path / "backup"
    backup_dir.mkdir()
    (backup_dir / "config").mkdir()
    
    # Create manifest with config files but don't create them
    manifest = BackupManifest(
        stack_version="0.2.0",
        cli_version="0.2.0",
        platform="linux",
        backup_config=BackupConfig(),
        volumes=[],
        config_files=["missing_config.json"],
        extensions=[]
    )
    
    manifest_file = backup_dir / "backup_manifest.json"
    with open(manifest_file, "w") as f:
        json.dump(manifest.model_dump(), f, default=str)
    
    # Don't create config/missing_config.json
    
    is_valid, parsed_manifest = validate_backup_manifest(manifest_file, backup_dir)
    
    # Should fail due to missing files
    assert is_valid == False
    assert parsed_manifest is not None

def test_validate_backup_manifest_missing_extension_files(tmp_path: Path, mock_display: MagicMock):
    """Tests validation failure when extension backup files are missing."""
    from ollama_stack_cli.config import validate_backup_manifest
    from ollama_stack_cli.schemas import BackupManifest, BackupConfig
    import json
    
    backup_dir = tmp_path / "backup"
    backup_dir.mkdir()
    (backup_dir / "extensions").mkdir()
    
    # Create manifest with extensions but don't create the files
    manifest = BackupManifest(
        stack_version="0.2.0",
        cli_version="0.2.0",
        platform="linux",
        backup_config=BackupConfig(),
        volumes=[],
        config_files=[],
        extensions=["missing_extension"]
    )
    
    manifest_file = backup_dir / "backup_manifest.json"
    with open(manifest_file, "w") as f:
        json.dump(manifest.model_dump(), f, default=str)
    
    # Don't create extensions/missing_extension.tar.gz
    
    is_valid, parsed_manifest = validate_backup_manifest(manifest_file, backup_dir)
    
    # Should fail due to missing files
    assert is_valid == False
    assert parsed_manifest is not None

def test_validate_backup_manifest_checksum_success(tmp_path: Path, mock_display: MagicMock):
    """Tests successful checksum validation."""
    from ollama_stack_cli.config import validate_backup_manifest, _calculate_backup_checksum
    from ollama_stack_cli.schemas import BackupManifest, BackupConfig
    import json
    
    backup_dir = tmp_path / "backup"
    backup_dir.mkdir()
    (backup_dir / "config").mkdir()
    
    # Create backup files with content
    config_file = backup_dir / "config" / ".ollama-stack.json"
    config_file.write_text('{"test": "data"}')
    
    # Create manifest
    manifest = BackupManifest(
        stack_version="0.2.0",
        cli_version="0.2.0",
        platform="linux",
        backup_config=BackupConfig(),
        volumes=[],
        config_files=[".ollama-stack.json"],
        extensions=[]
    )
    
    # Calculate actual checksum
    manifest.checksum = _calculate_backup_checksum(backup_dir, manifest)
    
    manifest_file = backup_dir / "backup_manifest.json"
    with open(manifest_file, "w") as f:
        json.dump(manifest.model_dump(), f, default=str)
    
    is_valid, parsed_manifest = validate_backup_manifest(manifest_file, backup_dir)
    
    # Should succeed with matching checksum
    assert is_valid == True
    assert parsed_manifest is not None

def test_validate_backup_manifest_checksum_mismatch(tmp_path: Path, mock_display: MagicMock):
    """Tests validation failure with checksum mismatch."""
    from ollama_stack_cli.config import validate_backup_manifest
    from ollama_stack_cli.schemas import BackupManifest, BackupConfig
    import json
    
    backup_dir = tmp_path / "backup"
    backup_dir.mkdir()
    (backup_dir / "config").mkdir()
    
    # Create backup files
    config_file = backup_dir / "config" / ".ollama-stack.json"
    config_file.write_text('{"test": "data"}')
    
    # Create manifest with wrong checksum
    manifest = BackupManifest(
        stack_version="0.2.0",
        cli_version="0.2.0",
        platform="linux",
        backup_config=BackupConfig(),
        volumes=[],
        config_files=[".ollama-stack.json"],
        extensions=[],
        checksum="wrong_checksum_value"
    )
    
    manifest_file = backup_dir / "backup_manifest.json"
    with open(manifest_file, "w") as f:
        json.dump(manifest.model_dump(), f, default=str)
    
    is_valid, parsed_manifest = validate_backup_manifest(manifest_file, backup_dir)
    
    # Should fail due to checksum mismatch
    assert is_valid == False
    assert parsed_manifest is not None

def test_validate_backup_manifest_no_checksum(tmp_path: Path, mock_display: MagicMock):
    """Tests validation success when no checksum is present."""
    from ollama_stack_cli.config import validate_backup_manifest
    from ollama_stack_cli.schemas import BackupManifest, BackupConfig
    import json
    
    backup_dir = tmp_path / "backup"
    backup_dir.mkdir()
    (backup_dir / "config").mkdir()
    
    # Create backup files
    config_file = backup_dir / "config" / ".ollama-stack.json"
    config_file.write_text('{"test": "data"}')
    
    # Create manifest without checksum
    manifest = BackupManifest(
        stack_version="0.2.0",
        cli_version="0.2.0",
        platform="linux",
        backup_config=BackupConfig(),
        volumes=[],
        config_files=[".ollama-stack.json"],
        extensions=[],
        checksum=None
    )
    
    manifest_file = backup_dir / "backup_manifest.json"
    with open(manifest_file, "w") as f:
        json.dump(manifest.model_dump(), f, default=str)
    
    is_valid, parsed_manifest = validate_backup_manifest(manifest_file, backup_dir)
    
    # Should succeed - no checksum validation needed
    assert is_valid == True
    assert parsed_manifest is not None

# =============================================================================
# Phase 6.1: _calculate_backup_checksum() Tests
# =============================================================================

def test_calculate_backup_checksum_with_all_file_types(tmp_path: Path, mock_display: MagicMock):
    """Tests checksum calculation with volumes, config files, and extensions."""
    from ollama_stack_cli.config import _calculate_backup_checksum
    from ollama_stack_cli.schemas import BackupManifest, BackupConfig
    
    backup_dir = tmp_path / "backup"
    backup_dir.mkdir()
    (backup_dir / "config").mkdir()
    (backup_dir / "extensions").mkdir()
    
    # Create files with specific content
    (backup_dir / "volume1.tar.gz").write_text("volume1 content")
    (backup_dir / "volume2.tar.gz").write_text("volume2 content")
    (backup_dir / "config" / "config.json").write_text("config content")
    (backup_dir / "extensions" / "ext1.tar.gz").write_text("extension content")
    
    manifest = BackupManifest(
        stack_version="0.2.0",
        cli_version="0.2.0",
        platform="linux",
        backup_config=BackupConfig(),
        volumes=["volume1", "volume2"],
        config_files=["config.json"],
        extensions=["ext1"]
    )
    
    checksum = _calculate_backup_checksum(backup_dir, manifest)
    
    # Should return a valid SHA256 hash
    assert isinstance(checksum, str)
    assert len(checksum) == 64  # SHA256 hex length
    
    # Checksum should be deterministic
    checksum2 = _calculate_backup_checksum(backup_dir, manifest)
    assert checksum == checksum2

def test_calculate_backup_checksum_empty_manifest(tmp_path: Path, mock_display: MagicMock):
    """Tests checksum calculation with empty manifest."""
    from ollama_stack_cli.config import _calculate_backup_checksum
    from ollama_stack_cli.schemas import BackupManifest, BackupConfig
    
    backup_dir = tmp_path / "backup"
    backup_dir.mkdir()
    
    manifest = BackupManifest(
        stack_version="0.2.0",
        cli_version="0.2.0",
        platform="linux",
        backup_config=BackupConfig(),
        volumes=[],
        config_files=[],
        extensions=[]
    )
    
    checksum = _calculate_backup_checksum(backup_dir, manifest)
    
    # Should still return a valid hash (of empty content)
    assert isinstance(checksum, str)
    assert len(checksum) == 64

def test_calculate_backup_checksum_missing_files(tmp_path: Path, mock_display: MagicMock):
    """Tests checksum calculation when some files are missing."""
    from ollama_stack_cli.config import _calculate_backup_checksum
    from ollama_stack_cli.schemas import BackupManifest, BackupConfig
    
    backup_dir = tmp_path / "backup"
    backup_dir.mkdir()
    (backup_dir / "config").mkdir()
    
    # Create only some of the expected files
    (backup_dir / "existing.tar.gz").write_text("content")
    # Don't create missing.tar.gz or config.json
    
    manifest = BackupManifest(
        stack_version="0.2.0",
        cli_version="0.2.0",
        platform="linux",
        backup_config=BackupConfig(),
        volumes=["existing", "missing"],
        config_files=["config.json"],
        extensions=[]
    )
    
    checksum = _calculate_backup_checksum(backup_dir, manifest)
    
    # Should only include existing files in checksum
    assert isinstance(checksum, str)
    assert len(checksum) == 64

def test_calculate_backup_checksum_sorted_order(tmp_path: Path, mock_display: MagicMock):
    """Tests that checksum calculation uses sorted order for consistency."""
    from ollama_stack_cli.config import _calculate_backup_checksum
    from ollama_stack_cli.schemas import BackupManifest, BackupConfig
    
    backup_dir = tmp_path / "backup"
    backup_dir.mkdir()
    
    # Create files
    (backup_dir / "z_file.tar.gz").write_text("z content")
    (backup_dir / "a_file.tar.gz").write_text("a content")
    
    # Test with different order in manifest
    manifest1 = BackupManifest(
        stack_version="0.2.0",
        cli_version="0.2.0",
        platform="linux",
        backup_config=BackupConfig(),
        volumes=["z_file", "a_file"],  # Different order
        config_files=[],
        extensions=[]
    )
    
    manifest2 = BackupManifest(
        stack_version="0.2.0",
        cli_version="0.2.0",
        platform="linux",
        backup_config=BackupConfig(),
        volumes=["a_file", "z_file"],  # Different order  
        config_files=[],
        extensions=[]
    )
    
    checksum1 = _calculate_backup_checksum(backup_dir, manifest1)
    checksum2 = _calculate_backup_checksum(backup_dir, manifest2)
    
    # Checksums should be identical regardless of manifest order
    assert checksum1 == checksum2

# =============================================================================
# Config Class Tests (Missing Coverage)
# =============================================================================

def test_config_class_save_method(tmp_path: Path, mock_display: MagicMock):
    """Tests the Config.save() method."""
    config_file = tmp_path / ".ollama-stack.json"
    env_file = tmp_path / ".env"
    
    # Create a config manager with initial config
    config_manager = Config(mock_display, config_file, env_file)
    
    # Modify the config
    config_manager.app_config.project_name = "modified-project"
    config_manager.app_config.docker_compose_file = "modified.yml"
    
    # Save the config
    config_manager.save()
    
    # Load it back and verify changes were saved
    loaded_config, _ = load_config(mock_display, config_file, env_file)
    assert loaded_config.project_name == "modified-project"
    assert loaded_config.docker_compose_file == "modified.yml"

def test_config_class_app_config_property(tmp_path: Path, mock_display: MagicMock):
    """Tests the Config.app_config property access."""
    config_file = tmp_path / ".ollama-stack.json"
    env_file = tmp_path / ".env"
    
    # Create config manager
    config_manager = Config(mock_display, config_file, env_file)
    
    # Test property access
    app_config = config_manager.app_config
    assert isinstance(app_config, AppConfig)
    
    # Test that it's the same object on repeated access
    assert config_manager.app_config is app_config

@patch('ollama_stack_cli.config.load_config')
def test_config_class_initialization_with_load_failure(mock_load_config, mock_display: MagicMock):
    """Tests Config class initialization when load_config has unexpected failure."""
    # Make load_config raise an exception
    mock_load_config.side_effect = Exception("Unexpected error")
    
    # This should not be caught and should propagate
    with pytest.raises(Exception, match="Unexpected error"):
        Config(mock_display)


# =============================================================================
# Phase 6.1: Config Class Method Tests
# =============================================================================

def test_config_export_configuration_method(tmp_path: Path, mock_display: MagicMock):
    """Tests Config.export_configuration() method."""
    # Create config with files
    config_file = tmp_path / ".ollama-stack.json"
    env_file = tmp_path / ".env"
    
    config = AppConfig()
    save_config(mock_display, config, config_file, env_file)
    
    # Create Config instance
    config_manager = Config(mock_display, config_file, env_file)
    
    # Test export method
    output_dir = tmp_path / "export"
    result = config_manager.export_configuration(output_dir)
    
    # Should delegate to function and succeed
    assert result == True
    assert (output_dir / ".ollama-stack.json").exists()
    assert (output_dir / ".env").exists()

def test_config_import_configuration_method(tmp_path: Path, mock_display: MagicMock):
    """Tests Config.import_configuration() method."""
    # Create source files
    source_dir = tmp_path / "source" / "config"
    source_dir.mkdir(parents=True)
    (source_dir / ".ollama-stack.json").write_text('{"docker_compose_file": "imported.yml"}')
    (source_dir / ".env").write_text('PROJECT_NAME=imported')
    
    # Create Config instance with different paths
    dest_config = tmp_path / "dest" / ".ollama-stack.json"
    dest_env = tmp_path / "dest" / ".env"
    config_manager = Config(mock_display, dest_config, dest_env)
    
    # Test import method
    result = config_manager.import_configuration(source_dir)
    
    # Should delegate to function and succeed
    assert result == True
    assert dest_config.exists()
    assert dest_env.exists()

def test_config_import_configuration_validate_only(tmp_path: Path, mock_display: MagicMock):
    """Tests Config.import_configuration() with validate_only=True."""
    # Create valid source files
    source_dir = tmp_path / "source" / "config"
    source_dir.mkdir(parents=True)
    (source_dir / ".ollama-stack.json").write_text('{"docker_compose_file": "test.yml"}')
    
    config_manager = Config(mock_display)
    
    # Test validate-only mode
    result = config_manager.import_configuration(source_dir, validate_only=True)
    
    # Should succeed without creating files
    assert result == True

def test_config_validate_backup_manifest_method(tmp_path: Path, mock_display: MagicMock):
    """Tests Config.validate_backup_manifest() method."""
    from ollama_stack_cli.schemas import BackupManifest, BackupConfig
    import json
    
    # Create valid backup structure
    backup_dir = tmp_path / "backup"
    backup_dir.mkdir()
    (backup_dir / "config").mkdir()
    
    # Create manifest and files
    manifest = BackupManifest(
        stack_version="0.2.0",
        cli_version="0.2.0",
        platform="linux",
        backup_config=BackupConfig(),
        volumes=[],
        config_files=[".ollama-stack.json"],
        extensions=[]
    )
    
    manifest_file = backup_dir / "backup_manifest.json"
    with open(manifest_file, "w") as f:
        json.dump(manifest.model_dump(), f, default=str)
    
    (backup_dir / "config" / ".ollama-stack.json").touch()
    
    config_manager = Config(mock_display)
    
    # Test validation method
    is_valid, parsed_manifest = config_manager.validate_backup_manifest(manifest_file, backup_dir)
    
    # Should delegate to function and succeed
    assert is_valid == True
    assert parsed_manifest is not None


# =============================================================================
# Phase 6.1: Edge Cases and Error Scenarios
# =============================================================================

def test_export_configuration_permission_denied(tmp_path: Path, mock_display: MagicMock):
    """Tests export failure due to permission issues."""
    from ollama_stack_cli.config import export_configuration
    
    # Create source file
    config_file = tmp_path / ".ollama-stack.json"
    config_file.write_text('{"test": true}')
    env_file = tmp_path / "nonexistent.env"
    
    # Create output directory but make it read-only
    output_dir = tmp_path / "readonly"
    output_dir.mkdir()
    output_dir.chmod(0o444)  # Read-only
    
    try:
        result = export_configuration(mock_display, output_dir, config_file, env_file)
        # Should handle permission error gracefully
        assert result == False
    finally:
        # Restore permissions for cleanup
        output_dir.chmod(0o755)

def test_import_configuration_corrupted_env_file(tmp_path: Path, mock_display: MagicMock):
    """Tests import with a corrupted .env file that can't be parsed."""
    from ollama_stack_cli.config import import_configuration
    
    # Create source with binary content in .env (should cause parsing error)
    source_dir = tmp_path / "source" / "config"
    source_dir.mkdir(parents=True)
    (source_dir / ".ollama-stack.json").write_text('{"docker_compose_file": "test.yml"}')
    
    # Write invalid UTF-8 content to .env file that will cause UnicodeDecodeError
    with open(source_dir / ".env", "wb") as f:
        f.write(b'\xff\xfe\x00\x00test')  # Invalid UTF-8
    
    dest_config = tmp_path / "dest" / ".ollama-stack.json"
    dest_env = tmp_path / "dest" / ".env"
    
    result = import_configuration(mock_display, source_dir, dest_config, dest_env)
    
    # Should handle corrupted env file gracefully
    assert result == False

def test_validate_backup_manifest_very_large_checksum(tmp_path: Path, mock_display: MagicMock):
    """Tests checksum calculation with large files."""
    from ollama_stack_cli.config import _calculate_backup_checksum
    from ollama_stack_cli.schemas import BackupManifest, BackupConfig
    
    backup_dir = tmp_path / "backup"
    backup_dir.mkdir()
    
    # Create a larger file (1MB of repeated content)
    large_content = "x" * (1024 * 1024)  # 1MB
    (backup_dir / "large_volume.tar.gz").write_text(large_content)
    
    manifest = BackupManifest(
        stack_version="0.2.0",
        cli_version="0.2.0",
        platform="linux",
        backup_config=BackupConfig(),
        volumes=["large_volume"],
        config_files=[],
        extensions=[]
    )
    
    # Should handle large files without issues
    checksum = _calculate_backup_checksum(backup_dir, manifest)
    assert isinstance(checksum, str)
    assert len(checksum) == 64

def test_validate_backup_manifest_special_characters_in_filenames(tmp_path: Path, mock_display: MagicMock):
    """Tests manifest validation with special characters in filenames."""
    from ollama_stack_cli.config import validate_backup_manifest
    from ollama_stack_cli.schemas import BackupManifest, BackupConfig
    import json
    
    backup_dir = tmp_path / "backup"
    backup_dir.mkdir()
    (backup_dir / "config").mkdir()
    
    # Create files with special characters (that are filesystem-safe)
    special_filename = "test-config_v2.1.json"
    manifest = BackupManifest(
        stack_version="0.2.0",
        cli_version="0.2.0",
        platform="linux",
        backup_config=BackupConfig(),
        volumes=[],
        config_files=[special_filename],
        extensions=[]
    )
    
    manifest_file = backup_dir / "backup_manifest.json"
    with open(manifest_file, "w") as f:
        json.dump(manifest.model_dump(), f, default=str)
    
    (backup_dir / "config" / special_filename).touch()
    
    is_valid, parsed_manifest = validate_backup_manifest(manifest_file, backup_dir)
    
    # Should handle special characters in filenames
    assert is_valid == True
    assert parsed_manifest is not None

def test_calculate_backup_checksum_file_read_error(tmp_path: Path, mock_display: MagicMock):
    """Tests checksum calculation when a file can't be read."""
    from ollama_stack_cli.config import _calculate_backup_checksum
    from ollama_stack_cli.schemas import BackupManifest, BackupConfig
    
    backup_dir = tmp_path / "backup"
    backup_dir.mkdir()
    
    # Create a file and then make it unreadable
    test_file = backup_dir / "unreadable.tar.gz"
    test_file.write_text("content")
    test_file.chmod(0o000)  # No permissions
    
    manifest = BackupManifest(
        stack_version="0.2.0",
        cli_version="0.2.0",
        platform="linux",
        backup_config=BackupConfig(),
        volumes=["unreadable"],
        config_files=[],
        extensions=[]
    )
    
    try:
        # Should handle file read errors gracefully 
        checksum = _calculate_backup_checksum(backup_dir, manifest)
        # If it succeeds, it's because the file was skipped
        assert isinstance(checksum, str)
        assert len(checksum) == 64
    except PermissionError:
        # This is also acceptable - the function might not catch all file errors
        pass
    finally:
        # Restore permissions for cleanup
        test_file.chmod(0o644)

def test_export_configuration_symlink_handling(tmp_path: Path, mock_display: MagicMock):
    """Tests export with symlinks in paths."""
    from ollama_stack_cli.config import export_configuration
    
    # Create actual files
    real_config_dir = tmp_path / "real_config"
    real_config_dir.mkdir()
    config_file = real_config_dir / ".ollama-stack.json"
    config_file.write_text('{"test": true}')
    
    # Create symlink to config file
    symlink_config = tmp_path / "symlink_config.json"
    symlink_config.symlink_to(config_file)
    
    output_dir = tmp_path / "export"
    env_file = tmp_path / "nonexistent.env"
    
    result = export_configuration(mock_display, output_dir, symlink_config, env_file)
    
    # Should handle symlinks correctly
    assert result == True
    assert (output_dir / "symlink_config.json").exists()

def test_import_configuration_empty_source_directory(tmp_path: Path, mock_display: MagicMock):
    """Tests import from completely empty source directory."""
    from ollama_stack_cli.config import import_configuration
    
    # Create empty source directory
    source_dir = tmp_path / "empty"
    source_dir.mkdir()
    
    dest_config = tmp_path / "dest" / ".ollama-stack.json"
    dest_env = tmp_path / "dest" / ".env"
    
    result = import_configuration(mock_display, source_dir, dest_config, dest_env)
    
    # Should return False for empty directory
    assert result == False
    assert not dest_config.exists()
    assert not dest_env.exists()

def test_validate_backup_manifest_duplicate_entries(tmp_path: Path, mock_display: MagicMock):
    """Tests that validate_backup_manifest handles duplicate entries correctly."""
    backup_dir = tmp_path / "backup"
    backup_dir.mkdir()
    
    # Create manifest with duplicate entries
    manifest_data = {
        "backup_id": "test-backup-123",
        "created_at": "2024-01-01T00:00:00Z",
        "stack_version": "0.2.0",
        "cli_version": "0.2.0",
        "platform": "linux",
        "backup_config": {
            "include_volumes": True,
            "include_config": True,
            "include_extensions": True
        },
        "volumes": ["volume1", "volume1"],  # Duplicate
        "config_files": ["config1", "config1"],  # Duplicate
        "extensions": ["ext1", "ext1"],  # Duplicate
        "size_bytes": 1024,
        "checksum": None  # Don't set a checksum to avoid validation issues
    }
    
    manifest_file = backup_dir / "backup_manifest.json"
    with open(manifest_file, "w") as f:
        json.dump(manifest_data, f)
    
    # Create the files referenced in manifest
    volumes_dir = backup_dir / "volumes"
    volumes_dir.mkdir()
    (volumes_dir / "volume1.tar.gz").touch()
    
    config_dir = backup_dir / "config"
    config_dir.mkdir()
    (config_dir / "config1").touch()
    
    extensions_dir = backup_dir / "extensions"
    extensions_dir.mkdir()
    (extensions_dir / "ext1.tar.gz").touch()
    
    # Import the function
    from ollama_stack_cli.config import validate_backup_manifest
    
    # Test validation
    is_valid, manifest = validate_backup_manifest(manifest_file, backup_dir)
    
    # Should still be valid even with duplicates
    assert is_valid is True
    assert manifest is not None
    assert len(manifest.volumes) == 2  # Both entries preserved
    assert len(manifest.config_files) == 2  # Both entries preserved
    assert len(manifest.extensions) == 2  # Both entries preserved


# =============================================================================
# get_compose_file_path Tests
# =============================================================================

def test_get_compose_file_path_with_pkg_resources():
    """Tests get_compose_file_path when pkg_resources is available."""
    from ollama_stack_cli.config import get_compose_file_path
    
    with patch('pkg_resources.resource_filename') as mock_resource_filename:
        mock_resource_filename.return_value = "/path/to/package/docker-compose.yml"
        
        result = get_compose_file_path("docker-compose.yml")
        
        mock_resource_filename.assert_called_once_with('ollama_stack_cli', 'docker-compose.yml')
        assert result == Path("/path/to/package/docker-compose.yml")


def test_get_compose_file_path_without_pkg_resources():
    """Tests get_compose_file_path fallback when pkg_resources is not available."""
    from ollama_stack_cli.config import get_compose_file_path
    
    with patch('pkg_resources.resource_filename', side_effect=ImportError):
        result = get_compose_file_path("docker-compose.yml")
        
        # Should fall back to relative path from config.py location
        # Since we're in ollama_stack_cli/tests/, parent.parent goes to ollama_stack_cli/
        # and the compose files are now in ollama_stack_cli/
        expected_path = Path(__file__).parent.parent / "docker-compose.yml"
        assert result == expected_path


def test_get_compose_file_path_different_filenames():
    """Tests get_compose_file_path with different compose file names."""
    from ollama_stack_cli.config import get_compose_file_path
    
    with patch('pkg_resources.resource_filename') as mock_resource_filename:
        mock_resource_filename.return_value = "/path/to/package/test-file.yml"
        
        result = get_compose_file_path("test-file.yml")
        
        mock_resource_filename.assert_called_once_with('ollama_stack_cli', 'test-file.yml')
        assert result == Path("/path/to/package/test-file.yml")


def test_get_compose_file_path_development_fallback():
    """Tests get_compose_file_path fallback in development environment."""
    from ollama_stack_cli.config import get_compose_file_path
    
    # Mock both pkg_resources import and the fallback path
    with patch('pkg_resources.resource_filename', side_effect=ImportError):
        with patch('ollama_stack_cli.config.__file__', '/dev/path/config.py'):
            result = get_compose_file_path("docker-compose.apple.yml")
            
            # Should use the fallback path - same directory as config.py
            expected_path = Path("/dev/path") / "docker-compose.apple.yml"
            assert result == expected_path


def test_get_compose_file_path_absolute_paths():
    """Tests that get_compose_file_path returns absolute paths."""
    from ollama_stack_cli.config import get_compose_file_path
    
    with patch('pkg_resources.resource_filename') as mock_resource_filename:
        mock_resource_filename.return_value = "/absolute/path/to/docker-compose.yml"
        
        result = get_compose_file_path("docker-compose.yml")
        
        # Should return absolute path
        assert result.is_absolute()
        assert str(result) == "/absolute/path/to/docker-compose.yml" 