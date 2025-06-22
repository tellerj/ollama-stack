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


class ResourceUsage(BaseModel):
    cpu_percent: Optional[float] = None
    memory_mb: Optional[float] = None


class ServiceStatus(BaseModel):
    name: str
    is_running: bool
    status: Optional[str] = None
    health: Optional[str] = None
    ports: Dict[str, Optional[int]] = Field(default_factory=dict)
    usage: ResourceUsage = Field(default_factory=ResourceUsage)


class ExtensionStatus(ServiceStatus):
    is_enabled: bool


class StackStatus(BaseModel):
    core_services: List[ServiceStatus]
    extensions: List[ExtensionStatus]


class EnvironmentCheck(BaseModel):
    name: str
    passed: bool
    details: str
    suggestion: Optional[str] = None


class CheckReport(BaseModel):
    checks: List[EnvironmentCheck]



