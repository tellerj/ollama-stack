import json
from pathlib import Path
from pydantic import ValidationError
from .schemas import AppConfig, PlatformConfig

DEFAULT_CONFIG_DIR = Path.home() / ".ollama-stack"
DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / ".ollama-stack.json"

def load_config(config_path: Path = DEFAULT_CONFIG_FILE) -> AppConfig:
    """
    Loads the application configuration from a JSON file.
    If the file doesn't exist, it creates a default configuration.
    """
    if not config_path.exists():
        # Create a default configuration with platform-specific settings
        config = AppConfig()
        config.platform = {
            "apple": PlatformConfig(compose_file="docker-compose.apple.yml"),
            "nvidia": PlatformConfig(compose_file="docker-compose.nvidia.yml"),
        }
        print(f"Creating default configuration at {config_path}")
        save_config(config, config_path)
        return config

    try:
        with open(config_path, "r") as f:
            data = json.load(f)
        return AppConfig(**data)
    except (json.JSONDecodeError, ValidationError) as e:
        print(f"Warning: Could not load or parse {config_path}. Using default configuration. Error: {e}")
        # Re-create a valid default config if the existing one is corrupt
        config = AppConfig()
        config.platform = {
            "apple": PlatformConfig(compose_file="docker-compose.apple.yml"),
            "nvidia": PlatformConfig(compose_file="docker-compose.nvidia.yml"),
        }
        save_config(config, config_path)
        return config


def save_config(config: AppConfig, config_path: Path = DEFAULT_CONFIG_FILE):
    """Saves the application configuration to a JSON file."""
    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w") as f:
            f.write(config.model_dump_json(indent=4))
    except IOError as e:
        print(f"Error: Could not save configuration to {config_path}. Error: {e}")


class Config:
    """A configuration manager that handles loading and accessing app configuration."""
    
    def __init__(self, config_path: Path = DEFAULT_CONFIG_FILE):
        """Initialize the Config with a loaded AppConfig."""
        self._app_config = load_config(config_path)
    
    @property
    def app_config(self) -> AppConfig:
        """Returns the loaded AppConfig object."""
        return self._app_config
    
    def save(self, config_path: Path = DEFAULT_CONFIG_FILE):
        """Save the current configuration to file."""
        save_config(self._app_config, config_path)



