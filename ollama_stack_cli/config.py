import json
import logging
import hashlib
import shutil
from pathlib import Path
from typing import Dict, Any, Optional
from pydantic import ValidationError
from dotenv import dotenv_values, set_key

from .schemas import AppConfig, PlatformConfig, BackupManifest
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
        
        # Load .env values into the config (only if they exist)
        env_vars = dotenv_values(env_path)
        if env_vars.get("PROJECT_NAME"):
            app_config.project_name = env_vars.get("PROJECT_NAME")
        if env_vars.get("WEBUI_SECRET_KEY"):
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


def export_configuration(
    display: Display,
    output_dir: Path,
    config_path: Path = DEFAULT_CONFIG_FILE,
    env_path: Path = DEFAULT_ENV_FILE,
) -> bool:
    """
    Export configuration files to a specified directory for backup purposes.
    
    Args:
        display: Display object for output
        output_dir: Directory to export configuration files to
        config_path: Path to the JSON config file
        env_path: Path to the .env file
        
    Returns:
        bool: True if export was successful, False otherwise
    """
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Copy configuration files if they exist
        files_exported = []
        
        if config_path.exists():
            config_dest = output_dir / config_path.name
            shutil.copy2(config_path, config_dest)
            files_exported.append(config_path.name)
            log.debug(f"Exported configuration file to {config_dest}")
        
        if env_path.exists():
            env_dest = output_dir / env_path.name
            shutil.copy2(env_path, env_dest)
            files_exported.append(env_path.name)
            log.debug(f"Exported environment file to {env_dest}")
        
        if files_exported:
            log.info(f"Exported configuration files: {', '.join(files_exported)}")
            return True
        else:
            log.warning("No configuration files found to export")
            return False
            
    except Exception as e:
        log.error(f"Failed to export configuration: {str(e)}")
        return False


def import_configuration(
    display: Display,
    source_dir: Path,
    config_path: Path = DEFAULT_CONFIG_FILE,
    env_path: Path = DEFAULT_ENV_FILE,
    validate_only: bool = False,
) -> bool:
    """
    Import and validate configuration files from a backup directory.
    
    Args:
        display: Display object for output
        source_dir: Directory containing the configuration files to import
        config_path: Destination path for the JSON config file
        env_path: Destination path for the .env file
        validate_only: If True, only validate without actually importing
        
    Returns:
        bool: True if import/validation was successful, False otherwise
    """
    try:
        source_config = source_dir / config_path.name
        source_env = source_dir / env_path.name
        
        # Validate configuration files first
        if source_config.exists():
            try:
                with open(source_config, "r") as f:
                    data = json.load(f)
                # Validate by creating AppConfig instance
                AppConfig(**data)
                log.debug(f"Configuration file validation passed: {source_config}")
            except (json.JSONDecodeError, ValidationError) as e:
                log.error(f"Invalid configuration file: {str(e)}")
                return False
        
        if source_env.exists():
            try:
                # Validate .env file format
                env_vars = dotenv_values(source_env)
                log.debug(f"Environment file validation passed: {source_env}")
            except Exception as e:
                log.error(f"Invalid environment file: {str(e)}")
                return False
        
        if validate_only:
            log.info("Configuration validation completed successfully")
            return True
        
        # Import files if validation passed
        files_imported = []
        
        if source_config.exists():
            config_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_config, config_path)
            files_imported.append(config_path.name)
            log.debug(f"Imported configuration file from {source_config}")
        
        if source_env.exists():
            env_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_env, env_path)
            files_imported.append(env_path.name)
            log.debug(f"Imported environment file from {source_env}")
        
        if files_imported:
            log.info(f"Imported configuration files: {', '.join(files_imported)}")
            return True
        else:
            log.warning("No configuration files found to import")
            return False
            
    except Exception as e:
        log.error(f"Failed to import configuration: {str(e)}")
        return False


