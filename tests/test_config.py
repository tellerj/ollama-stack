import json
from pathlib import Path
from unittest.mock import patch
from ollama_stack_cli.config import load_config, save_config, AppConfig, PlatformConfig
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
    config = load_config(mock_display, config_file, env_file)
    
    # Check that the default config was created and returned
    assert config_file.exists()
    assert env_file.exists()
    assert isinstance(config, AppConfig)
    assert config.docker_compose_file == "docker-compose.yml"
    mock_display.info.assert_called_once()

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
    loaded_config = load_config(mock_display, config_file, env_file)
    
    # Check that the loaded config matches the saved one
    assert loaded_config.docker_compose_file == "custom-compose.yml"
    assert loaded_config.project_name == "my-test-stack"
    assert loaded_config.webui_secret_key == "super-secret"

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
    config = load_config(mock_display, config_file, env_file)
    assert isinstance(config, AppConfig)
    mock_display.warning.assert_called_once()

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
    config = load_config(mock_display, config_file, env_file)
    assert isinstance(config, AppConfig)
    mock_display.warning.assert_called_once() 