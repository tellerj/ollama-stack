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