def validate_backup_manifest(
    manifest_path: Path,
    backup_dir: Path,
) -> tuple[bool, Optional[BackupManifest]]:
    """
    Validate a backup manifest file and verify backup integrity.
    
    Args:
        manifest_path: Path to the backup manifest file
        backup_dir: Directory containing the backup files
        
    Returns:
        tuple: (is_valid, manifest) where is_valid is True if valid, manifest is the parsed manifest or None
    """
    try:
        if not manifest_path.exists():
            log.error(f"Backup manifest not found: {manifest_path}")
            return False, None
        
        # Parse and validate manifest
        with open(manifest_path, "r") as f:
            manifest_data = json.load(f)
        
        try:
            manifest = BackupManifest(**manifest_data)
        except ValidationError as e:
            log.error(f"Invalid backup manifest format: {str(e)}")
            return False, None
        
        # Verify backup files exist
        missing_files = []
        
        # Check volume backup files
        for volume in manifest.volumes:
            volume_file = backup_dir / f"{volume}.tar.gz"
            if not volume_file.exists():
                missing_files.append(f"volume: {volume}")
        
        # Check config files
        for config_file in manifest.config_files:
            config_path = backup_dir / "config" / config_file
            if not config_path.exists():
                missing_files.append(f"config: {config_file}")
        
        # Check extension files
        for extension in manifest.extensions:
            ext_file = backup_dir / "extensions" / f"{extension}.tar.gz"
            if not ext_file.exists():
                missing_files.append(f"extension: {extension}")
        
        if missing_files:
            log.error(f"Missing backup files: {', '.join(missing_files)}")
            return False, manifest
        
        # Verify checksum if present
        if manifest.checksum:
            calculated_checksum = _calculate_backup_checksum(backup_dir, manifest)
            if calculated_checksum != manifest.checksum:
                log.error("Backup checksum mismatch - backup may be corrupted")
                return False, manifest
            log.debug("Backup checksum verification passed")
        
        log.info("Backup manifest validation completed successfully")
        return True, manifest
        
    except Exception as e:
        log.error(f"Failed to validate backup manifest: {str(e)}")
        return False, None


def _calculate_backup_checksum(backup_dir: Path, manifest: BackupManifest) -> str:
    """
    Calculate a checksum for the backup directory contents.
    
    Args:
        backup_dir: Directory containing backup files
        manifest: Backup manifest with file list
        
    Returns:
        str: SHA256 checksum of backup contents
    """
    hasher = hashlib.sha256()
    
    # Sort files for consistent checksum calculation
    all_files = []
    
    # Add volume files
    for volume in sorted(manifest.volumes):
        volume_file = backup_dir / f"{volume}.tar.gz"
        if volume_file.exists():
            all_files.append(volume_file)
    
    # Add config files
    for config_file in sorted(manifest.config_files):
        config_path = backup_dir / "config" / config_file
        if config_path.exists():
            all_files.append(config_path)
    
    # Add extension files
    for extension in sorted(manifest.extensions):
        ext_file = backup_dir / "extensions" / f"{extension}.tar.gz"
        if ext_file.exists():
            all_files.append(ext_file)
    
    # Calculate hash of all files
    for file_path in sorted(all_files):
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hasher.update(chunk)
    
    return hasher.hexdigest()


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
    
    def export_configuration(self, output_dir: Path) -> bool:
        """Export configuration files to specified directory."""
        return export_configuration(self._display, output_dir, self._config_path, self._env_path)
    
    def import_configuration(self, source_dir: Path, validate_only: bool = False) -> bool:
        """Import and validate configuration files from backup directory."""
        return import_configuration(self._display, source_dir, self._config_path, self._env_path, validate_only)
    
    def validate_backup_manifest(self, manifest_path: Path, backup_dir: Path) -> tuple[bool, Optional[BackupManifest]]:
        """Validate a backup manifest file and verify backup integrity."""
        return validate_backup_manifest(manifest_path, backup_dir)



