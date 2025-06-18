from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class PlatformConfig(BaseModel):
    compose_file: str

class ExtensionsConfig(BaseModel):
    enabled: List[str] = Field(default_factory=list)
    config: Dict[str, Any] = Field(default_factory=dict)

class AppConfig(BaseModel):
    docker_compose_file: str = "docker-compose.yml"
    data_directory: str = "~/.ollama-stack/data"
    backup_directory: str = "~/.ollama-stack/backups"
    platform: Dict[str, PlatformConfig] = Field(default_factory=dict)
    extensions: ExtensionsConfig = Field(default_factory=ExtensionsConfig)



