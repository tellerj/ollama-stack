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