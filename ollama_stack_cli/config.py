import json
import logging
from pathlib import Path
from pydantic import ValidationError
from dotenv import dotenv_values, set_key

from .schemas import AppConfig, PlatformConfig
from .display import Display

log = logging.getLogger(__name__)

DEFAULT_CONFIG_DIR = Path.home() / ".ollama-stack"
DEFAULT_ENV_FILE = DEFAULT_CONFIG_DIR / ".env"
DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / ".ollama-stack.json"


def load_config(
    display: Display,
    config_path: Path = DEFAULT_CONFIG_FILE,
    env_path: Path = DEFAULT_ENV_FILE,
) -> tuple[AppConfig, bool]:
    """
    Loads the application configuration from JSON and .env files.
    If they don't exist, it creates default configurations.
    
    Returns:
        tuple: (AppConfig, fell_back_to_defaults)
    """
    if not config_path.exists() or not env_path.exists():
        log.info(f"Creating default configuration files in {DEFAULT_CONFIG_DIR}")
        app_config = AppConfig()
        app_config.platform = {
            "apple": PlatformConfig(compose_file="docker-compose.apple.yml"),
            "nvidia": PlatformConfig(compose_file="docker-compose.nvidia.yml"),
        }
        save_config(display, app_config, config_path)
        # Create a default .env file
        set_key(env_path, "PROJECT_NAME", "ollama-stack")
        set_key(env_path, "WEBUI_SECRET_KEY", "your-secret-key-here")
        return app_config, False  # Created new config, not a fallback

    try:
        with open(config_path, "r") as f:
            data = json.load(f)
        app_config = AppConfig(**data)
        
        # Load .env values into the config
        env_vars = dotenv_values(env_path)
        app_config.project_name = env_vars.get("PROJECT_NAME")
        app_config.webui_secret_key = env_vars.get("WEBUI_SECRET_KEY")

        return app_config, False  # Successfully loaded config
    except (json.JSONDecodeError, ValidationError) as e:
        # Keep quiet for now, but track that we fell back to defaults
        log.debug(f"Config fallback: {type(e).__name__}")
        
        app_config = AppConfig() # Return a default, in-memory config
        return app_config, True  # Fell back to defaults

def save_config(
    display: Display,
    config: AppConfig,
    config_path: Path = DEFAULT_CONFIG_FILE,
    env_path: Path = DEFAULT_ENV_FILE,
):
    """Saves the application configuration to JSON and .env files."""
    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w") as f:
            f.write(config.model_dump_json(indent=4, exclude={"project_name", "webui_secret_key"}))
        
        # Save relevant keys to .env file
        if config.project_name:
            set_key(env_path, "PROJECT_NAME", config.project_name)
        if config.webui_secret_key:
            set_key(env_path, "WEBUI_SECRET_KEY", config.webui_secret_key)

    except IOError as e:
        log.error(f"Could not save configuration to {config_path}.", exc_info=True)

class Config:
    """A configuration manager that handles loading and accessing app configuration."""
    
    def __init__(self, display: Display, config_path: Path = DEFAULT_CONFIG_FILE, env_path: Path = DEFAULT_ENV_FILE):
        """Initialize the Config with a loaded AppConfig."""
        self._display = display
        self._config_path = config_path
        self._env_path = env_path
        self._app_config, self._fell_back_to_defaults = load_config(display, config_path, env_path)
    
    @property
    def app_config(self) -> AppConfig:
        """Returns the loaded AppConfig object."""
        return self._app_config
    
    @property
    def fell_back_to_defaults(self) -> bool:
        """Returns True if the config fell back to defaults due to loading errors."""
        return self._fell_back_to_defaults
    
    def save(self):
        """Save the current configuration to file."""
        save_config(self._display, self._app_config, self._config_path, self._env_path)



