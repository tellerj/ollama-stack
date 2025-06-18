import json
from pathlib import Path
from unittest.mock import patch
from ollama_stack_cli.config import load_config, save_config, AppConfig, PlatformConfig

def test_load_config_creates_default_when_not_exists(tmp_path: Path):
    """
    Tests that a default config is created if one doesn't exist.
    """
    config_file = tmp_path / ".ollama-stack.json"
    
    # Ensure the file doesn't exist initially
    assert not config_file.exists()
    
    # Load config
    config = load_config(config_file)
    
    # Check that a file was created
    assert config_file.exists()
    
    # Check that the loaded config is the default
    assert config == AppConfig(
        platform={
            "apple": PlatformConfig(compose_file="docker-compose.apple.yml"),
            "nvidia": PlatformConfig(compose_file="docker-compose.nvidia.yml"),
        }
    )
    
    # Check that the file content is correct
    with open(config_file, "r") as f:
        data = json.load(f)
    assert AppConfig(**data) == config

def test_save_and_load_config(tmp_path: Path):
    """
    Tests that a config can be saved and then loaded correctly.
    """
    config_file = tmp_path / ".ollama-stack.json"
    
    # Create a custom config
    custom_config = AppConfig(
        docker_compose_file="custom-compose.yml",
        data_directory="/custom/data",
    )
    
    # Save and load the config
    save_config(custom_config, config_file)
    loaded_config = load_config(config_file)
    
    # Check that the loaded config matches the custom one
    assert loaded_config == custom_config

def test_load_config_with_corrupt_file(tmp_path: Path):
    """
    Tests that a default config is loaded if the config file is corrupt.
    """
    config_file = tmp_path / ".ollama-stack.json"
    
    # Create a corrupt file
    with open(config_file, "w") as f:
        f.write("{ not_valid_json }")
        
    # Load config, should not raise an error but return a default config
    config = load_config(config_file)
    
    # Check that the loaded config is the default
    assert config == AppConfig(
        platform={
            "apple": PlatformConfig(compose_file="docker-compose.apple.yml"),
            "nvidia": PlatformConfig(compose_file="docker-compose.nvidia.yml"),
        }
    )

def test_load_config_with_invalid_schema(tmp_path: Path):
    """
    Tests that a default config is loaded if the config file has an invalid schema.
    """
    config_file = tmp_path / ".ollama-stack.json"
    
    # Create a file with an invalid schema (e.g., wrong data type)
    invalid_data = {"docker_compose_file": 123} # Should be a string
    with open(config_file, "w") as f:
        json.dump(invalid_data, f)
        
    # Load config, should not raise an error but return a default config
    config = load_config(config_file)
    
    # Check that the loaded config is the default
    assert config == AppConfig(
        platform={
            "apple": PlatformConfig(compose_file="docker-compose.apple.yml"),
            "nvidia": PlatformConfig(compose_file="docker-compose.nvidia.yml"),
        }
    ) 